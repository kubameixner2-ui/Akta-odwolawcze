# Akta odwoławcze — uruchomienie na laptopie jury

Aplikacja działa na komputerze jury. Python czyta pliki PDF i wykonuje OCR lokalnie. Tryb domyślny `hybrid` wysyła do usługi modelu fragmenty tekstu, gdy potrzebuje pomocy przy klasyfikacji lub ekstrakcji. Zespół udostępnia dane dostępowe do usługi osobnym, prywatnym kanałem.

## 1. Przygotuj katalog

Pobierz lub sklonuj publiczne repozytorium. Otwórz terminal w katalogu, w którym są `run.py` i `requirements.txt`. Umieść dostarczony przez zespół plik `.env` obok `run.py`. Program wczyta go przy uruchomieniu. Następnie umieść PDF-y w `input/`, zachowując strukturę katalogów spraw.

## 2. Zainstaluj zależności i sprawdź połączenie

**Windows, PowerShell, Python 3.13**

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe check_api.py
```

**Linux, Bash, Python 3.13**

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python check_api.py
```

Oczekiwany komunikat to `ok`. Test wykonuje rzeczywiste zapytanie z ograniczeniem odpowiedzi do schematu JSON. Błąd HTTP 401 lub 403 oznacza, że należy sprawdzić klucz oraz uprawnienia do projektu. W przypadku braku Pythona 3.13 w Ubuntu zobacz [instrukcję instalacji](../README.md).

## 3. Przetwórz dokumenty

**Windows**

```powershell
.\.venv\Scripts\python.exe run.py
```

**Linux**

```bash
.venv/bin/python run.py
```

Dla `input/sprawa_A/dokument.pdf` powstaje `output/sprawa_A/dokument.json`. Dokument spoza obsługiwanych klas otrzymuje w odpowiednim miejscu plik `.json` o rozmiarze 0 bajtów. Opcja `--trace` zapisuje ścieżkę ekstrakcji i informacje o stronach na standardowym wyjściu diagnostycznym.

## 4. Opcjonalny podgląd w przeglądarce

Uruchom ten sam interpreter z `run.py --ui` i otwórz adres wyświetlony w terminalu. Wybierz PDF, kliknij **Analizuj** i **Pobierz JSON**. Pobrany plik zostanie zapisany przez przeglądarkę. Zakończ sesję za pomocą **Ctrl+C**. Do oceny wsadowej służy polecenie z punktu 3.

GPU oraz działające urządzenie uczestnika nie są wymagane przy uruchomieniu z działającym zewnętrznym API zespołu. [Specyfikacja UZP](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/blob/0b360a9da4b482a6a280696df6714404e0953505/README.md#L119-L192)
