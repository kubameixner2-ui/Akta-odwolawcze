"""Reconcile scanned fields with the text of the same PDF."""
import re
from pathlib import Path

import morfeusz2  # type: ignore[import-untyped]
import pymupdf  # type: ignore[import-untyped]

from fields import DATE, WORD, Record, flat, iso


def normalize_nip(party: Record) -> None:
    value = party.get("nip")
    if isinstance(value, str):
        digits = re.sub(r"[\s-]", "", value)
        if re.fullmatch(r"[0-9]{10}", digits):
            party["nip"] = digits


def power_fields(record: Record, pages: list[str]) -> None:
    source = flat(" ".join(pages))
    clauses = re.findall(r"\breprezentowan\w*\s+przez\s*:\s*([^()]{1,260})\(\s*dalej\b", source, re.I)
    for owner in record["mocodawca"]:
        data = owner["data"]
        normalize_nip(data)
        short = re.fullmatch(r"(.+)\s+S\.A\.", data.get("nazwa") or "", re.I)
        if short and data.get("typ") == "osoba_prawna":
            forms = set(re.findall(r"(?<!\w)(" + re.escape(short[1]) +
                                   r" (?:spółka akcyjna|S\.A\.)) z siedzibą\b", source, re.I))
            if len(forms) == 1:
                data["nazwa"] = forms.pop()
        signers = owner["podpisujacy"]
        if len(signers) < 2 or any(not s["imie_nazwisko"] for s in signers):
            continue
        names = [flat(s["imie_nazwisko"]).casefold() for s in signers]
        orders = set()
        for clause in clauses:
            positions = [list(re.finditer(r"(?<!\w)" + re.escape(name) + r"(?!\w)", clause.casefold()))
                         for name in names]
            if all(len(hits) == 1 for hits in positions):
                orders.add(tuple(sorted(range(len(names)), key=lambda i: positions[i][0].start())))
        if len(orders) == 1:
            owner["podpisujacy"] = [signers[i] for i in orders.pop()]


