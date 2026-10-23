# -*- mode: python ; coding: utf-8 -*-
"""SoiLuat.exe — không kèm Tesseract. Chạy: pyinstaller pack/SoiLuat.spec"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent
datas = collect_data_files("soiluat")
# seed từ điển (db.init_schema nạp lúc mở kho); thêm tường minh phòng khi collect bỏ sót
seed = ROOT / "src" / "soiluat" / "synonyms_seed.csv"
if seed.exists() and not any(Path(s).name == seed.name for s, _ in datas):
    datas.append((str(seed), "soiluat"))
hidden = collect_submodules("soiluat") + [
    "uvicorn.logging",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.loops.auto",
    "multipart",
]

a = Analysis(
    [str(ROOT / "pack" / "run_search.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Search App không kèm OCR/ảnh/mô hình (hợp đồng 0.7)
    excludes=["pytesseract", "PIL", "cv2", "torch", "onnx", "onnxruntime", "llama_cpp"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SoiLuat",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SoiLuat",
)
