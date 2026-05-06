"""
Standalone script: upload all pack/UI images to Cloudinary.
Run: python upload_pack_images.py
Set CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET before running.
"""
import os
import time
from pathlib import Path

import cloudinary
import cloudinary.uploader
import cloudinary.api

CLOUD_NAME = "djaj8fwjh"
API_KEY = os.environ.get("CLOUDINARY_API_KEY", "")
API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")

IMAGES_DIR = Path("static/images")
FOLDER = "ui/packs"

PACK_IMAGES = [
    "pack.png",
    "bundle_pack.png",
    "kanto_pack.png",
    "johto_pack.png",
    "hoenn_pack.png",
    "sinnoh_pack.png",
    "unova_pack.png",
    "kalos_pack.png",
    "alola_pack.png",
    "galar_pack.png",
    "kanto_bundle_pack.png",
    "johto_bundle_pack.png",
    "hoenn_bundle_pack.png",
    "sinnoh_bundle_pack.png",
    "unova_bundle_pack.png",
    "kalos_bundle_pack.png",
    "alola_bundle_pack.png",
    "galar_bundle_pack.png",
]

cloudinary.config(cloud_name=CLOUD_NAME, api_key=API_KEY, api_secret=API_SECRET)


def get_existing() -> set[str]:
    existing = set()
    next_cursor = None
    while True:
        kwargs = {"resource_type": "image", "type": "upload", "prefix": FOLDER + "/", "max_results": 500}
        if next_cursor:
            kwargs["next_cursor"] = next_cursor
        result = cloudinary.api.resources(**kwargs)
        for r in result.get("resources", []):
            existing.add(r["public_id"])
        next_cursor = result.get("next_cursor")
        if not next_cursor:
            break
    return existing


def main():
    if not API_KEY or not API_SECRET:
        print("Set CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET env vars first.")
        return

    print("Fetching existing Cloudinary files...")
    existing = get_existing()
    print(f"Already on Cloudinary: {len(existing)}")

    for filename in PACK_IMAGES:
        local_path = IMAGES_DIR / filename
        stem = Path(filename).stem
        public_id = f"{FOLDER}/{stem}"

        if not local_path.exists():
            print(f"  SKIP {filename} — not found locally")
            continue

        if public_id in existing:
            print(f"  EXISTS {filename}")
            continue

        try:
            cloudinary.uploader.upload(
                str(local_path),
                public_id=public_id,
                resource_type="image",
                overwrite=True,
            )
            print(f"  OK {filename}")
        except Exception as exc:
            print(f"  ERROR {filename}: {exc}")
        time.sleep(0.3)

    print("Done.")
    print()
    print("Cloudinary base URL for reference:")
    print(f"  https://res.cloudinary.com/{CLOUD_NAME}/image/upload/f_auto,q_auto,w_140/{FOLDER}/<stem>")


if __name__ == "__main__":
    main()
