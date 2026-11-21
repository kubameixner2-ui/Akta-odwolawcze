"""Labelled fields and first-allegation rules for Polish KIO documents."""
from __future__ import annotations

import re
from datetime import date
from typing import Any

Record = dict[str, Any]
MONTHS = "stycznia lutego marca kwietnia maja czerwca lipca sierpnia września października listopada grudnia".split()
DATE = rf"(?:\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}[./-]\d{{1,2}}[./-]\d{{4}}|\d{{1,2}}\s+(?:{'|'.join(MONTHS)})\s+\d{{4}})"
UP = "A-ZĄĆĘŁŃÓŚŹŻ"
WORD = rf"[{UP}][a-ząćęłńóśźżA-ZĄĆĘŁŃÓŚŹŻ-]+"
NAME = rf"{WORD}(?: {WORD}){{1,2}}"
LAWYER = r"(?i:\badw\.|\br\.\s*pr\.|\bradc[ayęą]\s+prawn\w*|\badwokat(?:a|owi|em|ce|k[aęąi])?)\s+"


def flat(text: str) -> str:
    return " ".join(text.split())


def take(pattern: str, text: str, flags: int = re.I) -> str | None:
    match = re.search(pattern, text, flags)
    return flat(match[1]).strip() if match else None


def iso(value: str | None) -> str | None:
    if not value:
        return None
    parts = re.split(r"[\s./-]+", value.lower())
    try:
        if len(parts[0]) == 4:
            year, month, day = map(int, parts)
        else:
            day, year = int(parts[0]), int(parts[2])
            month = int(parts[1]) if parts[1].isdigit() else MONTHS.index(parts[1]) + 1
        return date(year, month, day).isoformat()
    except (ValueError, IndexError):
        return None


def transfer(text: str) -> Record:
    t = flat(text)
    sep = r"[.:\s]+"
    def account(labels: str, party: str) -> str | None:
        found = take(rf"(?:{labels})(?:\s+nr)?{sep}((?:PL\s*)?\d(?: ?\d){{19,33}})(?!\d)", t)
        if not found and (m := re.search(rf"\b(?:{party})\b", t, re.I)):
            parties = r"\b(?:beneficjent|odbiorca|dane odbiorcy|adresat przelewu|płatnik|zleceniodawca|dane nadawcy|nadawca)\b"
            block = re.split(parties, t[m.end():m.end()+200], maxsplit=1, flags=re.I)[0]
            found = take(r"\b((?:PL\s*)?\d{2}(?:\s?\d{4}){6})(?!\d)", block)
        return re.sub(r"\D", "", found) if found else None

    day = take(rf"(?:data (?:operacji|realizacji|wykonania|transakcji)|bank potwierdza, że w dniu){sep}({DATE})", t)
    amount = take(rf"(?:\bkwota(?: operacji| przelewu)?|wartość|w kwocie){sep}(?:PLN\s*)?(\d[\d ]*[,.]\d{{2}})", t)
    ref = take(r"(?:numer (?:transakcji|referencyjny)|nr ref\.?|identyfikator (?:operacji|transakcji))(?: operacji)?[:.\s]+([\w/-]*\d[\w/-]*)", t)
    title = take(r"^\s*(?:tytuł(?: przelewu|em)?|opis(?: operacji)?)\b[:. \t]*\s*([\s\S]+?)(?=\n\s*(?:nr ref|numer |identyfikator |status|waluta|typ operacji|kanał|tryb|kwota|wartość|data |opłata|zrealizowano|bank nie|potwierdzenie ma)|\Z)", text, re.I | re.M)
    if title:
        title = re.sub(r'^[„“"](.*)[”"]\.?$', r"\1", title)
    return {"przelew_bankowy": {
        "z_rachunku": account(r"z rachunku|rachunek (?:nadawcy|obciążany|zleceniodawcy|płatnika)", r"płatnik|zleceniodawca|dane nadawcy|nadawca"),
        "na_rachunek": account(r"na rachunek|rachunek (?:odbiorcy|beneficjenta|uznawany)", r"beneficjent|odbiorca|dane odbiorcy|adresat przelewu"),
        "kwota": float(amount.replace(" ", "").replace(",", ".")) if amount else None,
        "data_operacji": iso(day), "numer_transakcji": ref, "tytul": title}}


def identifier(label: str, text: str) -> str | None:
    return take(rf"\b{label}\s*:?\s*(\d[\d-]{{7,16}})\b", text)


def lawyers(text: str) -> list[Record]:
    found: dict[str, str | None] = {}
    for m in re.finditer(LAWYER + rf"({NAME})(?:,?\s*PESEL\s*:?\s*(\d{{11}}))?", flat(text)):
        found[m[1]] = m[2] or found.get(m[1])
    return [{"imie_nazwisko": k, "pesel": v} for k, v in found.items()]


