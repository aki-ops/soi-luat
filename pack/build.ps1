# Đóng gói onedir, MỘT app. Chạy từ thư mục gốc repo, Python 3.11+.
# Kết quả: $Out\SoiLuat\ (copy NGUYÊN thư mục này sang máy dùng)
#   SoiLuat.exe                 app duy nhất: tìm, nạp file, OCR, nhúng vector; "SoiLuat.exe import ..." là dòng lệnh
#   tesseract\                  -Tesseract: chỉ tesseract.exe + DLL nó cần, tessdata chỉ vie + osd (xoay trang)
#   models\aiteamvn-embedding\, models\aiteamvn-reranker\, models\LICENSE-Apache-2.0.txt   -Models: mô hình Advance (thiếu thì Advance báo chưa cài / tìm như Normal)
# Không kèm kho dữ liệu: data\ tạo trống ở thư mục chạy lần đầu.
# -Setup: thêm bước đóng MỘT file cài đặt SoiLuat-Setup.exe (Inno Setup 6, cài cho người dùng, không cần admin).
# Cần thêm trên máy build cho Advance: onnxruntime, tokenizers, numpy (không có thì bản đóng gói chỉ chạy Normal).
param(
    [string]$Out = "dist",
    [string]$Tesseract = "",   # thư mục cài Tesseract 5 (vd. "C:\Program Files\Tesseract-OCR")
    [string]$VieData = "",     # đường dẫn vie.traineddata (bản UB-Mannheim mặc định chỉ có eng/osd)
    [switch]$Setup,            # thêm: đóng thành MỘT file cài đặt $Out\SoiLuat-Setup.exe (cần Inno Setup 6)
    [string]$Models = ""       # thư mục do pack\export_models.py tạo (aiteamvn-embedding, aiteamvn-reranker, LICENSE-Apache-2.0.txt)
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) { python -m pip install -e ".[pack,word,ocr]" }
python -m PyInstaller --noconfirm --distpath $Out pack/SoiLuat.spec
$app = Join-Path $Out "SoiLuat"
if ($Tesseract) {
    $td = Join-Path $app "tesseract\tessdata"
    New-Item -ItemType Directory -Force $td | Out-Null
    # DLL mà tesseract.exe cần (dò bằng objdump trên Tesseract 5.4 UB-Mannheim); bỏ công cụ huấn luyện, pango/cairo, eng
    $need = "tesseract.exe libtesseract-5.dll libleptonica-6.dll libarchive-13.dll libb2-1.dll libbz2-1.dll " +
        "libcrypto-3-x64.dll libdeflate.dll libexpat-1.dll libgcc_s_seh-1.dll libgif-7.dll libiconv-2.dll " +
        "libjbig-0.dll libjpeg-8.dll libLerc.dll liblz4.dll liblzma-5.dll libopenjp2-7.dll libpng16-16.dll " +
        "libsharpyuv-0.dll libstdc++-6.dll libtiff-6.dll libwebp-7.dll libwebpmux-3.dll libwinpthread-1.dll " +
        "libzstd.dll zlib1.dll"
    foreach ($f in $need.Split(" ")) { Copy-Item -Force (Join-Path $Tesseract $f) (Join-Path $app "tesseract") }
    Copy-Item -Force (Join-Path $Tesseract "tessdata\osd.traineddata") $td
}
if ($VieData) {
    $td = Join-Path $app "tesseract\tessdata"
    New-Item -ItemType Directory -Force $td | Out-Null
    Copy-Item -Force $VieData $td
}
if ($Models) {
    foreach ($m in "aiteamvn-embedding", "aiteamvn-reranker") {
        $src = Join-Path $Models $m
        foreach ($f in "tokenizer.json", "onnx\model_int8.onnx", "NOTICE.md") {
            if (-not (Test-Path (Join-Path $src $f))) { throw "Thiếu $src\$f (chạy pack\export_models.py trước)" }
        }
        Copy-Item -Recurse -Force $src (Join-Path $app "models\$m")
    }
    Copy-Item -Force (Join-Path $Models "LICENSE-Apache-2.0.txt") (Join-Path $app "models")
}
if (-not (Test-Path (Join-Path $app "SoiLuat.exe"))) { throw "Thiếu SoiLuat.exe" }
Write-Host "Xong: $app\SoiLuat.exe"
Write-Host "Copy cả thư mục $app. App chỉ nghe 127.0.0.1, cổng 8000 (bận thì 8001-8020)."
if ($Setup) {
    $iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
              "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $iscc) { throw "Thiếu Inno Setup 6: winget install JRSoftware.InnoSetup" }
    & $iscc "/DSrc=$((Resolve-Path $app).Path)" "/DOut=$((Resolve-Path $Out).Path)" pack\SoiLuat.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup lỗi" }
    Write-Host "File cài đặt: $Out\SoiLuat-Setup.exe"
}
