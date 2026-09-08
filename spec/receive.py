"""Receive OTLP where the collector already sends it, and watch what arrives.

    python3 spec/receive.py --history history.jsonl --against eu-ai-act

Then point an OpenTelemetry collector at it:

    exporters:
      otlphttp/testimony:
        endpoint: http://127.0.0.1:4318

The argument for a SIEM-first pipeline is right, and the consequence is that
anything asking an enterprise to export somewhere new has already lost. So this
is not a new destination. It speaks OTLP/HTTP on the port the protocol already
uses, which means the integration is three lines of collector config and no
code at all.

**It binds to localhost and it is meant to run in your own infrastructure.**
Nothing is sent anywhere, there is no account, and the tool has no way to reach
this author. That is not a courtesy: an assessor cannot put a client's
telemetry through somebody else's service, and a deployer forwarding audit
records to a third party has moved the problem rather than solved it. Binding
anywhere else needs `--host` and says why on the way past.

It is a receiver and not a collector. It does not store spans, forward them,
retain them or look at their contents beyond asking which fields are present.
What it keeps is the reading: which criteria the arriving telemetry could
evidence, appended to a history that is itself a Testimony Record.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import io
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import criteria                                              # noqa: E402
import testimony_convert as tc                               # noqa: E402
import watch as w                                            # noqa: E402

OTLP_HTTP_PORT = 4318
TRACES = "/v1/traces"
MAX_BODY = 32 * 1024 * 1024


class Receiver(BaseHTTPRequestHandler):
    history = "history.jsonl"
    instrument = "eu-ai-act"
    quiet = False

    def _reply(self, code: int, body: dict) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:                              # noqa: N802
        if self.path.rstrip("/") != TRACES:
            # Only traces. Saying so beats accepting metrics and logs and
            # silently doing nothing with them, which would look like it
            # worked.
            self._reply(404, {"error": "only %s is served here" % TRACES})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            self._reply(413, {"error": "body must be between 1 byte and %d"
                              % MAX_BODY})
            return
        raw = self.rfile.read(length)
        if (self.headers.get("Content-Type") or "").startswith(
                "application/x-protobuf"):
            # Protobuf is the collector's default and reading it would need a
            # dependency this file does not take. Refused with the one line of
            # config that fixes it, rather than accepted and misread.
            self._reply(415, {"error": "send OTLP/JSON: set encoding: json on "
                              "the otlphttp exporter"})
            return
        try:
            doc = json.loads(raw.decode("utf-8"))
        except Exception:                                   # noqa: BLE001
            self._reply(400, {"error": "body is not JSON"})
            return
        if not tc.is_otlp(doc):
            self._reply(400, {"error": "not an OTLP trace export: no "
                              "resourceSpans"})
            return

        rows = tc.otlp_rows(doc)
        if not rows:
            self._reply(200, {"spans": 0, "read": False})
            return
        res = w.watch(self.history, rows, self.instrument)
        if not self.quiet:
            print(w.summarise(res, self.instrument, self.history))
            print()
        self._reply(200, {"spans": len(rows), "read": True,
                          "reading": res["run"],
                          "changed": len(res["changed"])})

    def do_GET(self) -> None:                               # noqa: N802
        self._reply(200, {"receiver": "machine-testimony",
                          "accepts": TRACES,
                          "encoding": "application/json",
                          "history": self.history,
                          "against": self.instrument})

    def log_message(self, fmt, *args):
        return                                              # the reading is


def make_server(history: str, instrument: str, host: str = "127.0.0.1",
                port: int = OTLP_HTTP_PORT) -> HTTPServer:
    """The bound server, so a caller can read the port it actually got.

    Port 0 asks the operating system for a free one, which is what the tests
    use: binding a fixed port repeatedly races with the previous socket still
    closing, and a flaky test is worse than none.
    """
    Receiver.history = history
    Receiver.instrument = instrument
    HTTPServer.allow_reuse_address = True
    return HTTPServer((host, port), Receiver)


def serve(history: str, instrument: str, host: str = "127.0.0.1",
          port: int = OTLP_HTTP_PORT, once: bool = False):
    srv = make_server(history, instrument, host, port)
    try:
        srv.handle_request() if once else srv.serve_forever()
    finally:
        srv.server_close()
    return srv


def main() -> int:
    args = sys.argv[1:]

    def opt(name, default=None):
        return args[args.index(name) + 1] if name in args and \
            args.index(name) + 1 < len(args) else default

    if "--help" in args or "-h" in args:
        raise SystemExit(__doc__.split("Copyright")[0].strip())
    history = opt("--history", "history.jsonl")
    instrument = opt("--against", "eu-ai-act")
    host = opt("--host", "127.0.0.1")
    port = int(opt("--port", str(OTLP_HTTP_PORT)))
    if instrument not in criteria.INSTRUMENTS:
        raise SystemExit("no published reading of %r. One of: %s"
                         % (instrument, ", ".join(sorted(criteria.INSTRUMENTS))))
    if host not in ("127.0.0.1", "localhost", "::1"):
        print("Binding to %s rather than localhost. This receiver has no "
              "authentication," % host)
        print("because it was built to sit inside the infrastructure that "
              "produces the")
        print("telemetry. If it is reachable from anywhere else, whatever is "
              "in front of it")
        print("is the only thing protecting it.")
        print()
    print("listening on http://%s:%d%s for OTLP/JSON" % (host, port, TRACES))
    print("history: %s, read against %s" % (history, instrument))
    print()
    print("point a collector at it:")
    print("  exporters:")
    print("    otlphttp/testimony:")
    print("      endpoint: http://%s:%d" % (host, port))
    print("      encoding: json")
    print()
    try:
        serve(history, instrument, host, port)
    except KeyboardInterrupt:
        print("stopped. The history is at %s and can be validated with"
              % history)
        print("  python3 spec/testimony_validate.py %s" % history)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
