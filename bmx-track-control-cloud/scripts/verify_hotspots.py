"""Refina coordenadas iniciales buscando el máximo de marcador en una ventana pequeña."""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
IMAGE_PATH = ROOT / "app" / "static" / "images" / "cancha.png"
OUTPUT_PATH = ROOT / "app" / "static" / "images" / "cancha-calibration.png"

# Punto inicial manual (left%, top%) basado en la foto con letras.
SEEDS: dict[str, tuple[float, float]] = {
    "B1": (18.5, 14.0),
    "B2": (32.5, 14.0),
    "A1": (18.0, 22.0),
    "A2": (70.5, 14.5),
    "M": (52.5, 15.5),
    "C": (59.0, 16.0),
    "H": (55.5, 19.5),
    "D": (85.0, 11.5),
    "G": (77.0, 17.5),
    "F": (67.0, 29.0),
    "I": (61.5, 35.5),
    "E": (85.0, 51.5),
    "L1": (11.0, 48.0),
    "L2": (74.0, 51.0),
    "L3": (15.5, 67.0),
    "K": (52.0, 91.0),
    "J": (80.5, 81.0),
}

SEARCH_RADIUS_PX = 18


def marker_score(img: np.ndarray, cx: int, cy: int, size: int = 24) -> float:
    half = size // 2
    h, w, _ = img.shape
    if cy - half < 0 or cy + half >= h or cx - half < 0 or cx + half >= w:
        return 0.0
    patch = img[cy - half : cy + half, cx - half : cx + half]
    orange = (
        (patch[:, :, 0] > 175)
        & (patch[:, :, 1] > 85)
        & (patch[:, :, 1] < 215)
        & (patch[:, :, 2] < 175)
    ).sum()
    light_bg = (
        (patch[:, :, 0] > 150)
        & (patch[:, :, 1] > 160)
        & (patch[:, :, 2] > 180)
    ).sum()
    return float(orange * 4 + light_bg)


def refine(img: np.ndarray, left_pct: float, top_pct: float) -> tuple[int, int, float]:
    h, w, _ = img.shape
    cx0 = int(left_pct / 100 * w)
    cy0 = int(top_pct / 100 * h)
    best = (cx0, cy0, 0.0)
    for cy in range(cy0 - SEARCH_RADIUS_PX, cy0 + SEARCH_RADIUS_PX + 1):
        for cx in range(cx0 - SEARCH_RADIUS_PX, cx0 + SEARCH_RADIUS_PX + 1):
            score = marker_score(img, cx, cy)
            if score > best[2]:
                best = (cx, cy, score)
    return best


def main() -> None:
    img = np.array(Image.open(IMAGE_PATH).convert("RGB"))
    h, w, _ = img.shape
    overlay = Image.open(IMAGE_PATH).convert("RGBA")
    draw = ImageDraw.Draw(overlay)

    print("TRACK_MAP_HOTSPOTS = [")
    for name, (left_seed, top_seed) in SEEDS.items():
        cx, cy, _ = refine(img, left_seed, top_seed)
        code = name[0]
        left_pct = cx / w * 100
        top_pct = cy / h * 100
        print(f"    {{'code': '{code}', 'top': {top_pct:.1f}, 'left': {left_pct:.1f}}},  # {name}")
        box = 13
        draw.rectangle((cx - box, cy - box, cx + box, cy + box), outline=(0, 180, 255, 255), width=2)
        draw.text((cx - 8, cy - 6), code, fill=(0, 80, 255, 255))
    print("]")
    overlay.save(OUTPUT_PATH)
    print(f"Guardado: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
