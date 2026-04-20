"""
Management command: download_sprites

Downloads official Pokemon sprites from PokeAPI GitHub CDN and generates
effect-processed variant images locally under static/sprites/.

Folder layout after running:
    static/sprites/base/{dex}.png
    static/sprites/shiny/{dex}.png
    static/sprites/battle_scene/{dex}.gif
    static/sprites/anime/{dex}.png
    static/sprites/watercolor/{dex}.png
    static/sprites/sketch/{dex}.png
    static/sprites/neon_glow/{dex}.png
    static/sprites/burn_scroll/{dex}.png
    static/sprites/tv_90s/{dex}.png
    static/sprites/holographic/{dex}.png
    static/sprites/color_swap/{dex}.png
    static/sprites/glitter/{dex}.png
    static/sprites/chrome/{dex}.png
    static/sprites/cartoon/{dex}.png

Requirements:
    pip install Pillow numpy

Usage:
    python manage.py download_sprites                      # all 905 pokemon, all variants
    python manage.py download_sprites --dex-end 151        # Gen 1 only
    python manage.py download_sprites --variants base shiny watercolor
    python manage.py download_sprites --force              # re-download/re-generate
    python manage.py download_sprites --dry-run            # preview without downloading
"""
from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from PIL import Image, ImageFilter

from apps.pokemon.models import Pokemon

logger = logging.getLogger(__name__)

# ── PokeAPI GitHub CDN URLs ─────────────────────────────────────────────────
_RAW = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon"

DOWNLOAD_SOURCES: dict[str, str] = {
    "base":         f"{_RAW}/other/official-artwork/{{dex}}.png",
    "shiny":        f"{_RAW}/other/official-artwork/shiny/{{dex}}.png",
    "battle_scene": f"{_RAW}/versions/generation-v/black-white/animated/{{dex}}.gif",
    "anime":        f"{_RAW}/versions/generation-iv/heartgold-soulsilver/{{dex}}.png",
}

DOWNLOAD_EXTENSIONS: dict[str, str] = {
    "base": ".png",
    "shiny": ".png",
    "battle_scene": ".gif",
    "anime": ".png",
}

EFFECT_VARIANTS: list[str] = [
    "watercolor",
    "sketch",
    "neon_glow",
    "burn_scroll",
    "tv_90s",
    "holographic",
    "color_swap",
    "glitter",
    "chrome",
    "cartoon",
]

ALL_VARIANTS: list[str] = list(DOWNLOAD_SOURCES.keys()) + EFFECT_VARIANTS


# ── Pixel effect utilities ──────────────────────────────────────────────────

def _clamp(arr: np.ndarray) -> np.ndarray:
    return np.clip(arr, 0, 255).astype(np.uint8)


