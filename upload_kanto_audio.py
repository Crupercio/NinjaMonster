"""
Standalone script: upload all 151 Kanto Pokemon name WAVs to Cloudinary.
Run: python upload_kanto_audio.py
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

AUDIO_DIR = Path("media/pokemon/audio/name/Kanto")
FOLDER = "pokemon/audio/name/Kanto"

cloudinary.config(cloud_name=CLOUD_NAME, api_key=API_KEY, api_secret=API_SECRET)


def get_existing() -> set[str]:
    existing = set()
    next_cursor = None
    while True:
        kwargs = {"resource_type": "video", "type": "upload", "prefix": FOLDER + "/", "max_results": 500}
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

    wavs = sorted(AUDIO_DIR.glob("*.wav"))
    print(f"Found {len(wavs)} WAV files locally.")

    print("Fetching existing Cloudinary files...")
    existing = get_existing()
    print(f"Already on Cloudinary: {len(existing)}")

    to_upload = []
    for wav in wavs:
        public_id = f"{FOLDER}/{wav.stem}"
        if public_id not in existing:
            to_upload.append((wav, public_id))

    print(f"Need to upload: {len(to_upload)}")

    for i, (wav, public_id) in enumerate(to_upload, 1):
        try:
            cloudinary.uploader.upload(
                str(wav),
                public_id=public_id,
                resource_type="video",
                overwrite=True,
            )
            print(f"  [{i}/{len(to_upload)}] OK {wav.stem[:30]}")
        except Exception as exc:
            print(f"  [{i}/{len(to_upload)}] ERROR #{i}: {exc}")
        # Small delay to avoid rate limits
        time.sleep(0.3)

    print("Done.")


if __name__ == "__main__":
    main()
