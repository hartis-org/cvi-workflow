#!/usr/bin/env python3
import os, sys, json
from pathlib import Path

def main():
    if len(sys.argv) < 3:
        print("Usage: setup_env.py <config.json> <output_dir>")
        sys.exit(1)

    config_fp = Path(sys.argv[1]).resolve()
    output_dir = Path(sys.argv[2]).resolve()

    print(f"🔹 Working dir: {os.getcwd()}")
    print(f"🔹 Config file: {config_fp}")
    print(f"🔹 Output dir: {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    if not config_fp.exists():
        print(f"❌ Configuration not found: {config_fp}")
        sys.exit(1)

    with open(config_fp) as f:
        config = json.load(f)

    expected_keys = ["weights"]
    for k in expected_keys:
        if k not in config:
            print(f"⚠️ Missing key '{k}' in configuration.")
        else:
            print(f"✅ Key '{k}' found.")

    for sub in ["data", "logs"]:
        d = output_dir / sub
        d.mkdir(exist_ok=True)
        print(f"📁 Created directory: {d}")

    validated_config_fp = output_dir / "config_validated.json"
    with open(validated_config_fp, "w") as f:
        json.dump(config, f, indent=2)
    print(f"✅ Saved validated config at: {validated_config_fp}")

if __name__ == "__main__":
    main()
