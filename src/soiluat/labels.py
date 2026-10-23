from __future__ import annotations

import re

from soiluat.fold import fold_search, search_accent
from soiluat.parse import ParsedUnit

FINE_RANGE_RE = re.compile(
    r"phạt tiền từ\s+([\d.]+)\s*((?:triệu\s+)?đồng)\s+đến\s+([\d.]+)\s*((?:triệu\s+)?đồng)",
    re.IGNORECASE,
)
FINE_TRIEU_ONE_RE = re.compile(
    r"phạt tiền\s+([\d.]+)\s*triệu đồng",
    re.IGNORECASE,
)
FINE_RATIO_RE = re.compile(r"gấp\s+\S+\s+lần|\d+\s*%|phần trăm", re.IGNORECASE)
HANH_VI_RE = re.compile(r"đối với hành vi\s+(.+)$", re.IGNORECASE | re.DOTALL)
PHAT_HANH_VI_RE = re.compile(
    r"phạt.{0,120}đối với (?:các |một trong các )?hành vi",
    re.IGNORECASE | re.DOTALL,
)
NEG_DUTY = ("không phải", "không bắt buộc", "không có nghĩa vụ")
PREAMBLE_FOLD = (
    "cong hoa xa hoi",
    "doc lap - tu do",
    "can cu luat",
    "can cu nghi dinh",
    "can cu thong tu",
)
THI_HANH_HINTS = ("dieu khoan thi hanh", "hieu luc thi hanh")
GENERAL_CHE_TAI_TITLES = (
    "hình thức xử phạt",
    "mức phạt tiền",
    "thẩm quyền xử phạt",
    "thời hiệu",
)
WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def _parse_vnd(s: str) -> int | None:
    digits = re.sub(r"[.\s]", "", s)
    if digits.isdigit():
        return int(digits)
    return None


def skip_label_zone(text: str, title: str = "") -> bool:
    blob = fold_search(f"{title} {text}")
    return any(p in blob for p in PREAMBLE_FOLD)


def _dieu_title_general(title: str) -> bool:
    t = search_accent(title)
    return any(t == g or t.startswith(g + " ") for g in GENERAL_CHE_TAI_TITLES)


def _first_word(text: str) -> str:
    m = WORD_RE.search(text or "")
    return (m.group(0) if m else "").lower()


def _has_duty_signal(low: str) -> bool:
    tmp = low
    for neg in NEG_DUTY:
        tmp = tmp.replace(neg, " ")
    return any(k in tmp for k in ("phải", "có trách nhiệm", "có nghĩa vụ"))


def _che_tai(
    unit: ParsedUnit,
    parent: ParsedUnit | None,
    dieu: ParsedUnit | None,
    from_table: bool,
) -> bool:
    if from_table:
        return False
    if dieu and _dieu_title_general(dieu.title):
        return False
    blob = f"{unit.title}\n{unit.text}"
    parent_blob = f"{parent.title}\n{parent.text}" if parent else ""
    if PHAT_HANH_VI_RE.search(blob):
        return True
    if unit.level == "diem" and parent and PHAT_HANH_VI_RE.search(parent_blob):
        return True
    khac_phuc = "bien phap khac phuc hau qua"
    in_khac = khac_phuc in fold_search(parent_blob if parent else "") or (
        dieu is not None and khac_phuc in fold_search(dieu.title)
    )
    if in_khac and _first_word(unit.text) == "buộc":
        return True
    return False


def labels_for_unit(
    unit: ParsedUnit,
    from_table: bool = False,
    parent: ParsedUnit | None = None,
    dieu: ParsedUnit | None = None,
) -> list[str]:
    if skip_label_zone(unit.text, unit.title):
        return []
    blob = f"{unit.title}\n{unit.text}"
    low = blob.lower()
    found: list[str] = []
    dieu_title = (dieu.title if dieu else "") or (unit.title if unit.level == "dieu" else "")
    if "giải thích từ ngữ" in search_accent(dieu_title):
        found.append("DINH_NGHIA")
    if _has_duty_signal(low):
        found.append("NGHIA_VU")
    if any(k in low for k in ("không được", "nghiêm cấm")) or re.search(
        r"(?<![a-z])cấm(?![a-z])", low
    ):
        found.append("CAM")
    if any(k in low for k in ("trong thời hạn", "chậm nhất", "trước ngày", "kể từ ngày")):
        found.append("THOI_HAN")
    if "phải đáp ứng" in low or "điều kiện" in low:
        found.append("DIEU_KIEN")
    if any(k in low for k in ("có quyền", "được quyền", "được phép")):
        found.append("QUYEN")
    if _che_tai(unit, parent, dieu, from_table):
        found.append("CHE_TAI")
    out: list[str] = []
    for x in found:
        if x not in out:
            out.append(x)
    return out


def extract_fines(text: str, from_table: bool) -> tuple[int | None, int | None]:
    if from_table:
        return None, None
    blob = text or ""
    clause = re.search(r"phạt tiền.{0,160}", blob, re.IGNORECASE)
    if clause and FINE_RATIO_RE.search(clause.group(0)):
        return None, None
    m = FINE_RANGE_RE.search(blob)
    if m:
        a = _parse_money(m.group(1), m.group(2))
        b = _parse_money(m.group(3), m.group(4))
        return a, b
    m2 = FINE_TRIEU_ONE_RE.search(blob)
    if m2:
        v = _parse_money(m2.group(1), "triệu đồng")
        return v, v
    return None, None


def _parse_money(num: str, unit: str) -> int | None:
    n = _parse_vnd(num)
    if n is None:
        return None
    if "triệu" in (unit or "").lower():
        return n * 1_000_000
    return n


def extract_hanh_vi(text: str) -> str | None:
    m = HANH_VI_RE.search(text or "")
    if not m:
        return None
    return m.group(1).strip().rstrip(".")


def is_thi_hanh(title: str, text: str = "") -> bool:
    return any(h in fold_search(f"{title} {text}") for h in THI_HANH_HINTS)
