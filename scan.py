"""Сканирование папки/диска для ClaudeSortBy.

Даёт плоский список элементов верхнего уровня с метаданными, достаточными
для того, чтобы Claude мог осмысленно их отсортировать, не читая содержимое
каждого файла. Для директорий считается количество вложенных элементов и
рекурсивный размер — но с бюджетом времени, чтобы сканирование `D:\` не
зависало навечно.
"""

import os
import time
import datetime

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".heic"}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv"}

MAX_TOP_ITEMS = 400          # не показываем Claude больше этого числа элементов
DIR_WALK_TIME_BUDGET = 0.35  # сек на подсчёт размера/кол-ва файлов ОДНОЙ папки
TOTAL_TIME_BUDGET = 12.0     # сек на весь скан


def human_size(n):
    if n is None:
        return "?"
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "Б" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} ПБ"


def _dir_stats(path, deadline):
    """Быстрый (ограниченный по времени) подсчёт файлов и суммарного размера."""
    count = 0
    total = 0
    truncated = False
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            if time.time() > deadline:
                truncated = True
                break
            for fn in filenames:
                count += 1
                try:
                    total += os.path.getsize(os.path.join(dirpath, fn))
                except OSError:
                    pass
    except OSError:
        pass
    return count, total, truncated


def _image_dims(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return None


def scan(root_path):
    """Возвращает (root_path, items, meta) где items — список dict."""
    start = time.time()
    total_deadline = start + TOTAL_TIME_BUDGET
    items = []
    truncated_listing = False

    with os.scandir(root_path) as it:
        entries = list(it)

    if len(entries) > MAX_TOP_ITEMS:
        # Сортируем по размеру/дате как эвристику перед обрезкой, чтобы не
        # потерять самое крупное/свежее.
        entries.sort(key=lambda e: _safe_mtime(e), reverse=True)
        entries = entries[:MAX_TOP_ITEMS]
        truncated_listing = True

    for entry in entries:
        try:
            is_dir = entry.is_dir(follow_symlinks=False)
        except OSError:
            continue

        try:
            stat = entry.stat(follow_symlinks=False)
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="minutes")
            ctime = datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(timespec="minutes")
        except OSError:
            mtime = ctime = None

        item = {
            "name": entry.name,
            "path": entry.path,
            "type": "dir" if is_dir else "file",
            "ext": "" if is_dir else os.path.splitext(entry.name)[1].lower(),
            "mtime": mtime,
            "ctime": ctime,
        }

        if is_dir:
            remaining = total_deadline - time.time()
            budget = min(DIR_WALK_TIME_BUDGET, max(0.05, remaining))
            deadline = time.time() + budget
            count, total, trunc = _dir_stats(entry.path, deadline)
            item["item_count"] = count
            item["size"] = total
            item["size_human"] = human_size(total) + ("+" if trunc else "")
        else:
            try:
                size = stat.st_size
            except Exception:
                size = None
            item["size"] = size
            item["size_human"] = human_size(size)
            if item["ext"] in IMAGE_EXT:
                dims = _image_dims(entry.path)
                if dims:
                    item["dims"] = f"{dims[0]}x{dims[1]}"

        items.append(item)

        if time.time() > total_deadline:
            truncated_listing = True
            break

    meta = {
        "truncated": truncated_listing,
        "scanned": len(items),
        "elapsed": round(time.time() - start, 2),
    }
    return root_path, items, meta


def _safe_mtime(entry):
    try:
        return entry.stat(follow_symlinks=False).st_mtime
    except OSError:
        return 0
