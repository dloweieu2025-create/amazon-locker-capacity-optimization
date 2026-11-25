# Current poster: poster3

Build from the repository root:

```bash
python poster/build_poster.py
```

The build writes only `output/pdf/poster3.pdf`. All logs, auxiliary files and
intermediate PDFs are created in an operating-system temporary directory and
removed automatically. It generates no TXT or PNG files. Existing PDFs are
preserved. Requires Tectonic or pdfLaTeX; use `--compiler PATH` if needed.

All content, equations, tables and vector graphics are LaTeX in `poster3.tex`.
`main.tex` includes that source for the project's editor. Use the build script
instead of directing raw compiler output into the PDF destination folder.

The structure follows the supplied scientific-poster guide: purpose and scope,
introduction, mathematical formulation, method and reproducibility, results,
interpretation and limitations, conclusion, and references. The visual design
retains the earlier A0 portrait grid, navy header, blue section bars, orange
accent and repository QR code. Results match the saved synthetic scenario data.

Earlier sources and PDFs are preserved. `poster_math.tex` is the preceding
math-focused revision; `generate_poster.py` builds the older ReportLab version.
