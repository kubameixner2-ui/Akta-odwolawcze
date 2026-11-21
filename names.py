"""Return dictionary-supported nominatives for Polish personal-name fields."""
import re
from typing import Any

import morfeusz2  # type: ignore[import-untyped]


def nominative(name: str, source: str, dictionary: morfeusz2.Morfeusz) -> str:
    parts = re.split(r"([\s\-‐‑]+)", name)
    words = parts[::2]
    if len(words) < 2:
        return name
    analyses: list[dict[tuple[str, str], set[str]]] = []
    for i, word in enumerate(words):
        labels = {"imię", "nazwisko"}
        if i == 0:
            labels = {"imię"}
        elif i == len(words) - 1:
            labels = {"nazwisko"}
        readings: dict[tuple[str, str], set[str]] = {}
        for _, _, (surface, lemma, tag, types, _) in dictionary.analyse(word):
            attrs = tag.split(":")
            if surface == word and labels.intersection(types) and len(attrs) == 4 and attrs[:2] == ["subst", "sg"]:
                readings.setdefault((attrs[2], attrs[3]), set()).add(lemma.partition(":")[0])
        if not readings:
            return name
        analyses.append(readings)
    shared = set.intersection(*(set(a) for a in analyses))
    if any(case == "nom" for case, _ in shared):
        return name
    for i, readings in enumerate(analyses):
        lemmas = set.union(*(readings[tag] for tag in (shared or readings.keys())))
        if len(lemmas) != 1:
            return name
        parts[2 * i] = next(iter(lemmas))
    candidate = "".join(parts)
    # A mixed-case reading needs corroboration elsewhere in the document.
    if shared or re.search(r"(?<!\w)" + re.escape(candidate) + r"(?!\w)", source, re.I):
        return candidate
    return name


def normalize_names(record: dict, pages: list[str]) -> None:
    dictionary = morfeusz2.Morfeusz(generate=False, expand_tags=True)
    source = " ".join(" ".join(pages).split())

    def visit(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key == "imie_nazwisko" and isinstance(item, str):
                    value[key] = nominative(item, source, dictionary)
                else:
                    visit(item)

    visit(record)
