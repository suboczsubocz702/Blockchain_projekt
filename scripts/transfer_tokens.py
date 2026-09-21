#ten plik został poprawiony za pomocą DeepSeek. Wszystkie niesamodzielne zmiany są podpisane w komentarzach.

"""
NOWY PLIK – wydzielony z deploy.py.
Powód: deploy.py w oryginalnej wersji wykonywał wszystkie trzy kroki
(token + DEX + transfer) w jednej sesji. Gdy wdrożenie DEX się przedłużyło,
skrypt padał i transfer tokenów trzeba było wykonywać ręcznie.
Rozdzielenie kroków pozwala uruchamiać je niezależnie.

ZMIANY:
1. nonce z "pending" – uwzględnia transakcje w mempoolu, zapobiega
   błędowi "nonce too low".
2. Adresy konwertowane przez to_checksum_address – web3.py wymaga
   formatu EIP-55.
3. Sanity check przed wywołaniem balanceOf – upewnia się, że pod
   token_address faktycznie jest kontrakt tokenu (nie DEX).
4. Jawny limit gazu dla każdej operacji.
"""
import json
import os
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

w3 = Web3(Web3.HTTPProvider(f"https://sepolia.infura.io/v3/{os.getenv('INFURA_KEY')}"))
MY_ADDRESS = os.getenv("MY_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
CHAIN_ID = 11155111

artifacts_dir = os.path.join(os.path.dirname(__file__), "..", "artifacts")
with open(os.path.join(artifacts_dir, "MyToken.json")) as f:
    token_artifact = json.load(f)
with open(os.path.join(artifacts_dir, "DEX.json")) as f:
    dex_artifact = json.load(f)
with open(os.path.join(artifacts_dir, "addresses.json")) as f:
    addresses = json.load(f)

# ZMIANA: konwersja adresów na checksum
token_addr = w3.to_checksum_address(addresses["token_address"])
dex_addr = w3.to_checksum_address(addresses["dex_address"])
my_addr = w3.to_checksum_address(MY_ADDRESS)

# ZMIANA: sanity check – czy token_addr to naprawdę token?
code = w3.eth.get_code(token_addr)
if len(code) == 0:
    raise SystemExit(f"BLAD: pod {token_addr} nie ma kontraktu!")

token = w3.eth.contract(address=token_addr, abi=token_artifact["abi"])
dex = w3.eth.contract(address=dex_addr, abi=dex_artifact["abi"])

# Sprawdź, że token_addr odpowiada na totalSupply (a DEX by nie odpowiedział)
try:
    token.functions.totalSupply().call()
except Exception:
    raise SystemExit(
        "BLAD: token_address nie odpowiada na totalSupply(). "
        "Sprawdz, czy token_address i dex_address nie sa zamienione w addresses.json"
    )


def send(fn, gas=300_000):
    """ZMIANA: nonce z 'pending' + EIP-1559."""
    base_fee = w3.eth.get_block("latest")["baseFeePerGas"]
    txn = fn.build_transaction({
        "chainId": CHAIN_ID,
        "from": my_addr,
        "nonce": w3.eth.get_transaction_count(my_addr, "pending"),
        "maxFeePerGas": base_fee * 2 + w3.to_wei(1, "gwei"),
        "maxPriorityFeePerGas": w3.to_wei(2, "gwei"),
        "gas": gas,
    })
    signed = w3.eth.account.sign_transaction(txn, private_key=PRIVATE_KEY)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    return w3.eth.wait_for_transaction_receipt(h, timeout=300)


AMOUNT = 500_000 * 10**18

print(f"Tokeny uzytkownika przed: {token.functions.balanceOf(my_addr).call() / 10**18:,.0f} MTK")

print("\n[1/2] Approve (DEX moze pobrac 500,000 MTK)...")
r = send(token.functions.approve(dex_addr, AMOUNT), gas=100_000)
print(f"  OK: {r.transactionHash.hex()}")

print("\n[2/2] depositTokens (DEX pobiera tokeny)...")
r = send(dex.functions.depositTokens(AMOUNT), gas=200_000)
print(f"  OK: {r.transactionHash.hex()}")

print(f"\nTokeny w DEX:  {token.functions.balanceOf(dex_addr).call() / 10**18:,.0f} MTK")
print(f"Tokeny user:   {token.functions.balanceOf(my_addr).call() / 10**18:,.0f} MTK")
