"""Движок ClaudeSortBy: обычный (только верхний уровень) и рекурсивный режим,
в котором Claude сам решает, в какие подпапки заглянуть.

Важно про безопасность: Claude НИКОГДА не получает инструментов файловой
системы (Bash/Read/Write/...). В рекурсивном режиме он лишь просит
Python показать содержимое конкретных подпапок (по имени), а Python сам
сканирует их и присылает обратно только имена/метаданные — так же, как
и в обычном режиме. Модель не может прочитать содержимое файлов и не
может выйти за пределы выбранной пользователем папки.
"""

import json
import os
import shutil
import subprocess

import scan


def _find_claude():
    """Ищет Claude Code CLI: env-переменная → PATH → типовые места установки."""
    override = os.environ.get("CLAUDESORTBY_CLAUDE")
    if override and os.path.exists(override):
        return override
    exe = shutil.which("claude")
    if exe:
        return exe
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".local", "bin", "claude.exe"),
        os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "claude-code", "claude.exe"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


CLAUDE_EXE = _find_claude()
MODEL = "haiku"
CALL_TIMEOUT_SEC = 90

# Не показывать консольное окно дочернего процесса (важно для exe/pythonw).
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

MAX_ROUNDS = 4
MAX_DIRS_PER_ROUND = 6
ITEM_BUDGET = 350

# Инструменты Claude не нужны вообще: и обычная сортировка, и рекурсивный
# обход строятся на данных, которые ему присылает Python. Явно запрещаем
# всё, что могло бы дать доступ к файловой системе/сети/другим сессиям.
DISALLOWED_TOOLS = [
    "Bash", "Read", "Write", "Edit", "NotebookEdit", "WebFetch", "WebSearch",
    "Task", "Skill", "Agent", "Workflow", "PowerShell",
    "CronCreate", "CronDelete", "CronList", "DesignSync",
    "EnterWorktree", "ExitWorktree", "Monitor", "PushNotification",
    "ReadMcpResourceDirTool", "ReadMcpResourceTool", "RemoteTrigger",
    "ReportFindings", "ScheduleWakeup", "SendMessage", "ShareOnboardingGuide",
    "TaskCreate", "TaskGet", "TaskList", "TaskOutput", "TaskStop",
    "TaskUpdate", "ToolSearch", "EnterPlanMode", "ExitPlanMode",
]

ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string"},
        "rank": {"type": "integer"},
        "score": {"type": "integer"},
        "reason": {"type": "string"},
        "highlight": {"type": "boolean"},
    },
    "required": ["path", "rank", "score", "reason"],
}

FLAT_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "items": {"type": "array", "items": ITEM_SCHEMA},
    },
    "required": ["items"],
}

STEP_SCHEMA = {
    "type": "object",
    "properties": {
        "done": {"type": "boolean"},
        "need_more": {"type": "array", "items": {"type": "string"}},
        "answer": {"type": "string"},
        "items": {"type": "array", "items": ITEM_SCHEMA},
    },
    "required": ["done"],
}

BASE_HINT = (
    "Ты — утилита ClaudeSortBy в контекстном меню Проводника Windows. "
    "Пользователь даёт СВОБОДНЫЙ текст: это может быть метрика сортировки "
    "('по важности') или вопрос ('где тут могут быть пароли?'). "
    "Ты видишь ТОЛЬКО имена и метаданные (тип, размер, даты, кол-во "
    "вложенных элементов, разрешение картинок) — содержимое файлов тебе "
    "недоступно и никогда не будет доступно, не притворяйся, что читал его."
)


