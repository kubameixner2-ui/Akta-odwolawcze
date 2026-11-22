"""Exercise the GitHub Pages package from a repository subpath in Chromium."""
import json
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pymupdf  # type: ignore[import-untyped]
from playwright.sync_api import expect, sync_playwright  # type: ignore[import-not-found]  # Installed by Pages CI.


def check(site: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(site.parent)))
    Thread(target=server.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{server.server_port}"
    sample = (site / "example-transfer.pdf").read_bytes()
    expected = {"przelew_bankowy": {
        "z_rachunku": "00000000000000000000000001", "na_rachunek": "00000000000000000000000002",
        "kwota": 200, "data_operacji": "2026-03-21", "numer_transakcji": "DEMO-2026-001",
        "tytul": "Oplata demonstracyjna"}}

    with sync_playwright() as driver:
        browser = driver.chromium.launch()
        page = browser.new_page()
        requests = []
        page.on("request", lambda req: requests.append((req.method, req.url)))
        page.goto(f"{origin}/{site.name}/")
        page.locator("#sample").click()
        download = page.locator("#download")
        expect(download).to_be_visible(timeout=120000)
        assert json.loads(page.locator("#json").inner_text()) == expected
        expect(page.locator("#pdf")).to_be_visible()
        with page.expect_download() as out:
            download.click()
        assert out.value.suggested_filename == "example-transfer.json"
        assert json.loads(Path(out.value.path()).read_bytes()) == expected

        def upload(name: str, data: bytes) -> dict:
            page.locator("#file").set_input_files({"name": name, "mimeType": "application/pdf", "buffer": data})
            page.locator("#go").click()
            expect(download).to_be_visible(timeout=120000)
            return json.loads(page.locator("#json").inner_text())

        with pymupdf.open(stream=sample, filetype="pdf") as source, pymupdf.open() as scan:
            first = source[0]
            sheet = scan.new_page(width=first.rect.width, height=first.rect.height)
            sheet.insert_image(sheet.rect, stream=first.get_pixmap(dpi=200).tobytes("png"))
            record = upload("scanned-transfer.pdf", scan.tobytes())["przelew_bankowy"]
            assert record["kwota"] == 200 and record["data_operacji"] == "2026-03-21"
        with pymupdf.open() as notice:
            notice.new_page().insert_text((40, 80), "General supplier information and opening times.")
            assert upload("notice.pdf", notice.tobytes()) == {}
        assert all(method == "GET" and (url.startswith(origin + "/") or url.startswith(("blob:", "data:")))
                   for method, url in requests), requests
        browser.close()
    server.shutdown()
    server.server_close()
    print("Passed sample, JSON download, scanned upload, and unsupported upload.")


if __name__ == "__main__":
    check(Path(sys.argv[1]).resolve())
