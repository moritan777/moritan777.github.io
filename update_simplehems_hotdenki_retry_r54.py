#!/usr/bin/env python3
"""Patch hotdenki_auto.py only; never delete downloaded data or modify DB."""
import argparse, ast, datetime, os, pathlib, py_compile, tempfile
HELPER = "def _hotdenki_raw_has_generation(path):\n    import json, math\n    try:\n        data = json.loads(path.read_text(encoding='utf-8-sig'))\n        if not isinstance(data, dict) or data.get('no_data') is True:\n            return False\n        reports = data.get('reports')\n        if not isinstance(reports, list) or not reports:\n            return False\n        for row in reports:\n            if not isinstance(row, dict):\n                continue\n            value = row.get('pv_generation')\n            if value is None or isinstance(value, bool):\n                continue\n            if isinstance(value, (int, float, str)):\n                try:\n                    if math.isfinite(float(value)):\n                        return True\n                except (TypeError, ValueError):\n                    pass\n        return False\n    except (OSError, ValueError, TypeError):\n        return False\n\n\ndef covered_days(root):\n    # Keep the original normalized-only handling, but an invalid raw response\n    # must not be considered covered just because a normalized file exists.\n    import datetime, re\n    covered = _covered_days_before_r54(root)\n    raw_states = {}\n    folder = root / 'imports' / 'raw'\n    if folder.exists():\n        for path in folder.glob('*.json'):\n            match = re.search(r'(\\d{8})', path.name)\n            if not match:\n                continue\n            try:\n                day = datetime.datetime.strptime(match.group(1), '%Y%m%d').date()\n            except ValueError:\n                continue\n            raw_states[day] = raw_states.get(day, False) or _hotdenki_raw_has_generation(path)\n    invalid = {day for day, valid in raw_states.items() if not valid}\n    if invalid:\n        print('Retry generation data (invalid raw response): ' + ', '.join(str(day) for day in sorted(invalid)))\n    return covered - invalid\n\n"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', default='/home/hems/simplehems-server-v2')
    args = parser.parse_args()
    target = pathlib.Path(args.app).resolve() / 'tools' / 'hotdenki_auto.py'
    source = target.read_text(encoding='utf-8')
    if 'def _covered_days_before_r54(' in source:
        print('r54 already applied; no changes made.')
        return
    tree = ast.parse(source)
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'covered_days']
    if len(nodes) != 1:
        raise SystemExit('covered_days not found uniquely; no changes made.')
    node = nodes[0]
    if len(node.args.args) != 1:
        raise SystemExit('Unexpected covered_days signature; no changes made.')
    lines = source.splitlines(keepends=True)
    original = ''.join(lines[node.lineno-1:node.end_lineno])
    renamed = original.replace('def covered_days(', 'def _covered_days_before_r54(', 1)
    updated = ''.join(lines[:node.lineno-1]) + renamed + '\n\n' + HELPER + ''.join(lines[node.end_lineno:])
    ast.parse(updated)
    # Test validation with representative fixtures, not real user data.
    import json
    ns = {}
    exec(HELPER[:HELPER.index('def covered_days(root):')], ns)
    with tempfile.TemporaryDirectory() as temp:
        fixture = pathlib.Path(temp) / 'sample.json'
        for data, expected in [
            ({'no_data': False, 'reports': [{'pv_generation': None}] * 24}, False),
            ({'no_data': False, 'reports': [{'pv_generation': 0}] * 24}, True),
            ({'no_data': True, 'reports': [{'pv_generation': 0}]}, False),
            ({'reports': [{'pv_generation': '12.5'}]}, True),
            ({'reports': []}, False),
            ({'reports': [{'pv_generation': 'NaN'}]}, False),
        ]:
            fixture.write_text(json.dumps(data), encoding='utf-8')
            assert ns['_hotdenki_raw_has_generation'](fixture) == expected
    backup = target.with_name(target.name + '.before-r54-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    fd = os.open(str(backup), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(source)
    fd, name = tempfile.mkstemp(prefix='hotdenki-r54-', suffix='.py', dir=target.parent)
    tmp = pathlib.Path(name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(updated)
        py_compile.compile(str(tmp), doraise=True)
        os.chmod(tmp, target.stat().st_mode & 0o777)
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)
    print('Backup:', backup)
    print('Applied r54. Press the generation update button. DB and JSON files unchanged.')

if __name__ == '__main__':
    main()
