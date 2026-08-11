"""Генерация превью (data URI) для отчёта ClaudeSortBy, с кэшем на диске."""

import os
import io
import base64
import hashlib
import shutil
import subprocess
import tempfile

CACHE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "ClaudeSortBy", "thumbcache")
os.makedirs(CACHE_DIR, exist_ok=True)

# ffmpeg опционален: без него видео получают эмодзи-иконку вместо кадра.
FFMPEG_EXE = shutil.which("ffmpeg")

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".heic"}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv"}

THUMB_SIZE = 320

ICON_BY_EXT = {
    ".pdf": "📕", ".doc": "📄", ".docx": "📄", ".txt": "📝", ".md": "📝",
    ".xls": "📊", ".xlsx": "📊", ".csv": "📊", ".ppt": "📽️", ".pptx": "📽️",
    ".zip": "🗜️", ".rar": "🗜️", ".7z": "🗜️",
    ".exe": "⚙️", ".msi": "⚙️",
    ".mp3": "🎵", ".wav": "🎵", ".flac": "🎵",
    ".py": "🐍", ".js": "📜", ".ts": "📜", ".html": "🌐", ".css": "🎨",
    ".json": "🔧", ".yaml": "🔧", ".yml": "🔧",
}


def _cache_key(path, mtime, size):
    h = hashlib.sha1(f"{path}|{mtime}|{size}".encode("utf-8", "ignore")).hexdigest()
    return os.path.join(CACHE_DIR, h + ".jpg")


def _to_data_uri(jpeg_bytes):
    b64 = base64.b64encode(jpeg_bytes).decode("ascii")
    return "data:image/jpeg;base64," + b64


def make_thumb_image(path, mtime, size):
    from PIL import Image, ImageOps
    cache_path = _cache_key(path, mtime, size)
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return _to_data_uri(f.read())
    try:
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im)
            im.thumbnail((THUMB_SIZE, THUMB_SIZE))
            im = im.convert("RGB")
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=80)
            data = buf.getvalue()
        with open(cache_path, "wb") as f:
            f.write(data)
        return _to_data_uri(data)
    except Exception:
        return None


def make_thumb_video(path, mtime, size):
    cache_path = _cache_key(path, mtime, size)
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return _to_data_uri(f.read())
    if not FFMPEG_EXE:
        return None
    try:
        with tempfile.TemporaryDirectory() as td:
            frame_path = os.path.join(td, "frame.jpg")
            subprocess.run(
                [FFMPEG_EXE, "-y", "-ss", "1", "-i", path,
                 "-frames:v", "1", "-vf", f"scale={THUMB_SIZE}:-1",
                 frame_path],
                capture_output=True, timeout=15,
                creationflags=CREATE_NO_WINDOW,
            )
            if not os.path.exists(frame_path):
                return None
            with open(frame_path, "rb") as f:
                data = f.read()
        with open(cache_path, "wb") as f:
            f.write(data)
        return _to_data_uri(data)
    except Exception:
        return None


def thumbnail_for(item):
    """Возвращает dict {kind: 'image'|'emoji', value: str} для элемента листинга."""
    if item["type"] == "dir":
        return {"kind": "emoji", "value": "📁"}

    ext = item.get("ext", "")
    path = item["path"]
    mtime = item.get("mtime") or ""
    size = item.get("size") or 0

    if ext in IMAGE_EXT:
        uri = make_thumb_image(path, mtime, size)
        if uri:
            return {"kind": "image", "value": uri}
        return {"kind": "emoji", "value": "🖼️"}

    if ext in VIDEO_EXT:
        uri = make_thumb_video(path, mtime, size)
        if uri:
            return {"kind": "image", "value": uri}
        return {"kind": "emoji", "value": "🎬"}

    return {"kind": "emoji", "value": ICON_BY_EXT.get(ext, "📦")}
