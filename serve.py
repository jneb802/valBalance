"""Run the local workbench: python3 serve.py, then open http://127.0.0.1:8765."""
import argparse
import json
import sys
import tempfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEB = Path(__file__).resolve().parent / 'web'
sys.path.insert(0, str(WEB.parent / 'workbench-source' / 'Balance'))
from import_players import import_folder


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Do not log character data or local file paths.

    def do_POST(self):
        origin = self.headers.get('Origin')
        expected = 'http://' + self.headers.get('Host', '')
        if (self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}'
                or origin not in (None, expected)
                or self.headers.get('Content-Type') != 'application/json'):
            self.send_error(403)
            return
        try:
            if self.path != '/api/import':
                self.send_error(404)
                return
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 25_000_000:
                raise ValueError('Import request must be between 1 byte and 25 MB')
            request = json.loads(self.rfile.read(size))
            files = request.get('files', [])
            paths = request.get('paths', [])
            if not isinstance(files, list) or not isinstance(paths, list) or len(files) + len(paths) > 20:
                raise ValueError('Load at most 20 files per request')
            errors = []
            with tempfile.TemporaryDirectory(prefix='valbalance-') as folder:
                folder = Path(folder)
                for i, entry in enumerate(files):
                    name = Path(entry['name']).name
                    content = entry['text'].encode('utf-8')
                    if len(content) > 5_000_000:
                        errors.append(dict(file=name, message='Export exceeds 5 MB'))
                        continue
                    (folder / f'{i}-{Path(name).stem}.yaml').write_bytes(content)
                for i, value in enumerate(paths):
                    path = Path(value).expanduser()
                    try:
                        if not path.is_file() or path.suffix.lower() not in ('.yaml', '.yml'):
                            raise ValueError('Select an existing YAML file')
                        if path.stat().st_size > 5_000_000:
                            raise ValueError('Export exceeds 5 MB')
                        (folder / f'path-{i}-{path.stem}.yaml').write_bytes(path.read_bytes())
                    except (OSError, ValueError):
                        errors.append(dict(file=path.name, message='Cannot read YAML file (missing, too large, or unsupported extension)'))
                data = json.loads((WEB / 'data.json').read_text())
                players, parse_errors = import_folder(folder, data['players'])
                for player in players:
                    for choice in player['choices']:
                        choice['profile']['dot'] = data['dot']
                result = dict(players=players, errors=errors + parse_errors)
            encoded = json.dumps(result, allow_nan=False).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        except (ValueError, TypeError, KeyError, OSError, AttributeError):
            self.send_error(400, 'Invalid import request')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    print(f'ValBalance: http://127.0.0.1:{args.port} (Ctrl+C to stop)', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), partial(Handler, directory=str(WEB))).serve_forever()
