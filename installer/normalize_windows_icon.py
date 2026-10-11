"""Normalize the existing user-approved JARVIS icon for PyInstaller AND Inno Setup.

Inno Setup 6 rejects some PNG-only or incomplete ICO directories that
PyInstaller accepts. Preserve the image (do not replace it with an unrelated
logo) and encode multiple real Windows BMP/DIB icon resources.

Runs before either EXE is built. No network, audio, or personal data.
"""
from __future__ import annotations

import argparse
import os
import struct
import tempfile
from pathlib import Path

from PIL import Image

# Never decode the corrupted 2.5 KB ICO from earlier builds. Instead,
# regenerate the Windows icon from the user's approved JARVIS logo image.
DEFAULT_SOURCE = Path("assets/JARVIS_AI_Logo_source.png")
REQUIRED_SIZES = (16, 32, 48, 64, 128, 256)
DEFAULT_OUTPUT = Path("assets/JARVIS_AI_Logo.ico")


def inspect_icon(path: Path) -> set[int]:
    """Validate the full ICO directory, ranges, and real DIB payloads."""
    content = Path(path).read_bytes()
    if len(content) < 6:
        raise ValueError("Windows ICO header missing")
    reserved, icon_type, count = struct.unpack_from("<HHH", content)
    if (reserved, icon_type) != (0, 1) or count < 1:
        raise ValueError("Not a genuine Windows ICO")
    found: set[int] = set()
    for index in range(count):
        pos = 6 + index * 16
        if pos + 16 > len(content):
            raise ValueError("Truncated icon directory")
        width, height, _, _, _, depth, size, offset = struct.unpack_from("<BBBBHHII", content, pos)
        width, height = width or 256, height or 256
        if size < 40 or offset + size > len(content) or offset < 6 + count * 16:
            raise ValueError("Truncated icon resource")
        # Inno Setup's PE resource writer accepts canonical DIB icon frames.
        if content[offset:offset + 4] != b"\x28\x00\x00\x00":
            raise ValueError("ICO resource is not Windows BMP/DIB encoded")
        if width != height or depth < 24:
            raise ValueError("Invalid dimensions or color depth")
        found.add(width)
    return found


def normalize_icon(source: Path, output: Path) -> Path:
    source, output = Path(source), Path(output)
    with Image.open(source) as im:
        # A malformed source that Pillow cannot decode must stop the build
        # rather than ship a random replacement logo.
        square = im.convert("RGBA")
        if min(square.size) < 64:
            raise ValueError("JARVIS icon source resolution too small")
        if square.width != square.height:
            side = max(square.size)
            canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            canvas.alpha_composite(square, ((side-square.width)//2, (side-square.height)//2))
            square = canvas
        if square.width < 256:
            square = square.resize((256, 256), Image.Resampling.LANCZOS)
        elif square.width > 256:
            square = square.resize((256, 256), Image.Resampling.LANCZOS)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".ico", delete=False) as tmp:
        temp = Path(tmp.name)
    try:
        square.save(temp, format="ICO",
                    sizes=[(n, n) for n in REQUIRED_SIZES],
                    bitmap_format="bmp")
        if not set(REQUIRED_SIZES).issubset(inspect_icon(temp)):
            raise ValueError("Missing icon dimensions for Windows installer")
        os.replace(temp, output)
    finally:
        temp.unlink(missing_ok=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    normalized = normalize_icon(args.source, args.output)
    print("Windows-compatible JARVIS ICO:", normalized,
          "sizes:", sorted(inspect_icon(normalized)))


if __name__ == "__main__":
    main()
