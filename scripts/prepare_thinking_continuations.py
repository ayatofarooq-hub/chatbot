"""Prepare generated thinking continuations without discarding native alpha."""

from PIL import Image

from scripts.align_flipbook_frames import ASSET_DIRECTORY, align_sheet
from scripts.remove_flipbook_background import connected_background


def prepare() -> None:
    for mode in ("day", "night"):
        for sequence in ("b", "c", "d"):
            stem = f"effendi-thinking-chair-{mode}-{sequence}-8"
            source_path = ASSET_DIRECTORY / f"{stem}-v1.png"
            transparent_path = ASSET_DIRECTORY / f"{stem}-transparent-v1.png"
            aligned_path = ASSET_DIRECTORY / f"{stem}-aligned-transparent-v1.png"
            with Image.open(source_path) as source:
                if "A" in source.getbands():
                    prepared = source.convert("RGBA")
                else:
                    prepared = connected_background(source)
                prepared.save(transparent_path, optimize=True)
            align_sheet(transparent_path, aligned_path)


if __name__ == "__main__":
    prepare()
