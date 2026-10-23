"""SoiLuat.exe — FastAPI, chỉ 127.0.0.1, không import OCR."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

from soiluat import pageimg, semantic
from soiluat.cards import assemble_cards, summarize
from soiluat.config import HOST, PORT, data_dir, db_path
from soiluat.db import backup_db, connect, init_schema
from soiluat.export_word import card_pages, export_cards, page_label
from soiluat.fold import display_addr
from soiluat.search import DIEU_CAP, apply_doc_filters, cascade_search

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
TEMPLATES.env.globals.update(page_label=page_label, card_pages=card_pages)
CSRF_TOKEN = secrets.token_urlsafe(32)
OCR_HELP = (
    "Cài Tesseract 5 (winget install UB-Mannheim.TesseractOCR) và chép vie.traineddata "
    r"vào %LOCALAPPDATA%\SoiLuat\tessdata (hoặc đặt SOILUAT_TESSDATA), rồi nạp lại với ô OCR."
)
_ocr_cache: dict | None = None

app = FastAPI(title="Soi Luật")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _test_bypass() -> bool:
    return os.environ.get("SOILUAT_ALLOW_TEST_HOST") == "1"


def _host_ok(host_header: str) -> bool:
    name = (host_header or "").split(":")[0].lower()
    allowed = {"127.0.0.1", "localhost"}
    if _test_bypass():
        allowed.add("testserver")
    return name in allowed


class HostGuard(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not _host_ok(request.headers.get("host") or ""):
            return PlainTextResponse("Bad Host", status_code=400)
        response = await call_next(request)
        if not _test_bypass():
            response.set_cookie(
                "soiluat_csrf",
                CSRF_TOKEN,
                samesite="strict",
                httponly=False,
            )
        return response


app.add_middleware(HostGuard)


def _check_csrf(request: Request, token: str = "") -> None:
    if _test_bypass():
        return
    cookie = request.cookies.get("soiluat_csrf")
    header = request.headers.get("x-csrf-token") or token
    if cookie != CSRF_TOKEN or header != CSRF_TOKEN:
        raise HTTPException(status_code=403, detail="CSRF")


def get_conn():
    conn = connect(db_path())
    init_schema(conn)
    return conn


def _tpl(request: Request, name: str, ctx: dict):
    ctx = {**ctx, "csrf_token": CSRF_TOKEN}
    return TEMPLATES.TemplateResponse(request, name, ctx)


def _card_dates(conn, cards) -> dict[int, dict]:
    """Ngày ban hành/hiệu lực theo unit đầu của thẻ (Card không mang ngày)."""
    ids = [c.unit_ids[0] for c in cards if c.unit_ids]
    if not ids:
        return {}
    q = ",".join("?" * len(ids))
    rows = conn.execute(
        "SELECT u.id, d.ngay_ban_hanh, d.ngay_hieu_luc FROM units u "
        f"JOIN documents d ON d.id = u.doc_id WHERE u.id IN ({q})",
        ids,
    ).fetchall()
    return {r["id"]: dict(r) for r in rows}


def _search_ctx(
    q: str,
    loai: str,
    co_quan: str,
    hieu_luc: str,
) -> dict:
    conn = get_conn()
    cards = []
    dates: dict[int, dict] = {}
    n = {"n1": 0, "n2": 0, "n3": 0, "n4": 0}
    hints: list[str] = []
    q2_note = ""
    empty_kho = False
    n_docs = conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"]
    empty_kho = int(n_docs or 0) == 0
    n_che = conn.execute(
        "SELECT COUNT(*) AS n FROM unit_labels WHERE label = 'CHE_TAI'"
    ).fetchone()["n"]
    if not empty_kho and int(n_che or 0) == 0:
        q2_note = (
            "Kho chưa có văn bản xử phạt — phần lớn thẻ là rủi ro chưa rõ chế tài (loại 3)."
        )
    if q.strip():
        # BM25 OR tự hạ trọng số từ phổ biến ("như thế nào", "được quy định"): không bỏ khung hỏi bằng danh sách
        result = cascade_search(conn, q)
        ids = apply_doc_filters(
            conn, result.ids, loai=loai, co_quan=co_quan, hieu_luc=hieu_luc
        )
        if result.note == "dieu" and len(ids) > DIEU_CAP:
            q2_note = (q2_note + " " if q2_note else "") + (
                f"Có {len(ids)} văn bản có Điều này, chỉ hiển thị {DIEU_CAP} — "
                "thêm số hiệu văn bản để thu hẹp."
            )
            ids = ids[:DIEU_CAP]
        idset = set(ids)
        cards = assemble_cards(
            conn,
            ids,
            synonym_note=result.note,
            fold_ids={i for i in result.fold_ids if i in idset},
            f2_ids={i for i in result.f2_ids if i in idset},
            tiers=result.tiers,
            intent=result.intent,
        )
        n = summarize(cards)
        conn.execute(
            "INSERT INTO query_log(query_raw, result_count, created_at) VALUES (?,?,?)",
            (q, len(cards), _now()),
        )
        conn.commit()
        if not cards:
            rows = conn.execute(
                "SELECT term FROM synonyms WHERE approved = 1 LIMIT 8"
            ).fetchall()
            hints = [r["term"] for r in rows]
        dates = _card_dates(conn, cards)
    conn.close()
    return {
        "q": q,
        "loai": loai,
        "co_quan": co_quan,
        "hieu_luc": hieu_luc,
        "cards": cards,
        "dates": dates,
        "n": n,
        "hints": hints,
        "q2_note": q2_note,
        "empty_kho": empty_kho,
    }


@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    q: str = Query(""),
    loai: str = Query(""),
    co_quan: str = Query(""),
    hieu_luc: str = Query(""),
):
    ctx = _search_ctx(q, loai, co_quan, hieu_luc)
    if request.headers.get("HX-Request"):
        return _tpl(request, "_results.html", ctx)
    return _tpl(request, "index.html", {**ctx, "mode": _mode_status()})


def _mode_status() -> dict:
    """Chế độ tìm + tình trạng mô hình; đếm Điều chưa nhúng chỉ khi advance (đỡ tốn ở normal)."""
    conn = get_conn()
    mode = semantic.get_mode(conn)
    installed = semantic.model_installed()
    pending = semantic.pending(conn) if mode == "advance" and installed else 0
    conn.close()
    return {"mode": mode, "installed": installed, "pending": pending}


@app.post("/settings/mode")
def set_search_mode(request: Request, mode: str = Form(...), q: str = Form(""), csrf_token: str = Form("")):
    _check_csrf(request, csrf_token)
    if mode not in semantic.MODES:
        raise HTTPException(status_code=400, detail="mode")
    conn = get_conn()
    semantic.set_mode(conn, mode)
    conn.close()
    return RedirectResponse("/?" + urlencode({"q": q}) if q else "/", status_code=303)


@app.get("/review", response_class=HTMLResponse)
def review(request: Request):
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT l.id, su.path AS spath, du.path AS dpath,
               su.raw_text AS stext, du.raw_text AS dtext,
               ds.so_hieu AS s_so, dd.so_hieu AS d_so
        FROM links l
        JOIN units su ON su.id = l.sanction_unit
        JOIN units du ON du.id = l.duty_unit
        JOIN documents ds ON ds.id = su.doc_id
        JOIN documents dd ON dd.id = du.doc_id
        WHERE l.confirmed = 0
        """
    ).fetchall()
    conn.close()
    items = []
    for r in rows:
        d = dict(r)
        d["saddr"] = display_addr(d.get("s_so"), d["spath"])
        d["daddr"] = display_addr(d.get("d_so"), d["dpath"])
        items.append(d)
    return _tpl(request, "review.html", {"rows": items})


