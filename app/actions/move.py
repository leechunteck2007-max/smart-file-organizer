import os, ctypes, uuid, shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from app import __version__
from app.scanner.scanner import sha256
from app.safety.policy import linked, under

def exclusive_move(source, destination):
    # MoveFileExW with flags=0: no overwrite and no cross-volume copy/delete fallback.
    if os.name == 'nt':
        function = ctypes.WinDLL('kernel32', use_last_error=True).MoveFileExW
        function.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        function.restype = ctypes.c_int
        if not function(str(source), str(destination), 0): raise ctypes.WinError(ctypes.get_last_error())
    else:
        raise OSError('Moves are supported only on Windows')

@contextmanager
def read_guard(path):
    handle = None
    if os.name == 'nt':
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                           ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        create.restype = ctypes.c_void_p
        # Deny write sharing for the full hash/move/verification interval.
        handle = create(str(path), 0x80000000, 1 | 4, None, 3, 0x80, None)
        if handle == ctypes.c_void_p(-1).value: raise ctypes.WinError(ctypes.get_last_error())
    try: yield
    finally:
        if handle is not None:
            close = kernel.CloseHandle; close.argtypes = [ctypes.c_void_p]; close(handle)

class MoveEngine:
    def __init__(self, store, policy):
        self.store, self.policy = store, policy
        self._suffixes = {}
    def move(self, plan):
        p = Path(plan.file.current_path); dest = Path(plan.destination)
        return self.execute(p, dest, plan.classification.reason, plan.classification.confidence,
                            expected=(plan.file.size, plan.file.modified_at))
    def execute(self, source, destination, reason, confidence, expected=None, undo_of=None, action_id=None):
        from contextlib import ExitStack
        with ExitStack() as stack:
            try: stack.enter_context(read_guard(source))
            except OSError as exc:
                action = action_id or str(uuid.uuid4())
                self.store.connection.execute('INSERT INTO actions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                    (action, datetime.now(timezone.utc).isoformat(), 'UNDO' if undo_of else 'MOVE',
                     str(source), str(destination), '', reason, confidence, 'FAILED', str(exc), 0, __version__))
                self.store.connection.commit()
                raise
            return self._execute(source, destination, reason, confidence, expected, undo_of, action_id)

    def _execute(self, source, destination, reason, confidence, expected=None, undo_of=None, action_id=None):
        source, destination = Path(source), Path(destination)
        action = action_id or str(uuid.uuid4()); digest = ''
        db = self.store.connection
        try:
            self.policy.clear_cache()
            if undo_of:
                veto = self.policy.veto(source, destination=True) or self.policy.veto(destination, destination=True)
            else: veto = self.policy.veto(source) or self.policy.valid_destination(destination)
            if veto: raise ValueError(veto)
            if not source.is_file(): raise FileNotFoundError('Source missing')
            if source == destination: raise ValueError('Source equals destination')
            s = source.stat()
            if s.st_nlink > 1: raise ValueError('Hard-linked file protected')
            if expected and (s.st_size, s.st_mtime) != expected: raise ValueError('Source changed since preview; rescan')
            if undo_of and destination.exists(): raise FileExistsError('Undo collision; review required')
            if not undo_of:
                base = destination; number = self._suffixes.get(str(base).casefold(), 2)
                while destination.exists():
                    destination = base.with_name(f'{base.stem} ({number}){base.suffix}'); number += 1
                self._suffixes[str(base).casefold()] = number
            digest = sha256(source)
            if undo_of and digest != undo_of['hash']: raise ValueError('Organized file modified; undo blocked')
            if source.stat().st_size != s.st_size or source.stat().st_mtime_ns != s.st_mtime_ns:
                raise ValueError('File is changing')
            destination.parent.mkdir(parents=True, exist_ok=True)
            if linked(destination.parent): raise ValueError('Destination reparse point')
            if source.stat().st_dev != destination.parent.stat().st_dev:
                raise ValueError('Cross-volume moves disabled in alpha; select a library on the source drive')
            if shutil.disk_usage(destination.parent).free < 1024 * 1024: raise OSError('Insufficient free space')
            db.execute('INSERT INTO actions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                (action, datetime.now(timezone.utc).isoformat(), 'UNDO' if undo_of else 'MOVE',
                 str(source), str(destination), digest, reason, confidence, 'PREPARED', '', 0, __version__))
            db.commit()
            # Recheck policy immediately before the filesystem operation.
            self.policy.clear_cache()
            veto = self.policy.veto(source, destination=bool(undo_of)) or (self.policy.veto(destination, True) if undo_of else self.policy.valid_destination(destination))
            if veto: raise ValueError(veto)
            exclusive_move(source, destination)
            if sha256(destination) != digest: raise ValueError('Post-move integrity mismatch; review required')
            db.execute("UPDATE actions SET status='SUCCESS', undo_available=? WHERE id=?", (0 if undo_of else 1, action))
            if undo_of: db.execute('UPDATE actions SET undo_available=0 WHERE id=?', (undo_of['id'],))
            db.commit()
            return action
        except Exception as exc:
            row = db.execute('SELECT id FROM actions WHERE id=?', (action,)).fetchone()
            if row: db.execute("UPDATE actions SET status='REVIEW', error=? WHERE id=?", (str(exc), action))
            else:
                db.execute('INSERT INTO actions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                    (action, datetime.now(timezone.utc).isoformat(), 'UNDO' if undo_of else 'MOVE', str(source),
                     str(destination), digest, reason, confidence, 'FAILED', str(exc), 0, __version__))
            db.commit()
            raise
    def recover(self):
        db = self.store.connection
        for row in db.execute("SELECT * FROM actions WHERE status='PREPARED'").fetchall():
            src, dst = Path(row['source']), Path(row['destination'])
            if not src.exists() and dst.is_file() and not linked(dst) and sha256(dst) == row['hash'] and row['type'] == 'MOVE':
                db.execute("UPDATE actions SET status='SUCCESS', undo_available=1 WHERE id=?", (row['id'],))
            else: db.execute("UPDATE actions SET status='REVIEW',error='Interrupted operation; inspect both paths' WHERE id=?", (row['id'],))
        db.commit()