def _run_claude(prompt, schema):
    if not CLAUDE_EXE:
        return None, (
            "Claude Code CLI не найден. Установи его (https://claude.com/claude-code) "
            "или укажи путь в переменной окружения CLAUDESORTBY_CLAUDE."
        )
    try:
        result = subprocess.run(
            [
                CLAUDE_EXE, "-p", "--model", MODEL,
                "--output-format", "json",
                "--json-schema", json.dumps(schema),
                "--disallowedTools", *DISALLOWED_TOOLS,
            ],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=CALL_TIMEOUT_SEC,
            creationflags=CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return None, "Claude не ответил за отведённое время"

    if result.returncode != 0:
        return None, f"claude завершился с кодом {result.returncode}: {result.stderr[:300]}"

    try:
        events = json.loads(result.stdout)
        final = events[-1]
        if final.get("is_error"):
            return None, str(final.get("result"))[:300]
        return final["structured_output"], None
    except Exception as e:
        return None, f"Не удалось разобрать ответ Claude: {e}"


def _item_view(it):
    return {k: v for k, v in it.items() if k not in ("path", "rel_path")}


def _apply_results(flat_by_relpath, tree_index, result_items, answer):
    ranked = []
    for r in result_items or []:
        rel = r.get("path")
        base = flat_by_relpath.get(rel)
        if base is None:
            continue
        merged = dict(base)
        merged["rank"] = r.get("rank", 999)
        merged["score"] = r.get("score", 0)
        merged["reason"] = r.get("reason", "")
        merged["highlight"] = bool(r.get("highlight", False))
        ranked.append(merged)
        node = tree_index.get(rel)
        if node is not None:
            node["rank"] = merged["rank"]
            node["score"] = merged["score"]
            node["reason"] = merged["reason"]
            node["highlight"] = merged["highlight"]

    covered = {r.get("path") for r in (result_items or [])}
    for rel, base in flat_by_relpath.items():
        if rel not in covered:
            merged = dict(base)
            merged.setdefault("rank", 999)
            merged.setdefault("score", 0)
            merged.setdefault("reason", "")
            merged.setdefault("highlight", False)
            ranked.append(merged)

    ranked.sort(key=lambda x: (x.get("rank", 999) if isinstance(x.get("rank"), (int, float)) else 999))
    return ranked, (answer or "").strip()


def _make_tree_root(root_path):
    return {"name": os.path.basename(root_path.rstrip("\\/")) or root_path, "rel_path": "", "type": "dir", "children": []}


def _attach_children(tree_index, parent_rel, items_meta):
    parent_node = tree_index[parent_rel]
    for it in items_meta:
        rel = f"{parent_rel}/{it['name']}" if parent_rel else it["name"]
        node = dict(it)
        node["rel_path"] = rel
        if node["type"] == "dir":
            node["children"] = []
        parent_node["children"].append(node)
        tree_index[rel] = node


def run_flat(root_path, query):
    """Обычный режим: только верхний уровень, один вызов Claude."""
    _, items, meta = scan.scan(root_path)
    if not items:
        return None, [], "", "Папка пуста — анализировать нечего.", meta

    tree_root = _make_tree_root(root_path)
    tree_index = {"": tree_root}
    _attach_children(tree_index, "", items)

    flat_by_relpath = {}
    for it in items:
        entry = dict(it)
        entry["rel_path"] = it["name"]
        flat_by_relpath[it["name"]] = entry

    payload = {
        "query": query,
        "root": root_path,
        "items": [dict(_item_view(it), path=it["name"]) for it in items],
    }
    prompt = (
        BASE_HINT
        + "\n\nЗАПРОС ПОЛЬЗОВАТЕЛЯ: " + query
        + "\n\nВерни JSON: answer (текстовый ответ на запрос, если это вопрос; "
          "иначе пустая строка) и items — по одному объекту на КАЖДЫЙ элемент "
          "из входа (path точно как во входе, rank — целое, 1 = лучший по "
          "запросу, score 1..5, reason — до 12 слов на русском, "
          "highlight=true для элементов, прямо отвечающих на вопрос)."
        + "\n\nДАННЫЕ:\n" + json.dumps(payload, ensure_ascii=False)
    )

    structured, err = _run_claude(prompt, FLAT_SCHEMA)
    if err or structured is None:
        ranked, answer = _apply_results(flat_by_relpath, tree_index, [], "")
        return tree_root, ranked, answer, f"Claude не ответил как ожидалось ({err}). Показан список без оценки.", meta

    ranked, answer = _apply_results(flat_by_relpath, tree_index, structured.get("items"), structured.get("answer"))
    return tree_root, ranked, answer, None, meta


def run_recursive(root_path, query):
    """Рекурсивный режим: Claude сам решает, в какие подпапки заглянуть.

    Claude не получает никаких инструментов файловой системы — он лишь
    называет относительные пути подпапок, а сканирование выполняет Python.
    """
    _, items, meta = scan.scan(root_path)
    if not items:
        return None, [], "", "Папка пуста — анализировать нечего.", meta

    tree_root = _make_tree_root(root_path)
    tree_index = {"": tree_root}
    _attach_children(tree_index, "", items)

    flat_by_relpath = {}
    for it in items:
        entry = dict(it)
        entry["rel_path"] = it["name"]
        flat_by_relpath[it["name"]] = entry

    expanded = set()
    warning = None
    total_scanned = len(items)
    truncated_by_budget = False
    force_final_next = False

    for round_no in range(MAX_ROUNDS):
        force_final = round_no == MAX_ROUNDS - 1 or total_scanned >= ITEM_BUDGET or force_final_next
        payload = {
            "query": query,
            "root": root_path,
            "items": [
                dict(_item_view(v), path=k, expandable=(v["type"] == "dir" and k not in expanded))
                for k, v in flat_by_relpath.items()
            ],
        }
        instruction = (
            "Если для уверенного ответа нужно заглянуть внутрь каких-то папок "
            f"(expandable=true) — верни done=false и need_more (до {MAX_DIRS_PER_ROUND} "
            "относительных путей папок ИЗ ДАННЫХ, ничего не выдумывай). "
            "Иначе верни done=true, answer (ответ на запрос, если это вопрос, "
            "иначе пустая строка) и items — по объекту на КАЖДЫЙ известный тебе "
            "элемент (path, rank целое, score 1..5, reason до 12 слов на "
            "русском, highlight=true для прямых попаданий)."
        )
        if force_final:
            instruction = (
                "Лимит обхода исчерпан, дальше вглубь заходить нельзя. "
                "Верни done=true с финальным answer и items по ВСЕМ известным "
                "элементам, как описано выше."
            )

        prompt = (
            BASE_HINT
            + "\n\nЗАПРОС ПОЛЬЗОВАТЕЛЯ: " + query
            + "\n\n" + instruction
            + "\n\nДАННЫЕ (все элементы, которые уже просканированы):\n"
            + json.dumps(payload, ensure_ascii=False)
        )

        structured, err = _run_claude(prompt, STEP_SCHEMA)
        if err or structured is None:
            warning = f"Claude не ответил как ожидалось ({err}). Показан частичный результат."
            break

        if structured.get("done") or force_final:
            ranked, answer = _apply_results(flat_by_relpath, tree_index, structured.get("items"), structured.get("answer"))
            return tree_root, ranked, answer, warning, {**meta, "scanned": total_scanned, "rounds": round_no + 1}

        requested = (structured.get("need_more") or [])[:MAX_DIRS_PER_ROUND]
        made_progress = False
        for rel in requested:
            rel_norm = rel.strip("/\\")
            if rel_norm in expanded or rel_norm not in flat_by_relpath and rel_norm not in tree_index:
                continue
            node = flat_by_relpath.get(rel_norm) or tree_index.get(rel_norm)
            if node is None or node.get("type") != "dir":
                continue
            full_path = os.path.abspath(os.path.join(root_path, rel_norm))
            root_abs = os.path.abspath(root_path)
            if os.path.commonpath([full_path, root_abs]) != root_abs:
                continue  # защита от выхода за пределы выбранной папки
            if not os.path.isdir(full_path):
                continue

            expanded.add(rel_norm)
            _, children, _ = scan.scan(full_path)
            if total_scanned + len(children) > ITEM_BUDGET:
                children = children[: max(0, ITEM_BUDGET - total_scanned)]
                truncated_by_budget = True
            _attach_children(tree_index, rel_norm, children)
            for c in children:
                child_rel = f"{rel_norm}/{c['name']}"
                entry = dict(c)
                entry["rel_path"] = child_rel
                flat_by_relpath[child_rel] = entry
            total_scanned += len(children)
            made_progress = True

        if not made_progress:
            # Claude попросил то, что уже раскрыто/не существует — просим финал
            # на следующем (последнем) круге.
            force_final_next = True

    # Если вышли из цикла без "done" (не должно происходить из-за force_final,
    # но подстрахуемся).
    ranked, answer = _apply_results(flat_by_relpath, tree_index, [], "")
    warning = warning or "Не удалось получить финальный ответ Claude вовремя."
    meta_out = {**meta, "scanned": total_scanned, "truncated": meta.get("truncated") or truncated_by_budget}
    return tree_root, ranked, answer, warning, meta_out


def run(root_path, query, recursive):
    if recursive:
        return run_recursive(root_path, query)
    return run_flat(root_path, query)
