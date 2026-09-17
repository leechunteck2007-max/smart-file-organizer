# Maintainer release checklist

1. Audit intended source using `python scripts/release_check.py`; visually inspect synthetic screenshots. Do not export private logs, runtime state, real documents or development Git refs.
2. Confirm owner license choice and verbatim dependency/runtime notices.
3. In a clean Windows x64 checkout with a fresh virtual environment and empty dependency store, follow README setup commands, including Electron's explicit runtime installer. Run `python scripts/build_smart_portable.py`.
4. Verify standalone parser/report/UI checks, all safety tests and ZIP manifest/CRC. Test a second PC and physical external drive before claiming that acceptance.
5. Review/update `OPEN_SOURCE_RELEASE_AUDIT.md` with actual results. Resolve local blockers before any public GitHub action.
6. If development history contains private snapshots, export an independent clean repository with `python scripts/prepare_public_repository.py`. Preserve the original metadata. Inspect/stage/scan the exported files before committing; push only the intended branch and tag. Never mirror private development refs.
7. Inspect GitHub authentication and any existing `smart-file-organizer` repository. Do not overwrite an unrelated repository. Configure its default branch, description/topics and private vulnerability reporting where available.
8. Push the audited source, verify README/images/license/templates and wait for Windows checks. Fix failures. The tag/manual build workflow retains an artifact without publishing a release.
9. After the workflow is validated, publish `v0.2.0-alpha` as a **pre-release**, with `docs/releases/v0.2.0-alpha.md`, the tested Windows ZIP and `SHA256SUMS.txt`. Do not label it stable or production-ready.
10. Download the public ZIP and verify SHA-256, release visibility and contents. Record repository/release/Actions links and remaining acceptance gaps.

Suggested repository: `smart-file-organizer`; visibility: public after gates pass. Description: Local-first Windows app that automatically scans, renames and organizes messy files — without permanently deleting them.

Topics: windows, file-organizer, file-management, desktop-app, automation, productivity, open-source, file-renaming.