@app.post("/links/{link_id}/confirm")
def confirm_link(
    request: Request, link_id: int, csrf_token: str = Form("")
):
    _check_csrf(request, csrf_token)
    conn = get_conn()
    conn.execute(
        "UPDATE links SET confirmed = 1, reviewed_at = ? WHERE id = ?",
        (_now(), link_id),
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/review", status_code=303)


@app.post("/links/{link_id}/reject")
def reject_link(
    request: Request, link_id: int, csrf_token: str = Form("")
):
    _check_csrf(request, csrf_token)
    conn = get_conn()
    conn.execute("DELETE FROM links WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/review", status_code=303)


@app.get("/review/pages", response_class=HTMLResponse)
def review_pages(request: Request):
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT p.id, p.page_no, p.kind, p.ocr_status, p.verification_status,
               p.raw_text, d.file_path, d.so_hieu
        FROM pages p
        JOIN documents d ON d.id = p.doc_id
        WHERE p.extraction_method LIKE '%ocr%'
           OR p.ocr_status IN ('cho_ocr','ocr_xong','can_duyet')
        ORDER BY p.id
        """
    ).fetchall()
    conn.close()
    return _tpl(request, "review_pages.html", {"rows": [dict(r) for r in rows]})


@app.get("/review/hints", response_class=HTMLResponse)
def review_hints(request: Request):
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT h.id, h.kind, h.target_so_hieu, h.snippet, h.confirmed,
               d.file_path, d.so_hieu
        FROM effect_hints h
        JOIN documents d ON d.id = h.source_doc_id
        WHERE h.confirmed = 0
        ORDER BY h.id
        """
    ).fetchall()
    conn.close()
    return _tpl(request, "review_hints.html", {"rows": [dict(r) for r in rows]})


