# Đóng gói onedir hai process. Chạy từ thư mục gốc repo, Python 3.11+.
# Kết quả: $Out\SoiLuat\SoiLuat.exe và $Out\SoiLuatImporter\SoiLuatImporter.exe (hai thư mục anh em:
# Search App tìm Importer ở ..\SoiLuatImporter\ — copy NGUYÊN thư mục $Out).
# Kèm OCR (tuỳ chọn): -Tesseract "C:\Program Files\Tesseract-OCR" chép vào $Out\SoiLuatImporter\tesseract\,
# -VieData đường dẫn vie.traineddata chép vào tesseract\tessdata\ (bản cài UB-Mannheim mặc định chỉ có eng/osd).
param(
    [string]$Out = "dist",
    [string]$Tesseract = "",
    [string]$VieData = ""
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
python -m pip install -e ".[pack,word]"
python -m PyInstaller --noconfirm --distpath $Out pack/SoiLuat.spec
python -m PyInstaller --noconfirm --distpath $Out pack/SoiLuatImporter.spec
$imp = Join-Path $Out "SoiLuatImporter"
if ($Tesseract) {
    Copy-Item -Recurse -Force $Tesseract (Join-Path $imp "tesseract")
}
if ($VieData) {
    $td = Join-Path $imp "tesseract\tessdata"
    New-Item -ItemType Directory -Force $td | Out-Null
    Copy-Item -Force $VieData $td
}
if (-not (Test-Path (Join-Path $imp "SoiLuatImporter.exe"))) { throw "Thiếu SoiLuatImporter.exe" }
Write-Host "Xong: $Out\SoiLuat\SoiLuat.exe và $Out\SoiLuatImporter\SoiLuatImporter.exe"
Write-Host "Copy cả thư mục $Out. Search App chỉ nghe 127.0.0.1, cổng 8000 (bận thì 8001-8020)."
