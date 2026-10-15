"""Build the single production CSS bundle used by the server-rendered UI.

Run before a deploy and after changing files in ``frontend/css``:
    python frontend/scripts/build_css.py

``--check`` is intended for CI: it fails when app.css was not rebuilt.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[1]
CSS_DIR = FRONTEND_DIR / "css"
OUTPUT_PATH = CSS_DIR / "app.css"
ENTRYPOINT_PATH = CSS_DIR / "style.css"

IMPORT_PATTERN = re.compile(
    r'''@import\s+url\(\s*["'](?P<path>[^?'"\)]+)(?:\?[^'"\)]*)?["']\s*\)\s*;'''
)


def minify_css(css: str) -> str:
    """Remove comments and redundant whitespace without changing CSS values."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r"\s*([{}:;,>])\s*", r"\1", css)
    return css.replace(";}", "}").strip() + "\n"


def source_files() -> tuple[str, ...]:
    """Use style.css as the single source of truth for bundle cascade order."""
    entrypoint = ENTRYPOINT_PATH.read_text(encoding="utf-8")
    files = tuple(match.group("path") for match in IMPORT_PATTERN.finditer(entrypoint))
    if not files:
        raise ValueError(f"No CSS imports found in: {ENTRYPOINT_PATH}")
    return files


def build_bundle() -> str:
    sources = []
    for relative_path in source_files():
        path = CSS_DIR / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"CSS source is missing: {path}")
        sources.append(path.read_text(encoding="utf-8"))
    return minify_css("\n".join(sources))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if app.css is not up to date")
    args = parser.parse_args()

    bundle = build_bundle()
    current = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else ""
    if args.check:
        if current != bundle:
            print("app.css is out of date. Run: python frontend/scripts/build_css.py")
            return 1
        print("app.css is up to date")
        return 0

    OUTPUT_PATH.write_text(bundle, encoding="utf-8", newline="\n")
    print(f"Built {OUTPUT_PATH.relative_to(FRONTEND_DIR.parent)} ({len(bundle)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
