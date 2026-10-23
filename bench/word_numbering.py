"""Đối chiếu số thứ tự Word tự đánh (ListString) với extract_docx. Cần Microsoft Word.

python bench/word_numbering.py OUT_DIR

Dựng vài file Word có đánh số tự động (Điều/khoản/điểm, số La Mã, khởi đầu ≠ 1, đánh số lại,
danh sách nhiều cấp "1.1", gạch đầu dòng) rồi so từng đoạn: ListString của Word + chữ  ==  dòng extract_docx.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from word_tools import WD_DOCX, word  # noqa: E402

from soiluat.extract import extract_docx  # noqa: E402

ARABIC, UROMAN, LROMAN, ULETTER, LLETTER = 0, 1, 2, 3, 4
BULLET = 23


def build(w, path: Path, paras: list[tuple[str, int]], levels: list[tuple[str, int]], start_at=None, restart=None):
    """paras: (text, mức 0 = không đánh số). levels: (NumberFormat, NumberStyle) từ cấp 1."""
    d = w.Documents.Add()
    d.Range().Text = "\n".join(t for t, _ in paras)
    lt = d.ListTemplates.Add(True)
    for i, (f, style) in enumerate(levels, start=1):
        L = lt.ListLevels(i)
        L.NumberFormat = f
        L.NumberStyle = style
        L.StartAt = 1
        L.ResetOnHigher = i - 1 if i > 1 else 0
    if start_at:
        lt.ListLevels(1).StartAt = start_at
    first = True
    for p, (_, lvl) in zip(d.Paragraphs, paras):
        if not lvl:
            continue
        cont = not first and not (restart and p.Range.Text.strip() in restart)  # False: đánh số lại từ 1
        p.Range.ListFormat.ApplyListTemplate(lt, cont)
        p.Range.ListFormat.ListLevelNumber = lvl
        first = False
    expected = []
    for p in d.Paragraphs:
        txt = p.Range.Text.rstrip("\r\x07").strip()
        if not txt and not p.Range.ListFormat.ListString:
            continue
        ls = p.Range.ListFormat.ListString or ""
        bullet = bool(ls) and not any(c.isalnum() for c in ls)  # gạch đầu dòng: extract in "- "
        expected.append(("- " + txt) if bullet else (ls + " " + txt).strip())
    d.SaveAs2(str(path.resolve()), WD_DOCX)
    d.Close(False)
    return expected


def norm(s: str) -> str:
    return " ".join(s.split())


CASES = {
    "n1_dieu_khoan_diem": dict(
        paras=[("Phạm vi điều chỉnh", 1), ("Nghị định này quy định A.", 2), ("Đối tượng B.", 2), ("Trường hợp một;", 3),
               ("Trường hợp hai;", 3), ("Giải thích từ ngữ", 1), ("Khoản đầu của điều hai.", 2), ("Điểm a của điều hai.", 3)],
        levels=[("Điều %1.", ARABIC), ("%2.", ARABIC), ("%3)", LLETTER)],
    ),
    "n2_la_ma_bat_dau_5": dict(
        paras=[("Quy định chung", 1), ("Nội dung một.", 2), ("Quy định cụ thể", 1), ("Nội dung hai.", 2),
               ("Nội dung ba.", 2), ("Quy định khác", 1)],
        levels=[("Chương %1.", LROMAN), ("%2.", ARABIC)],
        start_at=5,
    ),
    "n3_legal_1_1": dict(
        paras=[("Mục tiêu", 1), ("Mục tiêu nhỏ A.", 2), ("Mục tiêu nhỏ B.", 2), ("Nhiệm vụ", 1), ("Nhiệm vụ nhỏ C.", 2),
               ("Chi tiết nhiệm vụ C.", 3)],
        levels=[("%1.", ARABIC), ("%1.%2", ARABIC), ("%1.%2.%3", ARABIC)],
    ),
    "n4_chuong_dieu_nhieu_cap": dict(
        paras=[("QUY ĐỊNH CHUNG", 1), ("Điều khoản thứ nhất", 2), ("Khoản a.", 3), ("QUY ĐỊNH CỤ THỂ", 1),
               ("Điều khoản thứ hai", 2), ("Khoản b.", 3), ("Khoản c.", 3)],
        levels=[("Chương %1", UROMAN), ("Điều %2.", ARABIC), ("%3)", LLETTER)],
    ),
    "n5_gach_dau_dong_xen_ke": dict(
        paras=[("Nguyên tắc", 1), ("Đoạn không đánh số xen giữa.", 0), ("Ý một", 2), ("Ý hai", 2), ("Nguyên tắc tiếp", 1),
               ("Ý ba", 2)],
        levels=[("%1.", ARABIC), ("•", BULLET)],
    ),
    "n6_danh_so_lai": dict(
        paras=[("Mục một", 1), ("Mục hai", 1), ("Mục ba", 1), ("Phụ lục một", 1), ("Phụ lục hai", 1)],
        levels=[("%1.", ARABIC)],
        restart={"Phụ lục một"},
    ),
}


def main(out: Path) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    out.mkdir(parents=True, exist_ok=True)
    w = word()
    bad = 0
    try:
        for name, c in CASES.items():
            f = out / f"{name}.docx"
            exp = build(w, f, c["paras"], c["levels"], start_at=c.get("start_at"), restart=c.get("restart"))
            got = [ln for pg in extract_docx(f) for ln in pg.text.split("\n") if ln.strip()]
            e, g = [norm(x) for x in exp], [norm(x) for x in got]
            ok = e == g
            bad += not ok
            print(("ĐÚNG " if ok else "LỆCH ") + name)
            if not ok:
                for i in range(max(len(e), len(g))):
                    a, b = (e[i] if i < len(e) else "-"), (g[i] if i < len(g) else "-")
                    print(("   = " if a == b else "   ! ") + f"Word: {a!r:45} extract: {b!r}")
    finally:
        w.Quit()
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
