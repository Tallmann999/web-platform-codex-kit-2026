#!/usr/bin/env python3
"""Read-only static audit of an UNPACKED web output folder; not portal QA."""
from __future__ import annotations
import argparse
import json
import os
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

PLATFORMS = ('generic', 'yandex', 'vk', 'ok', 'crazygames', 'poki', 'gamedistribution', 'playgama')
FORBIDDEN_DIRS = {'.git', '.agents', '.codex', 'node_modules', 'Library', 'Temp', '__pycache__'}
SECRET_SUFFIX = {'.pem', '.key', '.p12', '.pfx', '.keystore'}

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.resources = []
        self.base_seen = False
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'base':
            self.base_seen = True
        attr = 'href' if tag == 'link' else 'src'
        if tag in {'script', 'link', 'img', 'audio', 'video', 'source', 'iframe'} and values.get(attr):
            self.resources.append(values[attr])

def audit(build: Path, platform: str = 'generic', max_total_mb: float | None = None,
          max_files: int | None = None) -> dict:
    root = build.resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Build must be an unpacked directory')
    out = {'schema_version': 1, 'read_only': True, 'platform': platform,
           'root': str(root), 'errors': [], 'warnings': [], 'external_hosts': [],
           'limits_are_user_supplied': True, 'scope': 'static-only; no SDK/browser/network tests'}
    paths = []
    total = 0
    folded = {}
    for folder, dirs, names in os.walk(root, followlinks=False):
        for d in list(dirs):
            p = Path(folder)/d
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                out['errors'].append('Symlink directory: '+rel)
                dirs.remove(d)
            elif d in FORBIDDEN_DIRS:
                out['errors'].append('Development/private directory in build: '+rel)
                dirs.remove(d)
        for n in names:
            p = Path(folder)/n
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                out['errors'].append('Symlink file: '+rel)
                continue
            size = p.stat().st_size
            total += size
            paths.append(p)
            if n == '.env' or n.startswith('.env.') or n in {'id_rsa', 'id_ed25519'} or p.suffix.lower() in SECRET_SUFFIX:
                out['errors'].append('Potential secret file (content not read): '+rel)
            lower = rel.casefold()
            if lower in folded and folded[lower] != rel:
                out['errors'].append('Case-colliding names: '+folded[lower]+' / '+rel)
            folded[lower] = rel
            if platform == 'playgama' and not rel.isascii():
                out['errors'].append('Non-Latin/ASCII path: '+rel)
    if not (root/'index.html').is_file() or (root/'index.html').is_symlink():
        out['errors'].append('No regular index.html in output root; verify hosting mode')
    for p in paths:
        if p.suffix.lower() != '.html' or p.stat().st_size > 2_000_000:
            continue
        parser = Links()
        parser.feed(p.read_text(encoding='utf-8', errors='replace'))
        if parser.base_seen:
            out['warnings'].append('HTML <base> needs browser validation: '+p.relative_to(root).as_posix())
            continue
        for url in parser.resources:
            try:
                parsed = urlsplit(url)
            except ValueError:
                out['warnings'].append('Malformed resource URL in '+p.relative_to(root).as_posix())
                continue
            if parsed.scheme in {'data', 'blob'}:
                continue
            if parsed.scheme or parsed.netloc:
                host = parsed.hostname or '[non-http resource]'
                if host not in out['external_hosts']:
                    out['external_hosts'].append(host)
                continue
            path = unquote(parsed.path)
            if not path or path.startswith('#'):
                continue
            if platform == 'yandex' and path == '/sdk.js':
                continue  # supplied by the Yandex host, intentionally not in ZIP
            target = root/path.lstrip('/') if path.startswith('/') else p.parent/path
            target = target.resolve()
            try:
                target.relative_to(root)
            except ValueError:
                out['errors'].append('Resource escapes output directory in '+p.relative_to(root).as_posix())
                continue
            if not target.is_file():
                out['errors'].append('Missing HTML resource: '+target.relative_to(root).as_posix())
            if path.startswith('/'):
                out['warnings'].append('Root-absolute URL needs target-host test: '+path)
    if max_total_mb is not None and total > max_total_mb*1_000_000:
        out['errors'].append('Uncompressed total exceeds supplied decimal-MB budget')
    if max_files is not None and len(paths) > max_files:
        out['errors'].append('File count exceeds supplied budget')
    if out['external_hosts']:
        out['warnings'].append('External hosts require platform allowlist review, including SDK exceptions')
    out.update(file_count=len(paths), total_bytes=total, total_decimal_mb=round(total/1_000_000, 3),
               static_result='FAIL' if out['errors'] else 'NO_STATIC_BLOCKERS_FOUND',
               initial_network_download='NOT_MEASURED', browser_sdk_result='NOT_RUN')
    out['warnings'].append('Does not inspect dynamic JS/CSS assets, archives, compressed bundles or all possible secrets; not a security scanner')
    return out

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--platform', choices=PLATFORMS, default='generic')
    parser.add_argument('--max-total-mb', type=float)
    parser.add_argument('--max-files', type=int)
    args = parser.parse_args()
    if (args.max_total_mb is not None and args.max_total_mb <= 0) or (args.max_files is not None and args.max_files <= 0):
        parser.error('Budgets must be positive')
    try:
        data = audit(args.build, args.platform, args.max_total_mb, args.max_files)
    except (OSError, ValueError) as exc:
        print(json.dumps({'error': type(exc).__name__, 'read_only': True}))
        return 2
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 1 if data['errors'] else 0

if __name__ == '__main__':
    raise SystemExit(main())
