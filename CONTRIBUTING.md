# Contributing

Follow the verified Windows setup/build commands in [README](README.md). Work on a small branch from main, describe the problem and keep changes focused. Use synthetic fixtures; never commit application state or real documents.

Preserve conservative eligibility, no-overwrite operations and durable Undo. Scanner, classifier, renamer, organizer, cleanup, safety or Undo changes must explain file-operation impact and test meaningful failures/collisions. Keep Python logic in the engine and UI actions behind the restricted bridge.

Before a PR, run Python tests, `scripts/release_check.py`, TypeScript/frontend checks and applicable desktop tests in [TESTING](TESTING.md). Windows CI must pass. Dependency changes need license review; change lockfiles only intentionally. Do not weaken protections to make failures disappear.

Use bug/feature issue forms with reproducible steps, versions and Undo outcome. Never upload private documents, sensitive names or unsanitized logs/reports. Vulnerabilities follow [SECURITY](SECURITY.md). PRs summarize behavior, validation and safety impact. Respect the [Code of Conduct](CODE_OF_CONDUCT.md).
