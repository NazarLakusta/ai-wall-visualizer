"""Full dekor.showroom catalog: paint colors, brand packs, gloss line, decor shades."""

import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
STEPS = (
    "seed_dekor_showroom_catalog.py",
    "seed_dekor_brand_packs.py",
    "seed_dekor_chinese_silk_shades.py",
    "link_store_brands.py",
)


def main() -> None:
    slug = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("STORE_SLUG", "dekor-showroom")
    env = {**os.environ, "STORE_SLUG": slug}
    print(f"Seeding full catalog for store slug: {slug}")

    for name in STEPS:
        path = SCRIPTS_DIR / name
        print(f"\n==> {name}")
        subprocess.run([sys.executable, str(path)], env=env, check=True)

    print(f"\nAll done for '{slug}'.")


if __name__ == "__main__":
    main()
