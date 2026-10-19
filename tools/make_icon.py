"""生成应用图标：多尺寸 .ico + 预览图。

ICO 用 32 位 BMP 条目（兼容性最好，不依赖 Pillow），
Windows 会在 16/24/32/48/256 各取对应那一帧，不会糊。
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ui.icon import paint_icon  # noqa: E402

OUT = ROOT / "assets"
SIZES = [16, 24, 32, 48, 64, 128, 256]


def _bmp_entry(img: QImage) -> bytes:
    """ICO 里的单帧：BITMAPINFOHEADER + BGRA 像素 + AND 掩码。"""
    w, h = img.width(), img.height()
    src = img.convertToFormat(QImage.Format_ARGB32)

    header = struct.pack(
        "<IiiHHIIiiII",
        40, w, h * 2, 1, 32, 0, w * h * 4, 0, 0, 0, 0,
    )

    # Qt 的 ARGB32 在小端内存里就是 B,G,R,A，正好是 BMP 要的顺序
    pixels = bytearray()
    for y in range(h - 1, -1, -1):            # BMP 自下而上
        line = src.constScanLine(y)
        pixels += bytes(line[: w * 4])

    # AND 掩码：1 = 透明。32 位图里 Windows 用 alpha，但掩码仍要占位
    mask_row = ((w + 31) // 32) * 4
    mask = bytearray(mask_row * h)
    for y in range(h):
        row_src = h - 1 - y
        base = y * mask_row
        line = src.constScanLine(row_src)
        for x in range(w):
            if line[x * 4 + 3] == 0:
                mask[base + x // 8] |= 0x80 >> (x % 8)

    return header + bytes(pixels) + bytes(mask)


def write_ico(path: Path, sizes: list[int]) -> int:
    frames = [(s, _bmp_entry(paint_icon(s))) for s in sizes]

    offset = 6 + 16 * len(frames)
    directory = b""
    for size, data in frames:
        directory += struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,
            0 if size >= 256 else size,
            0, 0, 1, 32, len(data), offset,
        )
        offset += len(data)

    blob = struct.pack("<HHH", 0, 1, len(frames)) + directory + b"".join(d for _s, d in frames)
    path.write_bytes(blob)
    return len(blob)


def main() -> int:
    app = QGuiApplication(sys.argv)  # noqa: F841
    OUT.mkdir(parents=True, exist_ok=True)

    ico = OUT / "app.ico"
    size = write_ico(ico, SIZES)
    print(f"ok {ico} ({size} bytes, {len(SIZES)} frames)")

    paint_icon(256).save(str(OUT / "app.png"), "PNG")
    print(f"ok {OUT / 'app.png'}")

    # 小尺寸放大 4 倍拼一张，方便肉眼检查糊不糊
    strip = QImage(16 * 4 + 24 * 4 + 32 * 4 + 48 * 4 + 256 + 80, 288, QImage.Format_ARGB32)
    strip.fill(Qt.transparent)
    p = QPainter(strip)
    x = 10
    for s in (16, 24, 32, 48):
        p.drawImage(x, 14, paint_icon(s).scaled(s * 4, s * 4, Qt.KeepAspectRatio,
                                                Qt.FastTransformation))
        x += s * 4 + 12
    p.drawImage(x, 14, paint_icon(256))
    p.end()
    build_dir = ROOT / "build"
    build_dir.mkdir(exist_ok=True)
    strip.save(str(build_dir / "preview-strip.png"), "PNG")
    print("ok build/preview-strip.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

