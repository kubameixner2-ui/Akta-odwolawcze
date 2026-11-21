"""Check the real batch CLI on a pinned public demo or a 150-PDF timing sample."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluate import KINDS, leaves
from extractor import SPECS

REVISION = "84cc976f0a9af5cee14f131c795f929134ca0fda"
REPOSITORY = "https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026.git"
LIMIT = 45 * 60
Sample = tuple[Path, Path, Path | None]  # Source PDF, relative input name, reference JSON.


def native(data: Path, case: int, kind: str, target: Path) -> Sample:
    folder = data / f"przyklad_{case:02}"
    pdf = folder / f"{kind}.pdf"
    if kind == "przelew" and not pdf.exists():
        pdf = folder / "potwierdzenie_przelewu.pdf"
    return pdf, target, folder / f"{kind}.json"


def demo(data: Path) -> list[Sample]:
    rows = [(1, 1, "odwolanie", 1), (1, 1, "pelnomocnictwo", 1),
            (1, 3, "pelnomocnictwo", 2), (1, 1, "przelew", 1),
            (2, 2, "odwolanie", 2), (2, 2, "pelnomocnictwo", 3), (2, 2, "przelew", 2)]
    samples = [native(data, case, kind, Path(f"case{dest}/{kind}_nr_{number}.pdf"))
               for dest, case, kind, number in rows]
    samples.append((data / "przyklad_04/2025_S 112-383751.pdf", Path("case3/attachment.pdf"), None))
    return samples


def timing(data: Path) -> list[Sample]:
    def opaque(index: int) -> Path:
        return Path(f"case{index // 3 + 1:02}/document{index % 3 + 1}.pdf")

    samples: list[Sample] = []
    for case in range(1, 36):
        for kind in KINDS.values():
            if case <= 34 or kind != "przelew":
                samples.append(native(data, case, kind, opaque(len(samples))))
    scans = sorted((data / "skany").rglob("*.pdf"))
    known_stems = set(KINDS) | set(KINDS.values())
    exclusions = sorted(p for p in data.rglob("*.pdf") if p.parent.name == "negatywne" or
                        (p.parent.name.startswith("przyklad_") and p.stem not in known_stems))
    if len(scans) != 30 or len(exclusions) != 16:
        raise ValueError(f"Expected 30 scans and 16 exclusions at {REVISION}, found {len(scans)} and {len(exclusions)}")
    for pdf in scans:
        samples.append((pdf, opaque(len(samples)), pdf.with_suffix(".json")))
    for pdf in exclusions:
        samples.append((pdf, opaque(len(samples)), None))
    return samples


def score_outputs(samples: list[Sample], output_dir: Path) -> dict[str, int]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"Invalid JSON number {value}")

    expected = {rel.with_suffix(".json"): gold for _, rel, gold in samples}
    written = {p.relative_to(output_dir) for p in output_dir.rglob("*") if p.is_file() or p.is_symlink()}
    validators = [Draft202012Validator(spec["schema"]) for spec in SPECS.values()]
    counts = dict.fromkeys(("zero_byte_outputs", "correct_zero_byte", "empty_in_scope", "nonempty_exclusions",
                            "wrong_class_in_scope", "invalid_paths", "invalid_utf8", "invalid_json",
                            "invalid_schema", "exact_in_scope"), 0)
    for relative in written:
        dest = output_dir / relative
        if dest.is_symlink():
            counts["invalid_paths"] += 1
            continue
        raw = dest.read_bytes()
        if not raw:
            counts["zero_byte_outputs"] += 1
        if relative not in expected:
            continue
        reference = expected[relative]
        if not raw:
            counts["correct_zero_byte" if reference is None else "empty_in_scope"] += 1
            continue
        counts["nonempty_exclusions"] += int(reference is None)
        try:
            record = json.loads(raw.decode("utf-8"), parse_constant=reject_constant)
        except UnicodeDecodeError:
            counts["invalid_utf8"] += 1
            continue
        except ValueError:
            counts["invalid_json"] += 1
            continue
        matching = [validator for validator in validators if validator.is_valid(record)] if isinstance(record, dict) else []
        if not matching:
            counts["invalid_schema"] += 1
        elif reference is not None:
            gold = json.loads(reference.read_bytes())
            if not any(validator.is_valid(gold) for validator in matching):
                counts["wrong_class_in_scope"] += 1
            else:
                counts["exact_in_scope"] += int(record == gold and leaves(record) == leaves(gold))
    exclusions = sum(reference is None for reference in expected.values())
    return {**counts, "outputs": len(written), "missing": len(expected.keys() - written),
            "unexpected": len(written - expected.keys()), "in_scope": len(samples) - exclusions,
            "expected_exclusions": exclusions, "exact_outputs": counts["exact_in_scope"] + counts["correct_zero_byte"]}


def verdict(profile: str, counts: dict[str, int], batch_exit: int, seconds: float) -> dict[str, bool | None]:
    format_faults = ("missing", "unexpected", "invalid_paths", "invalid_utf8", "invalid_json", "invalid_schema")
    format_ok = not any(counts[field] for field in format_faults)
    disposition_ok = not any(counts[field] for field in ("empty_in_scope", "nonempty_exclusions", "wrong_class_in_scope"))
    contract_ok = batch_exit == 0 and format_ok and disposition_ok
    within_time = batch_exit != 124 and seconds <= LIMIT if profile == "timing" else None
    exact = counts["exact_outputs"] == counts["in_scope"] + counts["expected_exclusions"]
    return {"output_format_ok": format_ok, "disposition_ok": disposition_ok, "output_contract_ok": contract_ok,
            "within_time_limit": within_time, "passed": contract_ok and (exact if within_time is None else within_time)}


def check(profile: str, mode: str, data: Path, run: Path) -> int:
    samples = demo(data) if profile == "demo" else timing(data)
    input_dir, output_dir = run / "input", run / "output"
    signatures = set()
    for pdf, relative, _ in samples:
        dest = input_dir / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pdf, dest)
        signatures.add(hashlib.sha256(dest.read_bytes()).digest())
    output_dir.mkdir()
    command = [sys.executable, str(ROOT / "run.py"), "--mode", mode,
               "--input", str(input_dir), "--output", str(output_dir)]
    print(f"Processing {len(samples)} PDFs in {run}", file=sys.stderr, flush=True)
    with (run / "batch.log").open("w", encoding="utf-8") as log:
        start = time.monotonic()
        try:
            status = subprocess.run(command, cwd=ROOT, stderr=log, timeout=LIMIT if profile == "timing" else None).returncode
        except subprocess.TimeoutExpired:
            status = 124
        seconds = time.monotonic() - start

    counts = score_outputs(samples, output_dir)
    checks = verdict(profile, counts, status, seconds)
    report = {"profile": profile, "mode": mode, "expected_fixture_revision": REVISION, "pdfs": len(samples),
              "distinct_source_paths": len({p for p, _, _ in samples}), "distinct_pdf_contents": len(signatures),
              **counts, **checks,
              "batch_exit": status, "wall_seconds": round(seconds, 3), "seconds_per_pdf": round(seconds / len(samples), 3),
              "time_limit_seconds": LIMIT if profile == "timing" else None}
    encoded = json.dumps(report, indent=2)
    (run / "report.json").write_text(encoded + "\n", "utf-8")
    print(encoded)
    return int(not checks["passed"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=("demo", "timing"))
    parser.add_argument("--mode", choices=("rules", "hybrid"), default="rules")
    parser.add_argument("--data", type=Path, help="Existing pinned organizer dane directory")
    args = parser.parse_args()
    if args.data is not None and not (args.data / "przyklad_01").is_dir():
        parser.error("--data must be the organizer's dane directory containing przyklad_01")
    results = ROOT / "results"
    results.mkdir(exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix=f"{args.profile}-{args.mode}-", dir=results))
    if args.data is not None:
        return check(args.profile, args.mode, args.data.resolve(), run)
    with tempfile.TemporaryDirectory(dir=run) as work:
        repo = Path(work) / "organizer"
        subprocess.run(["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", REPOSITORY, str(repo)], check=True)
        paths = ["dane"] if args.profile == "timing" else [f"dane/przyklad_{case:02}" for case in range(1, 5)]
        subprocess.run(["git", "-C", str(repo), "sparse-checkout", "set", *paths], check=True)
        subprocess.run(["git", "-C", str(repo), "checkout", "--quiet", "--detach", REVISION], check=True)
        return check(args.profile, args.mode, repo / "dane", run)


if __name__ == "__main__":
    raise SystemExit(main())
