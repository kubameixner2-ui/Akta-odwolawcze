"""Case-wise exact-leaf micro-F1 proxy. Gold is read after predictions are written."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from jsonschema import Draft202012Validator

from extractor import CODES, SPECS, read_pages
from run import batch
from scan_fields import reconcile_scan

KINDS = {"odwolanie": "odwolanie", "pelnomocnictwo": "pelnomocnictwo", "potwierdzenie_przelewu": "przelew"}


def leaves(value: Any, path: tuple = ()) -> set[tuple]:
    if isinstance(value, (dict, list)):
        items = value.items() if isinstance(value, dict) else enumerate(value)
        return {leaf for key, child in items for leaf in leaves(child, (*path, key))}
    if value is None:
        return set()
    kind = "number" if type(value) in (int, float) else type(value).__name__
    return {(path, kind, value)}


def f1(c: Counter) -> float:
    denom = 2*c["tp"] + c["fp"] + c["fn"]
    return 2*c["tp"]/denom if denom else 0.0


def evaluate(data: Path, split: str, mode: str, output: Path, replay_from: Path | None = None) -> dict:
    documents: list[tuple[Path, Path, Path, str]] = []
    if split == "scans":
        scan_kinds = {"odwolania": "odwolanie", "pelnomocnictwa": "pelnomocnictwo", "potwierdzenia": "przelew"}
        for folder_name, kind in scan_kinds.items():
            for pdf in sorted((data / "skany" / folder_name).rglob("*.pdf")):
                relative = Path(f"scan {len(documents) + 1:02}.pdf")
                documents.append((pdf, pdf.with_suffix(".json"), relative, kind))
        size = {"scans": len(documents)}
    else:
        folders = sorted(p for p in data.glob("przyklad_*") if p.is_dir() and
                         (int(p.name.split("_")[-1]) % 5 == 0) == (split == "holdout"))
        for folder in folders:
            for j, (stem, kind) in enumerate(KINDS.items()):
                relative = Path(folder.name) / f"document {j}.pdf"
                pdf = folder / f"{stem}.pdf"
                documents.append((pdf if pdf.is_file() else folder / f"{kind}.pdf", folder / f"{kind}.json", relative, kind))
        size = {"cases": len(folders)}
    if not documents:
        raise ValueError(f"No UZP documents for {split} in {data}")
    counts: dict[str, Counter] = {kind: Counter() for kind in KINDS.values()}
    start = time.monotonic()
    if replay_from is not None:
        if split != "scans" or replay_from.resolve() == output.resolve():
            raise ValueError("Scan replay requires a separate output directory and --split scans")
        output.mkdir(parents=True, exist_ok=True)
        for i, (pdf, _, relative, _) in enumerate(documents, 1):
            name = relative.with_suffix(".json")
            saved = (replay_from / name).read_bytes()
            if saved.strip():
                record = json.loads(saved)
                # Identify the saved prediction by its schema. Its reference is opened only during scoring.
                saved_kind = next((k for k, spec in SPECS.items() if record.keys() == spec["schema"]["properties"].keys()), None)
                if saved_kind is None:
                    raise ValueError(f"Unrecognized prediction structure in {replay_from / name}")
                document = pdf.read_bytes()
                pages, ocr = read_pages(document)
                if ocr:
                    reconcile_scan(saved_kind, record, pages, CODES, document)
                Draft202012Validator(SPECS[saved_kind]["schema"]).validate(record)
                saved = (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode()
            (output / name).write_bytes(saved)
            print(f"{i}/{len(documents)} replayed {name}", file=sys.stderr, flush=True)
        status = 0
    else:
        with TemporaryDirectory() as tmp:
            inp = Path(tmp)
            for pdf, _, relative, _ in documents:
                (inp / relative.parent).mkdir(parents=True, exist_ok=True)
                shutil.copyfile(pdf, inp / relative)
            status = batch(inp, output, mode)
    for _, reference, relative, kind in documents:
        p = output / relative.with_suffix(".json")
        raw = p.read_text("utf-8") if p.exists() else ""
        actual = json.loads(raw) if raw.strip() else None
        expected = json.loads(reference.read_text("utf-8"))
        a, b = leaves(actual), leaves(expected)
        counts[kind].update(tp=len(a & b), fp=len(a - b), fn=len(b - a), documents=1,
                            correct_type=int(isinstance(actual, dict) and actual.keys() == expected.keys()),
                            exact=int(actual == expected and a == b))
    counts["ALL"] = sum(counts.values(), Counter())
    return {"split": split, **size, "mode": "replay" if replay_from is not None else mode, "batch_exit": status,
            "elapsed_seconds": round(time.monotonic() - start, 2),
            "results": {name: {**{k: c[k] for k in ("documents", "correct_type", "exact", "tp", "fp", "fn")},
                               "f1": round(f1(c), 6)} for name, c in counts.items()}}


def evaluate_negatives(data: Path, mode: str, output: Path) -> dict:
    positive_stems = set(KINDS) | set(KINDS.values())
    candidates = sorted(p for p in data.rglob("*.pdf")
                        if p.parent.name == "negatywne" or
                        (p.parent.name.startswith("przyklad_") and p.stem not in positive_stems))
    if not candidates:
        raise ValueError(f"No released negative PDFs in {data}")
    expected = []
    with TemporaryDirectory() as tmp:
        source = Path(tmp)
        for i, pdf in enumerate(candidates):
            relative = Path(f"case {i // 3}") / f"document {i}.pdf"
            dest = source / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pdf, dest)
            expected.append(output / relative.with_suffix(".json"))
        status = batch(source, output, mode)
    empty = sum(p.is_file() and p.stat().st_size == 0 for p in expected)
    return {"split": "negatives", "mode": mode, "batch_exit": status, "documents": len(expected),
            "zero_byte_files": empty, "wrong_or_missing": len(expected) - empty}


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("data", type=Path, help="Organizer's dane directory")
    cli.add_argument("--split", choices=["dev", "holdout", "scans", "negatives"], default="holdout")
    cli.add_argument("--mode", choices=["hybrid", "rules", "llm"], default="hybrid")
    cli.add_argument("--replay-from", type=Path, help="Re-score saved scan predictions with current OCR corrections and no API calls")
    cli.add_argument("--output", type=Path, required=True, help="Prediction directory separate from gold")
    args = cli.parse_args()
    if args.replay_from is not None and args.split != "scans":
        cli.error("--replay-from requires --split scans")
    result = (evaluate_negatives(args.data, args.mode, args.output) if args.split == "negatives" else
              evaluate(args.data, args.split, args.mode, args.output, args.replay_from))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(result["batch_exit"])
