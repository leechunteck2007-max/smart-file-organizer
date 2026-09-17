# Privacy

Classification, hashing, renaming and file organization execute locally. No account, remote model or telemetry uploader is part of the application. Electron loads local assets, disables renderer Node integration, isolates the preload bridge, rejects new windows/navigation, denies permission requests and blocks non-local web requests. Development dependency installation and GitHub downloads use the network separately.

## Local data

Default state lives at `%LOCALAPPDATA%\SmartFileOrganizer`:

- SQLite settings/history: library/exclusions, scan metadata, paths, names, sizes, timestamps, hashes where computed, reasons, confidence and session/operation status.
- Content cache: up to 20,000 extracted document characters per cached file. This is sensitive even though it remains local.
- `Reports/`: DOCX and JSON appendices with paths, changes and cleanup information. Word reports include the current Windows username and computer name.
- Desktop state/diagnostic logs: Electron state and engine/startup errors, which may include paths.

Organization libraries and **Review Before Delete** contain originals at new names/locations. This app does not encrypt them. Windows permissions, backups and the chosen storage service determine access. Libraries/reports in cloud-synced folders may be uploaded by that service; the app does not control it.

## Sharing and removal

Never attach unsanitized reports, logs, screenshots, databases or personal documents to public issues. Reproduce with generated fixtures and replace identities, paths, names and text before sharing.

Close the app before removing the extracted program. Removing state discards settings, cached text, reports and Undo history; it does not restore moved files. Perform desired Undo first and preserve backups. No secure-erasure feature is provided.

See [Security reporting](../SECURITY.md).
