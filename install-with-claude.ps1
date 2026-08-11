# Автоустановка ClaudeSortBy в контекстное меню силами Claude Code.
# Claude сам запустит install.ps1, проверит реестр и починит проблемы.
# Запускается через install-with-claude.cmd (двойной клик).

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $claude) {
    $fallback = Join-Path $env:USERPROFILE ".local\bin\claude.exe"
    if (Test-Path $fallback) {
        $claude = $fallback
    } else {
        Write-Host "Claude Code CLI не найден. Установи его: https://claude.com/claude-code" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Claude устанавливает ClaudeSortBy в контекстное меню, подожди..." -ForegroundColor Cyan

& $claude -p ("Установи ClaudeSortBy в контекстное меню Проводника. " +
    "Прочитай файл FIX.md в текущей папке и выполни его шаги 1-3: запусти install.ps1, " +
    "проверь ключи реестра, проверь наличие Claude CLI. Если что-то не так — почини " +
    "по таблице из FIX.md. В конце одной строкой напиши итог.") `
    --allowedTools "Read" "Glob" "Grep" "Bash" "PowerShell"

Write-Host ""
Write-Host "Готово. В Windows 11 пункт «Отсортировать по…» находится в" -ForegroundColor Green
Write-Host "«Показать дополнительные параметры» (Shift+F10 по папке или диску)." -ForegroundColor Green
