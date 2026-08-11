"""Генерация HTML-отчёта ClaudeSortBy: сетка / дерево + лайтбокс с зумом."""

import html
import json
import os
import tempfile
import time
import webbrowser

from thumbs import thumbnail_for


def _stars(score):
    try:
        score = int(round(float(score)))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(5, score))
    return (
        f'<span class="s-on">{"★" * score}</span>'
        f'<span class="s-off">{"★" * (5 - score)}</span>'
    )


def _file_uri(path):
    return "file:///" + path.replace("\\", "/").replace(" ", "%20")


def _meta_line(it):
    if it["type"] == "dir":
        subtitle = f'{it.get("item_count", 0)} эл.'
    else:
        subtitle = it.get("dims", "")
    return " · ".join(x for x in [it.get("size_human", ""), subtitle, it.get("mtime", "")] if x)


def _attach_thumbs(node, root_path, lightbox_images, thumb_by_relpath):
    abs_path = os.path.join(root_path, node["rel_path"].replace("/", os.sep)) if node["rel_path"] else root_path
    item_for_thumb = dict(node)
    item_for_thumb["path"] = abs_path
    thumb = thumbnail_for(item_for_thumb)
    if thumb["kind"] == "image":
        thumb = {"kind": "image", "value": thumb["value"], "idx": len(lightbox_images)}
        lightbox_images.append(node["rel_path"])
    thumb_by_relpath[node["rel_path"]] = thumb
    node["thumb"] = thumb
    for child in node.get("children", []):
        _attach_thumbs(child, root_path, lightbox_images, thumb_by_relpath)


def _tile_html(it, thumb, idx_map):
    is_img = thumb["kind"] == "image"
    thumb_html = (
        f'<img src="{thumb["value"]}" loading="lazy" class="thumb-img" '
        f'onclick="openLightbox({idx_map.get(it["rel_path"], -1)})">'
        if is_img else
        f'<div class="thumb-emoji">{thumb["value"]}</div>'
    )
    highlight_cls = " highlight" if it.get("highlight") else ""
    abs_uri = it["_uri"]
    return f"""
    <div class="tile{highlight_cls}">
      <div class="thumb">{thumb_html}<div class="rank">#{it.get('rank', '?')}</div></div>
      <div class="tile-body">
        <a class="name" href="{abs_uri}" title="{html.escape(it['rel_path'])}">{html.escape(it['name'])}</a>
        <div class="stars">{_stars(it.get('score', 0))}</div>
        <div class="meta">{html.escape(_meta_line(it))}</div>
        <div class="reason">{html.escape(it.get('reason', ''))}</div>
      </div>
    </div>"""


def build_html(root_path, query, tree_root, ranked_items, answer, warning, meta):
    lightbox_images_rel = []
    thumb_by_relpath = {}
    if tree_root is not None:
        _attach_thumbs(tree_root, root_path, lightbox_images_rel, thumb_by_relpath)

    idx_map = {rel: i for i, rel in enumerate(lightbox_images_rel)}
    lightbox_uris = [_file_uri(os.path.join(root_path, rel.replace("/", os.sep))) for rel in lightbox_images_rel]

    tiles = []
    for it in ranked_items:
        it = dict(it)
        it["_uri"] = _file_uri(it["path"])
        thumb = thumb_by_relpath.get(it["rel_path"], {"kind": "emoji", "value": "📦"})
        tiles.append(_tile_html(it, thumb, idx_map))

    def tree_node_to_json(node):
        thumb = node.get("thumb", {"kind": "emoji", "value": "📁" if node["type"] == "dir" else "📦"})
        out = {
            "name": node["name"],
            "rel_path": node["rel_path"],
            "type": node["type"],
            "meta": _meta_line(node),
            "rank": node.get("rank"),
            "score": node.get("score", 0),
            "reason": node.get("reason", ""),
            "highlight": bool(node.get("highlight")),
            "thumb_kind": thumb["kind"],
            "thumb_value": thumb["value"],
            "lightbox_idx": idx_map.get(node["rel_path"], -1),
            "uri": _file_uri(os.path.join(root_path, node["rel_path"].replace("/", os.sep)) if node["rel_path"] else root_path),
        }
        if node["type"] == "dir":
            out["children"] = [tree_node_to_json(c) for c in node.get("children", [])]
        return out

    tree_json = tree_node_to_json(tree_root) if tree_root is not None else None

    answer_html = (
        f'<div class="answer"><div class="answer-label">Ответ Claude</div>{html.escape(answer)}</div>'
        if answer else ""
    )
    warning_html = f'<div class="warning">⚠️ {html.escape(warning)}</div>' if warning else ""
    truncated_html = (
        f'<div class="warning">⚠️ Показаны не все элементы ({meta.get("scanned", "?")} просканировано, '
        f'обход обрезан по лимиту/времени).</div>'
        if meta.get("truncated") else ""
    )
    rounds_note = (
        f'<div class="root">рекурсивно, раундов: {meta["rounds"]}</div>' if meta.get("rounds") else ""
    )

    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>{html.escape(query)}</title>