def appeal_fields(record: Record, pages: list[str], causes: dict[str, str]) -> None:
    filing = record["OdwolanieKIO"]
    for key in ("data", "czynnosc_dzien"):
        value = filing[key]
        if value and re.fullmatch(DATE, value, re.I):
            filing[key] = iso(value) or value

    page = pages[0] if pages else ""
    for party in record["Odwolujacy"] + record["Zamawiajacy"]:
        normalize_nip(party)
    authorities = record["Zamawiajacy"]
    leaders = [party for party in authorities if party["prowadzacy_postepowanie"] == 1]
    if len(authorities) > 1 and len(leaders) == 1 and leaders[0]["nip"]:
        blocks = re.split(r"(?m)^[ \t]*\d+[.)][ \t]+", page)[1:]
        marked = [b for b in blocks if re.search(r"\b(?:zamawiający prowadzący postępowanie|lider postępowania)\b", flat(b), re.I)]
        nips = re.findall(r"\bNIP\s*:?\s*([0-9][0-9 -]*[0-9])", marked[0], re.I) if len(marked) == 1 else []
        if [re.sub(r"[ -]", "", nip) for nip in nips] == [leaders[0]["nip"]]:
            for party in authorities:
                if party["prowadzacy_postepowanie"] is None:
                    party["prowadzacy_postepowanie"] = 0
    # A letterhead may name a different city from the dated filing line below it.
    city = filing["miejscowosc"] or ""
    date_line = rf"(?m)^[ \t]*({WORD}(?: {WORD}){{0,3}}),?[ \t]+(?:dnia )?({DATE})(?:[ \t]*(?:roku|r\.))?[ \t]*$"
    stamps = [m for m in re.finditer(date_line, page) if iso(m[2]) == filing["data"] and filing["data"]]
    if len(stamps) == 1 and city and re.search(r"(?<!\w)" + re.escape(city) + r"(?!\w)", page[:stamps[0].start()], re.I):
        filing["miejscowosc"] = stamps[0][1]

    applicants = record["Odwolujacy"]
    if len(applicants) == 1 and re.search(r"działając w imieniu własnym jako odwołujący\b", flat(page), re.I):
        party = applicants[0]
        rep = party["pelnomocnik"]
        source = flat(" ".join(pages))
        firm = flat(rep["nazwa"] or "").casefold()
        name = flat(rep["imie_nazwisko"] or "")
        same_party = firm and firm == (party["nazwa"] or "").casefold()
        officer = (r"\bw imieniu odwołującego\s*:\s*" + re.escape(name) +
                   r"\s*[,–—-]?\s+(?:prezes|wiceprezes|członek|członkini)\s+zarządu\b")
        signed_for_company = (name and re.search(officer, source, re.I)
                              and (not firm or firm not in source.casefold()))
        counsel = re.search(r"\breprezentowan\w*\s+przez\b|\bpe[łlt]nomocni(?:k|cz)\w*\b", source, re.I)
        if not rep["mail"] and (same_party and not re.search(r"przez\s+pe[łlt]nomocnik", page, re.I)
                                or signed_for_company and not counsel):
            party["przez-pelnomocnika"] = 0
            rep["nazwa"] = rep["imie_nazwisko"] = None

    # A numbered first challenge to an omission carries a different cause code.
    complaint = re.split(r"\bwnoszę odwołanie wobec\s*:", flat(" ".join(pages[:2])), maxsplit=1, flags=re.I)
    if len(complaint) == 2:
        first = re.search(r"(?:^|\s)([1-9Il|])[.)]\s+(\S+)\s+(\S+)", complaint[1][:250], re.I)
        omissions = {"odrzucenia": (1, 7), "wykluczenia": (3, 8), "unieważnienia": (9, 10)}
        if (first and first[1] in "1Il|" and first[2].casefold() in ("zaniechania", "zaniechanie")
                and first[3].casefold() in omissions):
            decision, omission = omissions[first[3].casefold()]
            if filing["czynnosc_powod_id"] == decision:
                filing["czynnosc_powod_id"] = omission
                filing["czynnosc_opis"] = causes[str(omission)]

    contract = record["ZamowieniePubliczne"]
    raw = contract["numer_bzp"] or ""
    notice = re.sub(r"\s+", "", raw).upper()
    if re.fullmatch(r"\d{4}/BZP\d{8}(?:/\d{2})?", notice):
        contract["numer_bzp"] = notice
    elif partial := re.fullmatch(r"BZP(\d{8})(/\d{2})?", notice):
        printed = re.findall(r"(?<!\d)(\d{4})\s*/\s*BZP\s*(\d{8})(?:\s*/\s*(\d{2}))?(?!\d|\s*/\s*\d)", page, re.I)
        matches = {f"{year}/BZP{number}" + (f"/{rev}" if rev else "") for year, number, rev in printed
                   if number == partial[1] and (not partial[2] or partial[2] == f"/{rev}")}
        if len(matches) == 1:
            contract["numer_bzp"] = matches.pop()
    elif raw and not contract["numer_postepowania"]:
        # An internal reference occasionally comes back under the BZP key.
        labelled = re.findall(r"\b(?:nr|numer)\s+(?:referencyjny(?:\s+sprawy)?|postępowania)\s*:\s*([\w./-]+)", page, re.I)
        if {value.rstrip(".") for value in labelled} == {raw} and any(c.isalpha() for c in raw) and any(c.isdigit() for c in raw):
            contract["numer_postepowania"], contract["numer_bzp"] = raw, None

    value = contract["numer_ted"] or ""
    ted = re.fullmatch(r"(\d{4})\s*/\s*S\s*\d{1,3}\s*[-–]\s*(\d{5,6})",
                       value, re.I)
    if ted:
        contract["numer_ted"] = f"{ted[2]}-{ted[1]}"
    elif cropped := re.fullmatch(r"(\d{1,3})\s*[-–]\s*(\d{5,6})", value):
        # The OCR may damage the S between year and issue. Both numeric parts must match.
        label = r"(?:\bTED|\bDzienniku\s+Urzędowym\s+Unii\s+Europejskiej)\s*(?:nr\.?)?\s*:?\s*"
        pair = rf"(?<!\d){cropped[1]}\s*[-–]\s*{cropped[2]}(?!\d)"
        years = set(re.findall(r"(?<!\d)(\d{4})\s*/\s*S\s*" + pair, page, re.I))
        years.update(re.findall(label + r"(\d{4})\s*/[\w\s|]{0,8}" + pair, page, re.I))
        if len(years) == 1:
            contract["numer_ted"] = f"{cropped[2]}-{years.pop()}"


