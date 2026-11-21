# Verification runbook

## Release decision

A clean Linux checkout installed on CPython 3.13.18 and produced the expected files through the CLI and browser. The public timing fixture showed why judging should use the configured hybrid mode. CPU rules finished within the time limit but missed 10 supported scans entirely. The team’s last live API run classified all 30 public scans and scored 96.14% field micro-F1. End-to-end hosted timing on 150 PDFs remains an open release check. [Measured counts](../benchmarks/readiness.json) · [Official processing limit][time]

## Scope and assumptions

1. **Source of truth.** The audit started from the public solution at `3518920`. All 36 tracked files matched the supplied source ZIP byte-for-byte. The original banner was present only in the ZIP. Generated results, credentials, installed dependencies and sample uploads belong outside the public source tree. Root `input/` and `output/` are part of the organizer’s interface. Each contains a tracked placeholder so a fresh checkout creates both folders. [Published baseline][base] · [Organizer’s folder contract][paths]
2. **Reference data.** We pinned the public PDFs to `84cc976`. Their `dane/` Git tree matches that at specification revision `0b360a9`. It contains 180 native-text positives, 30 labeled scans and 16 exclusion paths. SHA-256 gives 221 distinct PDFs across the 226 paths. The organizer’s separate application template contains two more example paths and an empty appeal reference. These demonstrate the interface and carry no field score here. [Pinned dataset][data] · [Template][template]
3. **Scoring.** Each populated scalar is identified by its full field path, array index, value type and value. Integers and JSON floats share the numeric type. Nulls contribute no field observations. A wrong non-null value usually costs one false positive and one false negative. A whole-document match also requires equality of the parsed JSON. This is the repository’s reproducible proxy. The judges use their own references and hidden cases. [Evaluator](../evaluate.py) · [Organizer’s evaluation rules][spec]
4. **Independence.** Every fifth numbered case forms the 12-case native holdout. The other 48 form development. Both partitions were revisited during development, and the published scans informed postprocessing. The live and replay scan measurements reuse the same 30 PDFs and must each be reported separately. Their scores do not predict a hidden ranking. [Earlier experiments](experiments.md) · [Saved live metrics](../benchmarks/scaleway-scans-v2-live.json)
5. **Runtime.** The 45-minute constraint applies to one 150-file batch. Network latency, scan density, the judge’s CPU and the chosen model affect elapsed time. UZP has placed the judging machine and detailed model-size scoring under review. The application supports CPU-only execution. Hosted inference uses the team’s API key and EU/EEA processing. [Technical and judging requirements][spec] · [Time limit][time]

## Run the 150-PDF check

From the project root, with runtime dependencies installed, run the following for the configuration you intend to submit. The hosted commands make live API calls. On Windows use `.\.venv\Scripts\python.exe` in place of `.venv/bin/python`.

```bash
.venv/bin/python check_api.py
.venv/bin/python scripts/check_public.py timing --mode hybrid
```

For an independent CPU baseline, run `.venv/bin/python scripts/check_public.py timing --mode rules`. For either command, append `--data /path/to/dane` to reuse a local copy of the pinned data. Without that option the checker fetches the public release into a temporary checkout. It writes the input layout, outputs, CLI diagnostics (`batch.log`) and `report.json` inside a new `results/timing-*/` directory for each run.

The timer starts immediately before launching the batch CLI and stops when it exits. It includes interpreter startup, PDF reads, OCR, model blocking time when applicable and file writes. Data fetching, staging and reference scoring take place outside the timer. The check enforces a 2,700-second subprocess timeout. Input filenames are opaque. Expected values are read after extraction. [Fixture builder and verifier](../scripts/check_public.py)

| Report field | Passing condition | Recorded CPU rules result |
| --- | --- | ---: |
| `within_time_limit` | Process finished within 2,700 s | true · 325.17 s |
| `output_format_ok` | Every expected output path exists, with valid paths and valid UTF-8, JSON and schema for nonempty records | true · 150/150 files |
| `disposition_ok` | Supported PDFs produce a nonempty record of the correct class and excluded PDFs produce an empty file | false · 10 supported scans empty |
| `output_contract_ok` | CLI exits successfully and both format and disposition pass | false |
| `exact_outputs` | Count of complete matches, including correct exclusions | 120/150 |
| `passed` | Timing profile requires both the output contract and the time limit. Demo also requires every output to match exactly. | false |

The known CPU timing failure returns a nonzero status from the **checker**. The measured extractor itself exited 0. The fixture draws 35 native appeals, 35 native powers of attorney, 34 native transfers, all 30 scans and all 16 exclusions. The exclusions contain 11 distinct byte sequences. The measured margin was `2700 − 325.17 = 2374.83` seconds. No inference about hosted runtime follows from this margin. Check the hosted run’s own `report.json` and read `batch.log` for API errors or the `partial_rules_after_api_error` route. [Timing record](../benchmarks/readiness.json)

## Reproduce the public scores

Run these from the project root. The checkout command pins the exact public data in its own directory and can be run again. The evaluation script compares final records with the reference JSONs after processing. The native and scan splits receive renamed inputs.

```bash
mkdir -p results
git init -q results/uzp-reference
git -C results/uzp-reference fetch --quiet --depth=1 https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026.git 84cc976f0a9af5cee14f131c795f929134ca0fda
git -C results/uzp-reference checkout --quiet --detach FETCH_HEAD
```

**Native text and exclusions, CPU only**

```bash
.venv/bin/python evaluate.py results/uzp-reference/dane --split dev --mode rules --output results/native-dev
.venv/bin/python evaluate.py results/uzp-reference/dane --split holdout --mode rules --output results/native-holdout
.venv/bin/python evaluate.py results/uzp-reference/dane --split negatives --mode rules --output results/exclusions
```

