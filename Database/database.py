"""Persistencia SQLite: trabajos (JSON completo) + tabla de clips para la biblioteca."""
import json, sqlite3, threading
from modules import config as cfg

_lock, _conn = threading.RLock(), None
SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, created REAL, status TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS clips(id TEXT PRIMARY KEY, job_id TEXT, created REAL, title TEXT, tags TEXT,
  layout TEXT, score INTEGER, start_s REAL, end_s REAL, file TEXT, thumb TEXT, status TEXT, trashed INTEGER);
CREATE INDEX IF NOT EXISTS ix_clips_job ON clips(job_id);
"""


def conn():
    global _conn
    if _conn is None:
        cfg.ensure()
        _conn = sqlite3.connect(cfg.DATA / "clipper.db", check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
    return _conn


def save_job(job):
    with _lock:
        c = conn()
        c.execute("INSERT OR REPLACE INTO jobs VALUES(?,?,?,?)",
                  (job["id"], job["created"], job["status"], json.dumps(job)))
        for k in job["clips"]:
            c.execute("INSERT OR REPLACE INTO clips VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (k["id"], job["id"], job["created"], k["title"], k["tags"], k["layout"], k["score"],
                       k["start"], k["end"], k["file"], k["thumb"], k["status"], int(k["trashed"])))
        c.commit()


def load_jobs():
    with _lock:
        return [json.loads(r["data"]) for r in conn().execute("SELECT data FROM jobs ORDER BY created")]


def library(q="", layout="", limit=200):
    sql = "SELECT * FROM clips WHERE trashed=0 AND status='ready'"
    args = []
    if q:
        sql += " AND (title LIKE ? OR tags LIKE ?)"
        args += [f"%{q}%"] * 2
    if layout:
        sql += " AND layout=?"
        args.append(layout)
    sql += " ORDER BY created DESC, rowid DESC LIMIT ?"
    args.append(limit)
    with _lock:
        return [dict(r) for r in conn().execute(sql, args)]
