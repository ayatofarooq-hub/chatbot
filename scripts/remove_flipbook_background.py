"""Remove the baked neutral checkerboard around whole-body flipbook frames."""

from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIRECTORY = ROOT / "frontend/images/ai-effendi/fallback"
JOBS = (
    ("effendi-fullbody-flipbook-v1.png", "effendi-fullbody-flipbook-transparent-v1.png"),
    ("effendi-idle-8-v1.png", "effendi-idle-8-transparent-v1.png"),
    ("effendi-talking-8-v1.png", "effendi-talking-8-transparent-v1.png"),
    ("effendi-thinking-8-v1.png", "effendi-thinking-8-transparent-v1.png"),
    ("effendi-night-idle-8-v1.png", "effendi-night-idle-8-transparent-v1.png"),
    ("effendi-night-talking-8-v1.png", "effendi-night-talking-8-transparent-v1.png"),
    ("effendi-night-thinking-8-v1.png", "effendi-night-thinking-8-transparent-v1.png"),
    ("effendi-thinking-chair-day-8-v1.png", "effendi-thinking-chair-day-8-transparent-v1.png"),
    ("effendi-thinking-chair-night-8-v1.png", "effendi-thinking-chair-night-8-transparent-v1.png"),
)


def is_background(pixel: tuple[int, int, int]) -> bool:
    # Generated sheets use both a pale and a medium neutral checker square.
    return min(pixel) >= 195 and max(pixel) - min(pixel) <= 18


def connected_background(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    seen = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def add(x: int, y: int) -> None:
        index = y * width + x
        if not seen[index] and is_background(pixels[x, y]):
            seen[index] = 1
            queue.append((x, y))

    for x in range(width):
        add(x, 0)
        add(x, height - 1)
    for y in range(height):
        add(0, y)
        add(width - 1, y)

    while queue:
        x, y = queue.popleft()
        if x > 0:
            add(x - 1, y)
        if x + 1 < width:
            add(x + 1, y)
        if y > 0:
            add(x, y - 1)
        if y + 1 < height:
            add(x, y + 1)

    alpha = Image.new("L", (width, height), 255)
    alpha_pixels = alpha.load()
    for y in range(height):
        row = y * width
        for x in range(width):
            if seen[row + x]:
                alpha_pixels[x, y] = 0

    alpha = alpha.filter(ImageFilter.GaussianBlur(0.45))
    result = image.convert("RGBA")
    result.putalpha(alpha)
    return keep_largest_component_per_cell(result)


def keep_largest_component_per_cell(
    image: Image.Image,
    columns: int = 4,
    rows: int = 2,
) -> Image.Image:
    """Discard isolated checker artifacts while preserving the main sprite."""

    alpha = image.getchannel("A")
    width, height = alpha.size
    cell_width = width // columns
    cell_height = height // rows
    pixels = alpha.load()
    keep = bytearray(width * height)

    for row in range(rows):
        for column in range(columns):
            left = column * cell_width
            top = row * cell_height
            right = left + cell_width
            bottom = top + cell_height
            seen = set()
            largest: list[tuple[int, int]] = []

            for y in range(top, bottom):
                for x in range(left, right):
                    if (x, y) in seen or pixels[x, y] < 24:
                        continue
                    component: list[tuple[int, int]] = []
                    queue = deque([(x, y)])
                    seen.add((x, y))
                    while queue:
                        current_x, current_y = queue.popleft()
                        component.append((current_x, current_y))
                        for next_x, next_y in (
                            (current_x - 1, current_y),
                            (current_x + 1, current_y),
                            (current_x, current_y - 1),
                            (current_x, current_y + 1),
                        ):
                            if (
                                left <= next_x < right
                                and top <= next_y < bottom
                                and (next_x, next_y) not in seen
                                and pixels[next_x, next_y] >= 24
                            ):
                                seen.add((next_x, next_y))
                                queue.append((next_x, next_y))
                    if len(component) > len(largest):
                        largest = component

            for x, y in largest:
                keep[y * width + x] = 1

    cleaned = image.copy()
    cleaned_alpha = cleaned.getchannel("A")
    cleaned_pixels = cleaned_alpha.load()
    for y in range(height):
        offset = y * width
        for x in range(width):
            if not keep[offset + x]:
                cleaned_pixels[x, y] = 0
    cleaned.putalpha(cleaned_alpha)
    return cleaned


if __name__ == "__main__":
    for source_name, output_name in JOBS:
        source_path = ASSET_DIRECTORY / source_name
        if not source_path.exists():
            continue
        output_path = ASSET_DIRECTORY / output_name
        output = connected_background(Image.open(source_path))
        output.save(output_path, optimize=True)
        print(
            f"Saved {output_path} ({output.width}x{output.height}, "
            f"RGBA, alpha={output.getchannel('A').getextrema()})"
        )
