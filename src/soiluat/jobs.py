"""Nạp file và nhúng vector chạy nền ngay trong Search App: một luồng, lần lượt từng file.

Search App không tự import OCR/trích chữ ở mức module: chúng chỉ nạp khi luồng nền chạy lần đầu,
nên chế độ Normal không tốn RAM cho phần nạp. Khi hàng đợi trống và đang ở chế độ Advance,
luồng này nhúng nốt các Điều chưa có vector, từng khối nhỏ để file mới nạp xen vào được ngay.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from soiluat import semantic
from soiluat.config import data_dir, db_path

# trùng importer.SUPPORTED_SUFFIXES (có test giữ hai tập khớp nhau)
SUFFIXES = frozenset(".docx .doc .rtf .pdf .txt .md .jpg .jpeg .png .tif .tiff .bmp .xlsx".split())
LABELS = {
    "cho": "Chờ", "dang_nap": "Đang nạp…", "du": "Xong", "can_ocr": "Cần OCR", "trung": "Trùng",
    "khong_doi": "Không đổi", "loi": "Lỗi", "bo_qua": "Bỏ qua",
}
BUSY = ("cho", "dang_nap")
KEEP = 300  # số dòng giữ lại trong danh sách (xoá dòng đã xong cũ nhất trước)
EMBED_CHUNK = 64


@dataclass
class Item:
    id: int
    name: str
    path: Path
    ocr: bool
    doan: bool
    state: str = "cho"
    note: str = ""


class Jobs:
    def __init__(self) -> None:
        self._cv = threading.Condition()
        self._items: list[Item] = []
        self._queue: deque[Item] = deque()
        self._seq = 0
        self._thread: threading.Thread | None = None
        self._current: Item | None = None
        self._todo: list[int] | None = None  # Điều chờ nhúng; None = chưa đếm / cần đếm lại
        self._stop = False
        self.embed = {"running": False, "done": 0, "total": 0}

    # ---- giao diện cho app ----

    def submit(self, paths: list[Path], *, ocr: bool, doan: bool) -> dict:
        """paths: file hoặc thư mục. Trả {"queued": n, "skipped": m} (m: file đuôi không hỗ trợ trong thư mục)."""
        from soiluat.importer import list_files  # nạp chậm: kéo theo trích chữ

        queued = skipped = 0
        with self._cv:
            for p in paths:
                if p.is_dir():
                    files, skip = list_files(p)
                    skipped += len(skip)
                else:
                    files = [p]
                for f in files:
                    self._seq += 1
                    it = Item(self._seq, f.name, f, ocr, doan)
                    if f.suffix.lower() not in SUFFIXES:
                        it.state, it.note = "bo_qua", f"đuôi {f.suffix or '(không có)'} không hỗ trợ"
                    else:
                        self._queue.append(it)
                        queued += 1
                    self._items.append(it)
            self._trim()
            self._todo = None
            self._ensure_thread()
            self._cv.notify_all()
        return {"queued": queued, "skipped": skipped}

    def wake(self) -> None:
        """Đổi chế độ tìm / vừa có việc mới: đếm lại Điều chưa nhúng."""
        with self._cv:
            self._todo = None
            self._ensure_thread()
            self._cv.notify_all()

    def clear(self) -> None:
        with self._cv:
            self._items = [i for i in self._items if i.state in BUSY]

    def stop(self) -> None:
        with self._cv:
            self._stop = True
            self._cv.notify_all()
        t = self._thread
        if t is not None and t is not threading.current_thread():
            t.join(timeout=10)

    def snapshot(self, conn=None) -> dict:
        with self._cv:
            items = list(self._items)
            cur = self._current
        pages = None
        if cur is not None and conn is not None:
            row = conn.execute(
                "SELECT pages_done, pages_total FROM import_jobs WHERE status = 'running' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row and row[1]:
                pages = [row[0] or 0, row[1]]
        out = []
        for i in items:
            d = {"id": i.id, "name": i.name, "state": i.state, "label": LABELS[i.state], "note": i.note,
                 "path": str(i.path)}
            if i is cur and pages:
                d["pages"] = pages
            out.append(d)
        n_busy = sum(1 for i in items if i.state in BUSY)
        return {
            "items": out,
            "total": len(items),
            "done": len(items) - n_busy,
            "active": n_busy > 0 or self.embed["running"],
            "embed": dict(self.embed),
        }

    # ---- luồng nền ----

    def _trim(self) -> None:
        extra = len(self._items) - KEEP
        if extra > 0:
            keep: list[Item] = []
            for i in self._items:
                if extra > 0 and i.state not in BUSY:
                    extra -= 1
                    continue
                keep.append(i)
            self._items = keep

    def _ensure_thread(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._stop = False
            self._thread = threading.Thread(target=self._run, name="soiluat-jobs", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        from soiluat.db import connect, init_schema
        from soiluat.importer import import_one

        conn = connect(db_path())  # kết nối riêng của luồng này
        init_schema(conn)
        root = data_dir()
        try:
            while not self._stop:
                with self._cv:
                    item = self._queue.popleft() if self._queue else None
                if item is not None:
                    self._import(conn, root, item, import_one)
                    continue
                if self._embed_chunk(conn):
                    continue
                with self._cv:
                    if not self._queue and not self._stop:
                        self._cv.wait(timeout=60)
        finally:
            conn.close()

    def _import(self, conn, root: Path, item: Item, import_one) -> None:
        item.state = "dang_nap"
        self._current = item
        try:
            item.state, item.note = import_one(conn, item.path, root, ocr=item.ocr, doan=item.doan)
        except Exception as e:  # noqa: BLE001 — một file hỏng không dừng cả hàng đợi
            item.state, item.note = "loi", f"{type(e).__name__}: {e}"
        finally:
            self._current = None
            self._todo = None  # có Điều mới: đếm lại phần cần nhúng

    def _embed_chunk(self, conn) -> bool:
        """Nhúng một khối Điều chưa có vector. True nếu đã làm gì đó (vòng lặp kiểm hàng đợi rồi làm tiếp)."""
        if semantic.get_mode(conn) != "advance" or not semantic.model_installed():
            self.embed = {"running": False, "done": 0, "total": 0}
            return False
        enc = semantic.encoder()
        if enc is None:
            self.embed = {"running": False, "done": 0, "total": 0}
            return False
        if self._todo is None:
            self._todo = semantic.missing_roots(conn)
            self.embed = {"running": bool(self._todo), "done": 0, "total": len(self._todo)}
        if not self._todo:
            self.embed["running"] = False
            return False
        part, self._todo = self._todo[:EMBED_CHUNK], self._todo[EMBED_CHUNK:]
        semantic.embed_roots(conn, enc, part)
        self.embed["done"] += len(part)
        if not self._todo:
            self.embed["running"] = False
        return True


JOBS = Jobs()