<style>
  :root {{
    --bg: #16171c; --panel: #1f2128; --text: #e8e8ec; --muted: #9a9ba5;
    --accent: #7c9eff; --accent-dark: #5a78d6; --border: #2c2f3a; --hl: #f0c975;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--text);
    font-family: "Segoe UI", system-ui, sans-serif;
  }}
  header {{
    padding: 16px 24px; border-bottom: 1px solid var(--border);
    display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
    position: sticky; top: 0; background: var(--bg); z-index: 5;
  }}
  header h1 {{ font-size: 18px; margin: 0; font-weight: 600; }}
  header .root {{ color: var(--muted); font-size: 13px; }}
  .tabs {{ display: flex; gap: 4px; margin-left: 8px; }}
  .tab-btn {{
    background: var(--panel); color: var(--muted); border: 1px solid var(--border);
    border-radius: 8px; padding: 6px 14px; cursor: pointer; font-size: 13px;
  }}
  .tab-btn.active {{ background: var(--accent); color: #101116; border-color: var(--accent); }}
  .controls {{ margin-left: auto; display: flex; align-items: center; gap: 8px; }}
  .controls label {{ color: var(--muted); font-size: 13px; }}
  .answer {{
    margin: 12px 24px 0; padding: 12px 16px; background: #1c2438; color: #cfe0ff;
    border-radius: 8px; font-size: 14px; border: 1px solid #35507a;
  }}
  .answer-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: #7c9eff; margin-bottom: 4px; }}
  .warning {{
    margin: 12px 24px 0; padding: 10px 14px; background: #3a2e12; color: #f0c975;
    border-radius: 8px; font-size: 13px;
  }}
  .view {{ display: none; }}
  .view.active {{ display: block; }}
  .grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(var(--tile,220px), 1fr));
    gap: 14px; padding: 20px 24px;
  }}
  .tile {{
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    overflow: hidden; display: flex; flex-direction: column;
    transition: border-color .15s, transform .15s;
  }}
  .tile:hover {{ border-color: var(--accent); transform: translateY(-2px); }}
  .tile.highlight {{ border-color: var(--hl); box-shadow: 0 0 0 1px var(--hl); }}
  .thumb {{
    position: relative; aspect-ratio: 4/3; background: #101116;
    display: flex; align-items: center; justify-content: center; overflow: hidden;
  }}
  .thumb-img {{ width: 100%; height: 100%; object-fit: cover; cursor: zoom-in; }}
  .thumb-emoji {{ font-size: 56px; }}
  .rank {{
    position: absolute; top: 8px; left: 8px; font-size: 11px; font-weight: 700;
    color: var(--accent); background: rgba(16,17,22,.85); padding: 2px 9px;
    border-radius: 999px; border: 1px solid var(--border);
  }}
  .tile-body {{
    padding: 10px 12px 12px; display: flex; flex-direction: column; gap: 4px; flex: 1;
  }}
  .stars {{ font-size: 17px; letter-spacing: 2px; line-height: 1; }}
  .s-on {{ color: var(--hl); }}
  .s-off {{ color: #3d4050; }}
  .name {{
    color: var(--text); text-decoration: none; font-size: 13px; font-weight: 600;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }}
  .name:hover {{ color: var(--accent); text-decoration: underline; }}
  .meta {{ color: var(--muted); font-size: 11px; }}
  .reason {{
    color: #c7c9d6; font-size: 12px; font-style: italic; margin-top: 2px;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden;
  }}

  .tree {{ padding: 16px 24px 32px; }}
  .tree ul {{ list-style: none; margin: 0; padding-left: 22px; }}
  .tree > ul {{ padding-left: 0; }}
  .tree li {{ margin: 2px 0; }}
  .tnode {{
    display: flex; align-items: center; gap: 8px; padding: 4px 8px; border-radius: 6px;
  }}
  .tnode.highlight {{ background: #2a2410; box-shadow: inset 0 0 0 1px var(--hl); }}
  .tnode:hover {{ background: var(--panel); }}
  .twiggle {{ width: 16px; text-align: center; color: var(--muted); cursor: pointer; user-select: none; }}
  .ticon {{ width: 22px; text-align: center; flex: none; }}
  .ticon img {{ width: 20px; height: 20px; object-fit: cover; border-radius: 4px; cursor: zoom-in; vertical-align: middle; }}
  .tname {{ color: var(--text); text-decoration: none; font-size: 13px; }}
  .tname:hover {{ color: var(--accent); text-decoration: underline; }}
  .tstars {{ font-size: 15px; letter-spacing: 1.5px; line-height: 1; flex: none; }}
  .tmeta {{ color: var(--muted); font-size: 11px; flex: none; }}
  .treason {{ color: #c7c9d6; font-size: 12px; font-style: italic; }}
  .tree li.collapsed > ul {{ display: none; }}

  #lightbox {{
    display: none; position: fixed; inset: 0; background: rgba(0,0,0,.9); z-index: 50;
    align-items: center; justify-content: center; overflow: hidden; cursor: grab;
  }}
  #lightbox img {{ max-width: 95vw; max-height: 95vh; transition: transform .05s; user-select: none; }}
  #lightbox .hint {{ position: absolute; bottom: 14px; left: 0; right: 0; text-align: center; color: #aaa; font-size: 12px; }}
</style>
</head>
<body>
<header>
  <h1>{html.escape(query)}</h1>
  <div class="root">{html.escape(root_path)}</div>
  {rounds_note}
  <div class="tabs">
    <button class="tab-btn active" id="tabGridBtn" onclick="showView('grid')">▦ Сетка</button>
    <button class="tab-btn" id="tabTreeBtn" onclick="showView('tree')">☰ Дерево</button>
  </div>
  <div class="controls" id="gridControls">
    <label for="tileSize">Размер плиток</label>
    <input type="range" id="tileSize" min="120" max="360" value="220">
  </div>
</header>
{answer_html}
{warning_html}
{truncated_html}

<div class="view active" id="viewGrid">
  <div class="grid" id="grid">
  {''.join(tiles)}
  </div>
</div>

<div class="view" id="viewTree">
  <div class="tree" id="tree"></div>
</div>

<div id="lightbox" onclick="if(event.target===this) closeLightbox()">
  <img id="lightboxImg">
  <div class="hint">Колесо — зум · перетаскивание — пан · Esc/клик по фону — закрыть</div>
</div>

<script>
  const images = {json.dumps(lightbox_uris)};
  const treeData = {json.dumps(tree_json)};
  let curIdx = 0, scale = 1, tx = 0, ty = 0, dragging = false, sx = 0, sy = 0;
  const lb = document.getElementById('lightbox');
  const img = document.getElementById('lightboxImg');

  function applyTransform() {{
    img.style.transform = `translate(${{tx}}px, ${{ty}}px) scale(${{scale}})`;
  }}
  function openLightbox(idx) {{
    if (idx < 0) return;
    curIdx = idx; scale = 1; tx = 0; ty = 0;
    img.src = images[idx];
    applyTransform();
    lb.style.display = 'flex';
  }}
  function closeLightbox() {{ lb.style.display = 'none'; }}
  document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeLightbox(); }});
  lb.addEventListener('wheel', e => {{
    e.preventDefault();
    const delta = -e.deltaY * 0.0015;
    scale = Math.min(8, Math.max(0.3, scale + delta * scale));
    applyTransform();
  }}, {{ passive: false }});
  img.addEventListener('mousedown', e => {{
    dragging = true; sx = e.clientX - tx; sy = e.clientY - ty; lb.style.cursor = 'grabbing';
  }});
  window.addEventListener('mouseup', () => {{ dragging = false; lb.style.cursor = 'grab'; }});
  window.addEventListener('mousemove', e => {{
    if (!dragging) return;
    tx = e.clientX - sx; ty = e.clientY - sy;
    applyTransform();
  }});

  const slider = document.getElementById('tileSize');
  const grid = document.getElementById('grid');
  slider.addEventListener('input', () => {{
    grid.style.setProperty('--tile', slider.value + 'px');
  }});

  function stars(score) {{
    score = Math.max(0, Math.min(5, Math.round(score || 0)));
    return '<span class="s-on">' + '★'.repeat(score) + '</span>'
         + '<span class="s-off">' + '★'.repeat(5 - score) + '</span>';
  }}

  function renderNode(node, depth) {{
    const li = document.createElement('li');
    const hasChildren = node.type === 'dir' && node.children && node.children.length > 0;
    if (hasChildren && depth > 0) li.classList.add('collapsed');

    const row = document.createElement('div');
    row.className = 'tnode' + (node.highlight ? ' highlight' : '');

    const twiggle = document.createElement('span');
    twiggle.className = 'twiggle';
    twiggle.textContent = hasChildren ? '▸' : '';
    if (hasChildren) {{
      twiggle.style.cursor = 'pointer';
      twiggle.onclick = () => {{
        li.classList.toggle('collapsed');
        twiggle.textContent = li.classList.contains('collapsed') ? '▸' : '▾';
      }};
      if (!li.classList.contains('collapsed')) twiggle.textContent = '▾';
    }}
    row.appendChild(twiggle);

    const icon = document.createElement('span');
    icon.className = 'ticon';
    if (node.thumb_kind === 'image') {{
      const im = document.createElement('img');
      im.src = node.thumb_value;
      im.loading = 'lazy';
      im.onclick = () => openLightbox(node.lightbox_idx);
      icon.appendChild(im);
    }} else {{
      icon.textContent = node.thumb_value;
    }}
    row.appendChild(icon);

    const name = document.createElement('a');
    name.className = 'tname';
    name.href = node.uri;
    name.textContent = node.name;
    row.appendChild(name);

    if (node.rank) {{
      const st = document.createElement('span');
      st.className = 'tstars';
      st.innerHTML = stars(node.score);
      row.appendChild(st);
    }}

    const meta = document.createElement('span');
    meta.className = 'tmeta';
    meta.textContent = node.meta || '';
    row.appendChild(meta);

    if (node.reason) {{
      const reason = document.createElement('span');
      reason.className = 'treason';
      reason.textContent = node.reason;
      row.appendChild(reason);
    }}

    li.appendChild(row);

    if (hasChildren) {{
      const ul = document.createElement('ul');
      node.children.forEach(c => ul.appendChild(renderNode(c, depth + 1)));
      li.appendChild(ul);
    }}
    return li;
  }}

  function buildTree() {{
    const container = document.getElementById('tree');
    if (!treeData) {{ container.textContent = 'Нет данных.'; return; }}
    const ul = document.createElement('ul');
    (treeData.children || []).forEach(c => ul.appendChild(renderNode(c, 0)));
    container.appendChild(ul);
  }}
  buildTree();

  function showView(name) {{
    document.getElementById('viewGrid').classList.toggle('active', name === 'grid');
    document.getElementById('viewTree').classList.toggle('active', name === 'tree');
    document.getElementById('tabGridBtn').classList.toggle('active', name === 'grid');
    document.getElementById('tabTreeBtn').classList.toggle('active', name === 'tree');
    document.getElementById('gridControls').style.display = name === 'grid' ? 'flex' : 'none';
  }}
</script>
</body>
</html>"""


def write_and_open(root_path, query, tree_root, ranked_items, answer, warning, meta):
    for it in ranked_items:
        it["path"] = os.path.join(root_path, it["rel_path"].replace("/", os.sep))

    html_text = build_html(root_path, query, tree_root, ranked_items, answer, warning, meta)
    out_dir = os.path.join(tempfile.gettempdir(), "ClaudeSortBy")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"report_{int(time.time())}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_text)
    webbrowser.open(_file_uri(out_path))
    return out_path
