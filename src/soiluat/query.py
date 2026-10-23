from __future__ import annotations

import re

from soiluat.fold import fold_search, search_accent

QUESTION_PHRASES = (
    "như thế nào",
    "thế nào",
    "ra sao",
    "có được không",
    "bao nhiêu",
    "bao lâu",
    "khi nào",
    "là gì",
    "làm gì",
    "phải làm gì",
    "có phải",
    "có được",
    "có cần",
    "hay không",
    "quy định về việc",
)
# Khung hỏi bỏ ở bất kỳ đâu (dài trước). Từ đệm giữa câu giữ lại: cần cho tầng 1 (cụm đúng).
_FRAMES = (
    "xin cho hỏi",
    "cho tôi hỏi",
    "cho hỏi",
    "xin hỏi",
    "tôi muốn biết",
    "theo quy định thì",
    "theo quy định",
    "quy định về việc",
    "quy định về",
    "như thế nào",
    "thế nào",
    "ra sao",
    "cần làm gì",
    "phải làm gì",
    "làm gì",
    "là gì",
    "trong bao lâu",
    "bao lâu",
    "khi nào",
    "bao nhiêu",
    "những gì",
    "hay không",
    "được không",
    "có không",
)
# Chỉ bỏ ở cuối câu ("… không?"): giữa câu "không" là phủ định, phải giữ.
_TAIL = ("không", "chưa", "gì", "vậy", "ạ")
# "X có phải … không": X là chủ ngữ, bỏ khi phần sau còn chữ.
_SUBJECT_MARKERS = (
    "có bắt buộc phải",
    "có bắt buộc",
    "có phải",
    "có được",
    "có cần",
    "có nghĩa vụ",
    "có trách nhiệm",
)
_EDGE_FILLER = ("thì", "các", "những", "việc", "về", "trong", "của", "và", "hay", "nếu", "khi", "để", "là")
# L17: ý định hỏi mức phạt.
MUC_PHAT_PHRASES = (
    "bị phạt bao nhiêu",
    "bị xử phạt",
    "mức xử phạt",
    "mức phạt tiền",
    "mức phạt",
    "phạt bao nhiêu",
    "bị phạt",
    "xử phạt",
    "chế tài",
    "phạt tiền",
)

_W = tuple[str, bool, str, str]  # (gốc, có dấu, search_accent, fold)


def _w(word: str) -> _W:
    sa, fd = search_accent(word), fold_search(word)
    return (word, sa != fd, sa, fd)


def _p(phrase: str) -> list[tuple[str, str]]:
    return [(search_accent(x), fold_search(x)) for x in phrase.split()]


def _eq(w: _W, p: tuple[str, str]) -> bool:
    """Từ gõ có dấu so có dấu; gõ không dấu so bản bỏ dấu."""
    return w[2] == p[0] if w[1] else w[3] == p[1]


def _prep(phrases) -> list[list[tuple[str, str]]]:
    return sorted((_p(p) for p in phrases), key=lambda x: -len(x))


_P_QUESTION = _prep(QUESTION_PHRASES)
_P_FRAMES = _prep(_FRAMES)
_P_TAIL = _prep(_TAIL)
_P_SUBJECT = _prep(_SUBJECT_MARKERS)
_P_EDGE = _prep(_EDGE_FILLER)
_P_MUC_PHAT = _prep(MUC_PHAT_PHRASES)
# đứng ngay trước cụm phạt thì đó là chủ đề tra cứu, không phải câu hỏi mức phạt
_P_NOT_INTENT = _prep(
    ("thẩm quyền", "hình thức", "biện pháp", "thủ tục", "nguyên tắc", "thời hiệu", "thời hạn",
     "biên bản", "quyết định", "việc", "đối tượng", "hành vi")
)


def _find(words: list[_W], pw: list[tuple[str, str]]) -> int:
    n = len(pw)
    for i in range(len(words) - n + 1):
        if all(_eq(words[i + j], pw[j]) for j in range(n)):
            return i
    return -1


def _remove_all(words: list[_W], phrases) -> tuple[list[_W], bool]:
    hit = False
    for pw in phrases:
        i = _find(words, pw)
        while i >= 0:
            words = words[:i] + words[i + len(pw) :]
            hit = True
            i = _find(words, pw)
    return words, hit


def _strip_end(words: list[_W], phrases, *, head: bool) -> list[_W]:
    changed = True
    while words and changed:
        changed = False
        for pw in phrases:
            n = len(pw)
            if head and _find(words[:n], pw) == 0:
                words, changed = words[n:], True
            elif len(words) >= n and _find(words[-n:], pw) == 0:
                words, changed = words[:-n], True
    return words


def _clean(words: list[_W]) -> list[_W]:
    words, _ = _remove_all(words, _P_FRAMES)
    words = _strip_end(words, _P_TAIL, head=False)
    words = _strip_end(words, _P_EDGE, head=True)
    return _strip_end(words, _P_EDGE, head=False)


def _split(raw: str) -> list[_W]:
    return [_w(x) for x in re.sub(r"[?!.,;:]+", " ", raw or "").split()]


def _join(words: list[_W]) -> str:
    return " ".join(w[0] for w in words)


def classify_query(raw: str) -> str:
    from soiluat.sohieu import find_so_hieu, find_so_hieu_prefix

    s = (raw or "").strip()
    if not s:
        return "empty"
    if find_so_hieu(s) or find_so_hieu_prefix(s) or re.search(r"Điều\s+\d+", s, re.I):
        return "so_hieu"
    words = _split(s)
    if any(_find(words, p) >= 0 for p in _P_QUESTION) or s.endswith("?"):
        return "question"
    if len(words) <= 8:
        return "keyword"
    return "question"


def strip_question(raw: str) -> str:
    words = _split(raw)
    for m in _P_SUBJECT:
        i = _find(words, m)
        if i >= 0:
            rest = _clean(words[i + len(m) :])
            if rest:
                return _join(rest)
            words = words[:i] + words[i + len(m) :]
            break
    kept = _clean(words)
    return _join(kept or words)


def _remove_muc_phat(words: list[_W]) -> tuple[list[_W], bool]:
    """Như _remove_all nhưng bỏ qua "xử phạt" làm danh từ ("thẩm quyền xử phạt")."""
    hit = False
    for pw in _P_MUC_PHAT:
        start = 0
        while (i := _find(words[start:], pw)) >= 0:
            i += start
            if any(i >= len(g) and _find(words[i - len(g) : i], g) == 0 for g in _P_NOT_INTENT):
                start = i + len(pw)
                continue
            words = words[:i] + words[i + len(pw) :]
            hit, start = True, i
    return words, hit


def split_intent(raw: str) -> tuple[str, str]:
    """('muc_phat', truy vấn đã bỏ cụm mức phạt) hoặc ('', raw). Bỏ hết chữ thì giữ nguyên."""
    words = _split(raw)
    rest, hit = _remove_muc_phat(words)
    if not hit:
        return "", raw
    rest = _clean(rest)
    return "muc_phat", (_join(rest) if rest else raw)
