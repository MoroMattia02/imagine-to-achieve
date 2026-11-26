"""WP D.1: drift tests for the code docs (docs/code/) and the book skeleton (docs/book/).

Acceptance (wp_docs_system.md, D.1 task 4); standard library only, fast:
- the generated block of ``docs/code/deps.md`` equals a fresh run of ``scripts/make_code_deps.py``;
- every module of ``src/twin/`` and the two algorithm files (``trust.py``, ``advantages.py``) has a
  section heading in ``files.md`` and a page in ``reference/`` (and the nav lists that page);
- every relative link in ``docs/code/**/*.md`` points to an existing file inside ``docs/code/``.

Also checked here: the generator itself on a small synthetic package (eager, lazy and by-path
imports, determinism), and that ``docs/book/main.tex`` includes the seven chapter files, since
TeX is not installed on every machine that runs the tests.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
import textwrap
from pathlib import Path
from types import ModuleType
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
CODE_DOCS = ROOT / "docs" / "code"
REFERENCE = CODE_DOCS / "reference"
GENERATOR = ROOT / "scripts" / "make_code_deps.py"
BOOK = ROOT / "docs" / "book"
BEGIN, END = "<!-- BEGIN GENERATED -->", "<!-- END GENERATED -->"
BOOK_CHAPTERS = (
    "00_overview",
    "01_paper_loop",
    "02_rl_to_fpo",
    "03_method",
    "04_twin",
    "05_trust_weighting",
    "06_decisions",
)


def _documented_modules() -> list[str]:
    """Dotted names of the modules the code docs must cover (``__init__.py`` holds no code)."""
    twin = sorted(
        f"twin.{p.stem}" for p in (ROOT / "src" / "twin").glob("*.py") if p.stem != "__init__"
    )
    return twin + ["rlinf_modified.algorithms.advantages", "rlinf_modified.algorithms.trust"]


def _load_generator() -> ModuleType:
    assert GENERATOR.is_file(), f"missing generator {GENERATOR.relative_to(ROOT)}"
    spec = importlib.util.spec_from_file_location("_make_code_deps", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look the module up while the class is built
    spec.loader.exec_module(module)
    return module


def _strip_code(md: str) -> str:
    """Markdown without fenced code blocks and inline code (links there do not count)."""
    md = re.sub(r"^(```|~~~).*?^\1[ \t]*$", "", md, flags=re.S | re.M)
    return re.sub(r"`[^`\n]*`", "", md)


def _headings(md: str) -> list[str]:
    md = re.sub(r"^(```|~~~).*?^\1[ \t]*$", "", md, flags=re.S | re.M)
    return [
        m.group(1).replace("`", "").strip()
        for m in re.finditer(r"^#{1,6}[ \t]+(.+?)[ \t#]*$", md, re.M)
    ]


# --- deps.md: the generated block --------------------------------------------------------------


def _generated_block(text: str) -> str:
    assert text.count(BEGIN) == 1 and text.count(END) == 1, (
        "need exactly one BEGIN and one END marker"
    )
    start, stop = text.index(BEGIN) + len(BEGIN), text.index(END)
    assert start <= stop, "END marker before BEGIN marker"
    return text[start:stop]


def test_deps_block_equals_a_fresh_run():
    deps = CODE_DOCS / "deps.md"
    assert deps.is_file(), "missing docs/code/deps.md"
    committed = _generated_block(deps.read_text(encoding="utf-8"))
    fresh = _load_generator().render_block(ROOT)
    assert committed == fresh, "docs/code/deps.md is stale: run python scripts/make_code_deps.py"


def test_deps_block_has_a_node_for_every_module():
    block = _load_generator().render_block(ROOT)
    for module in _documented_modules():
        node = module.replace(".", "_")
        assert re.search(rf"^\s*{node}\[", block, re.M), f"no graph node for {module}"


def test_internal_imports_have_no_cycle():
    """deps.md says so; checked on the same edges the graph is drawn from."""
    gen = _load_generator()
    modules = set(_documented_modules())
    graph: dict[str, set[str]] = {m: set() for m in modules}
    for e in gen.collect(ROOT, gen.module_files(ROOT)):
        if e.target in modules:
            graph[e.importer].add(e.target)
    done: set[str] = set()

    def visit(m: str, path: tuple[str, ...]) -> None:
        assert m not in path, f"import cycle: {' -> '.join(path + (m,))}"
        if m not in done:
            for t in sorted(graph[m]):
                visit(t, path + (m,))
            done.add(m)

    for m in sorted(modules):
        visit(m, ())


# --- the generator, on a synthetic package -------------------------------------------------------

_SYNTHETIC = {
    "src/twin/a.py": """
        from __future__ import annotations
        import sys
        import numpy as np
        from twin.b import g, f
        if sys.platform == "linux":
            import mujoco

        def h():
            import torch
            return torch

        class C:
            def m(self):
                from twin import b
                return b
    """,
    "src/twin/b.py": """
        import importlib.util
        from pathlib import Path
        ROOT = Path(__file__).parent
        TARGET = ROOT / "vendor" / "pkg" / "loaded.py"

        def f():
            return importlib.util.spec_from_file_location("x", TARGET)

        def g():
            pass
    """,
    "src/twin/__init__.py": "",
    "src/rlinf_modified/algorithms/trust.py": "import torch\n",
    "src/rlinf_modified/algorithms/advantages.py": """
        import torch
        from rlinf_modified.algorithms.trust import x
    """,
}


def _synthetic_root(tmp: str) -> Path:
    root = Path(tmp)
    for rel, src in _SYNTHETIC.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(src), encoding="utf-8")
    return root


def test_generator_classifies_imports():
    gen = _load_generator()
    with tempfile.TemporaryDirectory() as tmp:
        root = _synthetic_root(tmp)
        edges = {(e.importer, e.target): e for e in gen.collect(root, gen.module_files(root))}
    assert set(edges) == {
        ("twin.a", "twin.b"),
        ("twin.a", "mujoco"),
        ("twin.a", "torch"),
        ("twin.b", "vendor/pkg/loaded.py"),
        ("rlinf_modified.algorithms.advantages", "rlinf_modified.algorithms.trust"),
        ("rlinf_modified.algorithms.advantages", "torch"),
        ("rlinf_modified.algorithms.trust", "torch"),
    }, "numpy, stdlib and __future__ must not be edges; __init__.py is not a module"
    ab = edges[("twin.a", "twin.b")]
    assert ab.names == ("b", "f", "g") and ab.eager and ab.lazy_in == ("C.m",)
    assert edges[("twin.a", "mujoco")].eager, "an import under a module-level `if` is eager"
    torch_a = edges[("twin.a", "torch")]
    assert not torch_a.eager and torch_a.lazy_in == ("h",)
    by_path = edges[("twin.b", "vendor/pkg/loaded.py")]
    assert by_path.kind == "by path" and not by_path.eager and by_path.lazy_in == ("f",)


def test_generator_output_is_deterministic_and_marks_externals():
    gen = _load_generator()
    with tempfile.TemporaryDirectory() as tmp:
        root = _synthetic_root(tmp)
        files = gen.module_files(root)
        block = gen.render_block(root, files)
        assert block == gen.render_block(root, list(reversed(files))), "depends on file order"
        assert block == gen.render_block(root, files), "not reproducible"
    assert not re.search(r"\d{4}-\d{2}-\d{2}|\d{2}:\d{2}:\d{2}", block), "no dates or times"
    assert "twin_a -.->|lazy| ext_torch" in block
    assert "twin_a --> twin_b" in block
    assert re.search(r"ext_torch\[.*\]:::external", block), "heavy imports are dashed nodes"
    assert re.search(r"ext_vendor_pkg_loaded_py\[.*loaded\.py.*\]:::external", block)
    assert "uses numpy" in block, "light third-party imports are named in the node label"


def test_generator_replaces_only_the_marked_block():
    gen = _load_generator()
    text = f"intro\n{BEGIN}\nold\n{END}\noutro\n"
    assert gen.replace_block(text, "\nnew\n") == f"intro\n{BEGIN}\nnew\n{END}\noutro\n"


# --- files.md and reference/ ---------------------------------------------------------------------


def test_every_module_has_a_section_in_files_md():
    files_md = CODE_DOCS / "files.md"
    assert files_md.is_file(), "missing docs/code/files.md"
    titles = {h.split()[0] for h in _headings(files_md.read_text(encoding="utf-8")) if h}
    missing = [m for m in _documented_modules() if m not in titles]
    assert not missing, f"files.md has no section heading for {missing}"


def test_every_module_has_a_reference_page():
    for module in _documented_modules():
        page = REFERENCE / f"{module}.md"
        assert page.is_file(), f"missing reference page {page.relative_to(ROOT)}"
        text = page.read_text(encoding="utf-8")
        assert re.search(rf"^::: {re.escape(module)}[ \t]*$", text, re.M), (
            f"{page.name}: no '::: {module}'"
        )


def test_no_reference_page_for_a_module_that_does_not_exist():
    pages = sorted(p.stem for p in REFERENCE.glob("*.md"))
    assert pages == sorted(_documented_modules())


def test_nav_lists_every_reference_page():
    config = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    missing = [m for m in _documented_modules() if f"reference/{m}.md" not in config]
    assert not missing, f"mkdocs.yml nav does not list the reference pages of {missing}"


# --- links -------------------------------------------------------------------------------------

_INLINE_LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^)]*[\"'])?\s*\)")
_REF_DEFINITION = re.compile(r"^[ \t]{0,3}\[[^\]]+\]:[ \t]*<?(\S+?)>?(?:[ \t].*)?$", re.M)
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def test_relative_links_point_to_existing_files():
    pages = sorted(CODE_DOCS.rglob("*.md"))
    assert pages, "no pages in docs/code/"
    broken = []
    for page in pages:
        md = _strip_code(page.read_text(encoding="utf-8"))
        targets = _INLINE_LINK.findall(md) + _REF_DEFINITION.findall(md)
        for target in targets:
            if _SCHEME.match(target) or target.startswith(("#", "/")):
                continue  # external link, anchor on the same page, or site-absolute (mkdocs warns)
            rel = unquote(target.split("#", 1)[0].split("?", 1)[0])
            resolved = (page.parent / rel).resolve()
            if not resolved.exists():
                broken.append(f"{page.relative_to(ROOT)}: {target} (missing)")
            elif not resolved.is_relative_to(CODE_DOCS.resolve()):
                broken.append(
                    f"{page.relative_to(ROOT)}: {target} (outside docs/code/, not in the site)"
                )
    assert not broken, "broken links:\n" + "\n".join(broken)


def test_link_checker_sees_inline_and_reference_links():
    md = (
        "a [x](files.md#y) b ![i](img.png 'title') `[no](skip.md)`\n"
        "[ref]: <deps.md>\n```\n[no](no.md)\n```\n"
    )
    found = _INLINE_LINK.findall(_strip_code(md)) + _REF_DEFINITION.findall(_strip_code(md))
    assert sorted(found) == ["deps.md", "files.md#y", "img.png"]


# --- the book skeleton -------------------------------------------------------------------------


def test_book_main_includes_the_seven_chapters():
    main = (BOOK / "main.tex").read_text(encoding="utf-8")
    main = re.sub(r"(?<!\\)%.*", "", main)  # drop comments
    included = tuple(re.findall(r"\\include\{chapters/([^}]+)\}", main))
    assert included == BOOK_CHAPTERS
    for name in BOOK_CHAPTERS:
        chapter = (BOOK / "chapters" / f"{name}.tex").read_text(encoding="utf-8")
        assert re.search(r"^\\chapter\{.+\}", chapter, re.M), f"{name}.tex has no \\chapter heading"
    for target in re.findall(r"\\input\{([^}]+)\}", main):
        path = BOOK / (target if target.endswith(".tex") else f"{target}.tex")
        assert path.is_file(), f"main.tex inputs a missing file {target}"
