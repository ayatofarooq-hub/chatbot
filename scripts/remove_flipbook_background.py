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
)


def is_background(pixel: tuple[int, int, int]) -> bool:
    return min(pixel) >= 225 and max(pixel) - min(pixel) <= 14


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
    return result


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
