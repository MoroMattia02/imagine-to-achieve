# Code docs

These pages describe the code of the scene digital twin (`src/twin/`) and of the trust weighting
(`src/rlinf_modified/algorithms/trust.py` and `advantages.py`): which file does what, who imports
whom, which function calls which, the data passed between modules, and the tests. *Why* the
method looks the way it does (equations, propositions, decisions) is in the concept book,
<a href="book.pdf">book.pdf</a>, which CI builds from `docs/book/` and publishes next to these pages.

| Page | Content |
|---|---|
| [Repository layout](layout.md) | the folders and files the twin and the trust weighting touch |
| [Dependencies](deps.md) | the import graph, generated from the code |
| [Files](files.md) | one section per module: role, public names, status |
| [Call flows](flows.md) | what calls what when a chunk runs; the planned integration |
| [Data types](types.md) | the dataclasses and enums passed between modules |
| [Testing](testing.md) | how to run the tests, and which test covers what |
| API reference | generated from the docstrings, one page per module (menu on the left) |

**Diagrams.** Hover over a diagram for its buttons: zoom in, zoom out, reset, full screen.
Ctrl/Cmd + wheel (or a trackpad pinch) zooms at the pointer, drag pans a zoomed diagram, and
double-click resets it.

**Status markers.** *implemented*: code and tests exist. *skeleton*: signatures exist, bodies raise
`NotImplementedError`. *planned*: not in the repo yet; the roadmap work package (WP) is named.
*(check)* marks what was inferred, not run.

**Numbering.** Step, equation, proposition and lemma numbers in the docstrings and on these pages
refer to the thesis proposal (`docs/thesis/thesis_proposal_final.pdf`, 27 Oct 2026), not to the
book. Roadmap WPs are those of `docs/thesis/data_free_roadmap.md`.

**Source of truth.** The repository. These pages and the book are rebuilt from it on every push;
neither the claude.ai project nor a PDF sent in chat is authoritative.

## Building the docs

```bash
pip install -e ".[docs]"                # mkdocs, mkdocs-material, mkdocstrings[python]
python scripts/make_code_deps.py        # after changing an import: regenerate deps.md
python -m pytest tests/test_docs.py -q  # drift tests (standard library only)
mkdocs build --strict                   # the site goes to site/; any warning fails the build
mkdocs serve                            # live preview at http://127.0.0.1:8000
```

Only the three packages of the `docs` extra are needed to build the site: the API pages are read
from the source by griffe, which does not import the code, so neither torch nor MuJoCo has to be
installed. `book.pdf` exists only on the deployed site; locally the link above is dead.

The book: `python scripts/make_book_figures.py docs/book/figures` (needs numpy and matplotlib),
then `make -C docs/book` (needs `latexmk` and a TeX distribution). CI does both.

**Deployment.** `.github/workflows/docs.yml` runs on every push to `twin` and `main`: it builds the
book PDF, runs `tests/test_docs.py` and `mkdocs build --strict`, copies `book.pdf` into the site and
deploys the site to GitHub Pages.
