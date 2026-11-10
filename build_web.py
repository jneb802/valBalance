"""Refresh the browser assets from the extracted workbench sources."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'workbench-source' / 'Balance'
sys.path.insert(0, str(SOURCE))
from build_workbench import build_data

if __name__ == '__main__':
    data = build_data()
    data = {key: data[key] for key in ('creatures', 'players', 'dot', 'hashes', 'revision', 'builtAt')}
    (ROOT / 'web/data.json').write_text(json.dumps(data, separators=(',', ':')))
    for name in ('workbench.js', 'workbench.css'):
        shutil.copyfile(SOURCE / name, ROOT / 'web' / name)
    print(f'Built {len(data["creatures"])} creatures')
