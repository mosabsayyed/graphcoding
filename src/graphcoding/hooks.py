"""Git hook installer — the enforcement layer.

pre-commit : blocks the commit when a file being committed drifts from the
             graph. Scoped to staged files so teammates' un-graphed WIP never
             deadlocks your commit.
post-commit: syncs the graph with what was just committed (belt + braces; the
             pre-commit gate should already have forced a sync).

Existing hooks are preserved: ours is appended behind a marker block.
"""
from __future__ import annotations

import os
import stat

MARKER_BEGIN = "# >>> graphcoding hook >>>"
MARKER_END = "# <<< graphcoding hook <<<"

PRE_COMMIT = f"""{MARKER_BEGIN}
# Block the commit if any STAGED file drifts from .graphcoding/graph.jsonl
if command -v graphcoding >/dev/null 2>&1; then
  graphcoding drift --staged || {{
    echo ""
    echo "[graphcoding] staged files drift from the graph."
    echo "[graphcoding] run: graphcoding sync --staged && git add .graphcoding/graph.jsonl"
    exit 1
  }}
fi
{MARKER_END}"""

POST_COMMIT = f"""{MARKER_BEGIN}
# Keep the graph in step with what was just committed
if command -v graphcoding >/dev/null 2>&1; then
  graphcoding sync --commit HEAD --quiet || true
fi
{MARKER_END}"""


def _install_one(hooks_dir: str, name: str, body: str) -> str:
    path = os.path.join(hooks_dir, name)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            content = f.read()
        if MARKER_BEGIN in content:
            head, _, rest = content.partition(MARKER_BEGIN)
            _, _, tail = rest.partition(MARKER_END)
            content = head.rstrip("\n") + "\n" + body + tail
        else:
            content = content.rstrip("\n") + "\n\n" + body + "\n"
    else:
        content = "#!/bin/sh\n\n" + body + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def install(root: str) -> list[str]:
    hooks_dir = os.path.join(root, ".git", "hooks")
    if not os.path.isdir(hooks_dir):
        raise SystemExit("not a git repository (no .git/hooks) — run inside a git repo")
    return [
        _install_one(hooks_dir, "pre-commit", PRE_COMMIT),
        _install_one(hooks_dir, "post-commit", POST_COMMIT),
    ]
