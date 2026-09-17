import sqlite3, json
from pathlib import Path

class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # Desktop RPC uses a single serialized worker; controls never access SQLite.
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('PRAGMA synchronous=FULL')
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS actions (
          id TEXT PRIMARY KEY, timestamp TEXT, type TEXT, source TEXT, destination TEXT,
          hash TEXT, reason TEXT, confidence INTEGER, status TEXT, error TEXT,
          undo_available INTEGER, version TEXT);
        CREATE TABLE IF NOT EXISTS decisions (path TEXT PRIMARY KEY, status TEXT);
        """)
        self.connection.commit()
    def load(self):
        row = self.connection.execute('SELECT value FROM settings WHERE id=1').fetchone()
        return json.loads(row[0]) if row else {}
    def save(self, data):
        self.connection.execute('INSERT OR REPLACE INTO settings VALUES (1,?)', (json.dumps(data),))
        self.connection.commit()
    def decision(self, path, status):
        self.connection.execute('INSERT OR REPLACE INTO decisions VALUES (?,?)', (path, status))
        self.connection.commit()
    def ignored(self):
        return {r[0] for r in self.connection.execute("SELECT path FROM decisions WHERE status IN ('Ignore','Reject')")}
    def history(self):
        return [dict(r) for r in self.connection.execute('SELECT * FROM actions ORDER BY timestamp DESC')]
    def close(self): self.connection.close()
