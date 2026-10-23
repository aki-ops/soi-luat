"""Ảnh trang gốc cho Search App: PDF render bằng pypdfium2 → PNG (không cần Pillow), file ảnh trả nguyên."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

from soiluat.config import data_dir

VIEWABLE = {".pdf": "pdf", ".png": "png", ".jpg": "jpg", ".jpeg": "jpg"}
MAX_W = 1100  # px: đủ đọc chữ, PNG vài trăm KB


def source_file(file_path: str) -> Path | None:
    """documents.file_path (tương đối data hoặc tuyệt đối, có thể kèm #vbN) → file thật nếu còn."""
    p = Path(file_path.split("#vb", 1)[0])
    if not p.is_absolute():
        p = data_dir() / p
    return p if p.is_file() else None


def can_view(file_path: str | None) -> bool:
    return bool(file_path) and Path(file_path.split("#vb", 1)[0]).suffix.lower() in VIEWABLE


def _png(rgb: bytes, w: int, h: int, stride: int) -> bytes:
    rows = b"".join(b"\0" + rgb[y * stride : y * stride + w * 3] for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows, 6))
        + chunk(b"IEND", b"")
    )


def render_pdf_page(path: Path, page_no: int) -> bytes | None:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        if not 1 <= page_no <= len(pdf):
            return None
        page = pdf[page_no - 1]
        scale = min(2.5, MAX_W / max(page.get_width(), 1))
        bmp = page.render(scale=scale, rev_byteorder=True)  # RGB, nền trắng
        return _png(bytes(bmp.buffer), bmp.width, bmp.height, bmp.stride)
    finally:
        pdf.close()
