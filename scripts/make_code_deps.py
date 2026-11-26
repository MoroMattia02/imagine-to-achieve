"""Write the import graph of the twin and trust-weighting code into docs/code/deps.md (WP D.1).

Parses ``src/twin/*.py`` and ``src/rlinf_modified/algorithms/{advantages,trust}.py`` with ``ast``
(nothing is imported, so torch and mujoco are not needed) and writes a Mermaid flowchart and a
table of the imported names between ``<!-- BEGIN GENERATED -->`` and ``<!-- END GENERATED -->``
in ``docs/code/deps.md``. The text outside the markers is left alone.

- An edge ``A --> B`` means "A imports from B". An import inside a function or method is *lazy*:
  it runs when the function is first called. Lazy-only edges are dotted and labelled ``lazy``.
- The heavy external libraries (``torch``, ``mujoco``) and files loaded by path with
  ``importlib.util.spec_from_file_location`` are dashed nodes. Other third-party imports (numpy)
  are named in the importing module's node label; the standard library is left out.
- Everything is sorted and there are no timestamps: a rerun on unchanged code writes the same
  bytes (``tests/test_docs.py`` checks this).

Usage: python scripts/make_code_deps.py [--check]
  --check   exit with status 1 if deps.md is not up to date, without writing it.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPS_MD = Path("docs") / "code" / "deps.md"
BEGIN = "<!-- BEGIN GENERATED -->"
END = "<!-- END GENERATED -->"
HEAVY = ("mujoco", "torch")  # drawn as dashed nodes
INTERNAL = ("twin", "rlinf_modified")  # top-level packages of src/
ALGORITHM_FILES = ("advantages.py", "trust.py")
# (dotted package, folder shown as the subgraph title), in drawing order
GROUPS = (("twin", "src/twin/"), ("rlinf_modified.algorithms", "src/rlinf_modified/algorithms/"))


@dataclass(frozen=True)
class Edge:
    """All imports of one target by one module, merged."""

    importer: str  # dotted module name
    target: str  # dotted module, heavy top-level package, or repo-relative path of a file
    kind: str  # "import" or "by path"
    names: tuple[str, ...]  # imported names, sorted; () when the whole module is imported
    eager: bool  # at least one import runs when the module is imported (also under if/try)
    lazy_in: tuple[str, ...]  # functions or methods (qualified names) that import it when called


def module_files(root: Path) -> list[Path]:
    """The documented modules: ``src/twin/*.py`` except ``__init__.py``, then the two files."""
    twin = sorted(p for p in (root / "src" / "twin").glob("*.py") if p.name != "__init__.py")
    algorithms = [root / "src" / "rlinf_modified" / "algorithms" / n for n in ALGORITHM_FILES]
    for path in algorithms:
        if not path.is_file():
            raise FileNotFoundError(f"expected {path.relative_to(root)}")
    return twin + algorithms


def module_name(root: Path, path: Path) -> str:
    return ".".join(path.relative_to(root / "src").with_suffix("").parts)


def _node_id(target: str) -> str:
    return re.sub(r"\W", "_", target)


def _scoped(node: ast.AST, scope: tuple[tuple[str, str], ...] = ()) -> Iterator:
    """Every node with the enclosing (kind, name) scopes; kind is "def" or "class"."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield from _scoped(child, scope + (("def", child.name),))
        elif isinstance(child, ast.ClassDef):
            yield from _scoped(child, scope + (("class", child.name),))
        elif isinstance(child, ast.Lambda):
            yield from _scoped(child, scope + (("def", "<lambda>"),))
        else:
            yield child, scope
            yield from _scoped(child, scope)


def _function(scope: tuple[tuple[str, str], ...]) -> str | None:
    """Qualified name of the innermost enclosing function, None at module or class level."""
    if not any(kind == "def" for kind, _ in scope):
        return None
    return ".".join(name for _, name in scope)


def _path_parts(expr: ast.expr) -> list[str]:
    """String pieces of a path expression such as ``ROOT / "a" / "b.py"`` or ``Path("a", "b")``."""
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return [expr.value]
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Div):
        return _path_parts(expr.left) + _path_parts(expr.right)
    if isinstance(expr, ast.Call):
        return [p for a in expr.args for p in _path_parts(a)]
    return []


def _by_path_target(call: ast.Call, assignments: dict[str, ast.expr]) -> str:
    location = call.args[1] if len(call.args) > 1 else None
    for kw in call.keywords:
        if kw.arg == "location":
            location = kw.value
    if isinstance(location, ast.Name) and location.id in assignments:
        location = assignments[location.id]
    parts = _path_parts(location) if location is not None else []
    return "/".join(parts) if parts else "(file loaded by path)"


def _resolve_from(module: str, node: ast.ImportFrom) -> str:
    if not node.level:
        return node.module or ""
    base = module.split(".")[: -node.level]
    return ".".join(base + ([node.module] if node.module else []))


def _analyse(path: Path, module: str, known: set[str]) -> tuple[list[Edge], tuple[str, ...]]:
    """Edges out of one module, and its other (light) third-party imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assignments = {
        t.id: n.value
        for n in tree.body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name)
    }
    found: dict[tuple[str, str], tuple[set[str], list[bool], set[str]]] = {}
    light: set[str] = set()

    def add(target: str, kind: str, names: Sequence[str], scope) -> None:
        names_set, eager, lazy_in = found.setdefault((target, kind), (set(), [False], set()))
        names_set.update(names)
        func = _function(scope)
        if func is None:
            eager[0] = True
        else:
            lazy_in.add(func)

    def classify(dotted: str, names: Sequence[str], scope) -> None:
        top = dotted.split(".")[0]
        if dotted in known:
            add(dotted, "import", names, scope)
        elif top in HEAVY:
            add(top, "import", names, scope)
        elif top in INTERNAL:
            add(dotted, "import", names, scope)  # internal, outside the documented set
        elif top and top not in sys.stdlib_module_names:
            light.add(top)

    for node, scope in _scoped(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                classify(alias.name, (), scope)
        elif isinstance(node, ast.ImportFrom):
            source = _resolve_from(module, node)
            for alias in node.names:
                submodule = f"{source}.{alias.name}"
                if submodule in known:  # from twin import ik
                    classify(submodule, (alias.name,), scope)
                else:
                    classify(source, (alias.name,), scope)
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name == "spec_from_file_location":
                add(_by_path_target(node, assignments), "by path", (), scope)

    edges = [
        Edge(module, target, kind, tuple(sorted(names)), eager[0], tuple(sorted(lazy)))
        for (target, kind), (names, eager, lazy) in found.items()
        if target != module
    ]
    return sorted(edges, key=lambda e: (e.target, e.kind)), tuple(sorted(light))


def _analyse_all(root: Path, files: Sequence[Path]):
    files = sorted(files, key=lambda p: module_name(root, p))
    known = {module_name(root, p) for p in files}
    modules, edges = {}, []
    for path in files:
        name = module_name(root, path)
        module_edges, light = _analyse(path, name, known)
        modules[name] = (path.name, light)
        edges.extend(module_edges)
    return modules, sorted(edges, key=lambda e: (e.importer, e.target, e.kind))


def collect(root: Path, files: Sequence[Path]) -> list[Edge]:
    """Import edges between the given module files, sorted by (importer, target)."""
    return _analyse_all(root, files)[1]


def _when(edge: Edge) -> str:
    lazy = ", ".join(f"`{f}`" for f in edge.lazy_in)
    if edge.eager and lazy:
        return f"at import; lazy in {lazy}"
    return "at import" if edge.eager else f"lazy, in {lazy}"


def render_block(root: Path = ROOT, files: Sequence[Path] | None = None) -> str:
    """The text between the markers (it starts and ends with a newline)."""
    modules, edges = _analyse_all(root, module_files(root) if files is None else files)
    lines = [
        "",
        "<!-- Written by scripts/make_code_deps.py; do not edit by hand, rerun the script. -->",
        "",
        "```mermaid",
        "flowchart TD",
    ]
    for package, title in GROUPS:
        members = [m for m in modules if m.rsplit(".", 1)[0] == package]
        if not members:
            continue
        lines.append(f'    subgraph {_node_id(package)}["{title}"]')
        for m in members:
            filename, light = modules[m]
            label = filename + (f"<br/>uses {', '.join(light)}" if light else "")
            lines.append(f'        {_node_id(m)}["{label}"]')
        lines.append("    end")
    externals = {}
    for e in edges:
        if e.kind == "by path":
            externals[e.target] = f"{e.target.rsplit('/', 1)[-1]}<br/>loaded by path"
        elif e.target not in modules:
            externals[e.target] = e.target
    for target in sorted(externals, key=_node_id):
        style = (
            ":::external" if target.split(".")[0] in HEAVY or "/" in target or "(" in target else ""
        )
        lines.append(f'    ext_{_node_id(target)}["{externals[target]}"]{style}')
    for e in edges:
        dst = _node_id(e.target) if e.target in modules else f"ext_{_node_id(e.target)}"
        if e.kind == "by path":
            arrow = "-->|by path|" if e.eager else "-.->|by path, lazy|"
        else:
            arrow = "-->" if e.eager else "-.->|lazy|"
        lines.append(f"    {_node_id(e.importer)} {arrow} {dst}")
    lines += ["    classDef external stroke-dasharray: 5 5", "```", ""]
    lines += ["| Module | Imports from | Names | When |", "|---|---|---|---|"]
    for e in edges:
        if e.kind == "by path":
            names = "the whole file, with `importlib`"
        else:
            names = ", ".join(f"`{n}`" for n in e.names) if e.names else "the module"
        lines.append(f"| `{e.importer}` | `{e.target}` | {names} | {_when(e)} |")
    return "\n".join(lines) + "\n\n"


def replace_block(text: str, block: str) -> str:
    """``text`` with everything between the two markers replaced by ``block``."""
    if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(END) < text.index(BEGIN):
        raise ValueError(f"need exactly one {BEGIN} followed by one {END}")
    head, rest = text.split(BEGIN)
    _, tail = rest.split(END)
    return head + BEGIN + block + END + tail


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="fail if deps.md is stale; write nothing"
    )
    args = parser.parse_args(argv)
    path = ROOT / DEPS_MD
    text = path.read_text(encoding="utf-8")
    updated = replace_block(text, render_block(ROOT))
    if args.check:
        if updated != text:
            print(
                f"{DEPS_MD.as_posix()} is stale: run python scripts/make_code_deps.py",
                file=sys.stderr,
            )
            return 1
        print(f"{DEPS_MD.as_posix()} is up to date")
        return 0
    if updated != text:
        path.write_text(updated, encoding="utf-8", newline="\n")
        print(f"updated {DEPS_MD.as_posix()}")
    else:
        print(f"{DEPS_MD.as_posix()} unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
