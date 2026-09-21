#ten plik został poprawiony za pomocą Deepseek, wprowadzone niesamodzielne zmiany są napisane w komentarzach do kodu
import json
import os
from solcx import compile_standard, install_solc

SOLC_VERSION = "0.8.20"
print(f"Instalowanie solc {SOLC_VERSION}...")
install_solc(SOLC_VERSION)

contracts_dir = os.path.join(os.path.dirname(__file__), "..", "contracts")
sources = {}

for filename in ["MyToken.sol", "DEX.sol"]:
    filepath = os.path.join(contracts_dir, filename)
    with open(filepath, "r") as f:
        sources[filename] = {"content": f.read()}

print("Kompilacja...")
compiled_sol = compile_standard(
    {
        "language": "Solidity",
        "sources": sources,
        "settings": {
            "outputSelection": {
                "*": {"*": ["abi", "evm.bytecode.object"]}
            }
        },
    },
    solc_version=SOLC_VERSION,
)

artifacts_dir = os.path.join(os.path.dirname(__file__), "..", "artifacts")
os.makedirs(artifacts_dir, exist_ok=True)

# ZMIANA: iterujemy po trójkach (nazwa_pliku, nazwa_kontraktu, nazwa_artefaktu)
contracts_to_save = [
    ("MyToken.sol", "MyToken", "MyToken"),
    ("DEX.sol", "DEX", "DEX"),
]

for filename, contract_name, artifact_name in contracts_to_save:
    contract_data = compiled_sol["contracts"][filename][contract_name]
    artifact = {
        "abi": contract_data["abi"],
        "bytecode": contract_data["evm"]["bytecode"]["object"],
    }
    output_path = os.path.join(artifacts_dir, f"{artifact_name}.json")
    with open(output_path, "w") as f:
        json.dump(artifact, f, indent=2)
    print(f"Zapisano {output_path}")

print("Kompilacja zakonczona pomyslnie.")
