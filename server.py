#!/usr/bin/env python3
"""
Local dev server for the Utopia Discovery Agent web UI.

Run:  python server.py
Then open http://localhost:7432 in your browser.
"""

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
PORT = int(os.environ.get("PORT", 7432))


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path in ('/', '/index.html', '/report.html'):
            data = (ROOT / 'report.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != '/run':
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length))
        venture = body.get('venture', '').strip()

        if not venture:
            self.send_response(400)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('X-Accel-Buffering', 'no')
        self.end_headers()

        venv_python = ROOT / 'venv' / 'bin' / 'python'
        python = str(venv_python) if venv_python.exists() else sys.executable

        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'

        proc = subprocess.Popen(
            [python, str(ROOT / 'agent.py'), venture],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(ROOT),
            env=env,
        )

        stdout_buf: list[bytes] = []

        def drain_stdout() -> None:
            stdout_buf.append(proc.stdout.read())

        t = threading.Thread(target=drain_stdout, daemon=True)
        t.start()

        try:
            for raw in proc.stderr:
                line = raw.decode('utf-8', errors='replace').rstrip()
                self._sse('log', line)
        except (BrokenPipeError, OSError):
            proc.kill()
            return

        t.join()
        proc.wait()

        stdout = stdout_buf[0].decode('utf-8', errors='replace').strip() if stdout_buf else ''

        if proc.returncode == 0 and stdout:
            self._sse('result', stdout)
        else:
            msg = f'Agent exited with code {proc.returncode}'
            if stdout:
                msg += f'\n{stdout}'
            self._sse('error', msg)

        self._sse('done', '')

    def _sse(self, event: str, data: str) -> None:
        msg = f'event: {event}\ndata: {json.dumps(data)}\n\n'
        try:
            self.wfile.write(msg.encode('utf-8'))
            self.wfile.flush()
        except (BrokenPipeError, OSError):
            pass

    def log_message(self, fmt, *args):
        pass


class ThreadingHTTPServer(HTTPServer):
    def process_request(self, request, client_address):
        t = threading.Thread(
            target=self._process_request_thread,
            args=(request, client_address),
            daemon=True,
        )
        t.start()

    def _process_request_thread(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)


if __name__ == '__main__':
    server = ThreadingHTTPServer(('', PORT), Handler)
    print(f'[server] Utopia Discovery Agent → http://localhost:{PORT}')
    print('[server] Press Ctrl+C to stop.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[server] Stopped.')
