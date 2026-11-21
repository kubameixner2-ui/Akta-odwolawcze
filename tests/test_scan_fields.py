import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pymupdf  # type: ignore[import-untyped]

import evaluate
import extractor
from fields import Record, appeal, transfer
from scan_fields import appeal_fields, power_fields, reread_account, transfer_fields


class ScanFieldTests(unittest.TestCase):
    def test_company_officer_signed_in_own_name(self) -> None:
        page = "Odwołujący:\nMosty S.A.\nul. Polna 8\nDziałając w imieniu własnym jako Odwołujący"
        signature = "W imieniu Odwołującego:\nAnna Lis\nWiceprezes Zarządu"
        for extra, expected in [("", 0), ("\nPełnomocnik: radca prawny Anna Lis", 1),
                                ("\nKancelaria Z", 1)]:
            record = appeal([page], extractor.CODES)
            party = record["Odwolujacy"][0]
            party.update({"przez-pelnomocnika": 1, "pelnomocnik": {
                "imie_nazwisko": "Anna Lis", "nazwa": "Kancelaria Z", "mail": None}})
            appeal_fields(record, [page, signature + extra], extractor.CODES)
            self.assertEqual(party["przez-pelnomocnika"], expected)
            self.assertEqual(party["pelnomocnik"]["nazwa"], "Kancelaria Z" if expected else None)

    def test_docket_below_page_count(self) -> None:
        ref = "L.dz. 41"
        footer = "\nStrona 1/1\nWpłynęło " + ref
        for page, expected in [(footer, None), ("Numer transakcji: " + ref + footer, ref),
                               ("Tytuł " + ref + footer, ref), (ref, ref)]:
            record = transfer("")
            record["przelew_bankowy"]["numer_transakcji"] = ref
            transfer_fields(record, [page])
            self.assertEqual(record["przelew_bankowy"]["numer_transakcji"], expected)

    def test_account_reread_requires_invalid_digits_and_unique_matching_role(self) -> None:
        valid = "67000011112222333344445555"
        invalid = valid[:-1] + "4"
        with patch("scan_fields.pymupdf.open", side_effect=AssertionError("unexpected OCR")):
            for value, page in [(valid, "Z rachunku: " + valid), (invalid, "Na rachunek: " + invalid),
                                (invalid, "Z rachunku: " + invalid + "\nNa rachunek: " + invalid)]:
                self.assertEqual(reread_account(value, "z_rachunku", [page], b"stub"), value)

    def test_two_crop_readings_must_agree(self) -> None:
        def text_pdf(line: str) -> bytes:
            with pymupdf.open() as doc:
                doc.new_page().insert_text((50, 70), line)
                return doc.tobytes()

        invalid = "12345678901234567890123456"
        first, second = "12345678701234567890123456", "12345678901234567880123456"
        page = "Z rachunku: PL" + invalid
        pdf = text_pdf(page)
        for readings, expected in [((first, first), first), ((first, second), invalid)]:
            with patch.object(pymupdf.Page, "get_textpage_ocr", autospec=True, side_effect=lambda p, **kw: p.get_textpage()), \
                    patch.object(pymupdf.Pixmap, "pdfocr_tobytes", side_effect=[text_pdf(n) for n in readings]):
                self.assertEqual(reread_account("PL" + invalid, "z_rachunku", [page], pdf), "PL" + expected)

    def test_scan_inference_uses_the_dated_line_and_first_challenge(self) -> None:
        page = ("ul. Polna 2, Kraków\nWarszawa, dnia 2 marca 2026 roku\n"
                "Odwołanie\nWnoszę odwołanie wobec: 1. zaniechania odrzucenia oferty.\n"
                "Ogłoszenie 2026/BZP 00123456/01")
        prediction = appeal([page], extractor.CODES)
        prediction["OdwolanieKIO"].update(data="02.03.2026", miejscowosc="Kraków", czynnosc_powod_id=1)
        prediction["ZamowieniePubliczne"]["numer_bzp"] = "BZP00123456"
        with patch.object(extractor, "read_pages", return_value=([page], [1])), \
                patch.object(extractor, "classify", return_value="odwolanie"), \
                patch.object(extractor, "completion", return_value=prediction):
            result, _ = extractor.extract(b"", "llm")
        assert result is not None
        filing = result["OdwolanieKIO"]
        self.assertEqual((filing["data"], filing["miejscowosc"], filing["czynnosc_powod_id"],
                          filing["czynnosc_opis"]), ("2026-03-02", "Warszawa", 7, extractor.CODES["7"]))
        self.assertEqual(result["ZamowieniePubliczne"]["numer_bzp"], "2026/BZP00123456/01")

    def test_conflicting_revisions_and_second_challenge(self) -> None:
        page = ("Wnoszę odwołanie wobec: 1. odrzucenia oferty 2. zaniechania odrzucenia drugiej oferty.\n"
                "2025/BZP 00123456/01 i 2025/BZP 00123456/02")
        record = appeal([page], extractor.CODES)
        record["OdwolanieKIO"]["czynnosc_powod_id"] = 1
        record["ZamowieniePubliczne"]["numer_bzp"] = "BZP00123456"
        appeal_fields(record, [page], extractor.CODES)
        self.assertEqual((record["OdwolanieKIO"]["czynnosc_powod_id"],
                          record["ZamowieniePubliczne"]["numer_bzp"]), (1, "BZP00123456"))

    def test_signers_need_one_shared_representation_clause(self) -> None:
        names = [{"imie_nazwisko": "Anna Lis"}, {"imie_nazwisko": "Jan Kot"}]
        owner: Record = {"data": {"nip": "012-345-67-89"}, "podpisujacy": copy.deepcopy(names)}
        record = {"mocodawca": [owner]}
        power_fields(record, ["Reprezentowana przez: Jan Kot (dalej A). Reprezentowana przez: Anna Lis (dalej B)."])
        self.assertEqual(owner["podpisujacy"], names)
        power_fields(record, ["Reprezentowana przez: Jan Kot, Anna Lis (dalej Spółka)."])
        self.assertEqual(owner["podpisujacy"], list(reversed(names)))
        self.assertEqual(owner["data"]["nip"], "0123456789")

    def test_transfer_keeps_ambiguous_roles_and_explicit_reference(self) -> None:
        page = ("Dane nadawcy\nDane odbiorcy\nPL67 0000 1111 2222 3333 4444 5555\n"
                "77 9999 8888 7777 6666 5555 4444\nKwota: -17,00 PLN\n"
                "Numer transakcji: F12\nwydruk_F12.pdf\nTytuł: Opłata sądowa")
        record = transfer("")
        bank = record["przelew_bankowy"]
        bank.update(kwota=-17, numer_transakcji="F12", tytul="Kwota PLN")
        transfer_fields(record, [page, "Tekst załącznika"])
        self.assertEqual((bank["z_rachunku"], bank["na_rachunek"], bank["kwota"], bank["numer_transakcji"],
                          bank["tytul"]), (None, None, 17, "F12", "Opłata sądowa"))

    def test_replay_uses_saved_prediction_without_api(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "data/skany/potwierdzenia/0001"
            folder.mkdir(parents=True)
            (folder / "0001.pdf").write_bytes(b"stub")
            previous = root / "original"
            previous.mkdir()
            previous_record = transfer("")
            previous_record["przelew_bankowy"]["kwota"] = -17
            saved = json.dumps(previous_record).encode()
            (previous / "scan 01.json").write_bytes(saved)
            gold = transfer("")
            gold["przelew_bankowy"]["kwota"] = 17
            (folder / "0001.json").write_text(json.dumps(gold))
            with patch.object(evaluate, "read_pages", return_value=(["Kwota: -17,00 PLN"], [1])), \
                    patch.object(evaluate, "batch", side_effect=AssertionError("network path called")):
                result = evaluate.evaluate(root / "data", "scans", "hybrid", root / "out", previous)
                with self.assertRaises(ValueError):
                    evaluate.evaluate(root / "data", "scans", "hybrid", previous, previous)
            self.assertEqual(result["results"]["ALL"]["exact"], 1)
            self.assertEqual((previous / "scan 01.json").read_bytes(), saved)
