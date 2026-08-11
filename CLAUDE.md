# CLAUDE.md

Контекст для Claude Code при работе в этом репозитории.

## Что это

ClaudeSortBy — пункт «Отсортировать по…» в контекстном меню Проводника Windows.
Пользователь вводит свободный запрос, `claude -p` (haiku) ранжирует содержимое
папки по именам/метаданным, результат — HTML-отчёт в браузере.

## Архитектура

- `sortby.pyw` — вход, tkinter-GUI. Работает и как скрипт, и внутри
  PyInstaller-exe (frozen: `BASE_DIR` = папка exe, `BUNDLE_DIR` = `_MEIPASS`).
- `scan.py` — листинг верхнего уровня с метаданными; бюджеты времени
  (`TOTAL_TIME_BUDGET`, `DIR_WALK_TIME_BUDGET`), обрезка до `MAX_TOP_ITEMS`.
- `engine.py` — вызовы Claude CLI. Ключевое: модель получает ТОЛЬКО имена и
  метаданные, все инструменты в `DISALLOWED_TOOLS` запрещены — не ослабляй это.
  Рекурсивный режим: Claude просит подпапки через `need_more`, Python сканирует
  сам, с защитой от выхода за пределы корня (`os.path.commonpath`).
  Поиск CLI: `CLAUDESORTBY_CLAUDE` → PATH → типовые пути. Все subprocess —
  с `CREATE_NO_WINDOW`.
- `report.py` — генерация HTML (сетка/дерево/лайтбокс) во временную папку.
- `thumbs.py` — превью: Pillow (опционален), ffmpeg из PATH (опционален),
  кэш в `%LOCALAPPDATA%\ClaudeSortBy\thumbcache`.
- `install.ps1` — HKCU-ключи `Directory\shell`, `Directory\Background\shell`,
  `Drive\shell`. Аргумент `"%1\."` — хвост `\.` намеренный (баг Windows с `D:\`
  и кавычкой), не удаляй.
- `FIX.md` — инструкция для Claude по установке/починке (её же использует
  `install-with-claude.cmd`). Если пользователь жалуется на установку — начни
  с FIX.md.

## Команды

- Запуск: `pythonw sortby.pyw <путь>` (или `python` для вывода ошибок в консоль).
- Сборка релиза: `powershell -ExecutionPolicy Bypass -File build.ps1` →
  `release/ClaudeSortBy-win64.zip`.
- Установка/удаление пункта меню: `install.ps1` / `uninstall.ps1`.

## Конвенции

- Язык UI, комментариев и строк — русский.
- Внешние зависимости держим опциональными (Pillow, ffmpeg) — без них всё
  работает, только беднее превью.
- Никаких абсолютных путей под конкретную машину — только PATH/env/поиск.
