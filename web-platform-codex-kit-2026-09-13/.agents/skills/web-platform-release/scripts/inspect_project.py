#!/usr/bin/env python3
"""Read-only, bounded project discovery; never executes project code or prints secrets."""
from __future__ import annotations
import argparse
import json
import os
import re
from pathlib import Path

SKIP = {'.git', '.agents', '.codex', 'node_modules', 'Library', 'Temp', 'Logs',
        'obj', 'bin', '.venv', 'venv', '__pycache__', 'docs', 'builds', 'dist'}
SOURCE = {'.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx', '.html', '.cs', '.jslib'}
MARKERS = {
    'yandex': ('yagames', 'ysdk.', 'sdk.games.s3.yandex.net'),
    'crazygames': ('crazygames.sdk', 'crazygames-sdk'),
    'poki': ('pokisdk', 'poki-sdk'),
    'vk': ('vkwebapp', '@vkontakte/vk-bridge'),
    'ok_legacy': ('fapi.', 'apiok.ru'),
    'gamedistribution': ('gdsdk', 'gd_options'),
    'playgama_bridge': ('playgama-bridge', 'playgama_bridge'),
    'gamepush': ('gamepush', 'gpsdk'),
}

def safe_spec(value: object) -> str:
    text = str(value)
    return text if re.fullmatch(r'[0-9a-zA-Z.*~^+<>=| _-]{1,80}', text) else '[non-semver spec omitted]'

def inspect(root: Path, max_files: int = 8000) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Root must be a directory')
    result = {'schema_version': 1, 'read_only': True, 'root': str(root),
              'engine_candidates': [], 'package_manifests': [], 'lockfiles': [],
              'instruction_files': [], 'html_entry_candidates': [],
              'sdk_hints': {}, 'warnings': [], 'commands_executed': [],
              'limits': {'max_files': max_files, 'source_scan_bytes': 8_000_000}}
    files = []
    for folder, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP and not (Path(folder)/d).is_symlink())
        for name in sorted(names):
            p = Path(folder)/name
            if p.is_symlink():
                result['warnings'].append('Skipped symlink: '+str(p.relative_to(root)))
                continue
            files.append(p)
            if len(files) >= max_files:
                break
        if len(files) >= max_files:
            result['warnings'].append('File limit reached: inventory is partial')
            break
    source_budget = 8_000_000
    for p in files:
        rel = p.relative_to(root).as_posix()
        if p.name in {'AGENTS.md', 'AGENTS.override.md'}:
            result['instruction_files'].append(rel)
        if p.name in {'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock', 'bun.lock', 'bun.lockb'}:
            result['lockfiles'].append(rel)
        if p.name == 'index.html':
            result['html_entry_candidates'].append(rel)
        try:
            if p.name == 'ProjectVersion.txt' and p.parent.name == 'ProjectSettings':
                text = p.read_text(encoding='utf-8', errors='replace')[:4096]
                m = re.search(r'^m_EditorVersion:\s*(\S+)', text, re.MULTILINE)
                result['engine_candidates'].append({'engine': 'Unity', 'file': rel,
                                                     'version': m.group(1) if m else 'unknown'})
            if p.name == 'package.json' and p.stat().st_size <= 1_000_000:
                data = json.loads(p.read_text(encoding='utf-8'))
                if not isinstance(data, dict):
                    raise ValueError('package.json must be object')
                scripts = data.get('scripts', {})
                entry = {'file': rel, 'script_names': sorted(scripts) if isinstance(scripts, dict) else []}
                result['package_manifests'].append(entry)
                deps = {}
                for key in ('dependencies', 'devDependencies'):
                    value = data.get(key, {})
                    if isinstance(value, dict):
                        deps.update(value)
                if 'phaser' in deps:
                    result['engine_candidates'].append({'engine': 'Phaser', 'file': rel,
                                                         'declared_version': safe_spec(deps['phaser']),
                                                         'locked_version': 'Read matching lockfile before changes'})
                for sdk, markers in MARKERS.items():
                    if any(any(marker in str(name).lower() for marker in markers) for name in deps):
                        result['sdk_hints'].setdefault(sdk, []).append(rel)
            if p.suffix.lower() in SOURCE and source_budget > 0:
                size = p.stat().st_size
                if size > 256_000:
                    continue
                text = p.read_text(encoding='utf-8', errors='replace').lower()
                source_budget -= size
                for sdk, markers in MARKERS.items():
                    if any(marker in text for marker in markers):
                        paths = result['sdk_hints'].setdefault(sdk, [])
                        if rel not in paths and len(paths) < 20:
                            paths.append(rel)
        except (OSError, ValueError) as exc:
            # Report path/type only: error payload could contain confidential text.
            result['warnings'].append(f'Cannot parse {rel}: {type(exc).__name__}')
    if not result['engine_candidates'] and result['html_entry_candidates']:
        result['engine_candidates'].append({'engine': 'HTML/JS or exported web build',
                                            'version': 'not detected'})
    if source_budget <= 0:
        result['warnings'].append('Source byte budget reached: SDK detection is partial')
    result['warnings'].append('Hints are not proof of working SDK, clean Git, successful build or MVP readiness')
    result['files_considered'] = len(files)
    return result

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    args = parser.parse_args()
    try:
        data = inspect(args.root)
    except (OSError, ValueError) as exc:
        print(json.dumps({'error': type(exc).__name__, 'read_only': True}))
        return 2
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
