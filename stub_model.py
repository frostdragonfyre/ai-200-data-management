"""A stub model endpoint for the demos. It is not a language model.

    python stub_model.py            # listens on http://127.0.0.1:8000

POST /answer with {"prompt": "..."} returns the first sentence of source [1]
with a citation, labeled STUB. The point of the demos is retrieval and
grounding; the stub keeps them independent of model quota and policy.
"""
import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8000


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        prompt = body.get("prompt", "")
        match = re.search(r"^\[1\] chunk \d+: (.+)$", prompt, re.MULTILINE)
        if match:
            sentence = re.split(r"(?<=[.!?])\s", match.group(1).strip())[0]
            answer = f"{sentence} [1]"
        else:
            answer = "I don't have a source that answers that."
        out = json.dumps({"model": "STUB (returns source [1])", "answer": answer}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"Stub model listening on http://127.0.0.1:{PORT}/answer (Ctrl+C to stop)")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