ACCOUNT = re.compile(r"(?<!\w)(?:PL[ \t]*)?[0-9]{2}(?:[ \t]?[0-9]{4}){6}(?!\w)", re.I)


def valid_nrb(digits: str) -> bool:
    return int(digits[2:] + "2521" + digits[:2]) % 97 == 1


def reread_account(value: str, role: str, pages: list[str], pdf: bytes) -> str:
    if not ACCOUNT.fullmatch(value):
        return value
    original = re.sub(r"\s", "", value).upper()
    digits = original.removeprefix("PL")
    if valid_nrb(digits):
        return value
    hits = [(i, m[0], line[:m.start()]) for i, page in enumerate(pages) for line in page.splitlines()
            for m in ACCOUNT.finditer(line) if re.sub(r"\D", "", m[0]) == digits]
    if len(hits) != 1:
        return value
    index, printed, prefix = hits[0]
    label = (r"z rachunku|rachunek (?:nadawcy|zleceniodawcy|płatnika)" if role == "z_rachunku" else
             r"na rachunek|rachunek (?:odbiorcy|beneficjenta)")
    if not re.search(rf"\b(?:{label})\s*:?\s*$", prefix, re.I):
        return value
    lang = {"language": "pol+eng", "tessdata": str(Path(__file__).with_name("tessdata"))}
    readings = set()
    try:
        with pymupdf.open(stream=pdf, filetype="pdf") as doc:
            page = doc[index]
            textpage = page.get_textpage_ocr(full=True, dpi=300, **lang)
            boxes = page.search_for(printed, textpage=textpage)
            if len(boxes) != 1:
                return value
            clip = (boxes[0] + (-3, -3, 3, 3)) & page.rect
            for dpi in (200, 300):
                image = page.get_pixmap(clip=clip, dpi=dpi)
                with pymupdf.open(stream=image.pdfocr_tobytes(**lang), filetype="pdf") as crop:
                    candidates = ACCOUNT.findall(crop[0].get_text())
                if len(candidates) != 1:
                    return value
                number = re.sub(r"\D", "", candidates[0])
                if not valid_nrb(number) or sum(a != b for a, b in zip(number, digits)) != 1:
                    return value
                readings.add(number)
    except (RuntimeError, ValueError, pymupdf.mupdf.FzErrorBase):
        return value
    if len(readings) == 1:
        return original.removesuffix(digits) + readings.pop()
    return value


