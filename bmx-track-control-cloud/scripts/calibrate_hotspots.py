"""Detecta marcadores (cuadro claro + letra naranja) y genera coordenadas + imagen de verificación."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
IMAGE_PATH = ROOT / "app" / "static" / "images" / "cancha.png"
OUTPUT_PATH = ROOT / "app" / "static" / "images" / "cancha-calibration.png"

# Regiones esperadas por marcador (left, top, right, bottom) en fracción 0-1.
REGIONS: dict[str, tuple[float, float, float, float]] = {
    "B1": (0.13, 0.07, 0.25, 0.19),
    "B2": (0.27, 0.07, 0.39, 0.19),
    "A1": (0.15, 0.17, 0.27, 0.29),
    "A2": (0.66, 0.10, 0.76, 0.22),
    "M": (0.50, 0.09, 0.58, 0.19),
    "C": (0.54, 0.11, 0.62, 0.21),
    "H": (0.53, 0.15, 0.61, 0.25),
    "D": (0.80, 0.07, 0.92, 0.19),
    "G": (0.72, 0.11, 0.82, 0.23),
    "F": (0.62, 0.23, 0.72, 0.33),
    "I": (0.58, 0.30, 0.68, 0.40),
    "E": (0.82, 0.46, 0.94, 0.58),
    "L1": (0.03, 0.40, 0.14, 0.52),
    "L2": (0.66, 0.40, 0.78, 0.54),
    "L3": (0.10, 0.60, 0.22, 0.74),
    "K": (0.46, 0.84, 0.58, 0.96),
    "J": (0.78, 0.78, 0.90, 0.90),
}


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
        (patch[:, :, 0] > 155)
        & (patch[:, :, 1] > 165)
        & (patch[:, :, 2] > 185)
        & (patch[:, :, 2] >= patch[:, :, 0])
    ).sum()
    white_bg = ((patch[:, :, 0] > 205) & (patch[:, :, 1] > 205) & (patch[:, :, 2] > 205)).sum()
    return float(orange * 3 + light_bg + white_bg * 0.5)


def find_marker(
    img: np.ndarray,
    bounds: tuple[float, float, float, float],
) -> tuple[int, int, float]:
    h, w, _ = img.shape
    left, top, right, bottom = bounds
    x0, x1 = int(left * w), int(right * w)
    y0, y1 = int(top * h), int(bottom * h)
    best = (0, 0, 0.0)
    for cy in range(y0, y1, 1):
        for cx in range(x0, x1, 1):
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
    for name, bounds in REGIONS.items():
        cx, cy, score = find_marker(img, bounds)
        code = name[0]
        top_pct = cy / h * 100
        left_pct = cx / w * 100
        print(
            f"    {{'code': '{code}', 'top': {top_pct:.1f}, 'left': {left_pct:.1f}}},  # {name}"
        )

        box = 14
        draw.rectangle(
            (cx - box, cy - box, cx + box, cy + box),
            outline=(255, 0, 0, 220),
            width=2,
        )
        draw.text((cx + 16, cy - 8), name, fill=(255, 0, 0, 255))
    print("]")

    overlay.save(OUTPUT_PATH)
    print(f"\nGuardado: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