def _screen(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """CSS screen blend: 255 - (255-a)(255-b)/255."""
    return 255.0 - (255.0 - a) * (255.0 - b) / 255.0


def _box_blur(arr: np.ndarray, radius: int) -> np.ndarray:
    """Box blur via Pillow. Returns float64 RGBA array."""
    img = Image.fromarray(arr.astype(np.uint8))
    return np.array(img.filter(ImageFilter.BoxBlur(radius))).astype(np.float64)


def _sobel_mag(arr: np.ndarray) -> np.ndarray:
    """Sobel edge magnitude. arr: H×W×4 RGBA → H×W float."""
    gray = arr[:, :, 0] * 0.299 + arr[:, :, 1] * 0.587 + arr[:, :, 2] * 0.114
    pad = np.pad(gray, 1, mode="edge")
    gx = (
        -pad[:-2, :-2] - 2 * pad[1:-1, :-2] - pad[2:, :-2]
        + pad[:-2, 2:] + 2 * pad[1:-1, 2:] + pad[2:, 2:]
    )
    gy = (
        -pad[:-2, :-2] - 2 * pad[:-2, 1:-1] - pad[:-2, 2:]
        + pad[2:, :-2] + 2 * pad[2:, 1:-1] + pad[2:, 2:]
    )
    return np.sqrt(gx ** 2 + gy ** 2)


def _hsl_to_rgb(h: np.ndarray, s: float = 1.0, lv: float = 0.55) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorised HSL→RGB. h in [0,1]. Returns r,g,b in [0,255]."""
    c = (1.0 - abs(2.0 * lv - 1.0)) * s
    x = c * (1.0 - np.abs((h * 6.0) % 2.0 - 1.0))
    m = lv - c / 2.0
    r = np.zeros_like(h)
    g = np.zeros_like(h)
    b = np.zeros_like(h)
    m0 = h < 1 / 6
    m1 = (h >= 1 / 6) & (h < 2 / 6)
    m2 = (h >= 2 / 6) & (h < 3 / 6)
    m3 = (h >= 3 / 6) & (h < 4 / 6)
    m4 = (h >= 4 / 6) & (h < 5 / 6)
    m5 = h >= 5 / 6
    r[m0] = c;  g[m0] = x[m0]
    r[m1] = x[m1]; g[m1] = c
    g[m2] = c;  b[m2] = x[m2]
    g[m3] = x[m3]; b[m3] = c
    r[m4] = x[m4]; b[m4] = c
    r[m5] = c;  b[m5] = x[m5]
    return (r + m) * 255.0, (g + m) * 255.0, (b + m) * 255.0


# ── Effect functions ────────────────────────────────────────────────────────

def apply_watercolor(arr: np.ndarray) -> np.ndarray:
    soft = _box_blur(arr, 3)
    edges = _sobel_mag(arr.astype(np.float64))
    m_e = edges.max() or 1.0
    rv, gv, bv = soft[:, :, 0], soft[:, :, 1], soft[:, :, 2]
    gr = rv * 0.299 + gv * 0.587 + bv * 0.114
    nr = np.minimum(255.0, gr * 0.12 + rv * 0.88 + 15.0)
    ng = np.minimum(255.0, gr * 0.12 + gv * 0.88 + 15.0)
    nb = np.minimum(255.0, gr * 0.12 + bv * 0.88 + 15.0)
    es = np.minimum(1.0, edges / (m_e * 0.3 + 1e-6))
    out = arr.astype(np.float64).copy()
    out[:, :, 0] = np.maximum(0.0, nr * (1.0 - es * 0.65))
    out[:, :, 1] = np.maximum(0.0, ng * (1.0 - es * 0.65))
    out[:, :, 2] = np.maximum(0.0, nb * (1.0 - es * 0.65))
    rng = np.random.default_rng(42)
    noise = (rng.random(arr.shape[:2]) - 0.5) * 7.0
    out[:, :, 0] = np.clip(out[:, :, 0] + noise, 0, 255)
    out[:, :, 1] = np.clip(out[:, :, 1] + noise, 0, 255)
    out[:, :, 2] = np.clip(out[:, :, 2] + noise, 0, 255)
    return _clamp(out)


def apply_sketch(arr: np.ndarray) -> np.ndarray:
    d = arr.astype(np.float64)
    gray = d[:, :, 0] * 0.299 + d[:, :, 1] * 0.587 + d[:, :, 2] * 0.114
    g_rgba = np.stack([gray, gray, gray, np.full_like(gray, 255.0)], axis=2)
    bl = _box_blur(g_rgba.astype(np.uint8), 8)[:, :, 0]
    v = np.where(bl < 1.0, 255.0, np.minimum(255.0, gray * 255.0 / (bl + 1e-6)))
    out = d.copy()
    out[:, :, 0] = np.minimum(255.0, v * 0.96 + 10.0)
    out[:, :, 1] = np.minimum(255.0, v * 0.94 + 8.0)
    out[:, :, 2] = np.minimum(255.0, v * 0.85)
    out[:, :, 3] = 255.0
    return _clamp(out)


def apply_neon_glow(arr: np.ndarray) -> np.ndarray:
    d = arr.astype(np.float64)
    edges = _sobel_mag(d)
    m_e = edges.max() or 1.0
    e = np.minimum(1.0, edges / (m_e * 0.28 + 1e-6))
    rv, gv, bv = d[:, :, 0], d[:, :, 1], d[:, :, 2]
    mx = np.maximum(np.maximum(rv, gv), bv)
    mx = np.where(mx == 0, 1.0, mx)
    out = np.zeros_like(d)
    out[:, :, 0] = np.minimum(255.0, rv / mx * e * 255.0)
    out[:, :, 1] = np.minimum(255.0, gv / mx * e * 255.0)
    out[:, :, 2] = np.minimum(255.0, bv / mx * e * 255.0)
    out[:, :, 3] = d[:, :, 3]
    neon_img = _clamp(out)
    blurred = np.array(
        Image.fromarray(neon_img).filter(ImageFilter.GaussianBlur(6))
    ).astype(np.float64)
    out2 = out.copy()
    for c in range(3):
        out2[:, :, c] = _screen(out[:, :, c], blurred[:, :, c] * 0.85)
    return _clamp(out2)


def apply_burn_scroll(arr: np.ndarray) -> np.ndarray:
    H, W = arr.shape[:2]
    d = arr.astype(np.float64)
    rv, gv, bv = d[:, :, 0], d[:, :, 1], d[:, :, 2]
    gr = rv * 0.299 + gv * 0.587 + bv * 0.114
    r_b = np.minimum(255.0, gr * 0.3 + rv * 0.9 + 28.0)
    g_b = np.minimum(255.0, gr * 0.12 + gv * 0.6 + 6.0)
    b_b = np.minimum(255.0, gr * 0.04 + bv * 0.3)
    out = d.copy()
    out[:, :, 0] = np.clip((r_b - 128.0) * 1.45 + 128.0, 0, 255)
    out[:, :, 1] = np.clip((g_b - 128.0) * 1.30 + 128.0, 0, 255)
    out[:, :, 2] = np.clip((b_b - 128.0) * 1.10 + 128.0, 0, 255)
    cy, cx = H / 2.0, W / 2.0
    yy = np.arange(H)[:, None]
    xx = np.arange(W)[None, :]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    inner_r = min(W, H) * 0.18
    outer_r = max(W, H) * 0.82
    t = np.clip((dist - inner_r) / (outer_r - inner_r + 1e-6), 0.0, 1.0)
    vig = t * 0.9
    out[:, :, 0] = np.clip(out[:, :, 0] * (1.0 - vig) + 4.0 * vig, 0, 255)
    out[:, :, 1] = np.clip(out[:, :, 1] * (1.0 - vig), 0, 255)
    out[:, :, 2] = np.clip(out[:, :, 2] * (1.0 - vig), 0, 255)
    return _clamp(out)


def apply_tv90s(arr: np.ndarray) -> np.ndarray:
    H, W = arr.shape[:2]
    d = arr.astype(np.float64).copy()
    orig = arr.astype(np.float64)
    sh = max(2, round(W * 0.004))
    x_idx = np.arange(W)
    d[:, :, 0] = orig[:, np.minimum(x_idx + sh, W - 1), 0]
    d[:, :, 2] = orig[:, np.maximum(x_idx - sh, 0), 2]
    rv, gv, bv = d[:, :, 0], d[:, :, 1], d[:, :, 2]
    gr = rv * 0.299 + gv * 0.587 + bv * 0.114
    rng = np.random.default_rng(7)
    n = (rng.random((H, W)) - 0.5) * 38.0
    d[:, :, 0] = np.clip(gr * 0.15 + rv * 0.85 + 8.0 + n, 0, 255)
    d[:, :, 1] = np.clip(gr * 0.10 + gv * 0.90 + 14.0 + n, 0, 255)
    d[:, :, 2] = np.clip(gr * 0.25 + bv * 0.75 - 4.0 + n, 0, 255)
    d[::2, :, :3] *= 0.88  # scanlines
    return _clamp(d)


def apply_holographic(arr: np.ndarray) -> np.ndarray:
    H, W = arr.shape[:2]
    d = arr.astype(np.float64)
    yy = np.arange(H)[:, None] / H
    xx = np.arange(W)[None, :] / W
    hue = ((xx * 260.0 + yy * 140.0) % 360.0) / 360.0
    hr, hg, hb = _hsl_to_rgb(hue, 1.0, 0.55)
    out = d.copy()
    out[:, :, 0] = _screen(d[:, :, 0], hr * 0.58)
    out[:, :, 1] = _screen(d[:, :, 1], hg * 0.58)
    out[:, :, 2] = _screen(d[:, :, 2], hb * 0.58)
    blurred = np.array(
        Image.fromarray(_clamp(out)).filter(ImageFilter.GaussianBlur(8))
    ).astype(np.float64)
    out2 = out.copy()
    for c in range(3):
        out2[:, :, c] = _screen(out[:, :, c], blurred[:, :, c] * 0.25)
    return _clamp(out2)


def apply_color_swap(arr: np.ndarray) -> np.ndarray:
    out = arr.copy()
    out[:, :, 0] = arr[:, :, 2]
    out[:, :, 1] = arr[:, :, 0]
    out[:, :, 2] = arr[:, :, 1]
    return out


def apply_glitter(arr: np.ndarray) -> np.ndarray:
    H, W = arr.shape[:2]
    d = arr.astype(np.float64)
    gr = d[:, :, 0] * 0.299 + d[:, :, 1] * 0.587 + d[:, :, 2] * 0.114
    out = d.copy()
    out[:, :, 0] = np.clip(gr + (d[:, :, 0] - gr) * 2.2, 0, 255)
    out[:, :, 1] = np.clip(gr + (d[:, :, 1] - gr) * 2.2, 0, 255)
    out[:, :, 2] = np.clip(gr + (d[:, :, 2] - gr) * 2.2, 0, 255)
    rng = np.random.default_rng(13)
    num = H * W // 90
    hues = rng.random(num)
    sxs = rng.integers(0, W, num)
    sys_ = rng.integers(0, H, num)
    szs = rng.integers(1, 5, num)
    for i in range(num):
        h_val = np.array([[hues[i]]])
        sr, sg, sb = _hsl_to_rgb(h_val, 1.0, 0.88)
        sr_v = float(sr.flat[0])
        sg_v = float(sg.flat[0])
        sb_v = float(sb.flat[0])
        sx, sy, sz = int(sxs[i]), int(sys_[i]), int(szs[i])
        xr = np.clip(np.arange(sx - sz, sx + sz + 1), 0, W - 1)
        yr = np.clip(np.arange(sy - sz, sy + sz + 1), 0, H - 1)
        out[sy, xr, 0] = sr_v
        out[sy, xr, 1] = sg_v
        out[sy, xr, 2] = sb_v
        out[yr, sx, 0] = sr_v
        out[yr, sx, 1] = sg_v
        out[yr, sx, 2] = sb_v
    blurred = np.array(
        Image.fromarray(_clamp(out)).filter(ImageFilter.GaussianBlur(3))
    ).astype(np.float64)
    out2 = out.copy()
    for c in range(3):
        out2[:, :, c] = _screen(out[:, :, c], blurred[:, :, c] * 0.2)
    return _clamp(out2)


def apply_chrome(arr: np.ndarray) -> np.ndarray:
    H, W = arr.shape[:2]
    d = arr.astype(np.float64)
    gr = d[:, :, 0] * 0.299 + d[:, :, 1] * 0.587 + d[:, :, 2] * 0.114
    v = np.clip((gr - 128.0) * 2.1 + 128.0, 0, 255)
    xx = np.arange(W)[None, :] / W
    yy = np.arange(H)[:, None] / H
    spec = np.minimum(35.0, (xx + 1.0 - yy) * 22.0)
    out = d.copy()
    out[:, :, 0] = np.clip(v * 0.80 + spec, 0, 255)
    out[:, :, 1] = np.clip(v * 0.86 + spec, 0, 255)
    out[:, :, 2] = np.clip(v + spec + 22.0, 0, 255)
    blurred = np.array(
        Image.fromarray(_clamp(out)).filter(ImageFilter.GaussianBlur(4))
    ).astype(np.float64)
    out2 = out.copy()
    for c in range(3):
        out2[:, :, c] = _screen(out[:, :, c], blurred[:, :, c] * 0.3)
    return _clamp(out2)


def apply_cartoon(arr: np.ndarray) -> np.ndarray:
    orig = arr.astype(np.float64)
    bl = _box_blur(arr, 2)
    step = 255.0 / 4.0
    rv = np.round(bl[:, :, 0] / step) * step
    gv = np.round(bl[:, :, 1] / step) * step
    bv = np.round(bl[:, :, 2] / step) * step
    gr = rv * 0.299 + gv * 0.587 + bv * 0.114
    out = orig.copy()
    out[:, :, 0] = np.clip(gr + (rv - gr) * 1.8, 0, 255)
    out[:, :, 1] = np.clip(gr + (gv - gr) * 1.8, 0, 255)
    out[:, :, 2] = np.clip(gr + (bv - gr) * 1.8, 0, 255)
    edges = _sobel_mag(orig)
    m_e = edges.max() or 1.0
    mask = edges > m_e * 0.22
    out[:, :, 0][mask] = 12.0
    out[:, :, 1][mask] = 12.0
    out[:, :, 2][mask] = 18.0
    return _clamp(out)


EFFECT_FN: dict[str, object] = {
    "watercolor":  apply_watercolor,
    "sketch":      apply_sketch,
    "neon_glow":   apply_neon_glow,
    "burn_scroll": apply_burn_scroll,
    "tv_90s":      apply_tv90s,
    "holographic": apply_holographic,
    "color_swap":  apply_color_swap,
    "glitter":     apply_glitter,
    "chrome":      apply_chrome,
    "cartoon":     apply_cartoon,
}


# ── HTTP downloader ─────────────────────────────────────────────────────────

def _download(url: str, dest: Path, retries: int = 2) -> bool:
    """Download url to dest. Returns True on success, False on 404 or error."""
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (StickerBot/2.0)"}
    )
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                dest.write_bytes(resp.read())
            return True
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return False
            if attempt < retries:
                time.sleep(2.0)
            else:
                logger.warning("HTTP %d downloading %s", exc.code, url)
                return False
        except Exception as exc:
            if attempt < retries:
                time.sleep(2.0)
            else:
                logger.warning("Failed %s: %s", url, exc)
                return False
    return False


# ── Management command ──────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        "Download Pokemon sprites from PokeAPI CDN and generate effect variants "
        "locally under static/sprites/."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--variants",
            nargs="+",
            choices=ALL_VARIANTS,
            default=ALL_VARIANTS,
            metavar="VARIANT",
            help=f"Variants to process. Default: all {len(ALL_VARIANTS)}.",
        )
        parser.add_argument(
            "--dex-start",
            type=int,
            default=1,
            metavar="N",
            help="First Pokédex number (inclusive). Default: 1.",
        )
        parser.add_argument(
            "--dex-end",
            type=int,
            default=905,
            metavar="N",
            help="Last Pokédex number (inclusive). Default: 905.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-download/regenerate even if file exists.",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.1,
            metavar="SECONDS",
            help="Seconds between HTTP downloads. Default: 0.1.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be done without downloading or processing.",
        )

    def handle(self, *args: object, **options: object) -> None:
        variants: list[str] = options["variants"]
        dex_start: int = options["dex_start"]
        dex_end: int = options["dex_end"]
        force: bool = options["force"]
        delay: float = options["delay"]
        dry_run: bool = options["dry_run"]

        sprites_root = Path(settings.BASE_DIR) / "static" / "sprites"

        if not dry_run:
            for v in ALL_VARIANTS:
                (sprites_root / v).mkdir(parents=True, exist_ok=True)

        qs = (
            Pokemon.objects.filter(
                pokedex_number__isnull=False,
                pokedex_number__gte=dex_start,
                pokedex_number__lte=dex_end,
            )
            .only("pokedex_number", "name")
            .order_by("pokedex_number")
        )
        pokemon_list = list(qs)

        if not pokemon_list:
            self.stdout.write(self.style.WARNING("No Pokemon found for the given range."))
            return

        download_variants = [v for v in variants if v in DOWNLOAD_SOURCES]
        effect_variants = [v for v in variants if v in EFFECT_FN]
        # If generating effects but base wasn't requested, we still need base images
        needs_base_auto = bool(effect_variants) and "base" not in variants

        self.stdout.write(
            f"\n{'[DRY RUN] ' if dry_run else ''}"
            f"Pokemon: {len(pokemon_list)} (#{dex_start}-#{dex_end})\n"
            f"Downloads:  {len(download_variants)} variant(s)\n"
            f"Effects:    {len(effect_variants)} variant(s)\n"
            f"Output:     {sprites_root}\n"
        )

        done_dl = skip_dl = fail_dl = 0
        done_fx = skip_fx = fail_fx = 0

        for pokemon in pokemon_list:
            dex: int = pokemon.pokedex_number  # type: ignore[assignment]

            # ── Downloads ────────────────────────────────────────────────
            for variant in download_variants:
                ext = DOWNLOAD_EXTENSIONS[variant]
                dest = sprites_root / variant / f"{dex}{ext}"
                url = DOWNLOAD_SOURCES[variant].format(dex=dex)

                if dest.exists() and not force:
                    skip_dl += 1
                    continue

                if dry_run:
                    self.stdout.write(f"  DL    #{dex:04d} {variant}")
                    done_dl += 1
                    continue

                if _download(url, dest):
                    done_dl += 1
                    self.stdout.write(f"  DL ok #{dex:04d} {variant}")
                else:
                    fail_dl += 1
                    self.stdout.write(f"  DL xx #{dex:04d} {variant} (not found)")
                time.sleep(delay)

            # ── Effect generation ────────────────────────────────────────
            if not effect_variants:
                continue

            base_path = sprites_root / "base" / f"{dex}.png"

            if needs_base_auto and not base_path.exists() and not dry_run:
                url = DOWNLOAD_SOURCES["base"].format(dex=dex)
                _download(url, base_path)
                time.sleep(delay)

            if dry_run:
                for variant in effect_variants:
                    self.stdout.write(f"  FX    #{dex:04d} {variant}")
                    done_fx += 1
                continue

            if not base_path.exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"  FX xx #{dex:04d} -- base image missing, skipping effects"
                    )
                )
                fail_fx += len(effect_variants)
                continue

            try:
                base_img = Image.open(base_path).convert("RGBA")
                base_arr = np.array(base_img)
            except Exception as exc:
                self.stdout.write(
                    self.style.WARNING(f"  FX xx #{dex:04d} -- cannot open base: {exc}")
                )
                fail_fx += len(effect_variants)
                continue

            for variant in effect_variants:
                dest = sprites_root / variant / f"{dex}.png"
                if dest.exists() and not force:
                    skip_fx += 1
                    continue

                fn = EFFECT_FN[variant]
                try:
                    result_arr = fn(base_arr)  # type: ignore[operator]
                    Image.fromarray(result_arr).save(dest, "PNG")
                    done_fx += 1
                    self.stdout.write(f"  FX ok #{dex:04d} {variant}")
                except Exception as exc:
                    fail_fx += 1
                    logger.warning("Effect %s failed for dex %d: %s", variant, dex, exc)
                    self.stdout.write(
                        self.style.WARNING(f"  FX xx #{dex:04d} {variant}: {exc}")
                    )

        self.stdout.write(self.style.SUCCESS(
            f"\nDone.\n"
            f"  Downloads: {done_dl} ok, {skip_dl} skipped, {fail_dl} failed\n"
            f"  Effects:   {done_fx} ok, {skip_fx} skipped, {fail_fx} failed\n"
            f"  Sprites at: {sprites_root}\n"
        ))
