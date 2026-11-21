# Akta odwoławcze · PDF → JSON

A Python 3.13+ prototype for UZP’s Odwołania2JSON challenge. Run `python run.py` from the project root. Each `input/<case>/<name>.pdf` produces `output/<case>/<name>.json` with the same relative path and stem. Recognized documents receive their class-specific JSON. An out-of-scope document receives a zero-byte `.json` file. More than one power of attorney per case is supported. Use `python run.py --ui` to review a PDF next to its JSON and download the result.

**Fresh hosted scan benchmark.** Scaleway Mistral Small 3.2 24B (`mistral/mistral-small-3.2-24b-instruct-2506:fp8`) scored **96.14%** exact-field micro-F1 on the 30 public UZP scans. It classified 30/30, matched 18 complete JSONs and finished in 271.75 s. After the signing-officer, receipt-stamp and account-line corrections, an offline replay of those same responses matched 21/30 and scored **97.25%** (301 TP, 9 FP, 8 FN). The scan cases informed development. [Fresh run counts](benchmarks/scaleway-scans-v2-live.json) · [Public scans](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/tree/eb1ab440325908c530bda355558bef727ca6cef5/dane/skany)

On the native-text files the rules path matched all 180 references. It produced empty output for all 16 excluded PDFs. [UZP reference revision](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/tree/84cc976f0a9af5cee14f131c795f929134ca0fda/dane) · [Earlier Qwen experiments](BENCHMARK.md)

## 1. Judging computer

**Uruchomienie dla jury.** Umieść prywatny plik `.env` przekazany przez zespół obok `run.py`. Zawiera on `KIO_LLM_BASE_URL`, `KIO_LLM_MODEL` i `KIO_LLM_API_KEY`. Włóż PDF-y do `input/` i wykonaj polecenia w katalogu repozytorium. Program zapisze dane do `output/`.

Windows PowerShell z Pythonem 3.13

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe check_api.py
.\.venv\Scripts\python.exe run.py
```

Linux z Pythonem 3.13

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python check_api.py
.venv/bin/python run.py
```

UZP specifies an Intel i7 office laptop with 16 GB RAM and no GPU. The client and OCR run on that computer. Inference runs through the team’s API. The following commands assume a Linux shell and Python 3.13. The repository includes Polish and English OCR language data. [UZP testing setup](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/blob/de135d20811caf630f3e94dc655ba5eebd9a6710/README.md)

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

UZP FAQ 1.0, items 6, 7, 11 and 12, require explicit `null` for missing nullable values, OCR for scans, a usable team-supplied API key, and a CLI with instructions. The FAQ specifies the EU for both provider and inference server. The repository allows the EU/EEA. Use an EU-based company that provides inference from an EU server. Record the provider’s company name and inference region for the judges. For judging, supply the actual HTTPS base URL, model ID and key together privately. Keep credentials out of the public repository. The setup below tests a real constrained completion before processing files.

```bash
read -rp 'EU HTTPS API base URL ending in /v1: ' KIO_LLM_BASE_URL
read -rp 'Model ID (the bundled server uses kio): ' KIO_LLM_MODEL
read -rsp 'Team API key: ' KIO_LLM_API_KEY
printf '\n'
export KIO_LLM_BASE_URL KIO_LLM_MODEL KIO_LLM_API_KEY
python check_api.py
python run.py
```

For unattended evaluation, the team can supply a private `.env` containing the three `export KIO_LLM_...=...` settings. Run `source .env`, `python check_api.py`, then `python run.py` in the same shell. `.env` is ignored by Git. Provide the provider’s legal name and the physical inference region alongside the private credentials.

The judge puts PDFs in `input/`. A fresh `output/` per run avoids leftovers from a different set of PDFs. Each input’s result is written atomically. The file for an excluded PDF contains zero bytes. A previously populated result at the same path is replaced. On a transport failure, hybrid retains any schema-valid rule record for a recognized type and reports the degraded route on stderr. An unrecoverable PDF failure is identified on stderr and the batch exits nonzero. `--trace` sends page references and extraction routes to stderr and keeps the judged JSON clean.

## 2. Earlier inference setups

The submitted hosted configuration uses Scaleway in Paris. This section records the earlier local model and alternative deployment experiments.

