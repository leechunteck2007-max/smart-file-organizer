from collections import defaultdict
from app.scanner.scanner import sha256
from app.core.models import DuplicateGroup

def detect(records):
    sizes = defaultdict(list); groups = []; errors = []
    for record in records:
        if not record.protected: sizes[record.size].append(record)
    for size, candidates in sizes.items():
        if len(candidates) < 2: continue
        hashes = defaultdict(list)
        for record in candidates:
            try:
                from pathlib import Path
                before = Path(record.current_path).stat()
                digest = sha256(record.current_path)
                after = Path(record.current_path).stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    errors.append('FileChanged'); continue
                hashes[digest].append(record.current_path)
            except OSError as exc: errors.append(type(exc).__name__)
        for digest, paths in hashes.items():
            if len(paths) > 1: groups.append(DuplicateGroup(digest, paths, size*(len(paths)-1)))
    return groups, errors
