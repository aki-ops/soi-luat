"""Tạo hai model ONNX int8 cho Advance, chạy MỘT lần trên máy build (cần mạng + vài GB trống). Không vào gói app.

    python pack/export_models.py OUT_DIR [--only embedding|reranker] [--notice-only]

Kết quả (đúng bố cục mà pack/build.ps1 chép vào models\\ cạnh SoiLuat.exe):
    OUT_DIR\\aiteamvn-embedding\\{tokenizer.json, onnx\\model_int8.onnx[.data], NOTICE.md}
    OUT_DIR\\aiteamvn-reranker\\{tokenizer.json, onnx\\model_int8.onnx[.data], NOTICE.md}
    OUT_DIR\\LICENSE-Apache-2.0.txt   (tải từ apache.org nếu thiếu)

Cần trên máy build: torch, transformers, onnx, onnxruntime, huggingface_hub, numpy, tokenizers
    pip install torch transformers onnx onnxruntime huggingface_hub numpy tokenizers
(dùng bản torch chỉ CPU cho nhẹ). Bản ghim bên dưới là bản đã đo: đổi thì phải đo lại độ chính xác và độ trễ.
--notice-only: chỉ viết lại NOTICE.md/LICENSE trong thư mục đã có model (không tải, không xuất).
"""
import argparse
import hashlib
import shutil
import sys
import urllib.request
from pathlib import Path

