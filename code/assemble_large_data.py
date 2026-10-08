from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

FILES = {
    "metadata_proxy_edges.csv.gz": 7,
    "roles.csv.gz": 7,
}

for name, n_parts in FILES.items():
    target = DATA / name
    if target.exists():
        print(f"[skip] {name} already exists")
        continue
    parts = [DATA / f"{name}.part{i:03d}" for i in range(n_parts)]
    missing = [p.name for p in parts if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing parts for {name}: {missing}")
    with target.open("wb") as out:
        for p in parts:
            out.write(p.read_bytes())
    print(f"[ok] assembled {name}")
