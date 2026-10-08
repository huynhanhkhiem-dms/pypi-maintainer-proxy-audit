#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ENCODED_DIR = ROOT / "data_encoded"

TARGETS = {
    "metadata_proxy_edges.csv.gz": "e0bac12fa6344c8385123e2a6c3eec924ef41937b3ecc00e6461922daea47441",
    "roles.csv.gz": "c59a6681c608db97f20646ddc17bb71a40ac9721bb4edd49e5b2f56901e6cb54",
    "journal_role_events.csv.gz": "a86359ae4aa3099f9cef289ff87eb949da456d111dbf1a259c2d0256964768b1",
}

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def reconstruct(name: str, expected_sha: str) -> None:
    target = DATA_DIR / name
    parts = sorted(ENCODED_DIR.glob(f"{name}.part*.b64"))
    if not parts:
        raise FileNotFoundError(f"No encoded parts found for {name}")

    encoded = "".join(p.read_text(encoding="ascii").strip() for p in parts)
    target.write_bytes(base64.b64decode(encoded, validate=True))

    observed = sha256(target)
    if observed != expected_sha:
        target.unlink(missing_ok=True)
        raise RuntimeError(
            f"Checksum mismatch for {name}: expected {expected_sha}, got {observed}"
        )
    print(f"OK  {name}  {observed}")

def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name, expected_sha in TARGETS.items():
        reconstruct(name, expected_sha)

if __name__ == "__main__":
    main()
