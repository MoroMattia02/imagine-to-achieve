# Book figures

One TikZ file per figure, `<chapter>_<name>.tex`, `\input` by its chapter (moved out of the
original notes unchanged in D.2). `tests/test_docs.py` checks that each file is input exactly once.

| File | Chapter | Original |
|---|---|---|
| `01_tensor.tex` | 01 | `awyi_optimisation.tex`, the B×G×N batch |
| `02_rl_loop.tex` | 02 | `fpo_from_zero.tex`, the RL loop |
| `03_pipeline.tex`, `03_grounded.tex` | 03 | `thesis_proposal_final.tex`, Figures 1 and 2 |
| `04_loop.tex` … `04_seq.tex` (nine) | 04 | `twin_walkthrough.tex`, Figures 1-9 |

The four images of chapter 02 (`field2d.pdf`, `densities.pdf`, `paths.pdf`, `slopefield.pdf`) are
not committed (`*.pdf` is gitignored). They are regenerated from the formulas of that chapter,
into this folder by default:

    python scripts/make_book_figures.py

CI runs this before it compiles the book; `make -C docs/book` does it when they are missing.
