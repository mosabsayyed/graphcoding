"""Scanner — turn source files into graph nodes and import edges.

Two jobs:
  * scan_repo():  full sweep — migrate an existing repo onto the graph.
  * scan_file():  one file — used by sync after every change.

Python is parsed with ast (imports, top-level defs, module docstring).
JS/TS/JSX/TSX/Vue/Svelte use regex import extraction with relative-path
resolution. Everything else gets a file node with language + first-comment
summary. Deliberately lightweight: the graph's value is the design layer
(summaries, planned nodes, cross-cutting edges an import scan can't see),
not perfect static analysis.
"""
from __future__ import annotations

import ast
import os
import re
import subprocess

from .store import Graph, Node

LANG = {
    ".py": "python", ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".go": "go", ".rs": "rust",
    ".rb": "ruby", ".java": "java", ".kt": "kotlin", ".c": "c", ".h": "c",
    ".cpp": "cpp", ".hpp": "cpp", ".cs": "csharp", ".php": "php",
    ".swift": "swift", ".css": "css", ".scss": "css", ".sql": "sql",
    ".sh": "shell", ".html": "html", ".vue": "vue", ".svelte": "svelte",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
    ".md": "markdown",
}

TEST_MARKERS = (".test.", ".spec.", "_test.")

JS_IMPORT_RE = re.compile(
    r"""(?:import\s+(?:[\w${},*\s]+\s+from\s+)?|export\s+[\w${},*\s]+\s+from\s+|require\()\s*['"]([^'"]+)['"]""")
JS_EXPORT_RE = re.compile(
    r"""export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const)\s+([A-Za-z_$][\w$]*)""")


def language_of(path: str) -> str:
    return LANG.get(os.path.splitext(path)[1], "")


def is_test(path: str) -> bool:
    base = os.path.basename(path)
    return base.startswith("test_") or any(m in base for m in TEST_MARKERS) \
        or "/tests/" in "/" + path or "/__tests__/" in "/" + path


def trackable(path: str, cfg: dict) -> bool:
    segs = path.split("/")
    if any(s in cfg["ignore_segments"] for s in segs):
        return False
    if cfg.get("ignore_tests") and is_test(path):
        return False
    return os.path.splitext(path)[1] in cfg["track_extensions"]


def tracked_files(root: str, cfg: dict) -> list[str]:
    """git ls-files when possible (respects .gitignore); os.walk fallback."""
    try:
        # cached + untracked-but-not-ignored: the graph should see WIP files too
        out = subprocess.run(
            ["git", "-C", root, "ls-files", "--cached", "--others",
             "--exclude-standard"],
            capture_output=True, text=True, check=True).stdout
        # a file deleted from the worktree is still in the index — drop it
        files = [p for p in out.splitlines()
                 if os.path.exists(os.path.join(root, p))]
    except (subprocess.CalledProcessError, FileNotFoundError):
        files = []
        for dirpath, dirnames, filenames in os.walk(root):
            rel = os.path.relpath(dirpath, root)
            dirnames[:] = [d for d in dirnames
                           if d not in cfg["ignore_segments"] and not d.startswith(".")]
            for fn in filenames:
                files.append(os.path.normpath(os.path.join(rel, fn)).replace(os.sep, "/"))
    return sorted(p for p in files if trackable(p, cfg))