@app.post("/hints/{hint_id}/confirm")
def confirm_hint(request: Request, hint_id: int, csrf_token: str = Form("")):
    _check_csrf(request, csrf_token)
    conn = get_conn()
    conn.execute(
        "UPDATE effect_hints SET confirmed = 1, reviewed_at = ? WHERE id = ?",
        (_now(), hint_id),
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/review/hints", status_code=303)


@app.post("/hints/{hint_id}/reject")
def reject_hint(request: Request, hint_id: int, csrf_token: str = Form("")):
    _check_csrf(request, csrf_token)
    conn = get_conn()
    conn.execute("DELETE FROM effect_hints WHERE id = ?", (hint_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/review/hints", status_code=303)


@app.get("/review/subjects", response_class=HTMLResponse)
def review_subjects(request: Request):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, phrase, kind, approved FROM subject_rules ORDER BY kind, id"
    ).fetchall()
    conn.close()
    return _tpl(request, "review_subjects.html", {"rows": [dict(r) for r in rows]})


@app.post("/subjects")
def add_subject(
    request: Request,
    phrase: str = Form(...),
    kind: str = Form(...),
    csrf_token: str = Form(""),
):
    _check_csrf(request, csrf_token)
    if kind not in ("uu_tien", "ha_uu_tien"):
        kind = "uu_tien"
    phrase = phrase.strip()
    if phrase:
        from soiluat.fold import fold_search

        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO subject_rules(phrase, phrase_fold, kind, approved) "
                "VALUES (?, ?, ?, 1)",
                (phrase, fold_search(phrase), kind),
            )
            conn.commit()
        except Exception:
            conn.rollback()
        conn.close()
    return RedirectResponse("/review/subjects", status_code=303)


@app.post("/subjects/{rule_id}/delete")
def delete_subject(request: Request, rule_id: int, csrf_token: str = Form("")):
    _check_csrf(request, csrf_token)
    conn = get_conn()
    conn.execute("DELETE FROM subject_rules WHERE id = ?", (rule_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/review/subjects", status_code=303)


@app.get("/review/synonyms", response_class=HTMLResponse)
def review_synonyms(request: Request):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, term, alt, kind, approved, reviewed_at FROM synonyms "
        "ORDER BY approved, term, alt"
    ).fetchall()
    kinds = [r["kind"] for r in conn.execute("SELECT DISTINCT kind FROM synonyms")]
    conn.close()
    return _tpl(
        request,
        "review_synonyms.html",
        {"rows": [dict(r) for r in rows], "kinds": kinds},
    )


@app.post("/synonyms")
def add_synonym(
    request: Request,
    term: str = Form(...),
    alt: str = Form(...),
    kind: str = Form(""),
    csrf_token: str = Form(""),
):
    _check_csrf(request, csrf_token)
    term, alt = term.strip(), alt.strip()
    if term and alt and term != alt:
        conn = get_conn()
        # người duyệt tự thêm → coi như đã duyệt
        conn.execute(
            "INSERT OR IGNORE INTO synonyms(term, alt, kind, approved, reviewed_at) "
            "VALUES (?, ?, ?, 1, ?)",
            (term, alt, kind.strip() or "dong_nghia", _now()),
        )
        conn.commit()
        conn.close()
    return RedirectResponse("/review/synonyms", status_code=303)


@app.post("/synonyms/{syn_id}/approve")
def approve_synonym(
    request: Request,
    syn_id: int,
    approved: int = Form(1),
    csrf_token: str = Form(""),
):
    _check_csrf(request, csrf_token)
    conn = get_conn()
    conn.execute(
        "UPDATE synonyms SET approved = ?, reviewed_at = ? WHERE id = ?",
        (1 if approved else 0, _now(), syn_id),
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/review/synonyms", status_code=303)


@app.post("/synonyms/{syn_id}/delete")
def delete_synonym(request: Request, syn_id: int, csrf_token: str = Form("")):
    _check_csrf(request, csrf_token)
    conn = get_conn()
    conn.execute("DELETE FROM synonyms WHERE id = ?", (syn_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/review/synonyms", status_code=303)


@app.get("/review/docs", response_class=HTMLResponse)
def review_docs(request: Request):
    conn = get_conn()
    docs = conn.execute(
        """
        SELECT id, file_path, so_hieu, loai, co_quan, hieu_luc, struct_score,
               extraction_method, ngay_ban_hanh, ngay_hieu_luc
        FROM documents
        ORDER BY IFNULL(struct_score, 1) ASC
        """
    ).fetchall()
    items = []
    for d in docs:
        units = conn.execute(
            "SELECT id, path, level, title, boundary_confidence, raw_text "
            "FROM units WHERE doc_id = ? ORDER BY id LIMIT 40",
            (d["id"],),
        ).fetchall()
        items.append({"doc": dict(d), "units": [dict(u) for u in units]})
    conn.close()
    return _tpl(request, "review_docs.html", {"items": items})


@app.post("/docs/{doc_id}/hieu-luc")
def set_hieu_luc(
    request: Request,
    doc_id: int,
    hieu_luc: str = Form(...),
    csrf_token: str = Form(""),
):
    _check_csrf(request, csrf_token)
    if hieu_luc not in ("con", "het", "chua_ro"):
        hieu_luc = "chua_ro"
    conn = get_conn()
    conn.execute(
        "UPDATE documents SET hieu_luc = ? WHERE id = ?",
        (hieu_luc, doc_id),
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/review/docs", status_code=303)


@app.post("/docs/{doc_id}/so-hieu")
def set_so_hieu(
    request: Request,
    doc_id: int,
    so_hieu: str = Form(""),
    csrf_token: str = Form(""),
):
    _check_csrf(request, csrf_token)
    from soiluat.sohieu import so_hieu_search_key

    so = so_hieu.strip()
    conn = get_conn()
    conn.execute(
        "UPDATE documents SET so_hieu = ?, so_hieu_search = ? WHERE id = ?",
        (so or None, so_hieu_search_key(so) if so else "", doc_id),
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/review/docs", status_code=303)


@app.get("/unit/{unit_id}", response_class=HTMLResponse)
def unit_view(request: Request, unit_id: int):
    conn = get_conn()
    u = conn.execute("SELECT * FROM units WHERE id = ?", (unit_id,)).fetchone()
    if u is None:
        conn.close()
        return HTMLResponse("Không tìm thấy đơn vị.", status_code=404)
    doc = conn.execute(
        "SELECT * FROM documents WHERE id = ?", (u["doc_id"],)
    ).fetchone()
    pages = conn.execute(
        "SELECT page_no, kind, ocr_status, verification_status FROM pages "
        "WHERE doc_id = ? AND page_no BETWEEN ? AND ? ORDER BY page_no",
        (u["doc_id"], u["page_from"] or 1, u["page_to"] or u["page_from"] or 1),
    ).fetchall()
    notes = _unit_notes(conn, u)
    conn.execute(
        "UPDATE query_log SET selected_unit = ?, selected_doc_id = ?, selected_path = ? "
        "WHERE id = (SELECT id FROM query_log ORDER BY id DESC LIMIT 1)",
        (unit_id, u["doc_id"], u["path"]),
    )
    conn.commit()
    conn.close()
    ud = dict(u)
    dd = dict(doc) if doc else {}
    ud["addr"] = display_addr(dd.get("so_hieu"), ud.get("path") or "")
    for nt in notes:
        nt["addr"] = display_addr(None, nt["path"])
    return _tpl(
        request,
        "unit.html",
        {
            "u": ud,
            "doc": dd,
            "pages": [dict(p) for p in pages],
            "notes": notes,
            "can_view": pageimg.can_view(dd.get("file_path")),
        },
    )


@app.get("/page/{doc_id}/{page_no}")
def page_image(doc_id: int, page_no: int):
    """Ảnh trang gốc để đối chiếu thẻ (đặc biệt chữ OCR). Chỉ phục vụ file đã nạp, theo doc_id."""
    conn = get_conn()
    row = conn.execute("SELECT file_path FROM documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()
    src = pageimg.source_file(row["file_path"]) if row else None
    kind = pageimg.VIEWABLE.get(src.suffix.lower()) if src else None
    if kind is None:
        return HTMLResponse("Không có ảnh trang gốc (file gốc không còn hoặc không phải PDF/ảnh).", status_code=404)
    hdr = {"Cache-Control": "private, max-age=3600"}
    if kind == "pdf":
        png = pageimg.render_pdf_page(src, page_no)
        if png is None:
            return HTMLResponse("Không có trang này.", status_code=404)
        return Response(png, media_type="image/png", headers=hdr)
    return FileResponse(src, media_type="image/png" if kind == "png" else "image/jpeg", headers=hdr)


def _unit_notes(conn, u) -> list[dict]:
    """Đơn vị ghi_chu treo dưới Điều chứa unit (hoặc dưới chính unit nếu không có Điều)."""
    root = u
    cur = u
    while cur is not None and cur["level"] != "dieu" and cur["parent_id"]:
        cur = conn.execute("SELECT * FROM units WHERE id = ?", (cur["parent_id"],)).fetchone()
    if cur is not None and cur["level"] == "dieu":
        root = cur
    rows = conn.execute(
        """
        WITH RECURSIVE sub(id) AS (
          SELECT ? UNION SELECT x.id FROM units x JOIN sub ON x.parent_id = sub.id
        )
        SELECT id, path, page_from, page_to, reviewed_text, raw_text FROM units
        WHERE level = 'ghi_chu' AND parent_id IN (SELECT id FROM sub) ORDER BY id
        """,
        (root["id"],),
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/missed", response_class=HTMLResponse)
def missed(request: Request):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, query_raw, result_count, created_at FROM query_log "
        "WHERE result_count = 0 ORDER BY id DESC LIMIT 100"
    ).fetchall()
    conn.close()
    return _tpl(request, "missed.html", {"rows": [dict(r) for r in rows]})


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def importer_cmd(args: list[str]) -> list[str]:
    """Lệnh gọi Importer: mã nguồn → python -m; bản đóng gói → SoiLuatImporter.exe."""
    if not _frozen():
        return [sys.executable, "-m", "soiluat.importer", *args]
    here = Path(sys.executable).resolve().parent
    for exe in (
        here / "SoiLuatImporter.exe",
        here.parent / "SoiLuatImporter" / "SoiLuatImporter.exe",
    ):
        if exe.is_file():
            return [str(exe), *args]
    raise FileNotFoundError(
        "Không tìm thấy SoiLuatImporter.exe (cạnh SoiLuat.exe hoặc ở ..\\SoiLuatImporter\\)."
    )


def _child_kw() -> dict:
    env = {**os.environ, "SOILUAT_DATA": str(data_dir()), "PYTHONIOENCODING": "utf-8"}
    # bản đóng gói: Importer là exe console, không bật cửa sổ đen
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if _frozen() else 0
    return {"env": env, "creationflags": flags}


def ocr_status(refresh: bool = False) -> dict:
    """Trạng thái OCR qua `importer --check-ocr` (không import OCR vào Search App)."""
    global _ocr_cache
    if _ocr_cache is not None and not refresh:
        return _ocr_cache
    try:
        r = subprocess.run(
            importer_cmd(["--check-ocr"]),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            **_child_kw(),
        )
        lines = [x for x in (r.stdout or "").splitlines() if x.strip().startswith("{")]
        st = json.loads(lines[-1]) if r.returncode == 0 and lines else None
        if not isinstance(st, dict) or "ok" not in st:
            raise ValueError(f"mã thoát {r.returncode}")
    except Exception as e:  # noqa: BLE001 — lỗi gì cũng chỉ là "không kiểm tra được"
        st = {"ok": None, "message": f"Không kiểm tra được OCR ({type(e).__name__}: {e})."}
    _ocr_cache = st
    return st


def _jobs_page(request: Request, err: str = "", status_code: int = 200, refresh: bool = False):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, status, phase, file_path, sha256, pages_done, pages_total, "
        "error, started_at, finished_at, existing_file_path "
        "FROM import_jobs ORDER BY id DESC LIMIT 50"
    ).fetchall()
    conn.close()
    resp = _tpl(
        request,
        "jobs.html",
        {
            "rows": [dict(r) for r in rows],
            "ocr": ocr_status(refresh),
            "ocr_help": OCR_HELP,
            "err": err,
        },
    )
    resp.status_code = status_code
    return resp


@app.get("/jobs", response_class=HTMLResponse)
def jobs(request: Request, ocr: str = Query("")):
    return _jobs_page(request, refresh=(ocr == "lai"))


@app.post("/export")
def export(
    request: Request,
    uid: list[int] = Form(default=[]),
    csrf_token: str = Form(""),
):
    _check_csrf(request, csrf_token)
    conn = get_conn()
    dest = data_dir() / "export.docx"
    cards = assemble_cards(conn, uid)
    export_cards(cards, dest)
    conn.close()
    return FileResponse(
        dest,
        filename="soiluat-baocao.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.post("/backup")
def backup(request: Request, csrf_token: str = Form("")):
    _check_csrf(request, csrf_token)
    dest = data_dir() / "backup" / "soiluat.db"
    backup_db(db_path(), dest)
    return {"ok": True, "path": str(dest)}


@app.post("/import-spawn")
def import_spawn(
    request: Request,
    path: str = Form(...),
    csrf_token: str = Form(""),
    doan: str = Form(""),
    ocr: str = Form(""),
):
    _check_csrf(request, csrf_token)
    src = Path(path.strip().strip('"'))
    if not path.strip() or not src.exists():
        return _jobs_page(request, f"Không thấy file/thư mục: {path}", 400)
    args = [str(src)]
    if ocr:
        args.append("--ocr")
    if doan:
        args.append("--doan")
    try:
        cmd = importer_cmd(args)
    except FileNotFoundError as e:
        return _jobs_page(request, str(e), 500)
    data_dir().mkdir(parents=True, exist_ok=True)
    # process con không có console khi đóng gói → ghi ra log để còn xem lỗi
    with open(data_dir() / "importer.log", "ab") as log:
        subprocess.Popen(
            cmd,
            cwd=str(Path.cwd()),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            **_child_kw(),
        )
    return RedirectResponse("/jobs", status_code=303)


def _port_busy(port: int) -> bool:
    # thử kết nối trước: app khác nghe [::]:port vẫn trả lời 127.0.0.1 dù bind được
    try:
        with socket.create_connection((HOST, port), timeout=0.3):
            return True
    except OSError:
        pass
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((HOST, port))
        return False
    except OSError:
        return True
    finally:
        s.close()


def pick_port(start: int, tries: int = 20) -> int:
    for port in range(start, start + tries + 1):
        if not _port_busy(port):
            return port
    raise SystemExit(f"Cổng {start}–{start + tries} đều bận. Đặt SOILUAT_PORT hoặc --port khác.")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="soiluat", description="Soi Luật — tra cứu, chỉ 127.0.0.1")
    ap.add_argument(
        "--port",
        type=int,
        default=os.environ.get("SOILUAT_PORT") or str(PORT),
        help="cổng mong muốn (mặc định 8000 hoặc env SOILUAT_PORT); bận thì thử 20 cổng kế tiếp",
    )
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # chuyển hướng ra file: cp1252 không in được tiếng Việt
        except Exception:  # noqa: BLE001
            pass
    data_dir().mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    conn.close()
    port = pick_port(args.port)
    url = f"http://{HOST}:{port}/"
    print(f"Soi Luật đang chạy: {url}", flush=True)
    if os.environ.get("SOILUAT_NO_BROWSER") != "1":
        threading.Timer(1.5, webbrowser.open, (url,)).start()
    uvicorn.run("soiluat.app:app", host=HOST, port=port, reload=False)


if __name__ == "__main__":
    main()