def appointees(text: str) -> list[Record]:
    block = re.search(r"(?is)\budziel\w*[\s:]+pe[łlt]nomocnictwa\s*:(.*?)\bdo reprezentowania\b", text)
    if not block:
        return lawyers(text)
    # Lists can put the profession after the name or omit it for employees.
    titled = rf"{LAWYER}({WORD}(?:\s+{WORD}){{1,2}})"
    untitled = rf"([^\W\d_]+(?:[ \t]+{WORD}){{1,2}})"
    matches = list(re.finditer(rf"(?:^|[,;]|\boraz\s+)[ \t]*(?:\d+[.)][ \t]*)?(?:{titled}|{untitled})"
                               rf"(?=[ \t]*(?:$|[,.(;—–-]))", block[1], re.M))
    people = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(block[1])
        pesel = take(r"\bPESEL\s*:?\s*(\d{11})\b", block[1][match.end():end])
        name = flat(match[1] or match[2])
        full_name = name[0].upper() + name[1:]
        people.append({"imie_nazwisko": full_name, "pesel": pesel})
    return people or lawyers(text)


def entity(section: str) -> Record:
    name = take(r"^\s*(.+?)(?=,\s*(?:ul\.|al\.|pl\.)|\n\s*(?:ul\.|al\.|pl\.|alej|\S+\s+\d+[,/]|(?:KRS|NIP|REGON)\b)|\Z)", section, re.I | re.S)
    return {"nazwa": name, **{k: identifier(k, section) for k in ("krs", "nip", "regon")}}


# Check omissions before the corresponding positive actions.
CAUSE_PATTERNS = {
    10: r"(?:zaniecha\w*|nie)\s+unieważ", 8: r"(?:zaniecha\w*|nie)\s+wyklucz",
    7: r"(?:zaniecha\w*|nie)\s+odrzuc", 9: r"unieważni", 3: r"wyklucz",
    1: r"odrzuc", 6: r"odpowiedzi|wyjaśnie[nń]", 5: r"zmodyfik|modyfikac",
    12: r"postanowie\w* umow|projekt\w* umow", 11: r"opis\w* przedmiot",
    4: r"opublikowa\w*|udostępni\w* (?:swz|specyfikac)", 2: r"wyb[oó]r|wybor",
}


def first_action(pages: list[str]) -> tuple[str, str]:
    without_footers = re.sub(r"(?im)^[ \t]*strona\s+\d+\s+z\s+\d+[ \t]*$", "", "\n".join(pages))
    t = flat(without_footers)
    first = take(r"(?:polegających na:\s*1[).]\s*|Zarzut nr 1\s*[–:-]\s*)(.{10,650}?)(?=\s+[2][).]\s|Zarzut nr 2|;|$)", t)
    events = list(re.finditer(rf"Zamawiający w dniu ({DATE}).{{0,480}}?(?=\.(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ]|$)|\s+Zarzut nr|$)", t))
    dates = {iso(s) for s in re.findall(DATE, first or "", re.I)}
    if len(dates) == 1:
        for event in events:
            if iso(event[1]) in dates:
                return event[0], first or ""
    return events[0][0] if events else "", first or ""


def appeal(pages: list[str], codes: dict[str, str]) -> Record:
    page = pages[0]
    headers = r"(?im)^\s*(?:Odwołujący\s*:|Zamawiający\s*[:(]|Wykonawca wybrany\b|Dotyczy\s*:|ODWOŁANIE\s*$|Prezes Krajowej|Krajowa Izba)"
    def section(label: str) -> str:
        heading = re.search(rf"(?im)^\s*{label}\s*:", page)
        return re.split(headers, page[heading.end():], maxsplit=1)[0].strip() if heading else ""

    appellant = section("Odwołujący")
    leader = re.split(r"(?i)\d\)\s*Lider Konsorcjum:\s*", appellant)[-1]
    leader = re.split(r"(?i)\d\)\s*Partner Konsorcjum", leader)[0]
    representative = take(r"reprezentowan\w* przez[.\s]*(?:pe[łlt]nomocnik\w*\s*)?:\s*(.*?)(?=adres do|\btel\.|$)", flat(appellant)) or ""
    names = lawyers(representative)
    firm = take(r"adres do korespondencji\s*:\s*(.+?)(?=,\s*(?:ul\.|al\.|pl\.)|\btel\.)", flat(appellant))
    mail = take(r"([\w.+-]+@[\w.-]+\.[\w-]+)", appellant)
    appellants = []
    if leader:
        appellants.append({**entity(leader), "przez-pelnomocnika": int(bool(representative or firm)),
            "pelnomocnik": {"imie_nazwisko": names[0]["imie_nazwisko"] if names else None, "nazwa": firm, "mail": mail}})
    authorities = []
    for m in re.finditer(r"(?im)^\s*\d+\)\s*Zamawiający\s*[–-]\s*([^:]+):\s*\n", page):
        block = re.split(headers + r"|(?im:^\s*\d+\)\s*Zamawiający)", page[m.end():], maxsplit=1)[0]
        authorities.append({**entity(block), "prowadzacy_postepowanie": int(bool(re.search("lider|prowadzący", m[1], re.I)))})
    if not authorities and (authority := section("Zamawiający")):
        authorities.append({**entity(authority), "prowadzacy_postepowanie": None})
    stamp = re.search(rf"(?m)^\s*({WORD}(?: {WORD}){{0,3}}),?\s+(?:dnia\s+)?({DATE})(?:\s+(?:roku|r\.))?\s*$", page)
    subject = flat(page)
    bzp = take(r"(\d{4}\s*/\s*BZP\s*\d{8}(?:/\d{2})?)", subject)
    ted = take(r"(?<![\d-])(\d{5,6}-\d{4})(?!\d)", subject)
    if alt := re.search(r"\b(\d{4})\s*/\s*S\s*\d{1,3}\s*[-–]\s*(\d{5,6})\b", subject, re.I):
        ted = f"{alt[2]}-{alt[1]}"
    action, _ = first_action(pages)
    code = next((n for n, pat in CAUSE_PATTERNS.items() if re.search(pat, action, re.I)), None)
    return {"OdwolanieKIO": {"data": iso(stamp[2]) if stamp else None, "miejscowosc": stamp[1] if stamp else None,
        "czynnosc_dzien": iso(take(rf"\bw dniu ({DATE})", action)), "czynnosc_powod_id": code,
        "czynnosc_opis": codes.get(str(code))}, "Odwolujacy": appellants, "Zamawiajacy": authorities,
        "ZamowieniePubliczne": {"tytul": take(r'\bpn\.\s*[„“"](.+?)[”"]', subject),
        "numer_postepowania": take(r"(?:nr referencyjny(?: sprawy)?|numer postępowania)\s*:\s*([\w./-]+)", subject),
        "numer_bzp": re.sub(r"\s", "", bzp) if bzp else None, "numer_ted": ted}}


