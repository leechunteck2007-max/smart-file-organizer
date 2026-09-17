"""Export audited source into a separate clean Git repository; never push."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from release_check import audit,candidates


def main():
    if not audit(ROOT):raise SystemExit('Source audit failed; no export made')
    target=ROOT/'build/public-repository'
    if not target.resolve().is_relative_to((ROOT/'build').resolve()):raise RuntimeError('Unsafe export target')
    if target.exists():raise SystemExit('Export already exists; inspect it instead of overwriting')
    for name in candidates(ROOT):
        source=ROOT/name;destination=target/name
        if source.is_symlink():raise RuntimeError('Do not export linked source files')
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,destination)
    subprocess.run(['git','init','-b','main'],cwd=target,check=True)
    # Generic, deliberately non-deliverable identity: no developer personal email.
    subprocess.run(['git','config','user.name','Smart File Organizer contributors'],cwd=target,check=True)
    subprocess.run(['git','config','user.email','contributors@smart-file-organizer.invalid'],cwd=target,check=True)
    if not audit(target):raise RuntimeError('Export audit failed')
    print('Clean public repository exported; original Git metadata preserved. No commit or push made.')


if __name__=='__main__':main()
