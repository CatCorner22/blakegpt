"""Verify the extracted character folder without changing any files."""
import hashlib
from pathlib import Path, PurePosixPath
import sys

root = Path(__file__).resolve().parent
expected = {}
for line in (root / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
    digest, relative = line.split('  ', 1)
    name = PurePosixPath(relative)
    if name.is_absolute() or '..' in name.parts or relative in expected:
        raise SystemExit('Invalid or duplicate inventory path')
    expected[relative] = digest
actual = {p.relative_to(root).as_posix() for p in root.rglob('*')
          if p.is_file() and p.name != 'SHA256SUMS.txt' and '__pycache__' not in p.parts}
errors = []
if actual != set(expected):
    errors.append('Missing or unexpected files: ' + repr(sorted(actual ^ set(expected))))
for relative, digest in expected.items():
    path = root / relative
    if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        errors.append('Changed or missing: ' + relative)
if errors:
    print('\n'.join(errors))
    sys.exit(1)
print(f'Verified {len(expected)} files. This checks bytes, not app or device behavior.')
