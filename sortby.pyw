"""ClaudeSortBy — окно ввода метрики, вызываемое из контекстного меню Проводника.

Использование: pythonw.exe sortby.pyw "<путь к папке или диску>"
"""

import json
import os
import random
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox

if getattr(sys, "frozen", False):
    # PyInstaller: BASE_DIR — папка с exe (там ищем редактируемый metrics.json),
    # BUNDLE_DIR — распакованные ресурсы (запасной metrics.json).
    BASE_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = BASE_DIR
    sys.path.insert(0, BASE_DIR)

import engine
import report

BG = "#16171c"
PANEL = "#1f2128"
TEXT = "#e8e8ec"
MUTED = "#9a9ba5"
ACCENT = "#7c9eff"
ACCENT_DARK = "#5a78d6"
BORDER = "#2c2f3a"


def load_metrics():
    for base in (BASE_DIR, BUNDLE_DIR):
        try:
            with open(os.path.join(base, "metrics.json"), encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            continue
    return ["по важности"]


class App:
    def __init__(self, root_path):
        self.root_path = root_path
        self.metrics = load_metrics()

        self.win = tk.Tk()
        self.win.title("Отсортировать по…")
        self.win.configure(bg=BG)
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)

        w, h = 460, 222
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")

        base_font = tkfont.Font(family="Segoe UI", size=11)
        small_font = tkfont.Font(family="Segoe UI", size=9)
        title_font = tkfont.Font(family="Segoe UI", size=12, weight="bold")

        pad = tk.Frame(self.win, bg=BG)
        pad.pack(fill="both", expand=True, padx=18, pady=16)

        tk.Label(pad, text="Отсортировать по…", bg=BG, fg=TEXT, font=title_font).pack(anchor="w")
        tk.Label(pad, text=self._short_path(root_path), bg=BG, fg=MUTED, font=small_font).pack(anchor="w", pady=(2, 12))

        row = tk.Frame(pad, bg=BG)
        row.pack(fill="x")

        self.entry = tk.Entry(
            row, font=base_font, bg=PANEL, fg=TEXT, insertbackground=TEXT,
            relief="flat", highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self.entry.insert(0, "важности")
        self.entry.focus_set()
        self.entry.select_range(0, "end")
        self.entry.bind("<Return>", lambda e: self.on_submit())
        self.entry.bind("<Escape>", lambda e: self.win.destroy())

        dice_btn = tk.Button(
            row, text="🎲", font=tkfont.Font(size=13), bg=PANEL, fg=TEXT,
            activebackground=BORDER, relief="flat", width=3, cursor="hand2",
            command=self.on_dice,
        )
        dice_btn.pack(side="left")

        hint = tk.Label(
            pad, text="Можно и метрику («по важности»), и вопрос («где тут могут быть пароли?»)",
            bg=BG, fg=MUTED, font=small_font,
        )
        hint.pack(anchor="w", pady=(6, 0))

        self.recursive_var = tk.BooleanVar(value=False)
        recursive_chk = tk.Checkbutton(
            pad, text="Рекурсивно (Claude сам решит, в какие подпапки заглянуть)",
            variable=self.recursive_var, bg=BG, fg=TEXT, selectcolor=PANEL,
            activebackground=BG, activeforeground=TEXT, font=small_font,
            highlightthickness=0, bd=0, cursor="hand2",
        )
        recursive_chk.pack(anchor="w", pady=(8, 0))

        btn_row = tk.Frame(pad, bg=BG)
        btn_row.pack(fill="x", pady=(14, 0))

        self.status = tk.Label(btn_row, text="", bg=BG, fg=MUTED, font=small_font, anchor="w")
        self.status.pack(side="left", fill="x", expand=True)

        cancel_btn = tk.Button(
            btn_row, text="Отмена", font=small_font, bg=BG, fg=MUTED,
            relief="flat", cursor="hand2", command=self.win.destroy,
        )
        cancel_btn.pack(side="right")

        self.ok_btn = tk.Button(
            btn_row, text="ОК", font=base_font, bg=ACCENT, fg="#101116",
            activebackground=ACCENT_DARK, relief="flat", cursor="hand2",
            padx=18, command=self.on_submit,
        )
        self.ok_btn.pack(side="right", padx=(0, 8))

    @staticmethod
    def _short_path(p):
        p = p.rstrip("\\/")
        if len(p) > 60:
            return "…" + p[-57:]
        return p

    def on_dice(self):
        metric = random.choice(self.metrics)
        self.entry.delete(0, "end")
        self.entry.insert(0, metric)

    def set_busy(self, busy, text=""):
        self.status.config(text=text)
        state = "disabled" if busy else "normal"
        self.entry.config(state=state)
        self.ok_btn.config(state=state)

    def on_submit(self):
        query = self.entry.get().strip()
        if not query:
            return
        recursive = self.recursive_var.get()
        busy_text = "Читаю содержимое…" if not recursive else "Читаю верхний уровень…"
        self.set_busy(True, busy_text)
        threading.Thread(target=self._run, args=(query, recursive), daemon=True).start()

    def _run(self, query, recursive):
        if recursive:
            self.win.after(0, lambda: self.set_busy(True, "Claude изучает папку (может заглянуть внутрь)…"))
        else:
            self.win.after(0, lambda: self.set_busy(True, "Спрашиваю Claude…"))

        try:
            tree_root, ranked, answer, warning, meta = engine.run(self.root_path, query, recursive)
        except Exception as e:
            self.win.after(0, lambda: self._fail(f"Ошибка: {e}"))
            return

        if tree_root is None:
            self.win.after(0, lambda: self._fail(warning or "Папка пуста — анализировать нечего."))
            return

        self.win.after(0, lambda: self.set_busy(True, "Строю отчёт…"))
        try:
            report.write_and_open(self.root_path, query, tree_root, ranked, answer, warning, meta)
        except Exception as e:
            self.win.after(0, lambda: self._fail(f"Не удалось построить отчёт: {e}"))
            return

        self.win.after(0, self.win.destroy)

    def _fail(self, message):
        self.set_busy(False, message)

    def run(self):
        self.win.mainloop()


def main():
    if len(sys.argv) < 2:
        root_path = os.getcwd()
    else:
        root_path = sys.argv[1]
        if root_path.startswith('"') and root_path.endswith('"'):
            root_path = root_path[1:-1]
        root_path = os.path.abspath(root_path)

    if not os.path.isdir(root_path):
        tk.Tk().withdraw()
        messagebox.showerror("ClaudeSortBy", f"Путь не найден:\n{root_path}")
        return

    App(root_path).run()


if __name__ == "__main__":
    main()
