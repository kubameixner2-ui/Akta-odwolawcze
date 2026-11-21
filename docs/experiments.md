# Earlier Qwen experiments and implementation decisions

The hosted Scaleway scan measurement and current judging instructions are in the [README](../README.md). The results below record the earlier Qwen setup and the UZP revisions used at the time.

**Earlier Qwen hybrid.** It copies amounts, names and account digits from labelled text and uses the team’s Qwen API for uncertain allegations, unfamiliar layouts and new classes. The submitted code achieved **99.75% exact-field micro-F1 on 180 public in-scope PDFs**. The first blind comparison scored **99.27%** on 36 PDFs for both hybrid and rules-only, and **78.42%** for full-document Qwen. This public experiment cannot establish the maximum possible hidden F1. The organizer’s separate hidden test contains real cases. [Task description, §§6–8](https://mudnibfuppwadjkynscc.supabase.co/storage/v1/object/public/task-files/057d36b5-cb92-4062-9393-983cb8a96088/files/aeabc57d-7420-4069-946e-2c4de71d87ed.pdf)

## 1. Establish the contract

We examined the official release at commit `de135d20811caf630f3e94dc655ba5eebd9a6710`. Under `dane/` are 60 positive case folders with 180 in-scope PDFs and 180 document-level JSON references. There are also 16 out-of-scope PDF paths, consisting of 12 in `negatywne/` and four inside case folders. Eleven of these PDFs are unique by SHA-256. The 180 positive PDFs and references are unchanged from the earlier benchmark at `8d0ef96245ad6dc3255767adf537fe8b86ed86f9`. Each input must produce its own same-path, same-stem output. An in-scope input gets a UTF-8 JSON record. An excluded PDF gets a zero-byte `.json` file. For instance, the reference is named `przelew.json`, but the judge-facing output for `potwierdzenie_przelewu.pdf` is `potwierdzenie_przelewu.json`. Only the evaluator knows the mapping between test inputs and reference filenames. [Official specification](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/blob/de135d20811caf630f3e94dc655ba5eebd9a6710/README.md) · [Negative-output instructions](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/blob/de135d20811caf630f3e94dc655ba5eebd9a6710/dane/negatywne/readme.md) · [Pinned data](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/tree/de135d20811caf630f3e94dc655ba5eebd9a6710/dane)

The slides’ 39 cases, 117 PDFs and YAML assertions describe an older revision. Its case 01 used containment and similarity assertions. The current repository has no executable official scorer. The testing computer is an Intel i7 with 16 GB RAM and no GPU. The CPU client runs OCR locally. The team supplies an API key to the judges. The stricter geographic requirement in the team’s copy of FAQ 1.0 is that both the provider and the inference server be in the EU. An EU company providing inference in Germany or France meets both texts. Hetzner is a German infrastructure provider for the proposed self-hosted option. The team would operate that API and should confirm that arrangement with UZP. Scaleway provides a vendor-operated Paris inference alternative. [Historical YAML](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/blob/49e7c35740530d486fc100220f4ab1e626c9ab07/dane/przyklad_01/ground_truth.yaml) · [Hardware and API rules](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/blob/de135d20811caf630f3e94dc655ba5eebd9a6710/README.md)

Preselection is 100% hidden-set F1. The team confirmed **50% F1, 30% extensibility and 20% architecture** for the final, matching §8 of the detailed task description. The signed regulations §2.4 and FAQ 10 describe the non-F1 half as one category. The latest README breaks that half into up to 20 points for model size (smaller receives more), 20 for extending types and fields, and 10 for extras such as a GUI. Demonstrate a 4B model on CPU, a fourth class and a new field loaded from configuration, and the side-by-side interface with validation and field evidence. The regulations §3.5 list Compose configuration for the winner’s handover and §4.1 asks teams to identify third-party components in their presentation. [Signed regulations](https://mudnibfuppwadjkynscc.supabase.co/storage/v1/object/public/task-files/057d36b5-cb92-4062-9393-983cb8a96088/files/aa36e74b-f96c-46cf-9970-5937ed203222.pdf) · [Task description](https://mudnibfuppwadjkynscc.supabase.co/storage/v1/object/public/task-files/057d36b5-cb92-4062-9393-983cb8a96088/files/aeabc57d-7420-4069-946e-2c4de71d87ed.pdf) · [Current rubric](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/blob/de135d20811caf630f3e94dc655ba5eebd9a6710/README.md)

## 2. Verify extraction decisions on development cases

- **Appeal dates and parties.** Fourteen of the 48 development appeals had blank first-page town and date despite displaying other addresses and dates. One appeal can name two lawyers while its reference selects the first and its power of attorney lists both. Recognize consortium leadership and company-specific signature blocks. Three development appeals had two contracting authorities and four development powers had two grantors. [Case 01](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/tree/8d0ef96245ad6dc3255767adf537fe8b86ed86f9/dane/przyklad_01) · [Case 41](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/tree/8d0ef96245ad6dc3255767adf537fe8b86ed86f9/dane/przyklad_41)
- **First allegation.** Distinguish a decision from the omission to take one. Use the first numbered allegation and the dated event it describes. Map the resulting number to the canonical description. For reason 6 the new dictionary and the annotated appeal field guide both use `Odpowiedzi/wyjaśnienia do SWZ`. All five public references with this reason, cases 19, 23, 25, 44 and 55, use `Odpowiedzi i wyjaśnienia do SWZ`. The submission uses the published dictionary. Its spelling costs five exact leaves against these references. The model and the numeric reason agree in all five. One value in `config/causes.json` controls the choice. [Dictionary](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/blob/de135d20811caf630f3e94dc655ba5eebd9a6710/oczekiwane-json/czynnosc_powod_id_dict.md) · [Appeal field guide](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/blob/de135d20811caf630f3e94dc655ba5eebd9a6710/oczekiwane-json/odwolanie.json#L5-L6) · [Reference example 19](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/blob/de135d20811caf630f3e94dc655ba5eebd9a6710/dane/przyklad_19/odwolanie.json#L5-L6)
- **Identifiers and money.** All 96 labelled development accounts were 26 digits. Applying `int(account[2:] + "2521" + account[:2]) % 97 == 1` accepted 33 and would have discarded 63 expected values. Nine began with zero. Copy the digits associated with the correct party. Link the amount and date to the executed transfer. In the development powers, the single non-null PESEL was a string. The LLM mapped a lawyer’s bar registration to PESEL in one real call, so the code checks for the printed PESEL label. [PESEL example](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/blob/8d0ef96245ad6dc3255767adf537fe8b86ed86f9/dane/przyklad_43/pelnomocnictwo.json) · [Transfer example](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/tree/8d0ef96245ad6dc3255767adf537fe8b86ed86f9/dane/przyklad_01)
- **Model evidence.** Grammar-constrained decoding improved structured tasks in Geng et al. Ravikumar et al. found that the best output representation varied across models and tasks. Both studies evaluated other datasets. The implementation includes field semantics in the prompt because llama.cpp uses its schema to constrain generation without injecting it into the model’s prompt. [Geng et al., EMNLP 2023](https://aclanthology.org/2023.emnlp-main.674/) · [Ravikumar et al., EACL 2026](https://aclanthology.org/2026.eacl-long.256/) · [llama.cpp documentation](https://github.com/ggml-org/llama.cpp/blob/b12603/grammars/README.md)

## 3. Evaluate the submission and its alternatives

The released configuration produced the following on the pinned public data. Both splits here are reruns after inspecting earlier errors. The first blind results follow below.

| Submission with dictionary spelling | In-scope PDFs | TP | FP | FN | Micro-F1 | Exact JSONs |
|---|---:|---:|---:|---:|---:|---:|
| Development cases | 144 | 1,616 | 3 | 3 | 99.81% | 141/144 |
| Reserved cases revisited | 36 | 411 | 2 | 2 | 99.52% | 34/36 |
| Combined | 180 | 2,027 | 5 | 5 | 99.75% | 175/180 |

All 180 documents were assigned the correct class. Each of the five whole-document mismatches is confined to the exact string for reason 6. The initial negative-set check produced empty files on 14/16 paths. Its two errors were duplicate copies of a teaching presentation about appeals. Clarifying the classifier prompt still allowed the model to treat the presentation as a filed appeal. The released classifier recognizes a numbered cover followed by repeated slide headings. After that correction, the hybrid wrote a same-path, zero-byte JSON file on **16/16 official negative paths** (11 distinct PDFs). This rerun includes the inspected example. The negative count is reported separately from positive-field F1.

### First blind comparison

We set aside cases 05, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55 and 60 before adjusting extraction rules. The remaining 48 cases were development data. The evaluator copies only PDFs to new directories under opaque filenames, runs the ordinary batch command, then reads the reference files. Each extraction sees exactly one PDF. The public cases contain repeated layouts. The separate task description, §§6–7, calls the training documents synthetic and the hidden cases real. The signed regulations specify at least ten hidden cases.

A scored item is a pair consisting of its full JSON path (including array indices) and its typed non-null scalar value. A wrong value contributes one false positive and one false negative. Null contributes no item. Strings compare exactly, JSON integers and floating-point numbers compare numerically, and booleans are distinct. We calculate `2 TP / (2 TP + FP + FN)`. A second check compares the complete JSON, including lists, expected nulls and keys.

| Frozen hybrid, first blind run | Documents | TP | FP | FN | Micro-F1 | Exact documents |
|---|---:|---:|---:|---:|---:|---:|
| Appeals | 12 | 243 | 3 | 3 | 98.78% | 11/12 |
| Powers of attorney | 12 | 95 | 0 | 0 | 100% | 12/12 |
| Transfers | 12 | 72 | 0 | 0 | 100% | 12/12 |
| All | 36 | 410 | 3 | 3 | 99.27% | 35/36 |

The rules-only run had the same counts. The frozen hybrid made two focused calls and returned the other 34 records without an API call. All 36 were classified correctly. The 48-case development hybrid matched 144/144 documents. These are measurements under the specified proxy.

**What failed.** In case 40 a page break interrupts the introduction to the first numbered allegation. The extractor chose a request for price explanations dated 18 September. The appeal challenged an award dated 9 October. That changed the date, reason ID and description. Removing stand-alone pagination and selecting the factual event with the allegation’s date resolved all three fields. With the earlier reference spelling for code 6, the corrected hybrid matched 413/413 non-null leaves and 36/36 entire documents on the revisited split, and 180/180 across the public positives. These are retrospective figures. To reproduce the frozen comparison, use a disposable copy of the project, set cause 6 to `Odpowiedzi i wyjaśnienia do SWZ` in `config/causes.json`, then run `git apply -R benchmarks/first-claim.patch` and the holdout evaluator. The rules-mode replay reproduced 410 TP, 3 FP and 3 FN. [Case 40](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/tree/de135d20811caf630f3e94dc655ba5eebd9a6710/dane/przyklad_40)

The organizer’s seven-page raster appeal required OCR on seven pages and produced a schema-valid appeal through the full API route. Its available reference was an empty placeholder, so field accuracy cannot be measured there. A separate nine-page TED notice was recognized as out of scope. [Organizer template](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/tree/de135d20811caf630f3e94dc655ba5eebd9a6710/szablon-aplikacja)

### Full-document API comparison

Using the earlier reference spelling for code 6 and the same reader, classifier, output schemas and semantic postprocessing, `--mode llm` sent every recognized reserved PDF to the Qwen service for full-field generation. All 36 yielded a record of the correct type. This run produced **78.42% field F1 and 8/36 exact JSONs**. It missed or mistranscribed 10 of the 12 first-claim trigger dates and 10 of 12 values for each of the two account fields. A valid JSON of the correct class can still contain incorrect party roles or digits.

| Type | Correct values | Extra or wrong | Missing or wrong | Micro-F1 | Exact JSONs |
|---|---:|---:|---:|---:|---:|
| Appeals | 212 | 93 | 34 | 76.95% | 0/12 |
| Powers of attorney | 85 | 10 | 10 | 89.47% | 7/12 |
| Transfers | 50 | 22 | 22 | 69.44% | 1/12 |
| All | 347 | 125 | 66 | 78.42% | 8/36 |

All 36 original predictions are included in these counts. We resumed from completed files after the server terminated and a subsequent request exceeded the original client timeout. The split and matching procedure behind the organizers’ reported 70% remain unverified.

### Controlled scan check

We also printed development case 01 to image-only PDFs at 160 dpi. Each page retained its physical dimensions. We verified that native extraction returned no text on every page and ran the normal 300-dpi Polish/English OCR path against the original references. On this four-page case the initial hybrid sent all three PDFs to the API. It recovered every expected value and added 13 extra values, giving 32 TP, 13 FP, 0 FN and 83.12% F1. Eleven extra values belonged to the appeal and two were attorneys attributed a second time as grantor signers. Rules alone scored 29 TP, 1 FP, 3 FN and 93.55%.

The corrected reader uses word positions when the grantor and acceptance signature headings occupy parallel columns. The router retains fully labelled, validated OCR records, and calls the model when fields remain unresolved. The corrected run matched all 3/3 references, including all 32 populated values. The appeal and power of attorney were complete after OCR and used the rule path. The bank document used the full API, with its labelled bank fields preserved. One clean rasterized case measures this failure mode. Physical scans with rotation, stamps, or low contrast can behave differently.

A second scan check used case 05, whose native-text documents were already in the reserved set. We handled its images with the routing and signature fixes before inspecting their errors. The first hybrid pass recovered 31 of 33 populated values with two false positives and two false negatives, giving **93.94% F1 and 1/3 exact documents**. In both fields, OCR had transcribed the company suffix `sp. z o.o.` with zeros. The subsequent correction is restricted to OCR-derived entity names and a zero in that exact suffix pattern. It retains the captured capitalization of `sp.`. The subsequent rerun recovered 33/33 values and all three complete references. That result includes the two errors already inspected. The pre-correction 93.94% is the result for the fresh scan rendering. Apply `git apply -R benchmarks/ocr-company-suffix.patch` in a separate copy to replay it. The official spelling is documented in art. 160 §2 of the Commercial Companies Code. [Official text](https://dziennikustaw.gov.pl/D2024000001801.pdf)

Recreate these inputs from the project root after the setup in the README. For the case 05 check, substitute `przyklad_05` in both paths below and use `--split holdout`. The evaluator exposes only PDFs to the classifier. Reference files are copied alongside the synthetic fixtures for scoring after predictions are written.

```bash
python - ../uzp-data/dane/przyklad_01 results/rasterized/przyklad_01 <<'PY'
from pathlib import Path
import shutil
import sys
import pymupdf

source, target = map(Path, sys.argv[1:])
target.mkdir(parents=True, exist_ok=True)
for pdf in sorted(source.glob("*.pdf")):
    with pymupdf.open(pdf) as original, pymupdf.open() as scan:
        for page in original:
            dest = scan.new_page(width=page.rect.width, height=page.rect.height)
            dest.insert_image(dest.rect, pixmap=page.get_pixmap(dpi=160, alpha=False))
        scan.save(target / pdf.name, deflate=True, garbage=4)
for gold in source.glob("*.json"):
    shutil.copyfile(gold, target / gold.name)
PY
python evaluate.py results/rasterized --split dev --mode hybrid --output results/rasterized-pred
```

### Endpoint and runner checks

The authenticated CPU endpoint returned HTTP 401 without a credential and passed `python check_api.py` with the private test credential. A fourth class defined on disk extracted `{"numer": "WN-27"}` via the real service and reported page 1 as its evidence. A regression test adds a required currency field to the existing transfer config. Another registers KIO judgments as a new type through configuration, even though the three-class submission excludes them. A Chromium check exercised both downloads: a transfer matched the reference JSON and a court order produced zero bytes. It checked the original-page preview, desktop columns and the 390-pixel mobile layout.

A sustained full-document benchmark lost its local server after 15 completed PDFs. The server command in the README bounds memory with `--cache-ram 0 -ub 128`. An 11-page appeal took 362 seconds in one full CPU call, exceeding the initial 240-second client timeout. The draft now allows 600 seconds per completion. If transport fails in hybrid mode, it keeps a schema-valid, partly populated rule record and marks the fallback on stderr. A required field with no schema-valid partial record still surfaces an error. UZP’s actual time budget is an open question.

## 4. Assumptions and decisions that would change the result

| Assumption | Evidence or reason | What would change |
|---|---|---|
| The judging computer can reach the team’s HTTPS endpoint | FAQ 11 requires a team-supplied key. The README specifies an i7, 16 GB RAM and EU/EEA service. | Use an approved team-operated server in Falkenstein or a company-operated Paris endpoint. Recheck latency and quality if the endpoint or model changes. |
| Each PDF supplies its own evidence | FAQ 6 asks for null where the document lacks a nullable fact. An appeal can intentionally omit facts present in its power of attorney. | Only reconsider joining files if UZP explicitly designates a field as case-level. |
| UZP’s “pusty plik” means zero bytes | The latest README and the separate negative-set instructions explicitly require an empty file at the expected path. | A later specification may define a different byte representation. |
| The canonical reason text comes from the new dictionary | Five existing references for reason 6 use the word `i` where the dictionary uses a slash. The field types and remaining values follow the valid JSON references. | A mentor ruling on reason 6 changes one configuration value. An official scorer would supersede our matching assumptions. |
| A working local open-weight setup is a viable candidate | The quantized Qwen model was run on CPU through the schema-constrained endpoint. A larger model has not been established as superior on this task. | Compare endpoint candidates using the same case split, held-back layouts, actual latency and compatible licensing. |

## Questions for the judges

1. Czy możecie podać przykład naliczania TP/FP/FN dla błędnej wartości, pola null, brakującego pola i listy w innej kolejności? Jak agregujecie F1 i na jakim zbiorze uzyskaliście wynik około 70%?
2. Dla `OdwolanieKIO.czynnosc_powod_id = 6`, czy automat porównuje dosłownie `czynnosc_opis`? Słownik podaje „Odpowiedzi/wyjaśnienia do SWZ”, przykład 19 podaje „Odpowiedzi i wyjaśnienia do SWZ”. Który zapis obowiązuje?
3. Jaki jest limit czasu na partię i na jeden PDF? Czy trzeba wcześniej przekazać adres HTTPS zespołu do listy dozwolonych?

At the UZP stand, ask to inspect a scan, a case with several powers of attorney and a missing field, and how the scorer treats such fields. These are the examples most likely to contradict the public-set results. The subsequent hosted scan benchmark used the team’s Scaleway endpoint and private key. Machine-readable counts for each run are in [the benchmark results](../benchmarks/public-rerun.json).
