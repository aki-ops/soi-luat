"""RAM và độ trễ của Search App thật (uvicorn, qua HTTP) trên kho Zalo, bật/tắt xếp lại theo nghĩa.

python bench/zalo/app_ram.py ZALO_DIR DATA_DIR [số câu]
Cần SOILUAT_MODEL_DIR (và onnxruntime/tokenizers/numpy trên PYTHONPATH) cho lượt "bat".
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import psutil

REPO = Path(__file__).resolve().parents[2]
PORT = 8765


def run(data: Path, qs: list[str], semantic_on: bool) -> dict:
    env = dict(os.environ, SOILUAT_DATA=str(data), PYTHONIOENCODING="utf-8", SOILUAT_ALLOW_TEST_HOST="1",
               SOILUAT_SEMANTIC="1" if semantic_on else "0",
               PYTHONPATH=os.pathsep.join([str(REPO / "src"), os.environ.get("PYTHONPATH", "")]))
    proc = subprocess.Popen([sys.executable, "-c",
                             f"import uvicorn; uvicorn.run('soiluat.app:app', host='127.0.0.1', port={PORT})"],
                            env=env, cwd=str(REPO), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p = psutil.Process(proc.pid)
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{PORT}", timeout=120) as cli:
            t0 = time.perf_counter()
            while True:
                try:
                    if cli.get("/").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                if time.perf_counter() - t0 > 60:
                    raise RuntimeError("Search App không lên sau 60 giây")
                time.sleep(0.1)
            time.sleep(2)
            idle = p.memory_info().rss
            lat, rss = [], []
            for q in qs:
                t = time.perf_counter()
                r = cli.get("/", params={"q": q}, headers={"HX-Request": "true"})
                lat.append((time.perf_counter() - t) * 1000)
                assert r.status_code == 200, r.status_code
                rss.append(p.memory_info().rss)
            mi = p.memory_info()
    finally:
        proc.terminate()
        proc.wait(10)
    rest = sorted(lat[1:])
    mb = lambda b: round(b / 2**20)  # noqa: E731
    return {"ram_ranh_mb": mb(idle), "ram_sau_cau_dau_mb": mb(rss[0]), "ram_cuoi_mb": mb(rss[-1]),
            "ram_dinh_mb": mb(getattr(mi, "peak_wset", max(rss))), "cau_dau_ms": round(lat[0]),
            "p50_ms": round(rest[len(rest) // 2]), "p95_ms": round(rest[int(len(rest) * .95)]), "so_cau": len(qs)}


def main(zalo: Path, data: Path, n: int) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    qs = {d["_id"]: d["text"] for d in map(json.loads, open(zalo / "queries.jsonl", encoding="utf-8"))}
    qids = sorted({json.loads(x)["query-id"] for x in open(zalo / "qrels_test.jsonl", encoding="utf-8")})
    sample = [qs[q] for q in qids[:: max(1, len(qids) // n)][:n]]
    for on in (False, True):
        print("bat" if on else "tat", run(data, sample, on), flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 60)
