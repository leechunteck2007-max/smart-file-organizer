"""Development launcher. Portable users launch SmartFileOrganizer.exe."""
from pathlib import Path
import subprocess
import sys


def main():
    root=Path(__file__).resolve().parent
    electron=root/'frontend/node_modules/electron/dist/electron.exe'
    if not electron.exists():
        raise SystemExit('Install frontend dependencies and build first: pnpm install; node node_modules/electron/install.js; pnpm run build')
    raise SystemExit(subprocess.call([str(electron),str(root/'frontend/electron/main.cjs'),*sys.argv[1:]],cwd=root))


if __name__=='__main__':main()
