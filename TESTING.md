# Testing

Use synthetic data or a disposable Windows account/VM. Never point fixtures at personal originals.

## Checks

After installing dependencies, from the project root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/release_check.py
Set-Location frontend
node --no-opt node_modules/typescript/bin/tsc --noEmit
node --no-opt node_modules/vite/bin/vite.js build
$env:SMART_QA_PYTHON = (Resolve-Path ..\.venv\Scripts\python.exe).Path
node --no-opt tests/desktop.cjs
Set-Location ..
```

The Python suite covers path/project protection, no overwrite, SHA-256 evidence, changed source/Undo collisions, conservative names and quarantine without deletion. Desktop tests create a disposable profile and replace discovery only in the fixture process; actual user folders are never discovered. They verify the two-click workflow and Undo; a mandatory approval prompt fails the test.

`python scripts/build_smart_portable.py` runs checks, freezes the engine and validates packaged UI, PDF extraction and DOCX generation with Python/Node removed from PATH. ZIP CRC and every manifest hash are checked. Local build evidence is ignored.

`scripts/release_check.py` audits publishable content, common credentials/personal paths, metadata and required documentation. It is a guardrail, not proof that every possible secret is absent. Screenshots require visual review too.

## Manual acceptance

Independent GitHub-hosted Windows VM CI and full packaging checks pass. On a second physical end-user PC without Python/Node, test disposable data: scan, rename, duplicates, report, collisions, locked files and Undo. Test physical external drives separately. Confirm projects remain unchanged. Physical-machine/drive acceptance remains pending.

First organization of personal originals requires explicit tester consent and backups. Read-only discovery does not authorize moves.