The CPU service uses llama.cpp b12603, Qwen3-4B-Instruct-2507, and Unsloth’s Q4_K_M quantization. These commands reproduce the tested Linux x86-64 build. Inter-request prompt caching is disabled and the physical prompt batch is limited to 128 tokens to bound memory during a long judging batch. Use a second terminal for the runner. [Model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) · [Weights and checksum](https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/blob/892322e1c0d25bf63f43c26df479b666d74e7a1b/Qwen3-4B-Instruct-2507-Q4_K_M.gguf) · [Server release](https://github.com/ggml-org/llama.cpp/releases/tag/b12603)

```bash
mkdir -p models
curl -fL --retry 2 https://github.com/ggml-org/llama.cpp/releases/download/b12603/llama-b12603-bin-ubuntu-x64.tar.gz -o models/llama.tar.gz
tar -xzf models/llama.tar.gz -C models
curl -fL --retry 2 https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/892322e1c0d25bf63f43c26df479b666d74e7a1b/Qwen3-4B-Instruct-2507-Q4_K_M.gguf -o models/qwen.gguf
printf '%s  %s\n' 3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597 models/qwen.gguf | sha256sum -c -
models/llama-b12603/llama-server -m models/qwen.gguf --alias kio --host 127.0.0.1 --port 8080 -ngl 0 -c 12288 -np 1 -t 8 --cache-ram 0 -ub 128
```

For a **local rehearsal**, leave all three `KIO_LLM_*` variables unset on the same machine. Defaults are `http://127.0.0.1:8080/v1`, model `kio` and no key. The earlier self-hosting proposal used a German Hetzner Online GmbH VM in **Falkenstein, Germany (`fsn1`)**. The provider documents its registered office and the physical datacenter. Place the inference process and the HTTPS reverse proxy on that VM and point the judging hostname directly to it. Create a private judging key and run the authenticated server. Hetzner supplies the VM. If the team runs the API as individuals, confirm that UZP accepts team-operated inference on an EU company's infrastructure. For an API operated directly by an EU vendor, the managed Paris option is documented below. The public URL and its availability are the team’s responsibility. The client allows up to 600 seconds for one full completion on a CPU endpoint. UZP’s total batch time limit is still unconfirmed. This is a deployment target. The benchmark used a local CPU server. [Provider](https://www.hetzner.com/legal/legal-notice/) · [Region and operator](https://docs.hetzner.com/cloud/general/locations/) [Server API and authentication options](https://github.com/ggml-org/llama.cpp/blob/b12603/tools/server/README.md)

```bash
umask 077
openssl rand -hex 32 > models/judge.key
models/llama-b12603/llama-server -m models/qwen.gguf --alias kio --host 127.0.0.1 --port 8080 -ngl 0 -c 12288 -np 1 -t 8 --cache-ram 0 -ub 128 --api-key-file models/judge.key
```

With Caddy installed, a real DNS record pointing at that VM and ports 80/443 open, run this command on the server in a second terminal. Caddy needs permission to bind those ports. The public API base is `https://<your-host>/v1`. [Caddy HTTPS reverse proxy](https://caddyserver.com/docs/quick-starts/reverse-proxy)

```bash
read -rp 'Judging hostname: ' KIO_HOSTNAME
caddy reverse-proxy --from "$KIO_HOSTNAME" --to 127.0.0.1:8080
```

**Managed EU option.** Scaleway SAS is registered in Paris and currently documents Paris, France as its serverless inference location. Its catalog lists `mistral/mistral-small-3.2-24b-instruct-2506:fp8` with Polish and structured-output support. The original weights are downloadable under Apache-2.0. Use a project-scoped base `https://api.scaleway.ai/<project-id>/v1` and an inference key scoped to that project. The hosted scan benchmark above used this model at `https://api.scaleway.ai/v1`. On the clean native holdout the hybrid only needed two small model calls, which exercise little of the new endpoint’s extraction ability. The measured Qwen scores apply to the Qwen configuration. The competition README also gives more points to a smaller model. [Provider](https://www.scaleway.com/en/legal-notice/) · [Physical location](https://www.scaleway.com/en/docs/generative-apis/faq/) · [Model catalog](https://www.scaleway.com/en/docs/generative-apis/reference-content/supported-models/) · [Weights and license](https://huggingface.co/mistralai/Mistral-Small-3.2-24B-Instruct-2506) · [Project API](https://www.scaleway.com/en/docs/generative-apis/api-cli/using-generative-apis/)

## 3. Implementation decisions and interfaces

Preselection uses 100% hidden F1. The team confirmed final weights of **50% F1, 30% extensibility and 20% architecture**, matching §8 of the detailed task description. For the final demonstration, run the comparison in section 5, load a fourth class using section 4, then show one document’s route, page evidence and schema-validated JSON with `--trace`. [Detailed task description](https://mudnibfuppwadjkynscc.supabase.co/storage/v1/object/public/task-files/057d36b5-cb92-4062-9393-983cb8a96088/files/aeabc57d-7420-4069-946e-2c4de71d87ed.pdf) The updated README also publishes a breakdown of the 50 non-F1 points. Model size receives up to 20, with smaller models favored. Adding classes and fields receives up to 20, and other features such as the GUI receive up to 10. Demonstrate adding a fourth class and reviewing a PDF next to its extracted JSON. [Updated judging criteria](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/blob/de135d20811caf630f3e94dc655ba5eebd9a6710/README.md)

| Interface | Behavior |
|---|---|
| `run.py` | Recursive CLI, original case paths and stems, UTF-8 output. The browser interface accepts one upload, renders the first page, opens the full PDF and downloads the same extracted data. |
| `extractor.read_pages(pdf)` | Reads native text in PDF content order. Uses 300-dpi Polish/English OCR on sparse, garbled or largely scanned pages. Records OCR page numbers. Paired grantor/attorney signature blocks are read by their page coordinates. |
| `extractor.classify` | Checks document genre and distinctive standalone headings by content. It distinguishes a filed appeal from a judgment or a teaching presentation that discusses appeals. Ambiguity goes to a schema-constrained classifier that can return an out-of-scope class. Filenames and sibling PDFs stay outside inference. |
| `fields.py` | Extracts role-labelled values. Separates the payer and payee, print and execution dates, companies and their signers. It preserves the first appeal allegation, blank header dates, array order, and explicit identifier digits including leading zeros. |
| `config/` | One JSON Schema, class label, headings and Polish instructions per type. The cause codebook maps all 12 numbers to canonical descriptions. Appeals use the consortium leader. Powers of attorney retain each grantor and its signers. |
| Team LLM API | `POST {KIO_LLM_BASE_URL}/chat/completions`. Uses bearer authentication when a key is set, a model alias, temperature zero, a schema in the prompt, and `response_format.type=json_schema`. Parses `choices[0].message.content` and validates against the local schema. |
| Default `hybrid` | Emits complete labelled records, asks a focused question for competing first-allegation interpretations, and uses full schema extraction for new classes and unresolved layouts, including scans. A complete OCR-derived record follows the same checks as native text. Company/PESEL semantics and canonical descriptions are enforced after generation. |
| Comparison modes | `--mode rules` disables model calls. `--mode llm` uses the same reader and classifier and sends every recognized document for full schema generation. The three modes use the same evaluation harness. |
| Local HTTP | `POST /extract` accepts raw `application/pdf`. HTTP 200 returns the canonical record. HTTP 204 gives the browser an empty response and enables a zero-byte download. `POST /preview` returns a PNG of the first page. The review server binds to loopback. |
| Evidence | `--trace` includes route, total pages, OCR page numbers, and the first page containing each matched literal. Dates, codebook descriptions and other derived values can lack a verbatim match. |

Short documents fit in one prompt. For long documents the model receives prioritized opening pages, selected later lines with nearby text and the last page ending. Field rules can scan all pages. Unusual layouts can place relevant evidence outside the selected text. The response schema constrains syntax; field meanings also appear in the Polish prompt. [PyMuPDF reading-order limitations](https://pymupdf.readthedocs.io/en/latest/recipes-common-issues-and-their-solutions.html) · [PyMuPDF OCR](https://pymupdf.readthedocs.io/en/latest/ocr/index.html) · [llama.cpp grammar support](https://github.com/ggml-org/llama.cpp/blob/b12603/grammars/README.md)

## 4. Add a type or field

Place a new JSON file in `config/` and restart. Its filename stem is the class ID. Include the class label, heading variants, extraction instructions and schema. A new field on an existing class can be added to its schema, required keys and instructions. If the existing rules omit a required field, validation invokes full model extraction. A fourth class loaded from disk extracted a document number on the real CPU endpoint. The tests also add a required currency field to the existing transfer schema and promote a previously excluded court judgment to a new configured type.

```json
{
  "label": "Wniosek",
  "headings": ["Wniosek"],
  "instructions": "Przepisz numer wniosku. Przy braku informacji wpisz null.",
  "schema": {
    "type": "object",
    "properties": {"numer": {"type": ["string", "null"]}},
    "required": ["numer"],
    "additionalProperties": false
  }
}
```

## 5. Reproduce and test

UZP added 30 labelled synthetic scans at revision `eb1ab44`. The scan evaluator renames the input PDFs and reads the reference JSON after extraction. Run these commands from the project root with the team API settings loaded to test the hosted hybrid on the scans.

```bash
git clone --filter=blob:none --no-checkout https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026.git ../uzp-scans
git -C ../uzp-scans sparse-checkout set dane/skany
git -C ../uzp-scans checkout --detach eb1ab440325908c530bda355558bef727ca6cef5
mkdir -p results
.venv/bin/python evaluate.py ../uzp-scans/dane --split scans --mode hybrid --output results/scans-hybrid > results/scans-hybrid-score.json
```

On the 30 UZP scans, rules-only micro-F1 was 40.82% before the nominative change and 49.89% after it. The team’s hosted Scaleway Mistral Small 3.2 hybrid processed all 72 pages in 453 seconds. Its saved predictions scored 78.46% field micro-F1 (244 TP, 69 FP, 65 FN) and matched 4/30 complete reference JSONs. Replaying the same predictions with the OCR corrections scored 96.93% (300 TP, 10 FP, 9 FN) and matched 20/30 documents. These are development results on public scans used to design the corrections. The hidden score is unknown. [Official scans](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/tree/eb1ab440325908c530bda355558bef727ca6cef5/dane/skany)

To reproduce the correction step with the team’s original predictions in `results/scaleway-scans`, run the following from the project root. It reads the PDFs again, performs OCR on the CPU and writes to a separate directory. It makes zero API calls.

```bash
.venv/bin/python evaluate.py ../uzp-scans/dane --split scans \
  --replay-from results/scaleway-scans --output results/scaleway-scans-replay
```

Both extraction routes use Morfeusz 2 for personal-name fields. The dictionary checks which nominatives are compatible with the observed given name and surname. For ambiguous readings the app preserves the extracted spelling. The provider documents its data handling and Paris hosting. [Morfeusz 2 and SGJP license](https://morfeusz.sgjp.pl/doc/license/en) · [UZP name field](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/blob/eb1ab440325908c530bda355558bef727ca6cef5/oczekiwane-json/odwolanie.json#L17) · [Scaleway privacy policy](https://www.scaleway.com/en/docs/generative-apis/reference-content/data-privacy/) · [Hosting location](https://www.scaleway.com/en/docs/generative-apis/faq/)

The commands below reproduce the earlier native-text benchmark.

```bash
git clone https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026.git ../uzp-data
git -C ../uzp-data checkout --detach de135d20811caf630f3e94dc655ba5eebd9a6710
mkdir -p input/demo
cp ../uzp-data/dane/przyklad_01/*.pdf input/demo/
python run.py --trace 2> demo-trace.jsonl
python evaluate.py ../uzp-data/dane --split negatives --mode hybrid --output results/negatives
python evaluate.py ../uzp-data/dane --split dev --mode hybrid --output results/dev
python evaluate.py ../uzp-data/dane --split holdout --mode hybrid --output results/holdout-hybrid
python evaluate.py ../uzp-data/dane --split holdout --mode rules --output results/holdout-rules
python evaluate.py ../uzp-data/dane --split holdout --mode llm --output results/holdout-llm
python -m pip install -r requirements-dev.txt
python -m mypy --check-untyped-defs fields.py extractor.py run.py check_api.py evaluate.py tests
python -m unittest discover -s tests -p test_fields.py -v
python -m unittest discover -s tests -p test_contract.py -v
python -m unittest discover -s tests -v
python run.py --ui
```

Open [the local review interface](http://127.0.0.1:8765). For hand-in, provide the title **Akta odwoławcze · PDF → JSON**, the public GitHub URL, and `python run.py`. The optional `python run.py --ui` accepts a PDF and shows it beside the extracted JSON. Deliver the EU API settings and working token privately for the judging window.

To publish the unpacked draft from your own GitHub account, start in its root after configuring Git and signing in to the GitHub CLI. The two judged folders are included as empty directories.

```bash
git init -b main
git add .
git commit -m 'Add the Odwolania2JSON extraction prototype'
gh repo create akta-odwolawcze --public --source=. --remote=origin --push
```

The competition regulations §3.5 list a Compose configuration for the winner’s handover. The container runs the same CPU batch and uses the team HTTPS address and private credentials. For a local container rehearsal, set the base URL to an inference service reachable from inside the container. With Docker Compose installed, populate `input/` and run the following in the repository root. The `config/` directory is mounted read-only so an added document class takes effect on the next run. [Competition regulations](https://mudnibfuppwadjkynscc.supabase.co/storage/v1/object/public/task-files/057d36b5-cb92-4062-9393-983cb8a96088/files/aa36e74b-f96c-46cf-9970-5937ed203222.pdf)

```bash
docker compose config -q
docker compose run --rm --build extractor
```

## 6. Licensing

Application source is offered under AGPL-3.0. The language models under `tessdata/` are the unmodified upstream Apache-2.0 Polish and English files. Download Qwen weights and the llama.cpp server separately. The organizers' PDFs and reference JSONs are obtained from their own repository. [Application license](LICENSE) · [PyMuPDF 1.26.6](https://pypi.org/project/PyMuPDF/1.26.6/) · [Pinned OCR data](https://github.com/tesseract-ocr/tessdata_fast/tree/87416418657359cb625c412a48b6e1d6d41c29bd) · [OCR license](tessdata/LICENSE)
