"""Normalize whole-character sprite frames to a fixed feet anchor and scale."""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIRECTORY = ROOT / "frontend/images/ai-effendi/fallback"
SOURCES = (
    "effendi-idle-8-transparent-v1.png",
    "effendi-talking-8-transparent-v1.png",
    "effendi-thinking-8-transparent-v1.png",
    "effendi-night-idle-8-transparent-v1.png",
    "effendi-night-talking-8-transparent-v1.png",
    "effendi-night-thinking-8-transparent-v1.png",
)
COLUMNS = 4
ROWS = 2
TARGET_HEIGHT = 450
TARGET_BOTTOM = 492


def feet_center(alpha: Image.Image) -> float:
    """Find the horizontal body anchor from the lowest 18% (legs and shoes)."""

    width, height = alpha.size
    pixels = alpha.load()
    start_y = max(0, int(height * 0.82))
    xs = [
        x
        for y in range(start_y, height)
        for x in range(width)
        if pixels[x, y] >= 96
    ]
    if not xs:
        return width / 2
    return (min(xs) + max(xs)) / 2


def align_sheet(source_path: Path, output_path: Path) -> None:
    source = Image.open(source_path).convert("RGBA")
    cell_width = source.width // COLUMNS
    cell_height = source.height // ROWS
    output = Image.new("RGBA", source.size, (0, 0, 0, 0))

    for frame in range(COLUMNS * ROWS):
        column = frame % COLUMNS
        row = frame // COLUMNS
        origin_x = column * cell_width
        origin_y = row * cell_height
        cell = source.crop((origin_x, origin_y, origin_x + cell_width, origin_y + cell_height))
        bounds = cell.getchannel("A").getbbox()
        if not bounds:
            continue

        character = cell.crop(bounds)
        scale = TARGET_HEIGHT / character.height
        maximum_width = cell_width - 12
        if character.width * scale > maximum_width:
            scale = maximum_width / character.width
        resized = character.resize(
            (max(1, round(character.width * scale)), max(1, round(character.height * scale))),
            Image.Resampling.LANCZOS,
        )

        anchor_x = feet_center(resized.getchannel("A"))
        paste_x = round(origin_x + cell_width / 2 - anchor_x)
        paste_y = round(origin_y + TARGET_BOTTOM - resized.height)
        output.alpha_composite(resized, (paste_x, paste_y))

    output.save(output_path, optimize=True)
    print(f"Saved {output_path.name}: {output.size}, {output.mode}")


if __name__ == "__main__":
    for source_name in SOURCES:
        source_path = ASSET_DIRECTORY / source_name
        output_path = ASSET_DIRECTORY / source_name.replace("-transparent-v1", "-aligned-transparent-v1")
        align_sheet(source_path, output_path)
