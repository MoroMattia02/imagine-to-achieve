# WP D: one documentation system (concept book + code docs)

Written 26 Nov 2026 for branch `twin` (after WP 1.3). Same working rules as the data-free roadmap (`CLAUDE.md`; one sub-package per session; tests first; one commit per sub-package; no push).

## Goal

Replace the growing set of separate PDFs with two maintained documents, both in the repo, both public:

| | Concept book | Code docs |
|---|---|---|
| For | understanding the method: equations, propositions, high-level explanations, diagrams | working with the code: files, dependencies, call flows, data types, how to run |
| Source | LaTeX in `docs/book/` | Markdown + Mermaid in `docs/code/`, API reference generated from docstrings |
| Output | `book.pdf`, built by CI (and locally with `latexmk` if TeX is installed) | a MkDocs site on GitHub Pages, with a link to `book.pdf` |
| Updated when | the method or a decision changes | every work package |

**Source of truth:** the repo. Neither the claude.ai project nor any PDF sent in chat is the source of truth. PDFs are never committed (`*.pdf` is already gitignored); CI builds them.

## Target layout

```
docs/
  book/
    main.tex                 # \include's the chapters; title page; table of contents
    preamble.tex             # packages, colours, box styles, shared notation macros
    chapters/
      00_overview.tex        # the thesis in two pages: question, RQs, loop figure
      01_paper_loop.tex      # from awyi_optimisation_notes.tex
      02_rl_to_fpo.tex       # from fpo_from_zero.tex
      03_method.tex          # from the proposal: Steps 1-9, propositions, assumptions
      04_twin.tex            # from twin_walkthrough.tex
      05_trust_weighting.tex # Step 8 + notes/d1_scale_policy.md
      06_decisions.tex       # short: pointer to open_items_and_deviations.md + key decisions
    figures/                 # one TikZ file per figure, \input by chapters
    import/                  # the original .tex files, dropped in by the user (D.2), deleted after porting
    Makefile                 # latexmk -pdf main.tex
  code/
    index.md                 # what the code docs cover, how to build them, link to book.pdf
    layout.md                # repository map (folder tree)
    deps.md                  # GENERATED dependency graph (Mermaid) between markers
    files.md                 # one section per module: role, public names, status
    flows.md                 # call flows (Mermaid flowcharts / sequence diagrams)
    types.md                 # data types passed between modules
    testing.md               # how to run tests; which test covers what
    reference/               # API pages via mkdocstrings (one per module)
  thesis/                    # unchanged: progress.md, open_items_and_deviations.md, roadmap, plan, guide, notes/
mkdocs.yml
scripts/make_code_deps.py
tests/test_docs.py
.github/workflows/docs.yml
```

## D.1 Skeleton, code docs, generator, CI (one session, about 1 day)

**Dependencies (asking now, as `CLAUDE.md` requires):** add an optional extra `docs` to `pyproject.toml` with `mkdocs`, `mkdocs-material`, `mkdocstrings[python]`. Nothing else. They are only needed to build the site, not to run the code or the tests.

**Tasks**

1. **MkDocs.**
   - `mkdocs.yml` with the Material theme.
   - Mermaid enabled through `pymdownx.superfences` (custom fence `mermaid`).
   - mkdocstrings with the Python handler and `paths: [src]`. Check which `docstring_style` renders the existing docstrings best (check), and record the choice.
   - Navigation in the order of the `docs/code/` list above.
   - mkdocstrings reads the source statically (via griffe), so building the site must not import torch or mujoco. Verify this.
2. **Code docs content.** Port the content of the code map PDF (*The twin codebase: files, dependencies and call flow*; the user provides `twin_code_map.tex` in `docs/book/import/`, or use the PDF text) into `layout.md`, `files.md`, `flows.md`, `types.md` and `testing.md`, **updated to the current commit** (WP 1.3 added `src/twin/compare.py`).
   - TikZ diagrams become Mermaid: the folder tree as a code block, call trees as `flowchart TD`, the integration sequence as `sequenceDiagram`.
   - Keep each page short and factual.
3. **Generated dependency graph.**
   - `scripts/make_code_deps.py` parses `src/twin/*.py` and `src/rlinf_modified/algorithms/{trust,advantages}.py` with `ast`.
   - It collects imports between these modules, including imports inside functions, which it marks as *lazy*.
   - It writes a Mermaid `flowchart` into `docs/code/deps.md` between `<!-- BEGIN GENERATED -->` and `<!-- END GENERATED -->`, with no timestamps, so the output is deterministic.
   - External heavy imports (`torch`, `mujoco`, the repo file loaded by path) appear as dashed nodes.
4. **Drift tests** (`tests/test_docs.py`, standard library only, fast):
   - the generated block in `deps.md` equals a fresh run of the generator;
   - every module in `src/twin/` and the two algorithm files has a section heading in `files.md` and a page in `reference/`;
   - every relative link in `docs/code/*.md` points to an existing file.
5. **Book skeleton.**
   - `main.tex`, `preamble.tex` (macros and box styles taken from the existing notes: `newc`, `keybox`, the `\VC`/`\VW`/`\VS` notation), empty chapter files with their section headings, and a `Makefile`.
   - The book must compile with no chapter content yet.
   - Equation and proposition numbers in docstrings keep referring to **the proposal** (as now), not to the book.
