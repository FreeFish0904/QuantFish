# Platform intro deck (Chinese)

`QuantFish-简介.pdf` is the 8-page Chinese introduction to the platform: what it
is, how the scoring loop works, the dual metric sets, the data release /
point-in-time contract, and how to run it offline.

The PDF is a build artifact. The sources are plain HTML next to it, one file per
page, and the math is written as real TeX (`\( ... \)` / `\[ ... \]`) that is
pre-rendered with [KaTeX](https://katex.org) at build time:

| File | Content |
| --- | --- |
| `intro.html` | Document head, page setup, cover page |
| `s1.html` … `s7.html` | Sections 1–7, each starts on its own printed page |
| `render-math.mjs` | Concatenates the sources, renders the TeX, inlines the KaTeX CSS and woff2 fonts, stamps the commit |
| `QuantFish-简介.pdf` | Generated output, committed so it can be linked from the README |

## Rebuild

```bash
./scripts/build-intro-pdf.sh
```

The script installs `katex` into a temporary directory (it is deliberately not a
dependency of `frontend/package.json`), renders `intro-full.html`, and prints it
with headless Google Chrome — set `CHROME_BIN` if Chrome lives elsewhere. The
version row on the cover is filled in from `git rev-parse --short HEAD` and the
commit date, so rebuild after the content you want to reference is committed.

On Linux the print step works the same way with `google-chrome` / `chromium`;
both `--print-to-pdf` and the KaTeX inlining are platform independent.
