# Удаляет пункт "Отсортировать по..." из контекстного меню Проводника.

$keys = @(
    "HKCU:\Software\Classes\Directory\shell\ClaudeSortBy",
    "HKCU:\Software\Classes\Directory\Background\shell\ClaudeSortBy",
    "HKCU:\Software\Classes\Drive\shell\ClaudeSortBy"
)

foreach ($k in $keys) {
    if (Test-Path $k) {
        Remove-Item -Path $k -Recurse -Force
        Write-Host "Удалено: $k" -ForegroundColor Yellow
    }
}

Write-Host "Готово." -ForegroundColor Green
