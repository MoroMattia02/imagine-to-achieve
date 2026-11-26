# Book figures

One TikZ file per figure, `<chapter>_<name>.tex`, `\input` by the chapters (added in D.2).

The four images of chapter 02 (`field2d.pdf`, `densities.pdf`, `paths.pdf`, `slopefield.pdf`) are
not committed (`*.pdf` is gitignored). They are regenerated from the formulas of that chapter:

    python scripts/make_book_figures.py docs/book/figures

CI runs this before it compiles the book.
