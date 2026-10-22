# -*- coding: utf-8 -*-
"""Build deterministic, safe SVG diagrams from an LLM-produced specification."""

import re
import textwrap
from xml.sax.saxutils import escape


MAX_NODES = 80
MAX_EDGES = 160
NODE_WIDTH = 230
NODE_HEIGHT = 82
LEVEL_GAP = 88
COL_GAP = 36


class DiagramSpecError(ValueError):
    pass


def _clean_text(value, limit=180):
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    return value[:limit]


def _clean_id(value, fallback):
    value = re.sub(r"[^a-zA-Z0-9_.:-]+", "-", str(value or "")).strip("-")
    return (value or fallback)[:80]


def _text_lines(value, width=28, maximum=3):
    text = _clean_text(value)
    if not text:
        return []
    lines = textwrap.wrap(text, width=width, break_long_words=True, break_on_hyphens=False)
    if len(lines) > maximum:
        lines = lines[:maximum]
        lines[-1] = lines[-1].rstrip(" .") + "…"
    return lines


def _levels(nodes, edges, diagram_type):
    ids = [node["id"] for node in nodes]
    if diagram_type == "employee_list" or not edges:
        return {node_id: index // 4 for index, node_id in enumerate(ids)}

    indegree = {node_id: 0 for node_id in ids}
    outgoing = {node_id: [] for node_id in ids}
    for edge in edges:
        source, target = edge["source"], edge["target"]
        outgoing[source].append(target)
        indegree[target] += 1

    queue = [node_id for node_id in ids if indegree[node_id] == 0]
    levels = {node_id: 0 for node_id in queue}
    visited = set()
    while queue:
        current = queue.pop(0)
        visited.add(current)
        for target in outgoing[current]:
            levels[target] = max(levels.get(target, 0), levels[current] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    # Cyclic or disconnected nodes are still rendered in stable rows.
    fallback_level = (max(levels.values()) + 1) if levels else 0
    for index, node_id in enumerate(ids):
        if node_id not in visited:
            levels[node_id] = fallback_level + (index // 4)
    return levels


def _normalize_spec(spec):
    if not isinstance(spec, dict):
        raise DiagramSpecError("Đặc tả sơ đồ không hợp lệ.")

    diagram_type = str(spec.get("diagram_type") or "flowchart").strip().lower()
    if diagram_type not in ("flowchart", "org_chart", "employee_list"):
        raise DiagramSpecError("Loại sơ đồ không được hỗ trợ.")

    raw_nodes = spec.get("nodes") or []
    raw_edges = spec.get("edges") or []
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise DiagramSpecError("Sơ đồ cần ít nhất một node.")
    if len(raw_nodes) > MAX_NODES or len(raw_edges) > MAX_EDGES:
        raise DiagramSpecError(
            f"Sơ đồ vượt giới hạn {MAX_NODES} node hoặc {MAX_EDGES} liên kết."
        )

    nodes, seen = [], set()
    for index, raw in enumerate(raw_nodes):
        if not isinstance(raw, dict):
            continue
        node_id = _clean_id(raw.get("id"), f"node-{index + 1}")
        if node_id in seen:
            node_id = f"{node_id}-{index + 1}"
        seen.add(node_id)
        label = _clean_text(raw.get("label") or raw.get("name") or node_id, 140)
        subtitle = _clean_text(raw.get("subtitle") or raw.get("detail"), 180)
        status = str(raw.get("status") or "normal").lower()
        if status not in ("normal", "start", "end", "approved", "pending", "rejected"):
            status = "normal"
        nodes.append({"id": node_id, "label": label, "subtitle": subtitle, "status": status})

    valid_ids = {node["id"] for node in nodes}
    edges = []
    for raw in raw_edges:
        if not isinstance(raw, dict):
            continue
        source = _clean_id(raw.get("source"), "")
        target = _clean_id(raw.get("target"), "")
        if source in valid_ids and target in valid_ids and source != target:
            edges.append({
                "source": source,
                "target": target,
                "label": _clean_text(raw.get("label"), 80),
            })

    return {
        "title": _clean_text(spec.get("title") or "Sơ đồ dữ liệu", 150),
        "diagram_type": diagram_type,
        "nodes": nodes,
        "edges": edges,
    }


def render_svg(spec):
    """Return normalized metadata and UTF-8 SVG bytes."""
    data = _normalize_spec(spec)
    nodes, edges = data["nodes"], data["edges"]
    levels = _levels(nodes, edges, data["diagram_type"])
    grouped = {}
    for node in nodes:
        grouped.setdefault(levels[node["id"]], []).append(node)

    max_cols = max(len(items) for items in grouped.values())
    width = max(760, 80 + max_cols * NODE_WIDTH + (max_cols - 1) * COL_GAP)
    height = 150 + len(grouped) * (NODE_HEIGHT + LEVEL_GAP)
    positions = {}
    for row_index, level in enumerate(sorted(grouped)):
        row = grouped[level]
        row_width = len(row) * NODE_WIDTH + max(0, len(row) - 1) * COL_GAP
        start_x = (width - row_width) / 2
        y = 104 + row_index * (NODE_HEIGHT + LEVEL_GAP)
        for col_index, node in enumerate(row):
            positions[node["id"]] = (start_x + col_index * (NODE_WIDTH + COL_GAP), y)

    palette = {
        "normal": ("#EEF4FF", "#2563EB"),
        "start": ("#ECFDF5", "#059669"),
        "end": ("#F5F3FF", "#7C3AED"),
        "approved": ("#ECFDF5", "#059669"),
        "pending": ("#FFF7ED", "#EA580C"),
        "rejected": ("#FEF2F2", "#DC2626"),
    }
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(data["title"])}">',
        '<defs><filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="3" stdDeviation="4" flood-opacity="0.16"/></filter><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#64748B"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#F8FAFC" rx="16"/>',
        f'<text x="{width / 2}" y="48" text-anchor="middle" font-family="Arial, sans-serif" font-size="24" font-weight="700" fill="#0F172A">{escape(data["title"])}</text>',
    ]

    for edge in edges:
        sx, sy = positions[edge["source"]]
        tx, ty = positions[edge["target"]]
        x1, y1 = sx + NODE_WIDTH / 2, sy + NODE_HEIGHT
        x2, y2 = tx + NODE_WIDTH / 2, ty
        mid_y = (y1 + y2) / 2
        path = f"M {x1:.1f} {y1:.1f} C {x1:.1f} {mid_y:.1f}, {x2:.1f} {mid_y:.1f}, {x2:.1f} {y2:.1f}"
        svg.append(f'<path d="{path}" fill="none" stroke="#64748B" stroke-width="2" marker-end="url(#arrow)"/>')
        if edge["label"]:
            label_x, label_y = (x1 + x2) / 2, mid_y - 6
            svg.append(f'<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#475569">{escape(edge["label"])}</text>')

    for node in nodes:
        x, y = positions[node["id"]]
        fill, stroke = palette[node["status"]]
        svg.append(f'<g filter="url(#shadow)"><rect x="{x:.1f}" y="{y:.1f}" width="{NODE_WIDTH}" height="{NODE_HEIGHT}" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="2"/></g>')
        label_lines = _text_lines(node["label"], width=27, maximum=2)
        subtitle_lines = _text_lines(node["subtitle"], width=33, maximum=1)
        label_y = y + (31 if subtitle_lines else 40)
        for index, line in enumerate(label_lines):
            svg.append(f'<text x="{x + NODE_WIDTH / 2:.1f}" y="{label_y + index * 18:.1f}" text-anchor="middle" font-family="Arial, sans-serif" font-size="15" font-weight="700" fill="#0F172A">{escape(line)}</text>')
        for index, line in enumerate(subtitle_lines):
            svg.append(f'<text x="{x + NODE_WIDTH / 2:.1f}" y="{y + 67 + index * 15:.1f}" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#475569">{escape(line)}</text>')

    svg.append('</svg>')
    safe_title = re.sub(r"[^a-zA-Z0-9_-]+", "_", data["title"]).strip("_") or "so_do_du_lieu"
    return {
        "title": data["title"],
        "diagram_type": data["diagram_type"],
        "node_count": len(nodes),
        "edge_count": len(edges),
        "filename": f"{safe_title[:80]}.svg",
        "svg_bytes": "".join(svg).encode("utf-8"),
    }

