#!/usr/bin/env bash
# Usage: bash scripts/build-pages.sh NEW_OUTPUT_DIRECTORY
set -euo pipefail
out=$(realpath -m "${1:?Pass a new output directory}")
cd "$(dirname "$0")/.."
mkdir "$out"
mkdir "$out/tessdata"
sed 's/data-engine="python"/data-engine="browser"/' index.html > "$out/index.html"
cp fields.py LICENSE docs/{browser_rules.py,field-rules.mjs,pdf-reader.mjs,example-transfer.pdf} "$out/"
cp -r config "$out/"
cp tessdata/LICENSE "$out/tessdata/"
for lang in pol eng; do
  gzip -nc "tessdata/$lang.traineddata" > "$out/tessdata/$lang.traineddata.gz"
done
bash scripts/pages-vendor.sh "$out"
