"""Apply the shipped heading and field rules to page text in the browser."""
import json
from pathlib import Path

from fields import appeal, classify_headings, power, transfer

CONFIG = Path(__file__).with_name("config")
CODES = json.loads((CONFIG / "causes.json").read_text("utf-8"))
SPECS = {p.stem: json.loads(p.read_text("utf-8")) for p in CONFIG.glob("*.json") if p.stem != "causes"}


def extract_json(page_texts: str) -> str:
    pages = json.loads(page_texts)
    kind, _ = classify_headings(pages, SPECS)
    if kind == "odwolanie":
        record = appeal(pages, CODES)
    elif kind == "pelnomocnictwo":
        record = power("\n".join(pages))
    elif kind == "przelew":
        record = transfer("\n".join(pages))
    else:
        record = {}
    return json.dumps(record, ensure_ascii=False)
