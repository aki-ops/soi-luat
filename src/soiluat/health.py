"""Khám sức khoẻ kho — CSV một dòng/file."""

from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from pathlib import Path

from soiluat.extract import extract_file, sha256_file
from soiluat.parse import parse_structure, split_documents
from soiluat.sohieu import find_so_hieu

try:
    from soiluat.extract import SUPPORTED_SUFFIXES
except ImportError:  # A chưa thêm: dùng tập theo H1
    SUPPORTED_SUFFIXES = frozenset(
        ".docx .doc .rtf .pdf .txt .md .jpg .jpeg .png .tif .tiff .bmp .xlsx".split()
    )

FIELDS = [
    "file",
    "loai",
    "so_trang",
    "so_trang_co_chu",
    "trang_text_ok",
    "trang_suspect",
    "trang_image",
    "trang_mixed",
    "trang_table",
    "can_ocr",
    "font_cu",
    "nghi_nhieu_van_ban",
    "so_dieu",
    "C_phu",
    "C_lien_tuc",
    "C_khoan",
    "S",
    "tang",
    "ranh_gioi_thap",
    "so_hieu",
    "sha256",
    "bytes",
    "co_cum_phat_tien_tu",
    "so_van_ban_co_phat_tien_tu",
    "ty_le_xu_phat",
]


def classify_loai(path: Path, pages) -> str:
    suf = path.suffix.lower().lstrip(".")
    if suf != "pdf":
        return suf
    kinds = {p.kind for p in pages}
    if kinds <= {"image"}:
        return "pdf-scan"
    if "image" in kinds or "mixed" in kinds:
        return "pdf-tron"
    return "pdf-chu"


def has_phat_tien_tu(text: str) -> bool:
    nfc = unicodedata.normalize("NFC", text or "")
    return "phạt tiền từ" in nfc.lower()


def health_row(path: Path) -> dict:
    pages = extract_file(path)
    text = "\n\n".join(p.text for p in pages)
    parsed = parse_structure(text)
    dieu = sum(1 for u in parsed.units if u.level == "dieu")
    kinds = [p.kind for p in pages]
    return {
        "file": str(path),
        "loai": classify_loai(path, pages),
        "so_trang": len(pages),
        "so_trang_co_chu": sum(1 for p in pages if (p.text or "").strip()),
        "trang_text_ok": kinds.count("text_ok"),
        "trang_suspect": kinds.count("text_suspect"),
        "trang_image": kinds.count("image"),
        "trang_mixed": kinds.count("mixed"),
        "trang_table": kinds.count("table"),
        "can_ocr": sum(1 for p in pages if p.ocr_status == "cho_ocr"),
        "font_cu": int("\u00d0" in text),
        # tách được nhiều văn bản, hoặc số Điều bắt đầu lại (D5~2)
        "nghi_nhieu_van_ban": int(
            len(split_documents(pages)) > 1
            or any("~" in u.addr_part for u in parsed.units if u.level == "dieu")
        ),
        "so_dieu": dieu,
        "C_phu": f"{parsed.c_phu:.3f}",
        "C_lien_tuc": f"{parsed.c_lien_tuc:.3f}",
        "C_khoan": f"{parsed.c_khoan:.3f}",
        "S": f"{parsed.s:.3f}",
        "tang": parsed.tier,
        "ranh_gioi_thap": parsed.n_low_conf,
        "so_hieu": parsed.so_hieu or find_so_hieu(text) or "",
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "co_cum_phat_tien_tu": int(has_phat_tien_tu(text)),
        "so_van_ban_co_phat_tien_tu": "",
        "ty_le_xu_phat": "",
    }


def scan_dir(root: Path) -> list[dict]:
    rows = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name.startswith("~$"):
            continue
        if p.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        try:
            rows.append(health_row(p))
        except Exception as e:
            rows.append(
                {
                    **{k: "" for k in FIELDS},
                    "file": str(p),
                    "loai": "loi",
                    "so_hieu": f"{type(e).__name__}: {e}",
                }
            )
    return rows


def summarize_q2(rows: list[dict]) -> dict:
    files = [r for r in rows if r.get("loai") not in ("loi", "tong_ket")]
    n = len(files)
    n_phat = sum(int(r.get("co_cum_phat_tien_tu") or 0) for r in files)
    ty_le = n_phat / max(1, n)
    return {
        **{k: "" for k in FIELDS},
        "file": "_TONG",
        "loai": "tong_ket",
        "so_van_ban_co_phat_tien_tu": n_phat,
        "ty_le_xu_phat": f"{ty_le:.4f}",
        "so_trang": n,
    }


def write_csv(rows: list[dict], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    out = list(rows)
    if out:
        out.append(summarize_q2(out))
    with dest.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in out:
            w.writerow(r)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Khám sức khoẻ kho văn bản")
    p.add_argument("thu_muc")
    p.add_argument("-o", "--out", default="health.csv")
    args = p.parse_args(argv)
    rows = scan_dir(Path(args.thu_muc))
    write_csv(rows, Path(args.out))
    print(f"Ghi {len(rows)} dòng → {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
