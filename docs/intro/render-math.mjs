// Assemble the intro document, render every \( ... \) / \[ ... \] with KaTeX,
// and inline the KaTeX stylesheet with its woff2 fonts as data URIs so the
// result is one self-contained HTML file that Chrome can print offline.
//
// Usage: KATEX_DIST=/path/to/node_modules/katex/dist node render-math.mjs [out.html]
//   KATEX_DIST defaults to <cwd>/node_modules/katex/dist
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..");
const DIST = process.env.KATEX_DIST ?? path.resolve(process.cwd(), "node_modules/katex/dist");
const OUT = path.resolve(process.argv[2] ?? path.join(HERE, "intro-full.html"));

const katex = createRequire(path.join(DIST, "..", "package.json"))("katex");

const read = (file) => fs.readFileSync(path.join(HERE, file), "utf8");
const git = (...args) => {
  try {
    return execFileSync("git", args, { cwd: REPO, encoding: "utf8" }).trim();
  } catch {
    return "unknown";
  }
};

let html = read("intro.html") +
  [1, 2, 3, 4, 5, 6, 7].map((i) => read(`s${i}.html`)).join("") +
  "\n</body>\n</html>\n";

html = html
  .replace("<!--commit-sha-->", git("rev-parse", "--short", "HEAD"))
  .replace("<!--build-date-->", git("log", "-1", "--format=%cs"))
  // Chrome needs absolute file URLs for the screenshots next to the sources.
  .replaceAll('src="../screenshots/', `src="file://${path.join(REPO, "docs", "screenshots")}/`);

let rendered = 0;
const tex = (source, displayMode) => {
  rendered += 1;
  return katex.renderToString(source.trim(), { displayMode, throwOnError: true, strict: false });
};

html = html
  .replace(/\\\[([\s\S]+?)\\\]/g, (_, body) => tex(body, true))
  .replace(/\\\(([\s\S]+?)\\\)/g, (_, body) => tex(body, false));

const leftover = html.match(/\\\(|\\\[/g);
if (leftover) throw new Error(`unrendered TeX delimiters left: ${leftover.length}`);
const placeholder = html.match(/<!--(commit-sha|build-date)-->/);
if (placeholder) throw new Error(`unfilled template placeholder: ${placeholder[0]}`);

let css = fs.readFileSync(path.join(DIST, "katex.min.css"), "utf8");
// Chrome only needs woff2; dropping the woff/ttf fallbacks keeps the inline CSS small.
css = css
  .replace(/,url\(fonts\/[^)]+\.woff\) format\("woff"\)/g, "")
  .replace(/,url\(fonts\/[^)]+\.ttf\) format\("truetype"\)/g, "");

let inlined = 0;
css = css.replace(/url\(fonts\/([^)]+\.woff2)\)/g, (_, file) => {
  const font = path.join(DIST, "fonts", file);
  if (!fs.existsSync(font)) throw new Error(`missing KaTeX font: ${file}`);
  inlined += 1;
  return `url(data:font/woff2;base64,${fs.readFileSync(font).toString("base64")})`;
});

const tuning = `
  .katex { font-size: 1.02em; }
  .tiny .katex, .small .katex { font-size: 1em; }
  .katex-display { margin: 0.4mm 0; }
  td .katex { white-space: nowrap; }
`;

html = html.replace("</head>", `<style data-katex>\n${css}\n${tuning}</style>\n</head>`);

fs.writeFileSync(OUT, html);
console.log(
  `rendered ${rendered} formulas, inlined ${inlined} fonts, wrote ${OUT} (${(html.length / 1024).toFixed(0)} kB)`
);
