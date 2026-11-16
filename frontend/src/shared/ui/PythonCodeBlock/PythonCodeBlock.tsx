import { useMemo } from "react";

import styles from "./PythonCodeBlock.module.css";

type PythonTokenType = "builtin" | "comment" | "decorator" | "function" | "keyword" | "number" | "string";

type PythonToken = {
  value: string;
  type?: PythonTokenType;
};

const TOKEN_PATTERN = /(#.*$|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b\d+(?:\.\d+)?\b|@[A-Za-z_][\w.]*|\b[A-Za-z_]\w*\b|\s+|.)/gm;

const PYTHON_KEYWORDS = new Set([
  "False",
  "None",
  "True",
  "and",
  "as",
  "assert",
  "async",
  "await",
  "break",
  "class",
  "continue",
  "def",
  "del",
  "elif",
  "else",
  "except",
  "finally",
  "for",
  "from",
  "global",
  "if",
  "import",
  "in",
  "is",
  "lambda",
  "nonlocal",
  "not",
  "or",
  "pass",
  "raise",
  "return",
  "try",
  "while",
  "with",
  "yield"
]);

const PYTHON_BUILTINS = new Set([
  "abs",
  "bool",
  "dict",
  "enumerate",
  "float",
  "int",
  "len",
  "list",
  "max",
  "min",
  "print",
  "range",
  "round",
  "set",
  "str",
  "sum",
  "tuple",
  "zip"
]);

const TOKEN_CLASS_BY_TYPE: Record<PythonTokenType, string> = {
  builtin: styles.pythonBuiltin,
  comment: styles.pythonComment,
  decorator: styles.pythonDecorator,
  function: styles.pythonFunction,
  keyword: styles.pythonKeyword,
  number: styles.pythonNumber,
  string: styles.pythonString
};

type PythonCodeBlockProps = {
  label: string;
  source: string;
};

export function PythonCodeBlock({ label, source }: PythonCodeBlockProps) {
  const tokens = useMemo(() => tokenizePython(source), [source]);

  return (
    <pre className={styles.codeBox}>
      <code aria-label={label} className={styles.pythonCode} data-language="python">
        {tokens.map((token, index) =>
          token.type ? (
            <span className={TOKEN_CLASS_BY_TYPE[token.type]} data-token={token.type} key={`${index}-${token.value}`}>
              {token.value}
            </span>
          ) : (
            token.value
          )
        )}
      </code>
    </pre>
  );
}

function tokenizePython(source: string): PythonToken[] {
  const matches = source.match(TOKEN_PATTERN) ?? [];
  const tokens: PythonToken[] = [];
  let expectingNamedBlock = false;

  for (const value of matches) {
    if (/^\s+$/.test(value)) {
      tokens.push({ value });
      continue;
    }

    const type = tokenType(value, expectingNamedBlock);
    tokens.push(type ? { value, type } : { value });

    if (value === "def" || value === "class") {
      expectingNamedBlock = true;
    } else if (type === "function" || /^[A-Za-z_]\w*$/.test(value) || value !== "_") {
      expectingNamedBlock = false;
    }
  }

  return tokens;
}

function tokenType(value: string, expectingNamedBlock: boolean): PythonTokenType | undefined {
  if (value.startsWith("#")) {
    return "comment";
  }
  if (value.startsWith("\"") || value.startsWith("'")) {
    return "string";
  }
  if (value.startsWith("@")) {
    return "decorator";
  }
  if (/^\d/.test(value)) {
    return "number";
  }
  if (expectingNamedBlock && /^[A-Za-z_]\w*$/.test(value)) {
    return "function";
  }
  if (PYTHON_KEYWORDS.has(value)) {
    return "keyword";
  }
  if (PYTHON_BUILTINS.has(value)) {
    return "builtin";
  }
  return undefined;
}
