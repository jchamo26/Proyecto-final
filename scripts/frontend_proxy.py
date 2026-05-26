import http.server
import socketserver
import http.client
import urllib.parse
import sys
import os

DIST_DIR = "frontend/dist"
HOST = "0.0.0.0"
PORT = 5173
AGENT_TARGET = ("127.0.0.1", 8300)
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "9002"))
API_TARGET = ("127.0.0.1", BACKEND_PORT)


class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)

    def do_GET(self):
        if self.path.endswith("/assets/index-ykaTBr-k.js"):
            asset_path = self.translate_path(self.path)
            try:
                with open(asset_path, "r", encoding="utf-8") as asset_file:
                    content = asset_file.read().replace("medico@example.com", "medico@pechychon.com")
                encoded = content.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
                return
            except Exception as exc:
                self.send_error(500, f"Unable to rewrite asset: {exc}")
                return

        return super().do_GET()

    def is_proxy_path(self, path: str) -> bool:
        return path.startswith("/api") or path.startswith("/agent")

    def get_target(self, path: str):
        if path.startswith("/agent"):
            return AGENT_TARGET
        return API_TARGET

    def do_proxy(self):
        target_host, target_port = self.get_target(self.path)
        conn = http.client.HTTPConnection(target_host, target_port, timeout=10)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else None

        # Forward headers (remove hop-by-hop)
        headers = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade")}

        try:
            conn.request(self.command, self.path, body=body, headers=headers)
            resp = conn.getresponse()
            self.send_response(resp.status, resp.reason)
            for k, v in resp.getheaders():
                if k.lower() == "transfer-encoding":
                    continue
                self.send_header(k, v)
            self.end_headers()
            data = resp.read()
            if data:
                self.wfile.write(data)
        except Exception as e:
            self.send_error(502, f"Bad gateway: {e}")
        finally:
            conn.close()

    def do_POST(self):
        if self.is_proxy_path(self.path):
            return self.do_proxy()
        return super().do_POST()

    def do_PUT(self):
        if self.is_proxy_path(self.path):
            return self.do_proxy()
        return super().do_PUT()

    def do_DELETE(self):
        if self.is_proxy_path(self.path):
            return self.do_proxy()
        return super().do_DELETE()

    def do_PATCH(self):
        if self.is_proxy_path(self.path):
            return self.do_proxy()
        return super().do_PATCH()


def run():
    with socketserver.ThreadingTCPServer((HOST, PORT), ProxyHandler) as httpd:
        print(f"Serving on http://{HOST}:{PORT} (serving {DIST_DIR})")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Shutting down")


if __name__ == "__main__":
    run()
