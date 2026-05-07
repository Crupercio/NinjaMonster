"""
Management command: upload_audio_to_cloudinary

Checks which Gen 1 Pokemon name audio files are missing from Cloudinary
and uploads them. Run on Railway to fix missing audio.

Usage:
    python manage.py upload_audio_to_cloudinary          # check & upload missing
    python manage.py upload_audio_to_cloudinary --all    # re-upload all
    python manage.py upload_audio_to_cloudinary --check  # check only, no upload
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import cloudinary
import cloudinary.api
import cloudinary.uploader
from django.core.management.base import BaseCommand

from apps.pokemon.models import Pokemon

CLOUDINARY_FOLDER = "pokemon/audio/name/Kanto"
LOCAL_AUDIO_DIR = Path("media/pokemon/audio/name/Kanto")


class Command(BaseCommand):
    help = "Check and upload missing Pokemon name audio files to Cloudinary"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--all", action="store_true", help="Re-upload all files")
        parser.add_argument("--check", action="store_true", help="Check only, no upload")

    def handle(self, *args: Any, **options: Any) -> None:
        cloud = cloudinary.config()
        if not cloud.cloud_name:
            self.stderr.write("Cloudinary not configured. Set CLOUDINARY_CLOUD_NAME, _API_KEY, _API_SECRET.")
            return

        gen1 = Pokemon.objects.filter(
            pokedex_number__gte=1, pokedex_number__lte=151
        ).order_by("pokedex_number")

        # Fetch existing files from Cloudinary
        self.stdout.write("Fetching Cloudinary file list...")
        existing: set[str] = set()
        next_cursor = None
        while True:
            kwargs: dict = {
                "resource_type": "video",
                "type": "upload",
                "prefix": f"{CLOUDINARY_FOLDER}/",
                "max_results": 500,
            }
            if next_cursor:
                kwargs["next_cursor"] = next_cursor
            result = cloudinary.api.resources(**kwargs)
            for r in result.get("resources", []):
                # public_id = "pokemon/audio/name/Kanto/001 - Bulbasaur"
                existing.add(r["public_id"])
            next_cursor = result.get("next_cursor")
            if not next_cursor:
                break

        self.stdout.write(f"Found {len(existing)} files on Cloudinary.")

        missing = []
        for pokemon in gen1:
            num = str(pokemon.pokedex_number).zfill(3)
            filename = f"{num} - {pokemon.name}.wav"
            public_id = f"{CLOUDINARY_FOLDER}/{num} - {pokemon.name}"
            local_path = LOCAL_AUDIO_DIR / filename

            on_cloudinary = public_id in existing
            on_disk = local_path.exists()

            if not on_cloudinary:
                missing.append((pokemon, filename, public_id, local_path, on_disk))

        if not missing and not options["all"]:
            self.stdout.write(self.style.SUCCESS("All 151 audio files are on Cloudinary."))
            return

        if options["check"]:
            self.stdout.write(f"\nMissing from Cloudinary ({len(missing)}):")
            for p, fn, pid, lp, on_disk in missing:
                status = "LOCAL OK" if on_disk else "MISSING LOCALLY TOO"
                self.stdout.write(f"  #{p.pokedex_number:03d} {p.name} — {status}")
            return

        # Upload missing (or all if --all)
        to_upload = missing
        if options["all"]:
            to_upload = [
                (p, f"{str(p.pokedex_number).zfill(3)} - {p.name}.wav",
                 f"{CLOUDINARY_FOLDER}/{str(p.pokedex_number).zfill(3)} - {p.name}",
                 LOCAL_AUDIO_DIR / f"{str(p.pokedex_number).zfill(3)} - {p.name}.wav",
                 (LOCAL_AUDIO_DIR / f"{str(p.pokedex_number).zfill(3)} - {p.name}.wav").exists())
                for p in gen1
            ]

        uploaded = 0
        for pokemon, filename, public_id, local_path, on_disk in to_upload:
            if not on_disk:
                self.stderr.write(f"  SKIP #{pokemon.pokedex_number:03d} {pokemon.name} — not found locally at {local_path}")
                continue
            try:
                cloudinary.uploader.upload(
                    str(local_path),
                    public_id=public_id,
                    resource_type="video",
                    overwrite=True,
                )
                uploaded += 1
                self.stdout.write(f"  ✓ #{pokemon.pokedex_number:03d} {pokemon.name}")
            except Exception as exc:
                self.stderr.write(f"  ERROR #{pokemon.pokedex_number:03d} {pokemon.name}: {exc}")

        self.stdout.write(self.style.SUCCESS(f"Done. Uploaded {uploaded} files."))
