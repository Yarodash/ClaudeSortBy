# Устанавливает пункт "Отсортировать по..." в контекстное меню Проводника
# (папки, фон папки, диски) — только для текущего пользователя (HKCU),
# без прав администратора.
#
# Работает в двух раскладках:
#   1. Релиз: рядом лежит ClaudeSortBy.exe — регистрируем его.
#   2. Исходники: рядом лежит sortby.pyw — регистрируем pythonw.exe + скрипт.

$ErrorActionPreference = 'Stop'

$exe = Join-Path $PSScriptRoot "ClaudeSortBy.exe"
$script = Join-Path $PSScriptRoot "sortby.pyw"

if (Test-Path $exe) {
    $launcher = "`"$exe`""
    $icon = $exe
    Write-Host "Режим: релизный exe ($exe)"
} elseif (Test-Path $script) {
    $pythonw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
    if (-not $pythonw) {
        Write-Error "pythonw.exe не найден в PATH, а ClaudeSortBy.exe рядом нет. Установи Python 3.10+ (с галочкой 'Add to PATH') или скачай релиз с exe."
        exit 1
    }
    $launcher = "`"$pythonw`" `"$script`""
    $icon = $pythonw
    Write-Host "Режим: исходники ($pythonw + sortby.pyw)"
} else {
    Write-Error "Рядом со скриптом нет ни ClaudeSortBy.exe, ни sortby.pyw. Запускай install.ps1 из папки ClaudeSortBy."
    exit 1
}

# Предупреждаем, если не найден Claude Code CLI (без него утилита не работает).
$claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $claude) {
    $fallback = Join-Path $env:USERPROFILE ".local\bin\claude.exe"
    if (Test-Path $fallback) { $claude = $fallback }
}
if (-not $claude) {
    Write-Warning "Claude Code CLI не найден. Установи его: https://claude.com/claude-code — без него сортировка работать не будет."
}

$label = "Отсортировать по…"

# %1 — путь к объекту (папка/диск), %V — текущая папка (для фона).
# Хвост "\." добавлен намеренно: для корня диска (D:\) значение %1/%V
# заканчивается бэкслэшем, и "%1" превращается в "D:\" — нечётное число
# бэкслэшей перед закрывающей кавычкой ломает разбор argv (классический
# баг Windows-шелла). "%1\." — валидный эквивалентный путь, который эту
# проблему обходит.
$targets = @(
    @{ Key = "HKCU:\Software\Classes\Directory\shell\ClaudeSortBy";            Arg = '"%1\."' },
    @{ Key = "HKCU:\Software\Classes\Directory\Background\shell\ClaudeSortBy"; Arg = '"%V\."' },
    @{ Key = "HKCU:\Software\Classes\Drive\shell\ClaudeSortBy";                Arg = '"%1\."' }
)

foreach ($t in $targets) {
    New-Item -Path $t.Key -Force | Out-Null
    Set-ItemProperty -Path $t.Key -Name "(default)" -Value $label
    Set-ItemProperty -Path $t.Key -Name "Icon" -Value "`"$icon`""
    $cmdKey = Join-Path $t.Key "command"
    New-Item -Path $cmdKey -Force | Out-Null
    Set-ItemProperty -Path $cmdKey -Name "(default)" -Value "$launcher $($t.Arg)"
}

Write-Host "Готово. Пункт «$label» появится в контекстном меню (Windows 11: через «Показать дополнительные параметры» / Shift+F10)." -ForegroundColor Green
Write-Host "Команда: $launcher" -ForegroundColor DarkGray