def transfer_fields(record: Record, pages: list[str], pdf: bytes | None = None) -> None:
    bank = record["przelew_bankowy"]
    source = "\n".join(pages)
    lines = source.splitlines()
    amount = bank["kwota"]
    if amount is not None and amount < 0:
        debits = re.findall(r"[-−][ \t]*(\d[\d \t]*[,.]\d{2})[ \t]*(?:PLN|zł)\b", source, re.I)
        if any(float(v.replace(" ", "").replace("\t", "").replace(",", ".")) == -amount for v in debits):
            bank["kwota"] = -amount

    accounts = list(ACCOUNT.finditer(source))
    sender = re.search(r"\b(?:z rachunku|nadawcy|zleceniodawcy|płatnika)\b", source, re.I)
    receiver = re.search(r"\b(?:na rachunek(?=[ \t]*:)|odbiorcy|beneficjenta|kontrahenta)\b", source, re.I)
    if len(accounts) == 2 and sender and receiver:
        roles = sorted([(sender.start(), "z_rachunku"), (receiver.start(), "na_rachunek")])
        if max(accounts[0].start(), roles[0][0]) < min(accounts[1].start(), roles[1][0]):
            for (_, role), account_match in zip(roles, accounts):
                account = re.sub(r"\s", "", account_match[0]).upper()
                digits = account.removeprefix("PL")
                if valid_nrb(digits):
                    bank[role] = account
    if pdf is not None:
        for role in ("z_rachunku", "na_rachunek"):
            if bank[role]:
                bank[role] = reread_account(bank[role], role, pages, pdf)

    ref = bank["numer_transakcji"]
    if ref:
        key = re.sub(r"\W", "", ref.casefold())
        seen = [line for line in lines if key and key in re.sub(r"\W", "", line.casefold())]
        if seen and all(re.search(r"[\s.]pd[fli1]\s*$", line, re.I) and
                        not re.search(r"\b(?:numer|identyfikator|nr)\b", line, re.I) for line in seen):
            bank["numer_transakcji"] = None
        elif seen and re.search(r"\bl\s*\.\s*dz\b", ref, re.I):
            # Incoming-mail stamps can fall below the bank's printed page count.
            bodies = [re.split(r"(?im)^[ \t]*strona\s+\d+\s*(?:/|z)\s*\d+\b", p, maxsplit=1)[0] for p in pages]
            label = r"\b(?:id|identyfikator|nr|numer)\.?\s+(?:ref\w*|operacji|przelewu|transakcji)\b"
            if not re.search(label, source, re.I) and all(key not in re.sub(r"\W", "", b.casefold()) for b in bodies):
                bank["numer_transakcji"] = None

    for label in (r"tytu[łlt](?:em| przelewu)?", r"opis(?: operacji)?"):
        heading = rf"(?im)^[^\w\n]*{label}\b[ \t:.]*(.*)$"
        match = next((m for page in pages if (m := re.search(heading, page))), None)
        if not match:
            continue
        body = []
        for line in [match[1], *match.string[match.end():].splitlines()]:
            if re.match(r"(?:kwota|wartość|data |numer |rachunek |nazwa odbiorcy|typ transakcji|waluta|status|dokument|potwierdzenie |signature |tryb |opłata\s*:)", line.strip(), re.I):
                break
            if re.search(r"\w{2}", line):
                body.append(line.strip())
        candidate = " ".join(body)
        current = bank["tytul"] or ""
        if candidate and (not current or re.match(r"^\W*(?:kwota|rachunek|nazwa odbiorcy)\b", current, re.I)
                          or (current.startswith(candidate) and not re.search(r"\w{2}", current[len(candidate):]))):
            bank["tytul"] = candidate
        break

    title = bank["tytul"] or ""
    for word in re.findall(r"\b[A-ZĄĆĘŁŃÓŚŹŻ]{4,}W(?= [A-ZĄĆĘŁŃÓŚŹŻ])", title):
        if word not in source:
            continue
        dictionary = morfeusz2.Morfeusz(generate=False)
        known = any(x[2][2] != "ign" for x in dictionary.analyse(word))
        adjective = any(x[2][2].startswith("adj:") for x in dictionary.analyse(word[:-1]))
        if not known and adjective:
            bank["tytul"] = re.sub(rf"\b{word}\b", word[:-1] + " W", bank["tytul"])


def reconcile_scan(kind: str, record: Record, pages: list[str], causes: dict[str, str], pdf: bytes | None = None) -> None:
    if kind == "odwolanie":
        appeal_fields(record, pages, causes)
    elif kind == "pelnomocnictwo":
        power_fields(record, pages)
    elif kind == "przelew":
        transfer_fields(record, pages, pdf)
