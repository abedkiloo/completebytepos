#!/usr/bin/env python3
"""
Verify per-module coverage gates after: coverage run manage.py test && coverage json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATES_FILE = Path(__file__).resolve().parent / 'coverage_gates.json'
COVERAGE_JSON = ROOT / 'coverage.json'


def _normalize(path: str) -> str:
    return path.replace('\\', '/').lstrip('./')


def _match_file(relative_include: str, coverage_path: str) -> bool:
    norm = _normalize(coverage_path)
    inc = _normalize(relative_include)
    return norm.endswith(inc) or norm.endswith('/' + inc)


def _file_stats(coverage_data: dict, relative_include: str) -> tuple[int, int]:
    covered = missing = 0
    for path, entry in coverage_data.get('files', {}).items():
        if not _match_file(relative_include, path):
            continue
        summary = entry.get('summary', {})
        covered += int(summary.get('covered_lines', 0))
        missing += int(summary.get('missing_lines', 0))
    return covered, missing


def package_percent(coverage_data: dict, includes: list[str]) -> float | None:
    total_covered = total_lines = 0
    for inc in includes:
        c, m = _file_stats(coverage_data, inc)
        if c + m == 0:
            continue
        total_covered += c
        total_lines += c + m
    if total_lines == 0:
        return None
    return 100.0 * total_covered / total_lines


def main() -> int:
    if not COVERAGE_JSON.is_file():
        print(f'Missing {COVERAGE_JSON} — run: coverage run manage.py test && coverage json', file=sys.stderr)
        return 1

    gates = json.loads(GATES_FILE.read_text())
    minimum = float(gates.get('minimum_percent', 95))
    coverage_data = json.loads(COVERAGE_JSON.read_text())

    failed = []
    skipped = []
    print(f'Coverage gates (minimum {minimum}%):\n')

    for pkg in gates.get('packages', []):
        name = pkg['name']
        includes = pkg.get('include', [])
        pct = package_percent(coverage_data, includes)
        if pct is None:
            skipped.append(name)
            print(f'  ⚠ {name}: no lines measured ({", ".join(includes)})')
            continue
        status = 'OK' if pct >= minimum else 'FAIL'
        print(f'  {status} {name}: {pct:.1f}%')
        if pct < minimum:
            failed.append((name, pct, includes))

    if skipped:
        print(f'\nSkipped {len(skipped)} package(s) with no coverage data.')

    ramp_up = gates.get('ramp_up') or []
    if ramp_up:
        print(f'\nRamp-up modules (target ≥ {minimum}%):\n')
        for rel in ramp_up:
            pct = package_percent(coverage_data, [rel])
            if pct is None:
                print(f'  ⚠ {rel}: no lines measured')
            else:
                status = 'OK' if pct >= minimum else '…'
                print(f'  {status} {rel}: {pct:.1f}%')

    if failed:
        print(f'\n{len(failed)} package(s) below {minimum}%:', file=sys.stderr)
        for name, pct, includes in failed:
            print(f'  - {name}: {pct:.1f}% → {includes}', file=sys.stderr)
        return 1

    print(f'\nAll measured gates ≥ {minimum}%.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
