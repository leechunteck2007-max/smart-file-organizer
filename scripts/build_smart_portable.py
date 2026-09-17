"""Build and verify a standalone Windows x64 alpha; never publish it."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import __version__ as VERSION
ARCHIVE = f'SmartFileOrganizer-v{VERSION}-Windows-x64.zip'


def stamp(executable, product):
    from PyInstaller.utils.win32.versioninfo import (
        VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable,
        StringStruct, VarFileInfo, VarStruct, write_version_info_to_executable)
    values = dict(CompanyName='Smart File Organizer contributors',
                  FileDescription=product, FileVersion='0.2.0.0',
                  ProductName='Smart File Organizer', ProductVersion=VERSION,
                  OriginalFilename=executable.name,
                  LegalCopyright='Copyright 2026 Smart File Organizer contributors')
    info = VSVersionInfo(ffi=FixedFileInfo(filevers=(0,2,0,0), prodvers=(0,2,0,0),
        mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0,0)),
        kids=[StringFileInfo([StringTable('040904B0', [StringStruct(k,v) for k,v in values.items()])]),
              VarFileInfo([VarStruct('Translation', [1033,1200])])])
    write_version_info_to_executable(str(executable), info)


def archive(package):
    # Whitelist user documentation: no logs, reports, test results or local history.
    private_names = {'SMART_RELEASE_REPORT.md', 'MVP_V2_REFACTOR_PLAN.md',
                     'REAL_SCAN_VALIDATION_REPORT.md', 'SMART_TEST_REPORT.md',
                     'SMART_EXTERNAL_TESTING.md', 'smart-package-test.json',
                     'smart-desktop-test.json'}
    for file in package.rglob('*'):
        if file.relative_to(package).as_posix() == 'resources/engine/_internal/docx/templates/default.docx':
            # python-docx's MIT-licensed blank runtime template is required for reports.
            vendor_template = importlib.metadata.distribution('python-docx').locate_file('docx/templates/default.docx')
            if hashlib.sha256(file.read_bytes()).digest() != hashlib.sha256(vendor_template.read_bytes()).digest():
                raise RuntimeError('Bundled Word runtime template differs from dependency')
            continue
        if file.is_file() and (file.name in private_names or file.name.startswith('.env')
                or file.suffix.lower() in {'.log','.db','.sqlite','.docx','.pdf','.dmp','.dump'}
                or {'.git','node_modules','tests','__pycache__'} & set(file.relative_to(package).parts)):
            raise RuntimeError('Private/development file in package: '+file.relative_to(package).as_posix())
    for name in ['LICENSE', 'THIRD_PARTY_NOTICES.md', 'KNOWN_ISSUES.md']:
        shutil.copy2(ROOT/name, package/name)
    documentation = package/'docs'
    documentation.mkdir(exist_ok=True)
    for name in ['SAFETY.md', 'PRIVACY.md']:
        shutil.copy2(ROOT/'docs'/name, documentation/name)
    (package/'README.txt').write_text(
        f'Smart File Organizer {VERSION}\n\n'
        'Two clicks from messy to organized.\n'
        'Extract the entire folder. Open SmartFileOrganizer.exe and keep its runtime files together.\n'
        'Python, Node and developer tools are not required. A Word-compatible viewer opens reports.\n\n'
        'ALPHA: Back up important files. Start with non-critical synthetic data in a disposable Windows account or VM. Bugs can occur.\n'
        'Scan Computer reads accessible eligible storage; Settings can exclude folders/drives.\n'
        'Organize Files authorizes automatic eligible moves, renames and cleanup quarantine.\n'
        'Review Before Delete holds cleanup extras. No automatic permanent deletion; space is not reclaimed.\n'
        'Undo refuses changed files and occupied original paths. Preserve local state while Undo is needed.\n'
        'Reports, cached text and history are local under %LOCALAPPDATA%\\SmartFileOrganizer.\n'
        'Read docs/SAFETY.md, docs/PRIVACY.md and KNOWN_ISSUES.md.\n'
        'This Windows x64 package is unsigned. Original code is MIT; component notices remain applicable.\n',
        encoding='utf-8')
    manifest = {p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(package.rglob('*')) if p.is_file() and p.name != 'manifest.json'}
    (package/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    target = ROOT/'dist'/ARCHIVE
    zipped = Path(shutil.make_archive(str(target.with_suffix('')), 'zip', package.parent, package.name))
    with zipfile.ZipFile(zipped) as file:
        if file.testzip() is not None:
            raise RuntimeError('ZIP CRC failed')
        for path, digest in manifest.items():
            if hashlib.sha256(file.read(package.name+'/'+path)).hexdigest() != digest:
                raise RuntimeError('ZIP manifest mismatch: '+path)
        forbidden = ['node_modules/', '.git/', 'organizer.sqlite', 'application.log', 'smart-desktop-test.json']
        if any(any(x in name for x in forbidden) for name in file.namelist()):
            raise RuntimeError('Private/development data in package')
    digest = hashlib.sha256(zipped.read_bytes()).hexdigest()
    (ROOT/'dist/SHA256SUMS.txt').write_text(digest+'  '+zipped.name+'\n', encoding='utf-8')
    print(json.dumps(dict(archive=zipped.name, bytes=zipped.stat().st_size,
                         sha256=digest, files=len(manifest), verified=True)))


def main():
    if sys.platform != 'win32':
        raise RuntimeError('Release packaging requires Windows x64')
    parser = argparse.ArgumentParser()
    parser.add_argument('--qa-python', default=sys.executable)
    parser.add_argument('--package-docs-only', action='store_true')
    args = parser.parse_args()
    package = ROOT/'dist/SmartFileOrganizer'
    (ROOT/'docs').mkdir(exist_ok=True)
    if args.package_docs_only:
        if not (package/'SmartFileOrganizer.exe').is_file():
            raise RuntimeError('No existing package to archive')
        archive(package)
        return
    subprocess.run([sys.executable, 'scripts/release_check.py'], cwd=ROOT, check=True)
    with (ROOT/'docs/smart-full-test-output.txt').open('w', encoding='utf-8') as output:
        subprocess.run([args.qa_python, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                       cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
    node = shutil.which('node')
    if not node:
        raise RuntimeError('Node is required for development builds')
    subprocess.run([node, '--no-opt', 'node_modules/typescript/bin/tsc', '--noEmit'], cwd=ROOT/'frontend', check=True)
    subprocess.run([node, '--no-opt', 'node_modules/vite/bin/vite.js', 'build'], cwd=ROOT/'frontend', check=True)
    environment = dict(os.environ, SMART_QA_PYTHON=args.qa_python)
    subprocess.run([node, '--no-opt', 'tests/desktop.cjs'], cwd=ROOT/'frontend', env=environment, check=True)
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--console', '--onedir',
                    '--name', 'SmartFileEngine', '--distpath', str(ROOT/'build/frozen-engine'),
                    '--workpath', str(ROOT/'build/pyinstaller-smart'), '--specpath', str(ROOT/'build'),
                    'smart_engine.py'], cwd=ROOT, check=True)
    electron = ROOT/'frontend/node_modules/electron/dist'
    if not (electron/'electron.exe').is_file():
        raise RuntimeError('Electron runtime was not installed')
    if package.exists():
        if package.resolve().parent != (ROOT/'dist').resolve() or package.name != 'SmartFileOrganizer':
            raise RuntimeError('Unsafe generated package path')
        shutil.rmtree(package)
    shutil.copytree(electron, package)
    (package/'electron.exe').rename(package/'SmartFileOrganizer.exe')
    stamp(package/'SmartFileOrganizer.exe', 'Smart File Organizer')
    embedded = package/'resources/app'
    embedded.mkdir(parents=True, exist_ok=True)
    (embedded/'package.json').write_text(json.dumps(dict(name='smart-file-organizer',
        version=VERSION, main='electron/main.cjs')), encoding='utf-8')
    shutil.copytree(ROOT/'frontend/electron', embedded/'electron')
    shutil.copytree(ROOT/'frontend/dist', embedded/'dist')
    shutil.copytree(ROOT/'build/frozen-engine/SmartFileEngine', package/'resources/engine')
    stamp(package/'resources/engine/SmartFileEngine.exe', 'Smart File Organizer Engine')
    notice = package/'NOTICE'
    notice.mkdir(exist_ok=True)
    # The root LICENSE is replaced by the application's MIT license during archive().
    shutil.copy2(package/'LICENSE', notice/'ELECTRON-LICENSE.txt')
    python_license = Path(sys.base_prefix)/'LICENSE.txt'
    if not python_license.is_file():
        raise RuntimeError('Python redistribution license missing')
    shutil.copy2(python_license, notice/'PYTHON-LICENSE.txt')
    for name in ['python-docx', 'pypdf', 'lxml', 'typing_extensions', 'pyinstaller']:
        distribution = importlib.metadata.distribution(name)
        for entry in distribution.files or []:
            if entry.name.lower().startswith(('license', 'copying', 'notice', 'authors')):
                file = distribution.locate_file(entry)
                if file.is_file():
                    shutil.copy2(file, notice/(name+'-'+file.name))
    for module in ['react', 'react-dom', 'lucide-react']:
        for file in (ROOT/'frontend/node_modules'/module).iterdir():
            if file.is_file() and file.name.lower().startswith(('license', 'copying', 'notice')):
                shutil.copy2(file, notice/(module+'-'+file.name))
    for file in (ROOT/'assets/licenses').iterdir():
        if file.is_file():
            shutil.copy2(file, notice/file.name)
    (notice/'README.txt').write_text(
        'Original app: MIT. Component licenses remain applicable.\n'
        'Chromium full notices: ../LICENSES.chromium.html. Electron MIT: ELECTRON-LICENSE.txt.\n'
        'Complete Python notice includes Microsoft Distributable Code conditions and third-party notices.\n'
        'Redistributors of Microsoft runtime code must comply with the same conditions; Windows only.\n'
        'PyInstaller COPYING includes the bootloader exception. See ../THIRD_PARTY_NOTICES.md.\n',
        encoding='utf-8')
    subprocess.run([sys.executable, str(ROOT/'scripts/check_smart_package.py')], cwd=ROOT, check=True)
    archive(package)


if __name__ == '__main__':
    main()
