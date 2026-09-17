"""Conservative review candidates. Never delete and never infer disuse from age."""
from datetime import datetime
from pathlib import Path
from app.duplicates.detect import detect


def cleanup_candidates(records):
    groups, errors = detect(records)
    candidates = []
    duplicate_paths = set()
    canonical_paths = set()
    by_path={r.current_path:r for r in records}
    for group in groups:
        canonical = sorted(group.files, key=lambda p: (len(Path(p).name), p.casefold()))[0]
        canonical_paths.add(canonical)
        for path in group.files:
            if path == canonical:
                continue
            duplicate_paths.add(path)
            record = by_path[path]
            candidates.append(dict(id='cleanup:'+record.id, record_id=record.id, file=record.filename, source=path,
                category='Duplicates', reason='SHA-256 identical to retained copy: '+canonical,
                size=record.size, risk='Low redundancy risk; review personal context', canonical=canonical, hash=group.hash))
    for record in records:
        if record.protected or record.current_path in duplicate_paths or record.current_path in canonical_paths:
            continue
        name = record.filename.lower()
        age = (datetime.now().timestamp()-record.modified_at)/86400
        category = ''
        reason = ''
        if record.extension in {'.exe','.msi','.iso'} and age >= 90 and any(word in name for word in ('setup','install')):
            category, reason = 'Installers', 'Installation-package name and age over 90 days; usage is unknown'
        elif record.extension in {'.zip','.7z'} and age >= 90 and any(word in name for word in ('setup','installer')):
            category, reason = 'Archives', 'Installer archive name and age over 90 days; usage is unknown'
        if category:
            candidates.append(dict(id='cleanup:'+record.id,record_id=record.id,file=record.filename,source=record.current_path,
                category=category,reason=reason,size=record.size,risk='Review required; may be needed',canonical='',hash=''))
    return candidates, groups, errors