6. **CI** (`.github/workflows/docs.yml`), on push to `twin` and `main`:
   - build the book PDF, e.g. with `xu-cheng/latex-action` on `docs/book/main.tex` (check the action's current version);
   - run `mkdocs build --strict`;
   - copy `book.pdf` into the site folder;
   - deploy to GitHub Pages with the official Pages actions (`actions/upload-pages-artifact`, `actions/deploy-pages`).
   No secrets are needed.
7. **`CLAUDE.md`, a definition of done for every future WP:**
   > A WP is finished only when: (1) docstrings of changed public functions are updated; (2) the affected `docs/code/` pages are updated and `python scripts/make_code_deps.py` has been run; (3) if the method or a decision changed, the matching book chapter and `open_items_and_deviations.md` are updated; (4) `progress.md` is updated; (5) `mkdocs build --strict` and `tests/test_docs.py` pass.

**Acceptance**
- `python -m pytest tests/test_docs.py -q` passes. Changing an import in a twin module without rerunning the generator makes it fail (show this once, then revert).
- `mkdocs build --strict` passes locally, and the API pages show the docstrings of `twin.ik`, `twin.actions`, `twin.compare` and `rlinf_modified.algorithms.trust`.
- `docs/book` compiles to a PDF with the chapter headings (in CI if TeX is not installed on the lab PC; check with `latexmk --version`).
- The existing test subsets still pass.

**User actions (outside Claude Code)**
- On GitHub, fork settings:
  - enable Actions (they are often disabled on forks);
  - Settings → Pages → Source: **GitHub Actions**.
- Pushing a file under `.github/workflows/` over HTTPS needs a token with permission to change workflows. For a fine-grained token, that is *Workflows: Read and write* in addition to *Contents*. Without it the push is rejected.

## D.2 Port the existing notes into the book (one session, about half a day)

**User:** copy these files from the claude.ai project into `docs/book/import/`:
- `awyi_optimisation_notes.tex`
- `fpo_from_zero.tex`
- `thesis_proposal_final.tex`
- `twin_walkthrough.tex`
- `twin_code_map.tex` (needed for D.1 step 2, if not already there)
- `docs/thesis/notes/d1_scale_policy.md` is already in the repo

**Tasks (mechanical port, no rewriting of content):**
1. For each file: strip its preamble and title, move shared macros into `preamble.tex` (resolve name clashes and keep one notation; list every renamed macro in the commit message), and put the body into the matching chapter.
2. Move each TikZ picture into `docs/book/figures/<chapter>_<name>.tex`.
3. `fpo_from_zero.tex` includes four images (`figs/field2d.pdf`, `figs/densities.pdf`, `figs/paths.pdf`, `figs/slopefield.pdf`) that are **not** in the repo or the project. Do not invent them. Write `scripts/make_book_figures.py` (numpy + matplotlib, if matplotlib is installed, otherwise ask) that regenerates them from the formulas in that chapter:
   - the vector field $v(z)=(2-z_1,1-z_2)$;
   - the two-point mixture densities;
   - straight training lines versus trajectories of $v^\star$;
   - the slope field of $v^\star$.
   Output goes to `docs/book/figures/`, and CI runs the script before compiling.
4. Chapter 03 takes the proposal's Sections 2-14 as they are. Do not change the proposal's wording. Where `open_items_and_deviations.md` §3 lists a correction (the proof of P4(b)), add a footnote, not an edit.
5. Chapter 05 adds the content of `notes/d1_scale_policy.md` (converted to LaTeX) after the Step 8 material.
6. Chapter 06 is short: the decisions marked *Approved* in `open_items_and_deviations.md`, with a pointer to that file for the rest.
7. Cross-references between chapters use `\cref` labels. Drop the "walkthrough §x" tags; they become real references.
8. Delete `docs/book/import/` in the same commit once everything is ported.

**Acceptance:** the book compiles without errors or undefined references. Every figure of the original documents is present (redrawn or regenerated). A page-by-page skim against the originals shows no lost section.

## D.3 After the port (Claude in chat, not Claude Code)

Editorial pass over the book: one consistent notation, removal of repetitions between chapters (the twin and method chapters overlap), and an updated overview chapter. Sent back as diffs to the chapter files.

## Order

Run D.1 after WP 1.5 (the end of Phase 1), so Phase 1 is not interrupted; D.2 right after it. From then on every WP updates the docs as part of its definition of done.

## Prompt for D.1

> Read `CLAUDE.md`, `docs/thesis/progress.md` and `docs/thesis/wp_docs_system.md`. Implement only **D.1**. I approve the optional `docs` extra (mkdocs, mkdocs-material, mkdocstrings[python]); install it into the venv under /data/moro. Start with `tests/test_docs.py` and show it failing, then build the generator, the code-doc pages (ported from `docs/book/import/twin_code_map.tex`, updated to the current commit), the book skeleton, the CI workflow and the `CLAUDE.md` definition of done. Run `mkdocs build --strict`, the docs test, the twin and trust test subsets, and paste the summaries. Report whether `latexmk` exists here. Update `progress.md`, make one commit, do not push. Stop and ask if anything in the WP is ambiguous.

## Prompt for D.2

> Read `docs/thesis/wp_docs_system.md`. Implement only **D.2**: port the files in `docs/book/import/` into the book chapters as described, without rewriting their content. Regenerate the four missing figures with `scripts/make_book_figures.py` (ask before adding matplotlib if it is not installed). Compile the book, list any undefined references or warnings, update `progress.md`, make one commit, do not push.
