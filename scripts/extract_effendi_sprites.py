"""Extract transparent animation sprites from the generated Effendi atlases."""

from pathlib import Path
from collections import deque

import numpy as np
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = PROJECT_ROOT / "frontend" / "images" / "ai-effendi"
OUTPUT_ROOT = ASSET_ROOT / "sprites"
ALPHA_THRESHOLD = 24


def largest_alpha_component(alpha: Image.Image) -> Image.Image:
    values = np.asarray(alpha)
    visible = values >= ALPHA_THRESHOLD
    visited = np.zeros(visible.shape, dtype=bool)
    largest: list[tuple[int, int]] = []
    height, width = visible.shape

    for y, x in zip(*np.nonzero(visible & ~visited)):
        if visited[y, x]:
            continue
        queue = deque([(int(y), int(x))])
        visited[y, x] = True
        component: list[tuple[int, int]] = []
        while queue:
            current_y, current_x = queue.popleft()
            component.append((current_y, current_x))
            for next_y, next_x in (
                (current_y - 1, current_x),
                (current_y + 1, current_x),
                (current_y, current_x - 1),
                (current_y, current_x + 1),
            ):
                if (
                    0 <= next_y < height
                    and 0 <= next_x < width
                    and visible[next_y, next_x]
                    and not visited[next_y, next_x]
                ):
                    visited[next_y, next_x] = True
                    queue.append((next_y, next_x))
        if len(component) > len(largest):
            largest = component

    filtered = np.zeros_like(values)
    if largest:
        component_y, component_x = zip(*largest)
        filtered[np.asarray(component_y), np.asarray(component_x)] = values[
            np.asarray(component_y), np.asarray(component_x)
        ]
    return Image.fromarray(filtered, mode="L")


def clean_and_trim(image: Image.Image, padding: int = 4) -> Image.Image:
    image = image.convert("RGBA")
    red, green, blue, alpha = image.split()
    alpha = largest_alpha_component(alpha)
    image = Image.merge("RGBA", (red, green, blue, alpha))
    bounds = alpha.getbbox()
    if bounds is None:
        raise ValueError("Sprite crop contains no visible pixels.")
    left, top, right, bottom = bounds
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(image.width, right + padding)
    bottom = min(image.height, bottom + padding)
    return image.crop((left, top, right, bottom))


def save_crop(source: Image.Image, name: str, box: tuple[int, int, int, int]) -> None:
    sprite = clean_and_trim(source.crop(box))
    sprite.save(OUTPUT_ROOT / f"{name}.png", optimize=True)
    print(f"{name}: {sprite.width}x{sprite.height}")


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    rig = Image.open(ASSET_ROOT / "effendi-rig-parts-alpha.png")
    rig_crops = {
        "torso": (600, 20, 930, 470),
        "arm-left": (400, 240, 600, 550),
        "arm-right": (930, 240, 1110, 550),
        "leg-left": (530, 450, 760, 840),
        "leg-right": (790, 450, 1010, 840),
        "hand-relaxed-left": (180, 780, 340, 910),
        "hand-greeting-left": (350, 760, 550, 920),
        "hand-point-left": (550, 760, 740, 920),
        "hand-fist-left": (760, 760, 930, 920),
        "hand-explain-left": (950, 760, 1160, 920),
        "hand-relaxed-right": (180, 890, 340, 1024),
        "hand-greeting-right": (350, 880, 550, 1024),
        "hand-point-right": (550, 880, 740, 1024),
        "hand-fist-right": (760, 880, 930, 1024),
        "hand-explain-right": (950, 880, 1160, 1024),
    }
    for name, box in rig_crops.items():
        save_crop(rig, name, box)

    faces = Image.open(ASSET_ROOT / "effendi-visemes-alpha.png")
    face_names = (
        "face-neutral", "face-smile", "face-blink", "face-aa",
        "face-ee", "face-oo", "face-mbp", "face-fv",
        "face-ln", "face-sz", "face-listening", "hat",
    )
    cell_width = faces.width // 4
    row_boundaries = (0, faces.height // 3, (faces.height * 2) // 3, faces.height)
    for index, name in enumerate(face_names):
        row, column = divmod(index, 4)
        box = (
            column * cell_width,
            row_boundaries[row],
            (column + 1) * cell_width,
            row_boundaries[row + 1],
        )
        if name.startswith("face-"):
            portrait = clean_and_trim(faces.crop(box))
            side_trim = 58
            portrait = portrait.crop(
                (
                    side_trim,
                    0,
                    portrait.width - side_trim,
                    min(248, portrait.height),
                )
            )
            portrait = clean_and_trim(portrait, padding=1)
            portrait.save(OUTPUT_ROOT / f"{name}.png", optimize=True)
            print(f"{name}: {portrait.width}x{portrait.height}")
        else:
            save_crop(faces, name, box)


if __name__ == "__main__":
    main()
