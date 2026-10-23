# Đóng gói onedir hai process. Chạy từ thư mục gốc repo, Python 3.11+.
# Kết quả trong $Out (copy NGUYÊN thư mục này sang máy dùng):
#   SoiLuat\SoiLuat.exe                    Search App (tìm SoiLuatImporter ở ..\SoiLuatImporter\)
#   SoiLuatImporter\SoiLuatImporter.exe    nạp file, OCR, nhúng vector
#   SoiLuatImporter\tesseract\             -Tesseract: chỉ tesseract.exe + DLL nó cần, tessdata chỉ vie + osd (xoay trang)
#   models\embeddinggemma\                 -Model: mô hình cho chế độ Advance (thiếu thì Advance báo chưa cài)
# Không kèm kho dữ liệu: data\ tạo trống ở thư mục chạy lần đầu.
# Cần thêm trên máy build cho Advance: onnxruntime, tokenizers, numpy (không có thì bản đóng gói chỉ chạy Normal).
param(
    [string]$Out = "dist",
    [string]$Tesseract = "",   # thư mục cài Tesseract 5 (vd. "C:\Program Files\Tesseract-OCR")
    [string]$VieData = "",     # đường dẫn vie.traineddata (bản UB-Mannheim mặc định chỉ có eng/osd)
    [string]$Model = ""        # thư mục mô hình EmbeddingGemma (tokenizer.json, onnx\model_quantized.onnx[_data])
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) { python -m pip install -e ".[pack,word,ocr]" }
python -m PyInstaller --noconfirm --distpath $Out pack/SoiLuat.spec
python -m PyInstaller --noconfirm --distpath $Out pack/SoiLuatImporter.spec
$imp = Join-Path $Out "SoiLuatImporter"
if ($Tesseract) {
    $td = Join-Path $imp "tesseract\tessdata"
    New-Item -ItemType Directory -Force $td | Out-Null
    # DLL mà tesseract.exe cần (dò bằng objdump trên Tesseract 5.4 UB-Mannheim); bỏ công cụ huấn luyện, pango/cairo, eng
    $need = "tesseract.exe libtesseract-5.dll libleptonica-6.dll libarchive-13.dll libb2-1.dll libbz2-1.dll " +
        "libcrypto-3-x64.dll libdeflate.dll libexpat-1.dll libgcc_s_seh-1.dll libgif-7.dll libiconv-2.dll " +
        "libjbig-0.dll libjpeg-8.dll libLerc.dll liblz4.dll liblzma-5.dll libopenjp2-7.dll libpng16-16.dll " +
        "libsharpyuv-0.dll libstdc++-6.dll libtiff-6.dll libwebp-7.dll libwebpmux-3.dll libwinpthread-1.dll " +
        "libzstd.dll zlib1.dll"
    foreach ($f in $need.Split(" ")) { Copy-Item -Force (Join-Path $Tesseract $f) (Join-Path $imp "tesseract") }
    Copy-Item -Force (Join-Path $Tesseract "tessdata\osd.traineddata") $td
}
if ($VieData) {
    $td = Join-Path $imp "tesseract\tessdata"
    New-Item -ItemType Directory -Force $td | Out-Null
    Copy-Item -Force $VieData $td
}
if ($Model) {
    $md = Join-Path $Out "models\embeddinggemma"
    New-Item -ItemType Directory -Force (Join-Path $md "onnx") | Out-Null
    Copy-Item -Force (Join-Path $Model "tokenizer.json") $md
    Copy-Item -Force (Join-Path $Model "onnx\model_quantized.onnx*") (Join-Path $md "onnx")
}
if (-not (Test-Path (Join-Path $imp "SoiLuatImporter.exe"))) { throw "Thiếu SoiLuatImporter.exe" }
Write-Host "Xong: $Out\SoiLuat\SoiLuat.exe và $Out\SoiLuatImporter\SoiLuatImporter.exe"
Write-Host "Copy cả thư mục $Out. Search App chỉ nghe 127.0.0.1, cổng 8000 (bận thì 8001-8020)."
