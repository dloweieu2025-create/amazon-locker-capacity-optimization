#!/usr/bin/env python3
"""Compile the LaTeX poster, placing ONLY poster3.pdf in output/pdf.

All compiler logs, auxiliary files and intermediate PDFs live in an OS temporary
directory that is removed automatically. No PNG or TXT files are generated.
Run from any directory: python /path/to/poster/build_poster.py
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent


def find_compiler(explicit=None):
    candidates = [explicit, shutil.which('tectonic'),
                  str(Path(tempfile.gettempdir()) / 'amazon-locker-poster-tectonic' / 'tectonic.exe'),
                  os.environ.get('CODEX_TECTONIC_PATH'), shutil.which('pdflatex')]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    raise SystemExit('Install Tectonic or pdfLaTeX, or pass --compiler PATH.')


def build(compiler):
    destination = HERE / 'output' / 'pdf' / 'poster3.pdf'
    with tempfile.TemporaryDirectory(prefix='amazon-locker-poster3-build-') as workdir:
        work = Path(workdir)
        source = work / 'poster3.tex'
        shutil.copyfile(HERE / 'poster3.tex', source)
        if 'tectonic' in compiler.name.lower():
            command = [str(compiler), '--keep-logs', '--outdir', str(work), str(source)]
            passes = 1
        else:
            command = [str(compiler), '-interaction=nonstopmode', '-halt-on-error',
                       '-output-directory=' + str(work), str(source)]
            passes = 2
        for _ in range(passes):
            result = subprocess.run(command, cwd=work, capture_output=True,
                                    text=True, encoding='utf-8', errors='replace')
            if result.returncode:
                raise SystemExit(result.stdout + result.stderr)
        logpath = work / 'poster3.log'
        log = logpath.read_text(encoding='utf-8', errors='replace') if logpath.exists() else ''
        failures = ('Overfull', 'Missing character', 'Package poster Error')
        if any(marker in log for marker in failures):
            raise SystemExit('Poster failed layout checks:\n' + log)
        compiled = work / 'poster3.pdf'
        if not compiled.is_file() or not compiled.read_bytes().startswith(b'%PDF-'):
            raise SystemExit('Compiler did not produce a valid PDF.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(compiled, destination)
    print(destination)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', help='Path to Tectonic or pdfLaTeX')
    build(find_compiler(parser.parse_args().compiler))

