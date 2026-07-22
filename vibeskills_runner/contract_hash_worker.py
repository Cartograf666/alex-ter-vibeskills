import sys
from pathlib import Path

import yaml


def main():
    if len(sys.argv) < 3:
        print("Usage: contract_hash_worker.py <contract_path> <trusted_scripts_dir>", file=sys.stderr)
        sys.exit(1)

    contract_path = Path(sys.argv[1]).resolve()
    trusted_scripts_dir = Path(sys.argv[2]).resolve()

    sys.path.insert(0, str(trusted_scripts_dir))
    try:
        from contract_lib import contract_payload_sha256
    except ImportError as e:
        print(f"Failed to import contract_lib: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        content = contract_path.read_text(encoding="utf-8")
        contract = yaml.safe_load(content)
        h = contract_payload_sha256(contract)
        print(h)
        sys.exit(0)
    except Exception as e:
        print(f"Error computing hash: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