MODELS = {
    "embedding": dict(
        dir="aiteamvn-embedding", repo="AITeamVN/Vietnamese_Embedding", rev="dea33aa1ab339f38d66ae0a40e6c40e0a9249568",
        license="Apache-2.0", base="BAAI/bge-m3 (MIT)",
        use="Mã hoá Điều và câu hỏi thành vector 1024 chiều (CLS, chuẩn hoá L2), 128 token."),
    "reranker": dict(
        dir="aiteamvn-reranker", repo="AITeamVN/Vietnamese_Reranker", rev="f536976248403314225d7fdfdbc87f0e9516a54e",
        license="Apache-2.0", base="BAAI/bge-reranker-v2-m3 (Apache-2.0)",
        tok_repo="BAAI/bge-reranker-v2-m3", tok_rev="953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
        use="Chấm điểm cặp (câu hỏi, Điều) để xếp lại top-5, tối đa 384 token."),
}
APACHE = "https://www.apache.org/licenses/LICENSE-2.0.txt"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def write_notice(out: Path, key: str) -> None:
    m = MODELS[key]
    d = out / m["dir"]
    files = [p for p in sorted(d.rglob("*")) if p.is_file() and p.name != "NOTICE.md"]
    tok = f"; tokenizer.json lấy từ {m['tok_repo']} @ {m['tok_rev']}" if "tok_repo" in m else ""
    lines = [
        f"# {m['dir']}", "",
        f"- Nguồn: https://huggingface.co/{m['repo']} @ {m['rev']}{tok}",
        f"- Giấy phép (theo thẻ model trên Hugging Face): {m['license']}; model nền: {m['base']}",
        "- Đã chuyển sang ONNX và lượng tử hoá int8 động (onnxruntime quantize_dynamic, QInt8) bằng pack/export_models.py;",
        "  trọng số đã đổi so với bản gốc.",
        f"- Dùng để: {m['use']}", "", "Văn bản giấy phép Apache-2.0: LICENSE-Apache-2.0.txt (cùng thư mục cha).", "",
        "| Tệp | Byte | SHA-256 |", "|---|---|---|",
    ] + [f"| {p.relative_to(d).as_posix()} | {p.stat().st_size} | {sha256(p)} |" for p in files]
    (d / "NOTICE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_license(out: Path) -> None:
    p = out / "LICENSE-Apache-2.0.txt"
    if not p.exists():
        with urllib.request.urlopen(APACHE, timeout=60) as r:
            p.write_bytes(r.read())


def quantize(src: Path, dst: Path) -> None:
    from onnxruntime.quantization import QuantType, quantize_dynamic
    quantize_dynamic(str(src), str(dst), weight_type=QuantType.QInt8, use_external_data_format=True)


def build_embedding(out: Path, tmp: Path) -> None:
    import numpy as np
    import onnxruntime as ort
    from huggingface_hub import hf_hub_download
    from tokenizers import Tokenizer
    m = MODELS["embedding"]; d = out / m["dir"]; (d / "onnx").mkdir(parents=True, exist_ok=True)
    for f in ("onnx/model.onnx", "onnx/model.onnx_data"):  # AITeamVN đã công bố bản ONNX fp32
        hf_hub_download(m["repo"], f, revision=m["rev"], local_dir=tmp)
    shutil.copy(hf_hub_download(m["repo"], "tokenizer.json", revision=m["rev"], local_dir=tmp), d / "tokenizer.json")
    quantize(tmp / "onnx" / "model.onnx", d / "onnx" / "model_int8.onnx")
    # kiểm: vector int8 gần vector fp32 (cosin)
    tok = Tokenizer.from_file(str(d / "tokenizer.json")); tok.enable_truncation(128)
    texts = ["Mức phạt khi vượt đèn đỏ đối với xe máy", "Điều 6. Xử phạt người điều khiển xe mô tô, xe gắn máy",
             "Điều 3. Giải thích từ ngữ"]
    enc = tok.encode_batch(texts); n = max(len(e.ids) for e in enc)
    ids = np.ones((len(texts), n), np.int64); mask = np.zeros_like(ids)
    for r, e in enumerate(enc):
        ids[r, :len(e.ids)] = e.ids; mask[r, :len(e.ids)] = 1
    out_v = []
    for p in (tmp / "onnx" / "model.onnx", d / "onnx" / "model_int8.onnx"):
        s = ort.InferenceSession(str(p), providers=["CPUExecutionProvider"])
        v = s.run(["sentence_embedding"], {"input_ids": ids, "attention_mask": mask})[0]
        out_v.append(v / np.linalg.norm(v, axis=1, keepdims=True))
    cos = (out_v[0] * out_v[1]).sum(1)
    print("embedding: cosin fp32 so với int8 =", cos.round(4).tolist(), flush=True)
    assert cos.min() > 0.9, "lượng tử hoá làm vector lệch quá nhiều"


def build_reranker(out: Path, tmp: Path) -> None:
    import numpy as np
    import onnxruntime as ort
    import torch
    from huggingface_hub import hf_hub_download
    from transformers import AutoModelForSequenceClassification
    m = MODELS["reranker"]; d = out / m["dir"]; (d / "onnx").mkdir(parents=True, exist_ok=True)
    src = tmp / "hf"
    for f in ("config.json", "model.safetensors"):
        hf_hub_download(m["repo"], f, revision=m["rev"], local_dir=src)
    shutil.copy(hf_hub_download(m["tok_repo"], "tokenizer.json", revision=m["tok_rev"], local_dir=tmp / "tok"),
                d / "tokenizer.json")
    model = AutoModelForSequenceClassification.from_pretrained(str(src), torch_dtype=torch.float32).eval()
    ids = torch.randint(5, 1000, (2, 16)); mask = torch.ones_like(ids)
    fp32 = tmp / "reranker_fp32.onnx"
    with torch.no_grad():
        torch.onnx.export(model, (ids, mask), str(fp32), input_names=["input_ids", "attention_mask"],
                          output_names=["logits"], opset_version=17, dynamo=False,
                          dynamic_axes={"input_ids": {0: "b", 1: "s"}, "attention_mask": {0: "b", 1: "s"}, "logits": {0: "b"}})
        ref = model(input_ids=ids, attention_mask=mask).logits.numpy()
    quantize(fp32, d / "onnx" / "model_int8.onnx")
    res = []
    for p in (fp32, d / "onnx" / "model_int8.onnx"):
        s = ort.InferenceSession(str(p), providers=["CPUExecutionProvider"])
        res.append(s.run(None, {"input_ids": ids.numpy(), "attention_mask": mask.numpy()})[0])
    print("reranker: logits PyTorch", ref.ravel().round(3).tolist(), "| fp32 ONNX", res[0].ravel().round(3).tolist(),
          "| int8", res[1].ravel().round(3).tolist(), flush=True)
    assert np.abs(res[0] - ref).max() < 1e-2, "ONNX fp32 lệch PyTorch"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out"); ap.add_argument("--only", choices=list(MODELS)); ap.add_argument("--notice-only", action="store_true")
    a = ap.parse_args()
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    keys = [a.only] if a.only else list(MODELS)
    if not a.notice_only:
        tmp = out / "_tmp"
        for k in keys:
            (build_embedding if k == "embedding" else build_reranker)(out, tmp / k)
        shutil.rmtree(tmp, ignore_errors=True)
    ensure_license(out)
    for k in keys:
        write_notice(out, k)
    print("xong:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
