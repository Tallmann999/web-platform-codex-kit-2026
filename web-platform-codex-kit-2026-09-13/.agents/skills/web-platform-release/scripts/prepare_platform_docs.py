#!/usr/bin/env python3
"""Plan new platform docs; writes ONLY with --write-new; never overwrites a folder."""
from __future__ import annotations
import argparse
import datetime
import json
from pathlib import Path

PLATFORMS = ('yandex', 'vk', 'ok', 'crazygames', 'poki', 'gamedistribution', 'playgama')

def prepare(root: Path, platform: str, write_new: bool = False) -> dict:
    if platform not in PLATFORMS:
        raise ValueError('Unsupported platform ID')
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Root must be directory')
    target = root/'docs'/'platforms'/platform
    # Never follow symlinked docs/platforms; check every intended output ancestor.
    for p in (root/'docs', root/'docs'/'platforms', target):
        if p.is_symlink():
            raise ValueError('Refusing symlinked output path')
        if p.exists() and not p.is_dir():
            raise ValueError('Output parent is not a directory')
    if target.exists():
        raise FileExistsError('Platform folder exists: review and merge manually; no overwrite')
    templates = Path(__file__).resolve().parent.parent/'assets'/'templates'
    items = {}
    for p in sorted(templates.glob('*.md')):
        items[p.name] = p.read_text(encoding='utf-8').replace('{{PLATFORM}}', platform).replace(
            '{{DATE}}', datetime.date.today().isoformat())
    if not items:
        raise ValueError('No templates found')
    report = {'write_requested': write_new, 'target': str(target), 'files': list(items),
              'status': 'PLAN_ONLY', 'no_code_modified': True}
    if write_new:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.mkdir(exist_ok=False)
        # Exclusive create preserves a concurrently added file; never overwrite.
        for name, content in items.items():
            with (target/name).open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(content)
        report['status'] = 'CREATED_NEW_TEMPLATES_REQUIRES_PROJECT_REVIEW'
    return report

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--platform', choices=PLATFORMS, required=True)
    parser.add_argument('--write-new', action='store_true', help='Use only AFTER explicit user approval')
    args = parser.parse_args()
    try:
        result = prepare(args.root, args.platform, args.write_new)
    except (OSError, ValueError) as exc:
        print(json.dumps({'error': type(exc).__name__, 'status': 'STOP_NO_OVERWRITE'}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
