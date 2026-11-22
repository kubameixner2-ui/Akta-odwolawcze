#!/usr/bin/env bash
# Assemble the browser runtimes on the build machine. Judges fetch them from Pages.
set -euo pipefail
vendor="$1/vendor"
mkdir -p "$vendor"/{mupdf,tesseract,pyodide}
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
unpack() {
  local package=$1 version=$2
  mkdir "$work/$package"
  curl --retry 3 -fsSL "https://registry.npmjs.org/$package/-/$package-$version.tgz" -o "$work/$package.tgz"
  tar -xzf "$work/$package.tgz" --strip-components=1 -C "$work/$package"
}
unpack mupdf 1.26.4
cp "$work/mupdf"/dist/{mupdf.js,mupdf-wasm.js,mupdf-wasm.wasm} "$work/mupdf/LICENSE" "$vendor/mupdf/"
unpack tesseract.js 6.0.1
cp "$work/tesseract.js"/dist/{tesseract.esm.min.js,worker.min.js,*.LICENSE.txt} "$work/tesseract.js/LICENSE.md" "$vendor/tesseract/"
unpack tesseract.js-core 6.0.0
cp "$work/tesseract.js-core"/{tesseract-core-lstm.wasm.js,tesseract-core-simd-lstm.wasm.js,LICENSE} "$vendor/tesseract/"
unpack pyodide 0.28.3
cp "$work/pyodide"/{pyodide.js,pyodide.mjs,pyodide.asm.js,pyodide.asm.wasm,pyodide-lock.json,python_stdlib.zip} "$vendor/pyodide/"
curl --retry 3 -fsSL https://raw.githubusercontent.com/pyodide/pyodide/0.28.3/LICENSE -o "$vendor/pyodide/LICENSE"
curl --retry 3 -fsSL https://raw.githubusercontent.com/python/cpython/v3.13.2/LICENSE -o "$vendor/pyodide/CPython-LICENSE"
