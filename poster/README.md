# Amazon Locker Capacity Optimization Poster

This is a self-contained A0 LaTeX poster project based on the ICFO `baposter` layout. It uses model outputs in `../reports/` and input probabilities in `../data/`.

## Files

- `poster.tex`: editable poster source
- `baposter.cls`: local poster class from the ICFO template
- `generate_figures.py`: regenerates the vector PDF charts
- `images/`: generated charts
- `main.tex`: wrapper used by the Codex LaTeX preview

## Generate the figures

From the repository root:

```bash
conda activate amazon-locker-capacity
python -m pip install reportlab
python poster/generate_figures.py
```

## Compile the poster

```bash
cd poster
latexmk -pdf poster.tex
```

Or, without `latexmk`:

```bash
pdflatex poster.tex
pdflatex poster.tex
```

The result is `poster.pdf`. Edit `YOUR NAME` and `COLLEAGUE NAME` near the top of `poster.tex` before the final build.

## Data shown

The baseline has four 46-slot lockers, seven planning days, 909 requests, 803 accepted packages, and an 88.3% acceptance rate. Scenarios compare 23, 46, and 69 slots per locker and a one-day pickup delay.

## Attribution

Layout adapted from [ICFO-poster-template](https://github.com/episanty/ICFO-poster-template) by Emilio Pisanty. The included `baposter.cls` retains its original notices.