def power(text: str) -> Record:
    body = re.split(r"(?i)reprezentowan\w* przez osoby|udziel\w* pełnomocnictwa|ustanawiam pełnomocnikiem|niniejszym upoważniam", flat(text), maxsplit=1)[0]
    signing = re.split(r"(?i)pełnomocnictwo przyjmuję", text)[0]
    owners = []
    numbered = re.split(r"(?:\(Konsorcjum\):\s*|;\s*)\d+\)\s*", body)
    for chunk in numbered[1:] if len(numbered) > 1 else [body]:
        person = take(rf"(?i:niżej podpisan[ya])\s+({NAME}),", chunk, 0)
        name = (take(r"pod firmą (.+?),\s*(?:ul\.|al\.)", chunk) or
                take(r"(?:Mocodawcą jest |Działając w imieniu )(.+?)(?:,\s*(?:ul\.|al\.)|\s*\(dalej)", chunk))
        if not name:
            if len(numbered) > 1:
                name = take(r"^(.+?),\s*(?:ul\.|al\.)", chunk)
            else:
                simple = take(r"(?im)^([^\n]+)\s*\n\s*(?:ul\.|al\.)", text)
                heading = "".join(ch + r"[ \t]*" for ch in "PEŁNOMOCNICTWO")
                parts = re.split(r"(?im)^\s*" + heading + r"(?:procesowe)?[ \t]*$\n?", text, maxsplit=1)
                name = simple or take(r"^(.{1,160}?)(?:,\s*(?:ul\.|al\.)|\s+z siedzibą\b)", flat(parts[-1]).lstrip())
        if name:
            name = re.split(r"(?i)pełnomocnictwo(?: procesowe)?\s+", name)[-1].strip()
        block = signing
        if len(numbered) > 1 and name:
            m = re.search(r"(?ims)^w imieniu\s+" + re.escape(name) + r":\s*([\s\S]*?)(?=^w imieniu |\Z)", signing)
            block = m[1] if m else ""
        signed = re.findall(rf"(?m)^\s*\.{{4,}}\s*\n(?:Za [^\n]+\n)?\s*({NAME})\s*$", block)
        if not signed and (label := re.search(r"(?im)^[ \t]*(?:Mocodawca|Podpis mocodawcy)[ \t]*:[ \t]*$", block)):
            signed = re.findall(rf"(?m)^[ \t]*({NAME})[ \t]*\n[ \t]*(?i:prezes|wiceprezes|członek zarządu|prokurent)\b",
                                block[label.end():])
        krs, nip = identifier("KRS", chunk), identifier("NIP", chunk)
        if not (name or person or krs or nip or signed):
            continue
        owner_type = None
        if person or re.search(r"\bCEIDG\b", chunk, re.I):
            owner_type = "osoba_fizyczna"
        elif krs or re.search(r"\b(?:sp\.|spółka\b|s\.\s*a\.)", name or "", re.I):
            owner_type = "osoba_prawna"
        owners.append({"data": {"typ": owner_type, "imie_nazwisko": person, "nazwa": name, "krs": krs, "nip": nip},
            "podpisujacy": [{"imie_nazwisko": x} for x in dict.fromkeys(signed)]})
    return {"mocodawca": owners, "pelnomocnicy": appointees(text)}
