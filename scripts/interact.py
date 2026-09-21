#kod poprawiony z DeepSeek. Wszystkie niesamodzielne zmiany zostały podpisane w komentarzach kodu.

"""
ZMIANY:
1. Kolejność scenariuszy: BUY przed APPROVE+SELL.
   Powód: DEX startuje z 0 ETH. Funkcja sell() wymaga, żeby DEX miał
   ETH na wypłatę dla sprzedającego. Pierwszy użytkownik musi więc
   najpierw kupić (BUY), żeby DEX zdobył ETH. Dopiero potem można
   sprzedawać (SELL). To naturalna kolejność w prawdziwych giełdach.
2. Adresy konwertowane przez to_checksum_address.
3. nonce z "pending" – jak w deploy.py i transfer_tokens.py.
4. Jawny limit gazu dla każdej operacji.
5. Sanity check – upewnia się, że DEX ma zapas tokenów przed startem.
6. Poprawione wywołanie approve: używamy `dex_addr` (checksum).
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

# ZMIANA: konwersja adresów na checksum (EIP-55)
token_addr = w3.to_checksum_address(addresses["token_address"])
dex_addr = w3.to_checksum_address(addresses["dex_address"])
my_addr = w3.to_checksum_address(MY_ADDRESS)

token = w3.eth.contract(address=token_addr, abi=token_artifact["abi"])
dex = w3.eth.contract(address=dex_addr, abi=dex_artifact["abi"])


def send_transaction(txn):
    signed = w3.eth.account.sign_transaction(txn, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)


def build_txn(contract_function, value=0, gas=None):
    """ZMIANA: EIP-1559 + pending nonce."""
    base_fee = w3.eth.get_block("latest")["baseFeePerGas"]
    tx_params = {
        "chainId": CHAIN_ID,
        "from": my_addr,
        "nonce": w3.eth.get_transaction_count(my_addr, "pending"),
        "maxFeePerGas": base_fee * 2 + w3.to_wei(1, "gwei"),
        "maxPriorityFeePerGas": w3.to_wei(2, "gwei"),
        "value": value,
    }
    if gas is not None:
        tx_params["gas"] = gas
    return contract_function.build_transaction(tx_params)


# ========== SANITY CHECK ==========
dex_token_balance = token.functions.balanceOf(dex_addr).call()
dex_eth_balance = w3.eth.get_balance(dex_addr)

if dex_token_balance == 0:
    raise SystemExit(
        "BLAD: DEX nie ma tokenow. Uruchom najpierw transfer_tokens.py."
    )
print(f"DEX ma {dex_token_balance / 10**18:,.0f} MTK i "
      f"{w3.from_wei(dex_eth_balance, 'ether')} ETH")

# ========== STAN POCZĄTKOWY ==========
print("\n" + "=" * 60)
print("STAN POCZATKOWY")
print("=" * 60)
user_token_balance = token.functions.balanceOf(my_addr).call()
user_eth_balance = w3.eth.get_balance(my_addr)

print(f"Tokeny uzytkownika:  {user_token_balance / 10**18:,.2f} MTK")
print(f"ETH uzytkownika:     {w3.from_wei(user_eth_balance, 'ether')} ETH")
print(f"Tokeny w DEX:        {dex_token_balance / 10**18:,.2f} MTK")

# ========== SCENARIUSZ 1: BUY ==========
# ZMIANA: BUY wykonujemy jako pierwszy, żeby DEX zdobył ETH na wypłaty.
print("\n" + "=" * 60)
print("SCENARIUSZ 1: BUY (zakup 50 MTK)")
print("=" * 60)

amount_to_buy = 50 * 10**18
token_price_wei = w3.to_wei(0.001, "ether")
cost_wei = (amount_to_buy * token_price_wei) // 10**18

print(f"Koszt: {w3.from_wei(cost_wei, 'ether')} ETH")

buy_txn = dex.functions.buy(amount_to_buy)
txn = build_txn(buy_txn, value=cost_wei, gas=150_000)
receipt = send_transaction(txn)
print(f"Buy wykonany. Hash: {receipt.transactionHash.hex()}")

# ========== SCENARIUSZ 2: APPROVE + SELL ==========
print("\n" + "=" * 60)
print("SCENARIUSZ 2: APPROVE + SELL (sprzedaz 100 MTK)")
print("=" * 60)

amount_to_sell = 100 * 10**18

print("\n[2a] Wywolanie approve() na tokenie...")
approve_txn = token.functions.approve(dex_addr, amount_to_sell)
txn = build_txn(approve_txn, gas=100_000)
receipt = send_transaction(txn)
print(f"Approve wykonany. Hash: {receipt.transactionHash.hex()}")

allowance = token.functions.allowance(my_addr, dex_addr).call()
print(f"Aktualny allowance: {allowance / 10**18:,.2f} MTK")

print("\n[2b] Wywolanie sell() na DEX...")
sell_txn = dex.functions.sell(amount_to_sell)
txn = build_txn(sell_txn, gas=200_000)
receipt = send_transaction(txn)
print(f"Sell wykonany. Hash: {receipt.transactionHash.hex()}")

# ========== STAN KOŃCOWY ==========
print("\n" + "=" * 60)
print("STAN KONCOWY")
print("=" * 60)
user_token_balance = token.functions.balanceOf(my_addr).call()
user_eth_balance = w3.eth.get_balance(my_addr)
dex_token_balance = token.functions.balanceOf(dex_addr).call()
dex_eth_balance = w3.eth.get_balance(dex_addr)

print(f"Tokeny uzytkownika:  {user_token_balance / 10**18:,.2f} MTK")
print(f"ETH uzytkownika:     {w3.from_wei(user_eth_balance, 'ether')} ETH")
print(f"Tokeny w DEX:        {dex_token_balance / 10**18:,.2f} MTK")
print(f"ETH w DEX:           {w3.from_wei(dex_eth_balance, 'ether')} ETH")

# ========== WERYFIKACJA ==========
print("\n" + "=" * 60)
print("WERYFIKACJA")
print("=" * 60)
remaining_allowance = token.functions.allowance(my_addr, dex_addr).call()
print(f"Pozostaly allowance: {remaining_allowance / 10**18:,.2f} MTK")
print("(Powinien byc 0, jesli sell pobral wszystkie zatwierdzone tokeny)")

print("\nInterakcja zakonczona.")
