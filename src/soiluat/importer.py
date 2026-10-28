"""Nạp văn bản vào kho (OCR, trích chữ, nhúng): dùng từ dòng lệnh; app gọi cùng hàm này qua soiluat.jobs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from soiluat import semantic
from soiluat.config import data_dir, db_path
from soiluat.db import connect, init_schema
from soiluat.ingest import finish_job, group_ids, ingest_path, start_job

try:
    from soiluat.extract import SUPPORTED_SUFFIXES
except ImportError:  # A chưa thêm: dùng tập theo H1
    SUPPORTED_SUFFIXES = frozenset(
        ".docx .doc .rtf .pdf .txt .md .jpg .jpeg .png .tif .tiff .bmp .xlsx".split()
    )


def check_ocr() -> dict:
    try:
        from soiluat.ocr import ocr_status

        return ocr_status()
    except Exception as e:  # noqa: BLE001 — H3: luôn in được một dòng JSON
        return {"ok": False, "tesseract_cmd": None, "tessdata": None, "langs": [],
                "message": f"Không kiểm tra được OCR: {e}"}


def list_files(target: Path) -> tuple[list[Path], list[Path]]:
    """(file nạp được, file bỏ qua vì đuôi không hỗ trợ). Bỏ file tạm Office '~$…'."""
    if not target.is_dir():
        return [target], []
    ok, skip = [], []
    for f in sorted(target.rglob("*")):
        if not f.is_file() or f.name.startswith("~$"):
            continue
        (ok if f.suffix.lower() in SUPPORTED_SUFFIXES else skip).append(f)
    return ok, skip


def _last_job(conn, after: int):
    return conn.execute(
        "SELECT status, error FROM import_jobs WHERE id > ? ORDER BY id DESC LIMIT 1",
        (after,),
    ).fetchone()


def import_one(conn, f: Path, root: Path, *, ocr: bool, doan: bool) -> tuple[str, str]:
    """(trạng thái, ghi chú): du | can_ocr | trung | khong_doi | loi."""
    before = conn.execute("SELECT COALESCE(MAX(id), 0) FROM import_jobs").fetchone()[0]
    try:
        doc_id = ingest_path(conn, f, root, run_ocr=ocr, force_doan=doan)
    except Exception as e:  # noqa: BLE001 — lỗi một file không dừng cả lượt
        job = _last_job(conn, before)
        msg = (job["error"] if job and job["error"] else None) or f"{type(e).__name__}: {e}"
        if job is None:  # lỗi trước khi kịp mở job (vd. không đọc được file)
            finish_job(conn, start_job(conn, str(f), ""), False, msg)
        return "loi", msg
    job = _last_job(conn, before)
    if job is None:
        return "khong_doi", ""
    if job["status"] == "skipped_duplicate":
        return "trung", ""
    if job["error"]:
        return "can_ocr", job["error"]
    row = conn.execute("SELECT file_path FROM documents WHERE id = ?", (doc_id,)).fetchone()
    n = len(group_ids(conn, row["file_path"])) if row else 1
    return "du", f"{n} văn bản" if n > 1 else ""


TEN = {"du": "đủ", "can_ocr": "cần OCR", "trung": "trùng", "khong_doi": "không đổi", "loi": "lỗi"}


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # console cp1252 không in được tiếng Việt
        except Exception:  # noqa: BLE001
            pass
    p = argparse.ArgumentParser(description="Nạp văn bản vào soiluat.db")
    p.add_argument("duong_dan", nargs="?", help="File hoặc thư mục")
    p.add_argument("--ocr", action="store_true", help="OCR trang ảnh (Tesseract)")
    p.add_argument("--doan", action="store_true", help="Ép chia theo đoạn (tầng 3)")
    p.add_argument("--check-ocr", action="store_true", help="In trạng thái OCR (JSON) rồi thoát")
    p.add_argument("--nhung", action="store_true",
                   help="Tính vector theo nghĩa cho các Điều chưa có (cần mô hình AITeamVN embedding; chậm, chạy một lần)")
    p.add_argument("--nen", action="store_true",
                   help="Với --nhung: chạy nền, 1 luồng, ưu tiên CPU thấp nhất (không làm chậm Word/Excel)")
    args = p.parse_args(argv)
    if args.check_ocr:
        print(json.dumps(check_ocr()))
        return 0
    if not args.duong_dan and not args.nhung:
        p.error("cần đường dẫn file hoặc thư mục")
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path())
    init_schema(conn)
    if not args.duong_dan:
        return _embed(conn, background=args.nen)
    files, skipped = list_files(Path(args.duong_dan))
    counts = dict.fromkeys(TEN, 0)
    for f in skipped:
        print(f"bỏ qua     | {f} | đuôi {f.suffix or '(không có)'} không hỗ trợ")
    for f in files:
        st, note = import_one(conn, f, root, ocr=args.ocr, doan=args.doan)
        counts[st] += 1
        print(f"{TEN[st]:<10} | {f}" + (f" | {note}" if note else ""), flush=True)
    print(
        f"Tổng {len(files)} file: đủ {counts['du']}, lỗi {counts['loi']}, trùng {counts['trung']}, "
        f"cần OCR {counts['can_ocr']}, không đổi {counts['khong_doi']}, bỏ qua {len(skipped)}"
    )
    rc = _embed(conn, background=args.nen) if args.nhung else 0
    if not args.nhung and (semantic.model_dir() / "tokenizer.json").exists():
        n = semantic.pending(conn)
        if n:
            cmd = "SoiLuat.exe import" if getattr(sys, "frozen", False) else "python -m soiluat.importer"
            print(f"Còn {n} Điều chưa có vector theo nghĩa (vẫn tìm được bằng BM25). "
                  f"Tính nền: {cmd} --nhung --nen")
    conn.close()
    return rc or (1 if counts["loi"] else 0)


def _embed(conn, background: bool = False) -> int:
    if background:
        semantic.THREADS = 1
        semantic.lower_priority()
    enc = semantic.encoder()
    if enc is None:
        print(f"Không nạp được mô hình theo nghĩa ở {semantic.model_dir()} (hoặc thiếu onnxruntime/tokenizers/numpy)")
        return 2
    ids = semantic.missing_roots(conn)
    print(f"Nhúng {len(ids)} Điều ({semantic.THREADS} luồng{', ưu tiên thấp' if background else ''})...", flush=True)

    def tick(done: int, total: int, sec: float) -> None:
        print(f"  {done}/{total} Điều, {sec:.0f} s, {done / max(sec, 1e-9):.1f} Điều/s", flush=True)

    sec = semantic.embed_roots(conn, enc, ids, progress=tick)
    print(f"Xong {len(ids)} Điều trong {sec:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
