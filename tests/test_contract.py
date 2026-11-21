import copy
import errno
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pymupdf  # type: ignore[import-untyped]
from jsonschema import ValidationError

import extractor
from run import batch, serve


COMPLETE_BANK = ("Potwierdzenie transakcji\nRachunek nadawcy: 00112233445566778899001122\n"
                 "Rachunek odbiorcy: 12345678901234567890123456\nKwota: 7,00 PLN\n"
                 "Data operacji: 2026-04-03\nNumer transakcji: X42\nOpis operacji: Praca")

def pdf(text: str) -> bytes:
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72, 72), text)
        return doc.tobytes()


class ContractTests(unittest.TestCase):
    def test_empty_input_explains_how_to_start(self) -> None:
        with TemporaryDirectory() as temp, redirect_stderr(io.StringIO()) as message:
            root = Path(temp)
            (root/".gitkeep").touch()
            self.assertEqual(batch(root, root/"output", "rules"), 0)
            self.assertFalse((root/"output").exists())
        self.assertEqual(message.getvalue().splitlines(),
                         [f"No PDF files found in {root}. Add a PDF there or select a directory with --input."])

    def test_missing_input_is_a_concise_cli_error(self) -> None:
        with TemporaryDirectory() as temp:
            source = Path(temp)/"missing"
            command = [sys.executable, str(Path(extractor.__file__).with_name("run.py")), "--input", str(source)]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stderr.strip(), f"Input directory does not exist: {source}")

    def test_ui_prints_assigned_port_when_default_is_busy(self) -> None:
        with patch("run.ThreadingHTTPServer") as bind, redirect_stdout(io.StringIO()) as output:
            server = bind.return_value
            server.server_port = 43721
            bind.side_effect = [OSError(errno.EADDRINUSE, "busy"), server]
            serve("rules", None)
        self.assertEqual([call.args[0] for call in bind.call_args_list], [("127.0.0.1", 8765), ("127.0.0.1", 0)])
        self.assertEqual(output.getvalue(), "http://127.0.0.1:43721\n")
        server.serve_forever.assert_called_once_with()

    def test_explicit_zero_prints_a_bound_port(self) -> None:
        with patch("run.ThreadingHTTPServer.serve_forever"), redirect_stdout(io.StringIO()) as output:
            serve("rules", 0)
        self.assertRegex(output.getvalue(), r"^http://127\.0\.0\.1:[1-9]\d*\n$")

    def test_busy_explicit_port_exits_without_advertising_a_url(self) -> None:
        with patch("run.ThreadingHTTPServer", side_effect=OSError(errno.EADDRINUSE, "busy")) as bind:
            with redirect_stdout(io.StringIO()) as output, self.assertRaisesRegex(SystemExit, "Port 8765 is already in use"):
                serve("rules", 8765)
        self.assertEqual(output.getvalue(), "")
        bind.assert_called_once()

    def test_unrelated_bind_error_preserves_the_cause(self) -> None:
        with patch("run.ThreadingHTTPServer", side_effect=PermissionError(errno.EACCES, "denied")) as bind:
            with redirect_stdout(io.StringIO()) as output, self.assertRaises(PermissionError):
                serve("rules", None)
        self.assertEqual(output.getvalue(), "")
        bind.assert_called_once()

    def test_tree_opaque_names_repeated_type_stale_output(self) -> None:
        bank = pdf("Potwierdzenie transakcji\nKwota: 7,00 PLN\nData operacji: 2026-04-03")
        with TemporaryDirectory() as temp, redirect_stderr(io.StringIO()):
            root = Path(temp)
            folder, out = root/"input"/"sprawa A"/"akta", root/"output"
            folder.mkdir(parents=True)
            for name in ("dowód 1.PDF", "dowód 2.pdf"):
                (folder/name).write_bytes(bank)
            (folder/"inne.pdf").write_bytes(pdf("Instrukcja archiwizacji danych w systemie"))
            self.assertEqual(batch(root/"input", out, "rules", True), 0)
            self.assertEqual(sorted(p.name for p in out.rglob("*.json")), ["dowód 1.json", "dowód 2.json", "inne.json"])
            self.assertEqual((out/"sprawa A/akta/inne.json").read_bytes(), b"")
            self.assertEqual(json.loads((out/"sprawa A/akta/dowód 1.json").read_text())["przelew_bankowy"]["kwota"], 7)
            (folder/"dowód 1.PDF").write_bytes((folder/"inne.pdf").read_bytes())
            self.assertEqual(batch(root/"input", out, "rules"), 0)
            self.assertEqual((out/"sprawa A/akta/dowód 1.json").read_bytes(), b"")

    def test_kio_order_discussing_an_appeal_is_excluded(self) -> None:
        pages = ["Sygn. akt: KIO 123/25\nPOSTANOWIENIE\nKrajowa Izba Odwoławcza\nOdwołanie"]
        with patch.object(extractor, "completion") as call:
            self.assertIsNone(extractor.classify(pages, True))
        call.assert_not_called()

    def test_numbered_teaching_slides_about_appeals_are_excluded(self) -> None:
        pages = ["Postępowanie administracyjne – część II", "Kontrola decyzji\nWykład o odwołaniach.",
                 "Kontrola decyzji\nOdwołujący a zamawiający."]
        with patch.object(extractor, "completion") as call:
            self.assertIsNone(extractor.classify(pages, True))
        call.assert_not_called()

    def test_config_can_promote_previously_excluded_judgments(self) -> None:
        pages = ["Sygn. akt KIO 7/26\nWYROK\nOdwołanie"]
        with patch.dict(extractor.SPECS, {"orzeczenie": {"label": "Wyrok KIO", "headings": ["wyrok"]}}):
            self.assertEqual(extractor.classify(pages, False), "orzeczenie")

    def test_new_class_from_disk_uses_configured_api(self) -> None:
        schema = {"type":"object","properties":{"numer":{"type":"string"}},"required":["numer"],"additionalProperties":False}
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            shutil.copy(extractor.__file__, folder/"extractor.py")
            shutil.copytree(extractor.CONFIG, folder/"config")
            (folder/"config/wniosek.json").write_text(json.dumps({
                "label":"Wniosek","headings":["Wniosek"],"instructions":"Podaj numer wniosku.","schema":schema}))
            spec = importlib.util.spec_from_file_location("new_classes", folder/"extractor.py")
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            reply = {"choices":[{"finish_reason":"stop","message":{"content":'{"numer":"X17"}'}}]}
            settings = {"KIO_LLM_BASE_URL":"http://127.0.0.1:9998/v1","KIO_LLM_MODEL":"model-test","KIO_LLM_API_KEY":"test-key"}
            with patch.dict(os.environ, settings), patch.object(module, "urlopen", return_value=io.BytesIO(json.dumps(reply).encode())) as post:
                record, audit = module.extract(pdf("Wniosek\nWniosek z numerem X17 do rejestru"), trace=True)
            self.assertEqual(record, {"numer":"X17"})
            self.assertEqual(audit["literal_pages"], {"/numer":1})
            request = post.call_args.args[0]
            body = json.loads(request.data)
            self.assertEqual(request.full_url, settings["KIO_LLM_BASE_URL"]+"/chat/completions")
            self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
            self.assertEqual(body["model"], "model-test")
            self.assertEqual(body["response_format"]["json_schema"]["schema"], schema)
            self.assertIn("Podaj numer", body["messages"][0]["content"])

    def test_scanned_parallel_signatures_keep_their_roles(self) -> None:
        with pymupdf.open() as original, pymupdf.open() as scan:
            p = original.new_page(width=610, height=205)
            p.insert_htmlbox(pymupdf.Rect(30, 65, 270, 185), "Mocodawca:<br>Anna Lis<br>Prezes Zarządu",
                             css="* {font-size: 16pt;}")
            p.insert_htmlbox(pymupdf.Rect(300, 65, 600, 185), "Pełnomocnictwo przyjmuję:<br>adw. Jan Nowak",
                             css="* {font-size: 16pt;}")
            scan.new_page(width=610, height=205).insert_image(p.rect, pixmap=p.get_pixmap(dpi=180, alpha=False))
            pages, ocr = extractor.read_pages(scan.tobytes())
        self.assertEqual(ocr, [1])
        result = extractor.power(pages[0])
        self.assertEqual(result["mocodawca"][0]["podpisujacy"], [{"imie_nazwisko": "Anna Lis"}])
        self.assertEqual(result["pelnomocnicy"], [{"imie_nazwisko": "Jan Nowak", "pesel": None}])

    def test_ocr_company_suffix_correction_is_limited_to_names(self) -> None:
        source = "Pełnomocnictwo\nMocodawcą jest Atlas Sp. Z 0.0., ul. Długa 1, KRS 0000000001, NIP 0000000002."
        for ocr, expected in [([1], "Atlas Sp. z o.o."), ([], "Atlas Sp. Z 0.0.")]:
            with patch.object(extractor, "read_pages", return_value=([source], ocr)):
                record, _ = extractor.extract(b"", "rules")
            assert record is not None
            owner = record["mocodawca"][0]["data"]
            self.assertEqual((owner["nazwa"], owner["krs"]), (expected, "0000000001"))

    def test_complete_fields_survive_ocr_routing(self) -> None:
        with patch.object(extractor, "read_pages", return_value=([COMPLETE_BANK], [1])), patch.object(extractor, "completion") as call:
            actual, audit = extractor.extract(b"")
        call.assert_not_called()
        assert actual is not None
        self.assertEqual(actual["przelew_bankowy"]["kwota"], 7)
        self.assertEqual((audit["route"], audit["ocr_pages"]), ("rules", [1]))

    def test_new_required_field_on_complete_bank_record_uses_schema(self) -> None:
        source = pdf(COMPLETE_BANK)
        original, _ = extractor.extract(source, "rules")
        assert original is not None
        self.assertTrue(all(v is not None for v in original["przelew_bankowy"].values()))
        spec = copy.deepcopy(extractor.SPECS["przelew"])
        schema = spec["schema"]["properties"]["przelew_bankowy"]
        schema["properties"]["waluta"] = {"type": ["string", "null"]}
        schema["required"].append("waluta")
        spec["instructions"] += " Przepisz walutę."
        generated = copy.deepcopy(original)
        generated["przelew_bankowy"]["waluta"] = "PLN"
        with patch.dict(extractor.SPECS, {"przelew": spec}), patch.object(extractor, "completion", return_value=generated) as call:
            actual, audit = extractor.extract(source)
        self.assertEqual(actual, generated)
        self.assertEqual(audit["route"], "full_api")
        self.assertIn("walutę", call.call_args.args[0])

    def test_api_timeout_preserves_observed_fields_in_hybrid(self) -> None:
        source = pdf("Potwierdzenie transakcji\nKwota: 7,00 PLN\nData operacji: 2026-04-03")
        with patch.object(extractor, "completion", side_effect=TimeoutError()):
            record, audit = extractor.extract(source)
            with self.assertRaises(TimeoutError):
                extractor.extract(source, "llm")
        assert record is not None
        self.assertEqual(record["przelew_bankowy"]["kwota"], 7)
        self.assertIsNone(record["przelew_bankowy"]["na_rachunek"])
        self.assertEqual(audit["route"], "partial_rules_after_api_error")

    def test_invalid_model_output_is_rejected(self) -> None:
        reply = {"choices":[{"finish_reason":"stop","message":{"content":'{"wrong":3}'}}]}
        with patch.object(extractor, "urlopen", return_value=io.BytesIO(json.dumps(reply).encode())):
            with self.assertRaises(ValidationError):
                extractor.completion("Kwota", "Kwota: 3 PLN", extractor.SPECS["przelew"]["schema"])
