"""Drift detection — compare the working tree against the graph.

Four findings:
  missing_node     file on disk with no graph node          (blocking)
  ghost_node       graph node whose file is gone            (blocking)
  not_deleted      marked to-be-deleted but still on disk   (blocking)
  unbuilt_planned  planned node with no file yet            (informational —
                   design ahead of code is the point)

Exit code 1 when any blocking drift exists, so hooks and CI can gate on it.
"""
from __future__ import annotations

import os

from .scan import tracked_files
from .store import Graph


def compute_drift(root: str, cfg: dict, graph: Graph) -> dict:
    disk = set(tracked_files(root, cfg))
    file_nodes = graph.file_nodes()
    missing = sorted(disk - set(file_nodes))
    ghosts, unbuilt, not_deleted = [], [], []
    for path, node in sorted(file_nodes.items()):
        on_disk = path in disk or os.path.exists(os.path.join(root, path))
        if node.status == "planned":
            if not on_disk:
                unbuilt.append(path)
            # planned + on disk = built but not synced -> caught as stale status
        elif node.status == "to-be-deleted":
            if on_disk:
                not_deleted.append(path)
            else:
                ghosts.append(path)  # deleted on disk, node awaiting removal
        elif not on_disk:
            ghosts.append(path)
    built_not_synced = [p for p, n in sorted(file_nodes.items())
                        if n.status == "planned"
                        and (p in disk or os.path.exists(os.path.join(root, p)))]
    return {
        "disk": len(disk),
        "nodes": len(file_nodes),
        "missing_node": missing,
        "ghost_node": ghosts,
        "not_deleted": not_deleted,
        "built_not_synced": built_not_synced,
        "unbuilt_planned": unbuilt,
    }


def blocking_count(report: dict, scope: set[str] | None = None) -> int:
    items = (report["missing_node"] + report["ghost_node"]
             + report["not_deleted"] + report["built_not_synced"])
    if scope is not None:
        items = [p for p in items if p in scope]
    return len(items)


def format_report(report: dict, scope: set[str] | None = None) -> str:
    def rows(key: str, mark: str) -> list[str]:
        items = report[key]
        if scope is not None:
            items = [p for p in items if p in scope]
        lines = [f"{key}: {len(items)}"]
        lines += [f"   {mark} {p}" for p in items[:25]]
        if len(items) > 25:
            lines.append(f"   … and {len(items) - 25} more")
        return lines

    out = ["=== graphcoding drift report ==="]
    out.append(f"disk tracked files: {report['disk']} | graph file nodes: {report['nodes']}")
    out += rows("missing_node", "+")
    out += rows("ghost_node", "-")
    out += rows("not_deleted", "!")
    out += rows("built_not_synced", "~")
    out += rows("unbuilt_planned", "?")
    n = blocking_count(report, scope)
    out.append("")
    out.append(f"DRIFT={'YES' if n else 'NONE'} ({n} blocking issue{'s' if n != 1 else ''})")
    if n:
        out.append("fix: graphcoding sync   (then re-run: graphcoding drift)")
    return "\n".join(out)