# -- per-language extraction --------------------------------------------------
def _py_extract(root: str, path: str, src: str):
    """Returns (summary, imports, symbols). Never raises on bad source."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return "", [], []
    doc = ast.get_docstring(tree) or ""
    summary = doc.strip().splitlines()[0] if doc.strip() else ""
    modules = []
    for stmt in ast.walk(tree):
        if isinstance(stmt, ast.Import):
            modules.extend(a.name for a in stmt.names)
        elif isinstance(stmt, ast.ImportFrom):
            prefix = "." * stmt.level
            base = prefix + (stmt.module or "")
            modules.append(base)
            # `from pkg import mod` — each name may itself be a module file
            for a in stmt.names:
                modules.append((base + "." + a.name) if stmt.module
                               else prefix + a.name)
    imports = []
    for m in modules:
        target = _py_resolve(root, path, m)
        if target:
            imports.append(target)
    symbols = []
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append((stmt.name, "CodeFunction", ast.get_docstring(stmt) or ""))
        elif isinstance(stmt, ast.ClassDef):
            symbols.append((stmt.name, "CodeClass", ast.get_docstring(stmt) or ""))
    return summary, sorted(set(imports)), symbols


def _py_resolve(root: str, path: str, module: str) -> str | None:
    """Map a python module string to a repo-relative file, if it lives in-repo."""
    if module.startswith("."):
        level = len(module) - len(module.lstrip("."))
        base = os.path.dirname(path)
        for _ in range(level - 1):
            base = os.path.dirname(base)
        tail = module.lstrip(".")
        parts = ([base] if base else []) + (tail.split(".") if tail else [])
        cand = "/".join(p for p in parts if p)
    else:
        cand = module.replace(".", "/")
    for suffix in (".py", "/__init__.py"):
        rel = cand + suffix
        if os.path.exists(os.path.join(root, rel)):
            return rel
    # src-layout: src/<pkg>/...
    for prefix in ("src/",):
        for suffix in (".py", "/__init__.py"):
            rel = prefix + cand + suffix
            if os.path.exists(os.path.join(root, rel)):
                return rel
    return None


def _js_resolve(root: str, path: str, spec: str) -> str | None:
    """Resolve a relative (or @/ aliased) JS/TS import to a repo file."""
    if spec.startswith("@/"):
        base_dir = "src" if os.path.isdir(os.path.join(root, "src")) else ""
        cand = os.path.normpath(os.path.join(base_dir, spec[2:]))
    elif spec.startswith("."):
        cand = os.path.normpath(os.path.join(os.path.dirname(path), spec))
    else:
        return None  # external package
    cand = cand.replace(os.sep, "/")
    exts = ["", ".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte", ".css", ".json"]
    for ext in exts:
        rel = cand + ext
        if os.path.isfile(os.path.join(root, rel)):
            return rel
    for ext in (".ts", ".tsx", ".js", ".jsx"):
        rel = cand + "/index" + ext
        if os.path.isfile(os.path.join(root, rel)):
            return rel
    return None


def _first_comment(src: str) -> str:
    """First comment or heading line — a serviceable auto-summary."""
    for line in src.splitlines()[:15]:
        s = line.strip()
        for prefix in ("#", "//", "/*", "*", "--", "<!--"):
            if s.startswith(prefix):
                text = s.lstrip("#/*-<!– ").rstrip("*/->").strip()
                if len(text) > 8 and not text.lower().startswith(("eslint", "ts-", "noqa", "prettier")):
                    return text
    return ""


def node_type_for(path: str, src: str = "") -> str:
    base = os.path.basename(path)
    ext = os.path.splitext(path)[1]
    if ext in (".json", ".yaml", ".yml", ".toml"):
        return "ConfigFile"
    if ext == ".md":
        return "Doc"
    if path.endswith(".d.ts"):
        return "TypeDef"
    if ext in (".tsx", ".jsx") and base[:1].isupper():
        return "Component"
    if re.match(r"^use[A-Z]", base) and ext in (".ts", ".tsx", ".js", ".jsx"):
        return "Hook"
    return "CodeFile"


def scan_file(root: str, path: str, cfg: dict) -> tuple[Node, list[Node]]:
    """Build the node (+ optional symbol sub-nodes) for one file."""
    full = os.path.join(root, path)
    try:
        with open(full, encoding="utf-8", errors="replace") as f:
            src = f.read()
    except OSError:
        src = ""
    lang = language_of(path)
    summary, imports, symbols = "", [], []
    if lang == "python":
        summary, imports, symbols = _py_extract(root, path, src)
    elif lang in ("typescript", "javascript", "vue", "svelte"):
        for spec in JS_IMPORT_RE.findall(src):
            t = _js_resolve(root, path, spec)
            if t:
                imports.append(t)
        imports = sorted(set(imports))
        if cfg.get("scan_symbols"):
            symbols = [(m, "CodeFunction", "") for m in JS_EXPORT_RE.findall(src)]
    if not summary:
        summary = _first_comment(src)
    node = Node(name=path, type=node_type_for(path, src), status="ok",
                language=lang, summary=summary,
                edges=[{"to": t, "type": "IMPORTS"} for t in imports if t != path])
    subs = []
    if cfg.get("scan_symbols") and symbols:
        for sname, stype, sdoc in symbols:
            if sname.startswith("_"):
                continue
            ssum = sdoc.strip().splitlines()[0] if sdoc.strip() else ""
            subs.append(Node(name=f"{path}::{sname}", type=stype, status="ok",
                             language=lang, summary=ssum))
            node.add_edge(f"{path}::{sname}", "CONTAINS")
    return node, subs


def scan_repo(root: str, cfg: dict, graph: Graph) -> dict:
    """Full sweep. Preserves human-written summaries and planned/delete marks."""
    files = tracked_files(root, cfg)
    added = updated = 0
    for path in files:
        node, subs = scan_file(root, path, cfg)
        old = graph.nodes.get(path)
        if old:
            # never clobber intent: keep richer summary and lifecycle statuses
            if old.summary and not node.summary:
                node.summary = old.summary
            if len(old.summary) > len(node.summary):
                node.summary = old.summary
            if old.status == "to-be-deleted":
                node.status = old.status
            updated += 1
        else:
            added += 1
        graph.nodes[path] = node
        for s in subs:
            prev = graph.nodes.get(s.name)
            if prev and len(prev.summary) > len(s.summary):
                s.summary = prev.summary
            graph.nodes[s.name] = s
    return {"files": len(files), "added": added, "updated": updated}
