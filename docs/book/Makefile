# Concept book. make: build main.pdf (needs latexmk and a TeX distribution).
# make figures: regenerate the images of chapter 02 (needs numpy and matplotlib).
# CI (.github/workflows/docs.yml) runs both, figures first.
PYTHON ?= python

.PHONY: all figures clean

all: main.pdf

main.pdf: main.tex preamble.tex $(wildcard chapters/*.tex) $(wildcard figures/*.tex)
	latexmk -pdf main.tex

figures:
	$(PYTHON) ../../scripts/make_book_figures.py figures

clean:
	latexmk -C main.tex
