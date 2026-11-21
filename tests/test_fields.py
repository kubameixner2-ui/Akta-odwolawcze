import unittest

from evaluate import leaves
from fields import appeal, iso, power, transfer


class FieldTests(unittest.TestCase):
    def test_bank_roles_zeros_commission_and_print_date(self) -> None:
        raw = """Potwierdzenie wykonania przelewu
Wydrukowano 01.05.2026
Rachunek odbiorcy: PL12 0000 0000 0000 0000 0000 1234
Z rachunku: 000000000000000000000001
Opłata: 0,00 zł
Kwota przelewu: PLN 3 200,50
Data wykonania: 28 kwietnia 2026
Tytuł przelewu: wpis do sprawy A/27
uzupełnienie
Numer referencyjny operacji: TX-456"""
        self.assertEqual(transfer(raw)["przelew_bankowy"], {
            "data_operacji":"2026-04-28", "kwota":3200.5, "z_rachunku":"000000000000000000000001",
            "na_rachunek":"12000000000000000000001234", "tytul":"wpis do sprawy A/27 uzupełnienie", "numer_transakcji":"TX-456"})

    def test_missing_account_cannot_borrow_from_other_party(self) -> None:
        d = transfer("Płatnik\nFirma X\nBeneficjent\nFirma Y\n01234567890123456789012345")["przelew_bankowy"]
        self.assertIsNone(d["z_rachunku"])
        self.assertEqual(d["na_rachunek"], "01234567890123456789012345")

    def test_absent_header_and_separate_action_date(self) -> None:
        p = """Prezes Krajowej Izby Odwoławczej
02-676 Warszawa
ODWOŁANIE
Zamawiający w dniu 3 kwietnia 2026 roku nie odrzucił oferty wykonawcy.
Zarzut nr 1 naruszenia przepisów. Zarzut nr 2 dotyczy wyboru oferty z 5 kwietnia 2026 r."""
        d = appeal([p], {"7":"Zaniechanie odrzucenia oferty"})["OdwolanieKIO"]
        self.assertEqual((d["czynnosc_powod_id"], d["czynnosc_dzien"]), (7, "2026-04-03"))
        self.assertIsNone(d["miejscowosc"])
        self.assertIsNone(d["data"])

    def test_first_allegation_spans_page_footer(self) -> None:
        pages = ["Zarzuty polegających na:\nStrona 1 z 3",
                 "1) wyborze oferty, o którym poinformowano w dniu 12 maja 2026 r.; "
                 "2) zaniechaniu wezwania, mimo że Zamawiający w dniu 5 kwietnia 2026 roku żądał wyjaśnień. "
                 "Zamawiający w dniu 12 maja 2026 roku ogłosił wybór oferty. Zarzut nr 1 – wadliwy wybór oferty;"]
        d = appeal(pages, {"2":"Ogłoszenie wyboru oferty"})["OdwolanieKIO"]
        self.assertEqual((d["czynnosc_powod_id"], d["czynnosc_dzien"]), (2, "2026-05-12"))

    def test_company_signer_and_attorney(self) -> None:
        raw = """PEŁNOMOCNICTWO
Mocodawcą jest Mosty S.A., ul. Długa 1, KRS 0000000001, NIP 0000000002.
Mocodawca ustanawiam pełnomocnikiem adw. Jan Nowak (nr wpisu WA 12345).
Mocodawca:
............................
Anna Lis
Prezes Zarządu
Pełnomocnictwo przyjmuję:
............................
adw. Jan Nowak"""
        d = power(raw)
        self.assertIsNone(d["mocodawca"][0]["data"]["imie_nazwisko"])
        self.assertEqual(d["mocodawca"][0]["podpisujacy"], [{"imie_nazwisko":"Anna Lis"}])
        self.assertEqual(d["pelnomocnicy"], [{"imie_nazwisko":"Jan Nowak","pesel":None}])

    def test_blank_power_has_no_invented_grantor(self) -> None:
        self.assertEqual(power("PEŁNOMOCNICTWO"), {"mocodawca": [], "pelnomocnicy": []})

    def test_invalid_date(self) -> None:
        self.assertIsNone(iso("32 lutego 2026"))

    def test_metric_preserves_path_and_types(self) -> None:
        self.assertEqual(leaves({"a":[1,None,3.0]}), leaves({"a":[1.0,None,3]}))
        self.assertNotEqual(leaves({"a":[1,2]}), leaves({"a":[2,1]}))
        self.assertNotEqual(leaves({"a":1}), leaves({"a":True}))
