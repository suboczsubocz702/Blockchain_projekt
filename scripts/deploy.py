#Ten plik został poprawiony za pomocą DeepSeek. Niesamodzielne zmiany są napisane w komentarzach pod kodem

"""
ZMIANY:
1. Używa EIP-1559 (maxFeePerGas + maxPriorityFeePerGas) zamiast gasPrice.
   Powód: gasPrice oparte na w3.eth.gas_price bywa za niskie w chwilach
   skoków aktywności sieci, przez co transakcja utyka w mempoolu.
   EIP-1559 z zapasem 2x base fee + napiwek prawie zawsze wystarcza.
2. Jawnie ustawiony limit gazu (gas=3_000_000) dla wdrożenia kontraktu.
   Powód: automatyczna estymacja gasu czasem zawodzi przy dużych
   kontraktach na zatłoczonej sieci.
3. Dodana funkcja save_addresses – bezpieczne zapisywanie adresów.
4. Dodany sanity check po wdrożeniu – sprawdza, że kod kontraktu istnieje
   pod nowym adresem, zanim zapisze go do addresses.json.
"""
import json
import os
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

INFURA_KEY = os.getenv("INFURA_KEY")
MY_ADDRESS = os.getenv("MY_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
RPC_URL = f"https://sepolia.infura.io/v3/{INFURA_KEY}"
CHAIN_ID = 11155111

w3 = Web3(Web3.HTTPProvider(RPC_URL))
assert w3.is_connected(), "Nie mozna polaczyc sie z Sepolia"

print(f"Polaczono z Sepolia. Adres: {MY_ADDRESS}")
print(f"Saldo ETH: {w3.from_wei(w3.eth.get_balance(MY_ADDRESS), 'ether')} ETH")

artifacts_dir = os.path.join(os.path.dirname(__file__), "..", "artifacts")
with open(os.path.join(artifacts_dir, "MyToken.json")) as f:
    token_artifact = json.load(f)
with open(os.path.join(artifacts_dir, "DEX.json")) as f:
    dex_artifact = json.load(f)


def send_transaction(txn):
    signed = w3.eth.account.sign_transaction(txn, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    # ZMIANA: timeout 300 zamiast domyślnych 120 sekund.
    # Powód: Infura na darmowym planie bywa wolna, a 120 s to zbyt mało
    # przy chwilowych przeciążeniach.
    return w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)


def build_txn(contract_function, value=0, gas=None):
    """
    ZMIANA: EIP-1559 zamiast gasPrice.
    Ustawiamy:
      maxFeePerGas         = 2 * base_fee + 1 gwei  (górny limit)
      maxPriorityFeePerGas = 2 gwei                  (napiwek dla walidatora)
      nonce z "pending"                              (uwzględnia mempool)
    """
    base_fee = w3.eth.get_block("latest")["baseFeePerGas"]
    tx_params = {
        "chainId": CHAIN_ID,
        "from": MY_ADDRESS,
        "nonce": w3.eth.get_transaction_count(MY_ADDRESS, "pending"),
        "maxFeePerGas": base_fee * 2 + w3.to_wei(1, "gwei"),
        "maxPriorityFeePerGas": w3.to_wei(2, "gwei"),
        "value": value,
    }
    if gas is not None:
        tx_params["gas"] = gas
    return contract_function.build_transaction(tx_params)


def save_addresses(token_addr, dex_addr=None):
    path = os.path.join(artifacts_dir, "addresses.json")
    addresses = {}
    if os.path.exists(path):
        with open(path) as f:
            addresses = json.load(f)
    addresses["token_address"] = Web3.to_checksum_address(token_addr)
    if dex_addr:
        addresses["dex_address"] = Web3.to_checksum_address(dex_addr)
    with open(path, "w") as f:
        json.dump(addresses, f, indent=2)


# ========== 1. WDROŻENIE TOKENU ==========
print("\n[1/3] Wdrazanie tokenu MyToken...")
MyToken = w3.eth.contract(abi=token_artifact["abi"], bytecode=token_artifact["bytecode"])
INITIAL_SUPPLY = 1_000_000

txn = build_txn(MyToken.constructor(INITIAL_SUPPLY), gas=3_000_000)
receipt = send_transaction(txn)
token_address = receipt.contractAddress

# Sanity check: czy pod adresem naprawdę jest kod?
assert len(w3.eth.get_code(token_address)) > 0, "Token nie zostal wdrożony!"
print(f"Token wdrożony pod adresem: {token_address}")
save_addresses(token_address)

# ========== 2. WDROŻENIE DEX ==========
print("\n[2/3] Wdrazanie kontraktu DEX...")
DEX = w3.eth.contract(abi=dex_artifact["abi"], bytecode=dex_artifact["bytecode"])

txn = build_txn(DEX.constructor(token_address), gas=3_000_000)
receipt = send_transaction(txn)
dex_address = receipt.contractAddress

assert len(w3.eth.get_code(dex_address)) > 0, "DEX nie zostal wdrożony!"
print(f"DEX wdrożony pod adresem: {dex_address}")
save_addresses(token_address, dex_address)

# ========== 3. PRZEKAZANIE TOKENÓW DO DEX ==========
print("\n[3/3] Przekazywanie tokenow do DEX...")
token_contract = w3.eth.contract(address=token_address, abi=token_artifact["abi"])
dex_contract = w3.eth.contract(address=dex_address, abi=dex_artifact["abi"])

tokens_for_dex = 500_000 * 10**18

# Approve – DEX może pobrać tokeny
txn = build_txn(token_contract.functions.approve(dex_address, tokens_for_dex), gas=100_000)
send_transaction(txn)
print("Approve wykonany.")

# depositTokens – DEX pobiera tokeny od właściciela
txn = build_txn(dex_contract.functions.depositTokens(tokens_for_dex), gas=200_000)
send_transaction(txn)
print("Tokeny przekazane do DEX.")

# ========== PODSUMOWANIE ==========
print("\n" + "=" * 50)
print("WDROZENIE ZAKONCZONE POMYSLNIE")
print("=" * 50)
print(f"Token (MyToken):  {token_address}")
print(f"DEX:              {dex_address}")
print(f"Zapas tokenow w DEX: {tokens_for_dex / 10**18:,.0f} MTK")
print(f"Cena: 1 MTK = 0.001 ETH")
print("=" * 50)
print("\nAdresy zapisane w artifacts/addresses.json")
