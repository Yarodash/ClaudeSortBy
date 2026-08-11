# Сборка релизного ClaudeSortBy.exe (PyInstaller) и release-архива.
# Запуск: powershell -ExecutionPolicy Bypass -File build.ps1

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

python -m pip install --quiet pyinstaller pillow

python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name ClaudeSortBy `
    --add-data "metrics.json;." `
    sortby.pyw

if (-not (Test-Path "dist\ClaudeSortBy.exe")) {
    Write-Error "Сборка не удалась: dist\ClaudeSortBy.exe отсутствует."
    exit 1
}

# Собираем release-папку и zip.
$rel = "release\ClaudeSortBy"
Remove-Item -Recurse -Force "release" -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $rel | Out-Null

Copy-Item "dist\ClaudeSortBy.exe" $rel
Copy-Item "metrics.json", "install.ps1", "uninstall.ps1", "install-with-claude.cmd", "FIX.md", "README.md" $rel

$zip = "release\ClaudeSortBy-win64.zip"
Compress-Archive -Path "$rel\*" -DestinationPath $zip -Force

Write-Host "Готово: $zip" -ForegroundColor Green
