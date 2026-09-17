"""Audit intended public source; print finding locations without secret values."""
import argparse
import ast
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.2.0-alpha'
REQUIRED = [
    'README.md','LICENSE','CONTRIBUTING.md','SECURITY.md','CODE_OF_CONDUCT.md',
    'CHANGELOG.md','ROADMAP.md','KNOWN_ISSUES.md','THIRD_PARTY_NOTICES.md',
    'LICENSE_RECOMMENDATION.md','.gitignore','.env.example',
    'docs/ARCHITECTURE.md','docs/SAFETY.md','docs/PRIVACY.md',
    'docs/releases/v0.2.0-alpha.md','.github/ISSUE_TEMPLATE/bug_report.yml',
    '.github/ISSUE_TEMPLATE/feature_request.yml','.github/pull_request_template.md',
    '.github/workflows/ci.yml','.github/workflows/release-build.yml']
PATTERNS = {
    'credential': re.compile(r'(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{35,}|AKIA[A-Z0-9]{16})'),
    'private-key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'credential-assignment': re.compile(r"""(?im)(?:api[_-]?key|password|secret|access[_-]?token)\s*[:=]\s*['"]([A-Za-z0-9_+/-]{16,})['"]"""),
    'personal-windows-path': re.compile(r'(?i)[A-Z]:[\\/]+Users[\\/]+(?!Public(?:[\\/]|\b)|Default(?:[\\/]|\b)|<)[A-Za-z0-9_. -]+[\\/]'),
    'personal-unix-path': re.compile(r'/(?:home|Users)/[A-Za-z0-9_.-]+/'),
}
PRIVATE_PARTS = {'node_modules','dist','build','__pycache__','.venv','test_data','runtime_data','reports','logs'}
PRIVATE_EXTENSIONS = {'.db','.sqlite','.log','.docx','.pdf','.dmp','.dump','.pyc'}


def candidates(root):
    result = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                            cwd=root, capture_output=True, check=True)
    return sorted(set(x.decode('utf-8') for x in result.stdout.split(b'\0') if x))


def audit(root):
    problems = []
    paths = candidates(root)
    for name in REQUIRED:
        if not (root/name).is_file():
            problems.append((name, 0, 'required-file-missing'))
    for name in paths:
        file = root/name
        parts = set(Path(name).parts)
        if parts & PRIVATE_PARTS or file.suffix.lower() in PRIVATE_EXTENSIONS or (file.name.startswith('.env') and file.name != '.env.example'):
            problems.append((name, 0, 'runtime-or-private-file'))
            continue
        if file.suffix.lower() == '.png':
            if not name.startswith('docs/screenshots/'):
                problems.append((name, 0, 'unreviewed-image'))
            continue
        if file.suffix.lower() not in {'.py','.md','.txt','.ts','.tsx','.cjs','.css','.html','.yml','.yaml','.json','.svg'} and file.name not in {'LICENSE','.gitignore','.gitattributes','.env.example'}:
            problems.append((name, 0, 'unreviewed-file-type'))
            continue
        content = file.read_text(encoding='utf-8')
        for kind, pattern in PATTERNS.items():
            for match in pattern.finditer(content):
                problems.append((name, content.count('\n', 0, match.start())+1, kind))
        if file.suffix == '.py':
            try:
                ast.parse(content, filename=name)
            except SyntaxError as exc:
                problems.append((name, exc.lineno, 'python-syntax'))
    metadata = json.loads((root/'frontend/package.json').read_text())
    if metadata['version'] != VERSION or VERSION not in (root/'app/__init__.py').read_text() or VERSION not in (root/'frontend/src/main.tsx').read_text():
        problems.append(('version', 0, 'metadata-mismatch'))
    if 'MIT License' not in (root/'LICENSE').read_text():
        problems.append(('LICENSE', 0, 'owner-license-not-resolved'))
    for name in ['home','scan','results','organized','report']:
        image = root/'docs/screenshots'/f'{name}.png'
        if not image.is_file() or not image.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
            problems.append((f'docs/screenshots/{name}.png', 0, 'screenshot-missing-or-invalid'))
    # Public Markdown relative links must resolve; image/query/fragment syntax kept simple.
    for name in paths:
        if name.endswith('.md'):
            content = (root/name).read_text(encoding='utf-8')
            for match in re.finditer(r'\]\(([^)\s]+)\)', content):
                target = match.group(1)
                if '://' in target or target.startswith('#'):
                    continue
                target = target.split('#')[0]
                if target and not ((root/name).parent/target).exists():
                    problems.append((name, content.count('\n',0,match.start())+1, 'broken-relative-link'))
    print(json.dumps(dict(passed=not problems, files=len(paths), findings=[
        dict(file=n,line=line,kind=kind) for n,line,kind in problems]), indent=2))
    return not problems


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    args=parser.parse_args()
    raise SystemExit(0 if audit(args.root.resolve()) else 1)


if __name__ == '__main__':
    main()
