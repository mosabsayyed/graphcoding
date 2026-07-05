"""Sync — reconcile the graph with a set of changed files.

Sources of the change set:
  --staged        files staged right now (pre-commit)
  --commit REF    files changed in a commit (post-commit, default HEAD)
  --files a b c   explicit list
  (none)          every drifting file from a fresh drift report

Rules:
  * added/modified file  -> rescan; planned becomes ok (the design was built);
                            human summaries survive unless the file's own
                            docstring/comment is richer
  * deleted file         -> node removed, along with edges pointing at it
  * to-be-deleted + gone -> node removed (deletion completed)
"""
from __future__ import annotations

import os
import subprocess

from .drift import compute_drift
from .scan import scan_file, trackable
from .store import Graph


def _git_changed(root: str, staged: bool, commit: str | None) -> list[tuple[str, str]]:
    if staged:
        cmd = ["git", "-C", root, "diff", "--cached", "--name-status"]
    else:
        ref = commit or "HEAD"
        cmd = ["git", "-C", root, "diff", "--name-status", f"{ref}~1..{ref}"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    changes = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            changes.append((parts[-1], parts[0][0]))  # renames: new path wins
    return changes


def sync(root: str, cfg: dict, graph: Graph,
         staged: bool = False, commit: str | None = None,
         files: list[str] | None = None) -> dict:
    if files:
        changes = [(f, "D" if not os.path.exists(os.path.join(root, f)) else "M")
                   for f in files]
    elif staged or commit:
        changes = _git_changed(root, staged, commit)
    else:
        rep = compute_drift(root, cfg, graph)
        changes = ([(p, "M") for p in rep["missing_node"] + rep["built_not_synced"]]
                   + [(p, "D") for p in rep["ghost_node"] + rep["not_deleted"]])
        # not_deleted files still exist; deleting the node is wrong — the FILE
        # should go. Surface them instead of silently "fixing" the graph.
        changes = [(p, s) for p, s in changes if p not in rep["not_deleted"]]

    upserted, removed, skipped = [], [], []
    for path, st in changes:
        if not trackable(path, cfg):
            continue
        if st == "D":
            if os.path.exists(os.path.join(root, path)):
                skipped.append(path)  # marked deleted in git but still on disk
                continue
            # drop the file node and its symbol sub-nodes
            for name in [n for n in graph.nodes
                         if n == path or n.startswith(path + "::")]:
                graph.delete(name)
            removed.append(path)
        else:
            node, subs = scan_file(root, path, cfg)
            old = graph.nodes.get(path)
            if old:
                if len(old.summary) > len(node.summary):
                    node.summary = old.summary
                # scanner owns IMPORTS; every hand-recorded edge type survives
                for e in old.edges:
                    if e["type"] != "IMPORTS":
                        node.add_edge(e["to"], e["type"])
            graph.nodes[path] = node
            for s in subs:
                prev = graph.nodes.get(s.name)
                if prev and len(prev.summary) > len(s.summary):
                    s.summary = prev.summary
                graph.nodes[s.name] = s
            upserted.append(path)
    graph.save()
    return {"upserted": upserted, "removed": removed, "skipped": skipped}
