@echo off
rem Автоустановка ClaudeSortBy в контекстное меню силами Claude Code.
rem Claude сам запустит install.ps1, проверит реестр и починит проблемы.
chcp 65001 >nul
cd /d "%~dp0"

where claude >nul 2>nul
if errorlevel 1 (
    if exist "%USERPROFILE%\.local\bin\claude.exe" (
        set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    ) else (
        echo Claude Code CLI не найден. Установи его: https://claude.com/claude-code
        pause
        exit /b 1
    )
)

echo Claude устанавливает ClaudeSortBy в контекстное меню, подожди...
claude -p "Установи ClaudeSortBy в контекстное меню Проводника. Прочитай файл FIX.md в текущей папке и выполни его шаги 1-3: запусти install.ps1, проверь ключи реестра, проверь наличие Claude CLI. Если что-то не так — почини по таблице из FIX.md. В конце одной строкой напиши итог." --allowedTools "Read" "Glob" "Grep" "Bash" "PowerShell"

echo.
echo Готово. В Windows 11 пункт "Отсортировать по…" находится в
echo "Показать дополнительные параметры" (Shift+F10 по папке или диску).
pause
