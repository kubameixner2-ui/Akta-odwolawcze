# Procurement Appeals to JSON

Extract structured data from Polish public procurement case files. The application reads native PDF text or runs OCR on scanned pages, recognizes the document type, and writes one JSON file per PDF. It extracts parties and grounds for appeal, grantors and attorneys, or bank accounts and payment amounts, depending on the document.

[Quick start](#quick-start) · [Batch and browser usage](#batch-and-browser-usage) · [Results](#results) · [Reproduce the benchmarks](#reproduce-the-benchmarks) · [Repository guide](#repository-guide)

## Quick start

### 1. Install

Use Python 3.13 or later. PDF reading and OCR run on the CPU. The judging setup uses a hosted model and needs no GPU or local model download.

```sh
git clone https://github.com/kubameixner2-ui/Akta-odwolawcze.git
cd Akta-odwolawcze
```

**Linux or WSL (Bash)**

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If WSL has `uv` but no `python3.13` command, use `uv venv --python 3.13 --seed .venv` in place of the first line.

**Windows (PowerShell)**

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use `.\.venv\Scripts\python.exe` wherever the commands use `python`. Run the remaining commands from the repository root.

### 2. Try one appeal without an API key

Save the sample PDF as `input/appeal.pdf`, then run the two commands below. The resulting JSON should contain the procurement reference `ZS.791.2026`. [Download the sample appeal](https://raw.githubusercontent.com/Urzad-Zamowien-Publicznych/hacknation-2026/84cc976f0a9af5cee14f131c795f929134ca0fda/dane/przyklad_01/odwolanie.pdf) · [Expected JSON](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/blob/84cc976f0a9af5cee14f131c795f929134ca0fda/dane/przyklad_01/odwolanie.json)

```sh
python run.py --mode rules
python -m json.tool --no-ensure-ascii output/appeal.json
```

### 3. Run the judging configuration

Place the team's private `.env` beside `run.py`. The application reads it automatically. For the recorded Scaleway run, the file had the settings below. Replace the placeholder with the private team key and keep the file out of Git.

```dotenv
KIO_LLM_BASE_URL=https://api.scaleway.ai/v1
KIO_LLM_MODEL=mistral/mistral-small-3.2-24b-instruct-2506:fp8
KIO_LLM_API_KEY=YOUR_PRIVATE_TEAM_KEY
```

Place the case folders under `input/`. The first command sends a real request and prints `ok` on success. The second runs the default hybrid batch. The hosted model is Mistral Small 3.2 24B, served by Scaleway in Paris. [Model card](https://huggingface.co/mistralai/Mistral-Small-3.2-24B-Instruct-2506) · [Provider and region](https://www.scaleway.com/en/docs/generative-apis/faq/)

```sh
python check_api.py
python run.py
```

## Batch and browser usage

The CLI reads PDFs recursively. For example, `input/case-07/attachment.pdf` produces `output/case-07/attachment.json`. Missing nullable fields contain `null`. A PDF outside the three supported classes produces a **zero-byte** `.json` at the same relative path. A nonzero exit code signals a processing error and the terminal identifies the affected file. Use a fresh output directory when switching datasets.

| Mode | When to use it |
| --- | --- |
| `hybrid` (default) | Run the judging configuration. Field rules handle recognizable layouts. The model can resolve ambiguous classifications, incomplete records, or competing grounds for appeal. |
| `rules` | Run locally without model calls. Useful for a first check or a native-text baseline. |
| `llm` | Send each recognized document to the model for schema-constrained extraction. Useful for comparing extraction methods. |

**Batch with a trace.** Set the input and output directories explicitly. The log collects the extraction route, OCR pages, page matches for literal field values, and any OCR diagnostics.

```sh
python run.py --input input --output output --trace 2> output/trace.log
```

**Review one PDF.** Start the browser interface, open `http://127.0.0.1:8765`, choose a PDF and start analysis. The first-page preview appears beside the JSON. The download goes to your browser's download folder. If port 8765 is busy, run `python run.py --ui --port 8766`. Press `Ctrl+C` to stop.

```sh
python run.py --ui
```

With Docker Compose, `docker compose run --rm --build extractor` runs the batch using the same `.env` and the mounted `input/`, `output/` and `config/` directories.

## Results

| Public evaluation | Exact reference JSONs | Field micro-F1 |
| --- | ---: | ---: |
| 30 scanned PDFs, live hosted hybrid | 18/30 | **96.14%** |
| Same 30 scans and saved responses, replayed after OCR corrections | 21/30 | **97.25%** |
| 180 native-text PDFs, rules only | 180/180 | **100.00%** |

The live run classified all 30 scans correctly in 271.75 seconds. Replay reapplied the updated field corrections to the saved responses and source PDFs with zero new model calls. The rules-only run also produced the required zero-byte file for **16/16** out-of-scope PDFs. The public scans informed development. The hidden judging score is unknown. [Live run counts](benchmarks/scaleway-scans-v2-live.json) · [Public dataset](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/tree/84cc976f0a9af5cee14f131c795f929134ca0fda/dane)

Field micro-F1 pools exact non-null values across documents, including their JSON paths, types and list positions. A whole-document match requires the entire JSON structure and values to agree. [Scoring code](evaluate.py)

## Reproduce the benchmarks

Fetch the public reference data once, from the project root. This revision contains the corrected native references, scans and out-of-scope PDFs.

```sh
git clone --filter=blob:none --no-checkout https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026.git ../uzp-data
git -C ../uzp-data sparse-checkout set dane
git -C ../uzp-data checkout --detach 84cc976f0a9af5cee14f131c795f929134ca0fda
```

**Native and out-of-scope checks.** The first two commands cover 48 development cases and 12 held-out cases, with three in-scope PDFs each. Every command prints a score report and writes its predictions to its own directory.

```sh
python evaluate.py ../uzp-data/dane --split dev --mode rules --output results/native-dev
python evaluate.py ../uzp-data/dane --split holdout --mode rules --output results/native-holdout
python evaluate.py ../uzp-data/dane --split negatives --mode rules --output results/negatives
```

**Scans.** The first command runs fresh hosted inference and saves a prediction for each scan. The second replays those files offline into a separate directory. The historical 97.25% used the team's saved predictions from the recorded live run. The public repository includes its score summary. A fresh model run can produce different predictions.

```sh
python evaluate.py ../uzp-data/dane --split scans --mode hybrid --output results/scans-live
python evaluate.py ../uzp-data/dane --split scans --replay-from results/scans-live --output results/scans-replay
```

## Repository guide

| Path | What it does |
| --- | --- |
| `run.py` · `index.html` | Batch CLI and local PDF/JSON review interface. |
| `extractor.py` · `check_api.py` | PDF text and OCR, classification, model requests, schema validation and the API connection check. |
| `fields.py` · `names.py` · `scan_fields.py` | Field extraction, Polish name normalization and scan-specific corrections. |
| `config/` · `tessdata/` | Document definitions and appeal reason codes, plus bundled Polish and English OCR data. |
| `input/` · `output/` | Default directories for source PDFs and generated JSON files. |
| `evaluate.py` · `tests/` · `benchmarks/` | Evaluation, regression tests and saved benchmark summaries. |
| `Dockerfile` · `compose.yaml` · `start-local-model.sh` | Containerized batch runner and an optional local Qwen launcher for Linux or WSL. |

To add a document type, create `config/<type>.json` with `label`, `headings`, `instructions` and a JSON `schema`. Restart the application in `hybrid` or `llm` mode. To add a field, update the existing schema and its extraction instructions. [Example type definition](config/przelew.json) · [Extension tests](tests/test_contract.py)

**Development checks**

```sh
python -m pip install -r requirements-dev.txt
python -m mypy --check-untyped-defs fields.py names.py scan_fields.py extractor.py run.py check_api.py evaluate.py tests
python -m unittest discover -s tests -v
```

For earlier model comparisons or a Polish-language handout, see the [experiment log](BENCHMARK.md) and [jury guide](DLA_JURY.md).

Application code is licensed under AGPL-3.0. The bundled OCR data carries its own Apache-2.0 license. [Application license](LICENSE) · [OCR data license](tessdata/LICENSE)
