import json
import runpy
import unittest
from email.message import Message
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from scripts.check_public import Sample, score_outputs, verdict


class ReadinessTests(unittest.TestCase):
    def test_api_check_reports_connection_and_authorization_failures(self) -> None:
        errors = [
            (URLError("connection refused"), "KIO_LLM_BASE_URL"),
            (HTTPError("https://example.invalid", 401, "Unauthorized", Message(), None), "HTTP 401"),
        ]
        for error, message in errors:
            with self.subTest(message=message), patch("extractor.completion", side_effect=error):
                with self.assertRaisesRegex(SystemExit, message):
                    runpy.run_module("check_api", run_name="__main__")

    def test_public_check_distinguishes_empty_exclusions_from_bad_records(self) -> None:
        with TemporaryDirectory() as directory:
            out = Path(directory)
            samples = [(Path("unused.pdf"), Path("notice.pdf"), None),
                       (Path("unused.pdf"), Path("appeal.pdf"), out / "reference.json"),
                       (Path("unused.pdf"), Path("transfer.pdf"), out / "reference.json")]
            (out / "notice.json").write_bytes(b"")
            (out / "appeal.json").write_bytes(b"")
            (out / "transfer.json").write_bytes(b"{}")
            counts = score_outputs(samples, out)
        self.assertEqual(counts["correct_zero_byte"], 1)
        self.assertEqual(counts["empty_in_scope"], 1)
        self.assertEqual(counts["invalid_schema"], 1)
        self.assertEqual(counts["exact_in_scope"], 0)

    def test_timing_distinguishes_wrong_class_from_inexact_fields(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            out = root / "output"
            out.mkdir()
            reference = root / "transfer.json"
            fields = {"kwota": 200, "data_operacji": None, "tytul": None,
                      "na_rachunek": None, "z_rachunku": None, "numer_transakcji": None}
            reference.write_text(json.dumps({"przelew_bankowy": fields}), encoding="utf-8")
            samples: list[Sample] = [(root / "a.pdf", Path("document.pdf"), reference),
                                     (root / "b.pdf", Path("notice.pdf"), None)]
            (out / "document.json").write_text('{"mocodawca": [], "pelnomocnicy": []}', encoding="utf-8")
            (out / "notice.json").write_bytes(reference.read_bytes())
            counts = score_outputs(samples, out)
            checks = verdict("timing", counts, 0, 10)
            self.assertEqual((counts["wrong_class_in_scope"], counts["nonempty_exclusions"]), (1, 1))
            self.assertTrue(checks["output_format_ok"] and checks["within_time_limit"])
            self.assertFalse(checks["output_contract_ok"])
            self.assertFalse(checks["passed"])

            fields["kwota"] = 199
            (out / "document.json").write_text(json.dumps({"przelew_bankowy": fields}), encoding="utf-8")
            (out / "notice.json").write_bytes(b"")
            counts = score_outputs(samples, out)
            self.assertEqual((counts["exact_in_scope"], counts["wrong_class_in_scope"]), (0, 0))
            self.assertTrue(verdict("timing", counts, 0, 10)["passed"])
            self.assertFalse(verdict("demo", counts, 0, 10)["passed"])
