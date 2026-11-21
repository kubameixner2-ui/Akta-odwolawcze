import copy
import unittest
from unittest.mock import patch

import extractor
from fields import appointees
from names import normalize_names


class PersonNameTests(unittest.TestCase):
    def test_person_fields_only(self) -> None:
        examples = {"Mateusza Szymańskiego": "Mateusz Szymański", "Annie Topolskiej": "Anna Topolska",
                    "Andrzeja Wróbla": "Andrzej Wróbel", "Danutą Nowak-Kowalską": "Danuta Nowak-Kowalska",
                    "Aleksandra Marciniak": "Aleksandra Marciniak", "Jolanta Zajkowski": "Jolanta Zajkowski",
                    "Dorota Grabowską": "Dorota Grabowska", "Anna Xqrz": "Anna Xqrz"}
        for source, expected in examples.items():
            with self.subTest(source=source):
                record = {"people": [{"imie_nazwisko": source}], "nazwa": source, "tytul": source}
                normalize_names(record, ["Podpis: Dorota Grabowska"])
                self.assertEqual(record, {"people": [{"imie_nazwisko": expected}], "nazwa": source, "tytul": source})

    def test_appointment_block_keeps_roles_and_pesel(self) -> None:
        text = ("Podpisujący: Jan Nowak. Spółka udziela pełnomocnictwa:\n"
                "1. Anna Lis — adwokat, PESEL: 00000000000,\n2. adw. Jan\nKowalski (nr wpisu WA-12)\n"
                "do reprezentowania spółki.")
        self.assertEqual(appointees(text), [{"imie_nazwisko": "Anna Lis", "pesel": "00000000000"},
                                          {"imie_nazwisko": "Jan Kowalski", "pesel": None}])

    def test_fast_and_model_routes(self) -> None:
        page = ("PEŁNOMOCNICTWO\nMocodawcą jest Mosty S.A., ul. Długa 1, KRS 0000000001, NIP 0000000002.\n"
                "Ustanawiam pełnomocnikiem adwokata Mateusza Szymańskiego.\nMocodawca:\n"
                "............................\nAnna Lis\nPrezes Zarządu")
        with patch.object(extractor, "read_pages", return_value=([page], [])):
            with patch.object(extractor, "completion") as api:
                fast, audit = extractor.extract(b"", "hybrid")
                api.assert_not_called()
            assert fast is not None
            self.assertEqual((audit["route"], fast["pelnomocnicy"][0]["imie_nazwisko"]), ("rules", "Mateusz Szymański"))
            reply = copy.deepcopy(fast)
            reply["pelnomocnicy"][0]["imie_nazwisko"] = "Mateusza Szymańskiego"
            with patch.object(extractor, "completion", return_value=reply) as api:
                actual, audit = extractor.extract(b"", "llm")
            self.assertIn("mianownika", api.call_args.args[0])
            self.assertEqual((audit["route"], actual), ("full_api", fast))
