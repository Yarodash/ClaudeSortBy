@echo off
rem ASCII-only wrapper: all logic and Russian text live in install-with-claude.ps1
rem (cmd.exe cannot reliably parse UTF-8 Cyrillic in batch files).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-with-claude.ps1"
pause
