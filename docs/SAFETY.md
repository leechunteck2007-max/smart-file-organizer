# Safety model

Smart File Organizer is alpha software that changes file names and locations. Maintain independent backups and start with non-critical synthetic data in a disposable Windows account or VM.

## Eligibility and protection

Discovery distinguishes personal storage from protected or unknown-risk areas. Windows, Program Files, application data, package/runtime trees and recognized software projects are vetoed. Protected directory trees are pruned before descending. Links, junctions/reparse points, multiple hard links, unavailable cloud files, incomplete downloads and unsupported risky files are excluded. Meaningful existing folders are preserved. Unusual project layouts may escape recognition: exclude them in Settings.

Scan is read-only with respect to source files. Local metadata/cache is written to application state. Cancel or a discovery-limit failure invalidates actionable plans. Changing settings requires another scan.

## File operations

Before moving, the engine validates source size/modified time, current eligibility and destination. On Windows it uses a same-volume atomic move without replace-existing flags. Cross-volume copy/delete fallbacks are disabled. Collisions select available suffixes and never silently overwrite a file. Failed moves remain recorded and reported; they do not trigger deletion.

High-confidence evidence enables renaming. Moderate-confidence files retain their names and use broad categories. Low-confidence files remain in place. Organization does not edit file contents.

## Cleanup

Duplicate detection groups by size then requires equal SHA-256 hashes. One canonical copy remains; extras are quarantined. Other cleanup evidence includes eligible aged installers and temporary/download patterns, with policy checks. Useful personal documents and photos are not quarantined just because they are old.

Candidates go to **Review Before Delete**, never automatic permanent deletion. Quarantine does not reclaim space. Inspect usefulness before manual deletion.

## History, failure and Undo

SQLite stores prepared intent before physical moves, with paths, reason, confidence, timestamps, status and session linkage. Keep `%LOCALAPPDATA%\SmartFileOrganizer` intact while Undo is needed. Closing during active organization is blocked until it finishes; a scan can be cancelled.

Undo checks moved bytes and refuses changed files, occupied original paths and unsafe paths. It reports partial failures rather than overwriting. Only empty directories recorded as created by a session can be removed, using empty-directory removal. A crash or external changes may require manual recovery from the journal/report. Undo is not a backup or a guarantee.

## Limits

Discovery stops at 250,000 files and does not offer an actionable partial plan. At most 500 new bounded document inspections occur per scan; cached results and conservative metadata fallback cover the remainder. Extraction limits include 10 MiB files, limited XML/text, the first two PDF pages, a five-second worker timeout and Windows worker memory limits. UI detail shows up to 500 records; DOCX sections cap at 1,000 rows, with complete local JSON/SQLite history.

Second-PC and physical external-drive acceptance remain pending. See [Known issues](../KNOWN_ISSUES.md).
