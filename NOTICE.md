# Notice And Content Boundary

This repository is a **toolchain and method** for reconstructing scanned textbooks
into LaTeX — not a reconstruction of any particular book. It contains no book text,
page images, or scans.

## MIT-Licensed Material

The repository-level `LICENSE` covers the material independently authored for this
project:

- the deterministic scripts under `scripts/` and the developer tools under `tools/`;
- the reference class and build script under `template/`;
- the instruction set in `SKILL.md` and the documentation under `references/`;
- the regression tests under `tests/`.

## Material That Is Not Licensed Here

- **Book content.** Any textbook text, formulas, exercises, figures or layout that a
  user reconstructs with this toolchain remains the property of the original author
  and publisher. Running these tools does not grant any right to that content. Use
  the toolchain only on material you are entitled to reproduce.
- **Examples in the documentation.** Where the documentation quotes a small fragment
  of a source book as a worked example (for instance a misprint that must be
  transcribed verbatim), that fragment remains the property of its rights holder and
  is included only as an illustrative case.
- **Source scans, page renders and reference projects.** These are local QA inputs.
  They must not be committed; `.gitignore` excludes the paths they normally live in.
- **Compiled outputs.** PDFs produced with this toolchain combine project
  infrastructure with the user's own content and are not licensed as a whole here.

## Dependencies

TeX Live, XeLaTeX, latexmk, Poppler, PyMuPDF, Pillow, and system fonts retain their
own licenses. They are runtime prerequisites, not bundled assets, and are not
relicensed by this repository.

## For Users Publishing A Reconstruction

If you publish a book reconstructed with this toolchain, the content rights are your
responsibility, not this repository's. See
[references/governance/release-and-open-source.md](references/governance/release-and-open-source.md)
for the boundary checklist and the pre-publish leak audit.
