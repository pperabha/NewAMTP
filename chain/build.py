"""Compile RootAnchor.sol into RootAnchor.json (ABI + bytecode), so running AMTP needs no compiler.

    .venv/bin/python chain/build.py          # downloads solc 0.8.28 once (py-solc-x), then compiles

The committed RootAnchor.json is the output of this script; rerun it only after editing the contract.
"""
import json
import os
import sys

import solcx

SOLC = "0.8.28"
EVM = "cancun"
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    solcx.install_solc(SOLC)
    src = open(os.path.join(HERE, "RootAnchor.sol"), encoding="utf-8").read()
    out = solcx.compile_standard({
        "language": "Solidity",
        "sources": {"RootAnchor.sol": {"content": src}},
        "settings": {"optimizer": {"enabled": True, "runs": 200}, "evmVersion": EVM,
                     "outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}}},
    }, solc_version=SOLC)
    for e in out.get("errors", []):
        print(e["formattedMessage"], file=sys.stderr)
        if e["severity"] == "error":
            raise SystemExit(1)
    c = out["contracts"]["RootAnchor.sol"]["RootAnchor"]
    art = {"contract": "RootAnchor", "solc": SOLC, "evm": EVM, "optimizer_runs": 200,
           "abi": c["abi"], "bytecode": "0x" + c["evm"]["bytecode"]["object"]}
    with open(os.path.join(HERE, "RootAnchor.json"), "w", encoding="utf-8") as f:
        json.dump(art, f, indent=1)
        f.write("\n")
    print(f"RootAnchor.json: {len(c['evm']['bytecode']['object']) // 2} bytes of bytecode, solc {SOLC}, {EVM}")


if __name__ == "__main__":
    main()
