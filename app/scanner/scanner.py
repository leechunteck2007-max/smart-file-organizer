import os, hashlib
from pathlib import Path
from app.core.models import FileRecord
from app.safety.policy import linked, under, TEMP_EXT

def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''): digest.update(chunk)
    return digest.hexdigest()

def scan(folders, policy):
    policy.clear_cache()
    records, errors, seen = [], [], set()
    def error(exc): errors.append(type(exc).__name__)
    for folder in folders:
        if not Path(folder).is_dir():
            errors.append('FolderMissing'); continue
        if linked(folder): errors.append('ReparseRootSkipped'); continue
        for root, dirs, names in os.walk(folder, followlinks=False, onerror=error):
            dirs[:] = [d for d in dirs if not linked(Path(root)/d)
                       and not under(Path(root)/d, policy.settings['library'])
                       and (not policy.state_dir or not under(Path(root)/d, policy.state_dir))]
            # Protected subtrees are never traversed, except projects: record project members for review.
            if policy.directory_veto(root):
                dirs[:] = []; errors.append('ProtectedSubtreeSkipped'); continue
            for name in names:
                p = Path(root)/name
                key = str(p.absolute()).casefold()
                if key in seen or p.suffix.lower() in TEMP_EXT or linked(p) or under(p, policy.settings['library']): continue
                seen.add(key)
                try:
                    s = p.stat()
                    if not p.is_file(): continue
                    reason = policy.veto(p)
                    records.append(FileRecord(hashlib.sha256(key.encode()).hexdigest()[:24], name,
                        p.suffix.lower(), s.st_size, s.st_ctime, s.st_mtime, str(p), str(p),
                        protected=bool(reason), project_member=bool(policy.project_root(p))))
                except OSError as exc: error(exc)
    return records, errors
