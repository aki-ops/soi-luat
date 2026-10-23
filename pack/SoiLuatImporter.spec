# -*- mode: python ; coding: utf-8 -*-
"""SoiLuatImporter.exe — được phép kèm Tesseract/vie nếu có trên máy build."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent
datas = collect_data_files("soiluat")
# win32com: đổi .doc/.rtf qua Word COM (tuỳ chọn, cần pywin32 trên máy build)
hidden = collect_submodules("soiluat") + [
    "onnxruntime",
    "tokenizers",
    "numpy",
    "pytesseract",
    "PIL",
    "soiluat.convert",
    "win32com",
    "win32com.client",
    "pythoncom",
    "pywintypes",
]
# Tesseract không gói vào exe: đặt thư mục tesseract\ (có tesseract.exe và
# tesseract\tessdata\vie.traineddata) cạnh SoiLuatImporter.exe — ocr.py tự tìm khi sys.frozen.

a = Analysis(
    [str(ROOT / "pack" / "run_importer.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Advance (semantic.py) cần onnxruntime + tokenizers + numpy; bỏ phần onnxruntime không dùng khi chỉ chạy suy luận
    excludes=["cv2", "torch", "onnx", "llama_cpp", "sympy", "huggingface_hub",
              "onnxruntime.transformers", "onnxruntime.quantization", "onnxruntime.tools",
              # numpy kéo theo thư viện tuỳ chọn có trên máy build (+~400 MB) mà app không import
              "pandas", "scipy", "matplotlib", "pyarrow", "numba", "llvmlite", "botocore", "boto3",
              "IPython", "tkinter", "sklearn"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SoiLuatImporter",
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
    name="SoiLuatImporter",
)
