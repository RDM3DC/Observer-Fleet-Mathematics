"""Local server for the Pi Flight Deck.

The static dashboard can read the bundled 50,000 pi digits directly, but this
server adds an on-demand `/api/pi` endpoint so the flight can keep going beyond
the bundled cache. Digits are cached locally in `assets/pi_dynamic_cache.txt`.
"""

from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import argparse
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import mpmath as mp


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
SEED_CACHE = ASSETS / "pi_50000.txt"
DYNAMIC_CACHE = ASSETS / "pi_dynamic_cache.txt"
MAX_CHUNK = 50_000
DEFAULT_PREFETCH = 2_000


class PiDigitStore:
    def __init__(self, cache_path: Path = DYNAMIC_CACHE) -> None:
        self.cache_path = cache_path
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.cache_path.exists():
            seed = SEED_CACHE.read_text(encoding="utf-8").strip() if SEED_CACHE.exists() else ""
            self.cache_path.write_text("".join(ch for ch in seed if ch.isdigit()), encoding="utf-8")

    def read(self) -> str:
        return self.cache_path.read_text(encoding="utf-8").strip()

    def ensure(self, length: int) -> str:
        digits = self.read()
        if len(digits) >= length:
            return digits

        mp.mp.dps = length + 8
        expanded = str(mp.pi).replace(".", "")[:length]
        self.cache_path.write_text(expanded, encoding="utf-8")
        return expanded

    def chunk(self, start: int, count: int) -> dict[str, object]:
        start = max(0, start)
        count = max(1, min(MAX_CHUNK, count))
        target = start + count + DEFAULT_PREFETCH
        digits = self.ensure(target)
        return {
            "start": start,
            "count": count,
            "digits": digits[start : start + count],
            "available": len(digits),
            "generated": len(digits) > (SEED_CACHE.stat().st_size if SEED_CACHE.exists() else 0),
        }


STORE = PiDigitStore()


class PiShipHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        if parsed.path == "/api/pi":
            self._send_pi_chunk(parsed.query)
            return
        super().do_GET()

    def _send_pi_chunk(self, query: str) -> None:
        try:
            params = parse_qs(query)
            start = int(params.get("start", ["0"])[0])
            count = int(params.get("count", ["2000"])[0])
            payload = STORE.chunk(start, count)
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:  # pragma: no cover - defensive server boundary
            body = json.dumps({"error": str(exc)}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Pi Flight Deck with on-demand pi digits.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), PiShipHandler)
    print(f"Pi Flight Deck: http://{args.host}:{args.port}/")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
