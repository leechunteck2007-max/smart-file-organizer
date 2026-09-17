# Known issues and acceptance gaps

- **Classification:** rules can make mistakes. Uncertain files stay unchanged; some supported files use broad categories. No image OCR; encrypted PDFs and legacy Office content are not extracted.
- **Bounded scans:** 250,000 discovered files abort actionable plans. Only 500 new inspections occur per scan; limited XML/text and first two PDF pages. Million-file performance has not been benchmarked.
- **Partial displays:** detail shows up to 500 records; Word sections cap at 1,000 rows. JSON/SQLite retain complete sessions.
- **Undo:** changed files or occupied originals are refused. Restore can be partial; preserve local state and independent backups.
- **Unavailable files:** locked/permission-denied/offline files may skip or fail with reported status. Cloud sync can change files or publish libraries/reports separately.
- **Recognition:** unfamiliar project layouts may lack known markers. Exclude important unusual projects/application data.
- **Acceptance gaps:** local and independent GitHub-hosted Windows VM checks pass, including packaged parser/report/UI with Python/Node removed from PATH. A second physical end-user PC, physical external drives and real personal-original organization acceptance remain pending.
- **Distribution:** unsigned Windows package. No installer, auto-updater or secure-erasure feature.
