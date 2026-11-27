# Concept book. make: build main.pdf (needs latexmk and a TeX distribution; the four images of
# chapter 02 are regenerated first when missing, which needs numpy and matplotlib).
# make figures: regenerate the images. CI (.github/workflows/docs.yml) runs the script, then latexmk.
PYTHON ?= python
IMAGES := $(addprefix figures/,field2d.pdf densities.pdf paths.pdf slopefield.pdf)

.PHONY: all figures clean

all: main.pdf

main.pdf: $(wildcard *.tex chapters/*.tex figures/*.tex) $(IMAGES)
	latexmk -pdf main.tex

$(IMAGES) &: ../../scripts/make_book_figures.py
	$(PYTHON) ../../scripts/make_book_figures.py figures

figures:
	$(PYTHON) ../../scripts/make_book_figures.py figures

clean:
	latexmk -C main.tex
