"""Extract transparent web puppet sprites from the cartoon Effendi atlases."""

from pathlib import Path

import numpy as np
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = PROJECT_ROOT / "frontend" / "images" / "ai-effendi" / "cartoon"
OUTPUT_ROOT = ASSET_ROOT / "sprites"


def remove_chroma_green(image: Image.Image) -> Image.Image:
    rgba = np.asarray(image.convert("RGBA")).copy()
    red = rgba[..., 0].astype(np.int16)
    green = rgba[..., 1].astype(np.int16)
    blue = rgba[..., 2].astype(np.int16)
    dominance = green - np.maximum(red, blue)
    alpha = np.clip((55 - dominance) * 6, 0, 255).astype(np.uint8)
    alpha[(green > 150) & (dominance > 55)] = 0
    rgba[..., 3] = np.minimum(rgba[..., 3], alpha)
    return Image.fromarray(rgba, mode="RGBA")


def trim(image: Image.Image, padding: int = 4) -> Image.Image:
    alpha = image.getchannel("A")
    bounds = alpha.getbbox()
    if bounds is None:
        raise ValueError("Sprite crop contains no visible pixels")
    left, top, right, bottom = bounds
    return image.crop(
        (
            max(0, left - padding),
            max(0, top - padding),
            min(image.width, right + padding),
            min(image.height, bottom + padding),
        )
    )


def save_crop(
    source: Image.Image,
    name: str,
    box: tuple[int, int, int, int],
    *,
    mirror: bool = False,
) -> None:
    sprite = trim(source.crop(box))
    if mirror:
        sprite = sprite.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    sprite.save(OUTPUT_ROOT / f"{name}.png", optimize=True)
    print(f"{name}: {sprite.width}x{sprite.height}")


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    rig = remove_chroma_green(Image.open(ASSET_ROOT / "effendi-cartoon-rig-parts.png"))
    rig_crops = {
        "legs": (35, 175, 300, 640),
        "leg-left": (35, 175, 174, 640),
        "leg-right": (160, 175, 300, 640),
        "arm-left": (335, 165, 530, 520),
        "torso": (570, 155, 950, 545),
        "arm-right": (995, 165, 1190, 520),
        "hand-relaxed-left": (330, 555, 455, 730),
        "hand-greeting-left": (470, 535, 630, 735),
        "hand-point-left": (655, 565, 850, 710),
        "hand-fist-left": (865, 565, 1025, 710),
        "hand-explain-left": (1025, 560, 1220, 720),
        "hand-relaxed-right": (330, 735, 455, 905),
        "hand-greeting-right": (470, 720, 630, 915),
        "hand-point-right": (655, 745, 850, 890),
        "hand-fist-right": (865, 745, 1025, 890),
        "hand-explain-right": (1025, 735, 1220, 900),
    }
    for name, box in rig_crops.items():
        save_crop(rig, name, box, mirror=name.startswith("hand-") and name.endswith("-right"))

    faces = remove_chroma_green(Image.open(ASSET_ROOT / "effendi-cartoon-visemes.png"))
    face_names = (
        "face-neutral", "face-smile", "face-blink", "face-aa",
        "face-ee", "face-oo", "face-mbp", "face-fv",
        "face-ln", "face-sz", "face-listening", "hat",
    )
    cell_width = faces.width // 4
    cell_height = faces.height // 3
    for index, name in enumerate(face_names):
        row, column = divmod(index, 4)
        save_crop(
            faces,
            name,
            (
                column * cell_width,
                row * cell_height,
                (column + 1) * cell_width,
                faces.height if row == 2 else (row + 1) * cell_height,
            ),
        )


if __name__ == "__main__":
    main()
