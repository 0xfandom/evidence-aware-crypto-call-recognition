"""Verify a local assessment folder. No network, model, imports or execution."""
import hashlib
import json
from pathlib import Path

base=Path(__file__).resolve().parent
manifest=json.loads((base/'PACKAGE_MANIFEST.json').read_text())
expected=set(manifest['files'])|{'PACKAGE_MANIFEST.json'}
actual={p.relative_to(base).as_posix()for p in base.rglob('*')if p.is_file()}
if actual!=expected:raise SystemExit('Unexpected or missing package files')
for name,h in manifest['files'].items():
    raw=base/name;p=raw.resolve()
    if base not in p.parents or raw.is_symlink():raise SystemExit('Unsafe package path')
    if hashlib.sha256(p.read_bytes()).hexdigest()!=h:raise SystemExit('Changed file: '+name)
print('Verified',len(manifest['files']),'pinned files; no model or candidate executed.')
