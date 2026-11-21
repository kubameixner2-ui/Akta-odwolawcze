"""Run the UZP batch contract or the local review interface."""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.error import URLError

import pymupdf  # type: ignore[import-untyped]
from jsonschema.exceptions import ValidationError

from extractor import extract

FAILURES = (ValueError, RuntimeError, OSError, KeyError, IndexError, ValidationError)


def batch(source: Path, target: Path, mode: str, trace: bool = False) -> int:
    if not source.is_dir():
        raise FileNotFoundError(f"Input directory does not exist: {source}")
    errors = 0
    for pdf in sorted(p for p in source.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf"):
        relative = pdf.relative_to(source)
        dest = target / relative.with_suffix(".json")
        try:
            record, audit = extract(pdf.read_bytes(), mode, trace)
            print(json.dumps({"file": str(relative), **audit}, ensure_ascii=False), file=sys.stderr)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(dir=dest.parent, mode="w", encoding="utf-8", delete=False) as tmp:
                temp = Path(tmp.name)
            try:
                payload = "" if record is None else json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
                temp.write_text(payload, "utf-8")
                temp.replace(dest)
            finally:
                temp.unlink(missing_ok=True)
        except FAILURES as err:
            dest.unlink(missing_ok=True)
            print(f"{relative}: {err}", file=sys.stderr)
            errors += 1
    return int(errors > 0)


def serve(mode: str, port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def send_body(self, status: int, body: bytes, mime: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path != "/":
                self.send_error(404)
                return
            self.send_body(200, Path(__file__).with_name("index.html").read_bytes(), "text/html; charset=utf-8")

        def do_POST(self) -> None:
            if self.path not in ("/extract", "/preview"):
                self.send_error(404)
                return
            if self.headers.get_content_type() != "application/pdf":
                self.send_error(415)
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                if length <= 0:
                    self.send_error(411)
                    return
                data = self.rfile.read(length)
                if self.path == "/preview":
                    with pymupdf.open(stream=data, filetype="pdf") as doc:
                        self.send_body(200, doc[0].get_pixmap(dpi=106, alpha=False).tobytes("png"), "image/png")
                    return
                record, _ = extract(data, mode)
                if record is None:
                    self.send_body(204, b"", "application/json")
                else:
                    self.send_body(200, json.dumps(record, ensure_ascii=False, indent=2).encode(), "application/json")
            except URLError as err:
                self.send_body(502, str(err).encode(), "text/plain; charset=utf-8")
            except (pymupdf.FileDataError, ValueError) as err:
                self.send_body(422, str(err).encode(), "text/plain; charset=utf-8")
            except FAILURES as err:
                self.send_body(500, str(err).encode(), "text/plain; charset=utf-8")
    print(f"http://127.0.0.1:{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KIO | Ekstrakcja dokumentów do JSON")
    parser.add_argument("--input", type=Path, default=Path("input"))
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--mode", choices=["hybrid", "rules", "llm"], default="hybrid")
    parser.add_argument("--trace", action="store_true", help="Include page references on stderr")
    parser.add_argument("--ui", action="store_true", help="Start the local PDF review service")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.ui:
        serve(args.mode, args.port)
    else:
        sys.exit(batch(args.input, args.output, args.mode, args.trace))