Expect 144 exact development records (1,619 TP), 36 exact native holdout records (413 TP) and 16 zero-byte exclusions. The timed CPU run also processed every one of the 30 labeled scans. [Split and timing records](../benchmarks/readiness.json)

**Fresh inference on scans**

```bash
.venv/bin/python check_api.py
.venv/bin/python evaluate.py results/uzp-reference/dane --split scans --mode hybrid --output results/scans-live
```

**Replay a saved run**

```bash
.venv/bin/python evaluate.py results/uzp-reference/dane --split scans --replay-from results/scans-live --output results/scans-replay
```

For the team’s historical run, use `results/scaleway-scans-v2-live` as `--replay-from` if that local folder contains all 30 predictions. New checkouts can create their own predictions with the preceding live command. Replay performs these steps for each saved result.

1. Load the saved prediction and identify the class from its schema keys. An empty prediction stays empty.
2. Re-read the original PDF, OCR the appropriate pages, and reconcile extracted fields using the current corrections. No model call occurs.
3. Validate the corrected record against the configured JSON Schema and write it to the separate replay directory.
4. Compare the output with the official JSON. Aggregate exact documents, true positives, false positives and false negatives. The saved class is retained, so replay does not re-test the live classifier. [Replay implementation](../evaluate.py) · [OCR corrections](../scan_fields.py)

## Where the scan errors are

| Scan class | Live TP / FP / FN | Live F1 | Live exact | Replay TP / FP / FN | Replay F1 | Replay exact |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Appeals | 171 / 8 / 6 | 96.07% | 4/10 | 172 / 5 / 5 | 97.18% | 5/10 |
| Powers of attorney | 78 / 1 / 0 | 99.36% | 9/10 | 78 / 1 / 0 | 99.36% | 9/10 |
| Transfers | 50 / 5 / 4 | 91.74% | 5/10 | 51 / 3 / 3 | 94.44% | 7/10 |
| **All** | **299 / 14 / 10** | **96.14%** | **18/30** | **301 / 9 / 8** | **97.25%** | **21/30** |

Micro-F1 is `2 × TP / (2 × TP + FP + FN)`. Summing counts before division gives `598 / 622 = 96.14%` live and `602 / 619 = 97.25%` on replay. These are **1.11 percentage points apart** on the same saved predictions. The recorded live run took 271.75 s for 30 scans and the team’s archived replay took 200.20 s. The Linux audit reproduced the replay counts. [Live](../benchmarks/scaleway-scans-v2-live.json) · [Archived replay](../benchmarks/scaleway-scans-v3-replay.json) · [Linux confirmation and field-by-field counts](../benchmarks/readiness.json)

The three remaining transfer mismatches all come from `przelew_bankowy/tytul`. They account for three FP and three FN, or `6 / (9 + 8) = 35.29%` of the remaining field errors. The other discrepancies are five mismatched appeal values and one extra grantor name. This identifies the exact fields worth checking against the next fresh API run. [Field audit](../benchmarks/readiness.json)

## Installation and regression checks

| Check | What was exercised | Boundary |
| --- | --- | --- |
| Linux x86-64 | Clean CPython 3.13.18 virtual environment, runtime and development dependencies, mypy, unit suite and public fixtures | Native execution on the audit host |
| Native Windows x64 | Pip resolved all eight runtime wheels for CPython 3.13 | The native Windows CLI and OCR still need an execution on Windows |
| Browser UI | Actual Chromium upload, first-page preview, analysis, JSON download and comparison with the public appeal reference | CPU rules mode |
| Docker | Docker Compose 2.39.4 parsed the service, environment and three mounts | Image execution needs a Docker engine |
| Hosted API | Team’s saved live run covered all 30 labeled scans. Local tests exercised API error handling | Fresh external inference and the 150-file hybrid timing still need the team endpoint |

Development commands for Linux or WSL follow. Run from the repository root. [Unit tests](../tests/) · [Machine-readable verification](../benchmarks/readiness.json)

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip check
.venv/bin/python -m mypy --explicit-package-bases --check-untyped-defs check_api.py evaluate.py extractor.py fields.py names.py run.py scan_fields.py scripts tests
.venv/bin/python -m unittest discover -s tests -v
```

| Terminal symptom | Action |
| --- | --- |
| `python3.13` is unavailable in WSL | Use the `uv` alternative in the [installation steps](../README.md#1-install), then install requirements with the environment’s interpreter. |
| `No PDF files found` | Put PDFs under the selected input folder, or run the self-contained demo. |
| HTTP 401 or 403 during `check_api.py` | Check the private team key and its permissions. A connection failure points to the base URL or network. Shell variables take precedence over the repository’s `.env`. |
| UI port already in use | Run without an explicit port and open the printed address, or use `--port 0`. |
| OCR prints “Line cannot be recognized” | Inspect the file’s output, exit status and field comparison. These warnings also appeared in the completed 30-scan run. |

[base]: https://github.com/kubameixner2-ui/Akta-odwolawcze/tree/3518920f02319278ce9a5305c95afc8abf9b31a0
[paths]: https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/blob/0b360a9da4b482a6a280696df6714404e0953505/README.md#L66-L101
[spec]: https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/blob/0b360a9da4b482a6a280696df6714404e0953505/README.md#L119-L184
[time]: https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/blob/0b360a9da4b482a6a280696df6714404e0953505/README.md#L186-L192
[data]: https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/tree/84cc976f0a9af5cee14f131c795f929134ca0fda/dane
[template]: https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/tree/0b360a9da4b482a6a280696df6714404e0953505/szablon-aplikacja
