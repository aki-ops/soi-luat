from soiluat.extract import classify_pdf_page, format_list_token, next_list_label


def test_classify_image_page_needs_ocr():
    kind, method, ocr = classify_pdf_page("ab", n_images=1, has_table=False)
    assert kind == "image"
    assert method == "pdf_text"
    assert ocr == "cho_ocr"


def test_classify_suspect_no_image():
    kind, _, ocr = classify_pdf_page("", n_images=0, has_table=False)
    assert kind == "text_suspect"
    assert ocr == "can_duyet"


def test_classify_text_ok():
    kind, _, ocr = classify_pdf_page("x" * 80, n_images=0, has_table=False)
    assert kind == "text_ok"
    assert ocr == "khong_can"


def test_classify_mixed():
    kind, _, ocr = classify_pdf_page("x" * 80, n_images=2, has_table=False)
    assert kind == "mixed"
    assert ocr == "khong_can"


def test_classify_table_keeps_non_ok_kind():
    kind, _, ocr = classify_pdf_page("ab", n_images=1, has_table=True)
    assert kind == "image"
    assert ocr == "cho_ocr"
    kind2, _, _ = classify_pdf_page("x" * 80, n_images=0, has_table=True)
    assert kind2 == "table"


def test_list_label_decimal_then_letter():
    counts: dict[tuple[int, int], int] = {}
    a = next_list_label(counts, 1, 0, "decimal", "%1.")
    b = next_list_label(counts, 1, 1, "lowerLetter", "%1)")
    c = next_list_label(counts, 1, 0, "decimal", "%1.")
    assert a == "1."
    assert b == "a)"
    assert c == "2."
    assert counts[(1, 1)] == 0


def test_format_list_token():
    assert format_list_token("decimal", 3) == "3"
    assert format_list_token("lowerLetter", 2) == "b"
    assert format_list_token("upperLetter", 1) == "A"
