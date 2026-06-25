import os, json
from datetime import datetime, timezone

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ── Backend selection ──────────────────────────────────────────
if DATABASE_URL:
    import psycopg2
    import psycopg2.extras

    def get_db():
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        return conn

    PLACEHOLDER = "%s"
    USE_PG = True
else:
    import sqlite3
    DB = os.path.join(os.path.dirname(__file__), "imu_data.db")

    def get_db():
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        return conn

    PLACEHOLDER = "?"
    USE_PG = False


# ── Init ───────────────────────────────────────────────────────
def init_db():
    conn = get_db()
    cur = conn.cursor()

    if USE_PG:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id            SERIAL PRIMARY KEY,
                feature       TEXT    NOT NULL,
                started_at    TEXT    NOT NULL,
                ended_at      TEXT,
                duration_s    REAL,
                reading_count INTEGER DEFAULT 0,
                notes         TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS imu_readings (
                id         SERIAL PRIMARY KEY,
                session_id INTEGER NOT NULL REFERENCES sessions(id),
                t          REAL    NOT NULL,
                yaw        REAL    NOT NULL,
                pitch      REAL    NOT NULL,
                roll       REAL    NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS session_events (
                id         SERIAL PRIMARY KEY,
                session_id INTEGER NOT NULL REFERENCES sessions(id),
                t          REAL    NOT NULL,
                event_type TEXT    NOT NULL,
                payload    TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_readings_session ON imu_readings(session_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_events_session   ON session_events(session_id)")
    else:
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                feature       TEXT    NOT NULL,
                started_at    TEXT    NOT NULL,
                ended_at      TEXT,
                duration_s    REAL,
                reading_count INTEGER DEFAULT 0,
                notes         TEXT
            );
            CREATE TABLE IF NOT EXISTS imu_readings (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES sessions(id),
                t          REAL    NOT NULL,
                yaw        REAL    NOT NULL,
                pitch      REAL    NOT NULL,
                roll       REAL    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS session_events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES sessions(id),
                t          REAL    NOT NULL,
                event_type TEXT    NOT NULL,
                payload    TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_readings_session ON imu_readings(session_id);
            CREATE INDEX IF NOT EXISTS idx_events_session   ON session_events(session_id);
        """)

    conn.commit()
    conn.close()


# ── Helpers ────────────────────────────────────────────────────
def _row_to_dict(row):
    if USE_PG:
        return dict(row)
    return dict(row)


def _fetchall(cur):
    if USE_PG:
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    return [dict(r) for r in cur.fetchall()]


def _fetchone(cur):
    if USE_PG:
        row = cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))
    row = cur.fetchone()
    return dict(row) if row else None


P = PLACEHOLDER


# ── Session CRUD ───────────────────────────────────────────────
def session_create(feature: str, started_at: str = None) -> int:
    conn = get_db()
    cur  = conn.cursor()
    now  = started_at or datetime.now(timezone.utc).isoformat()
    if USE_PG:
        cur.execute(
            f"INSERT INTO sessions (feature, started_at) VALUES ({P},{P}) RETURNING id",
            (feature, now)
        )
        session_id = cur.fetchone()[0]
    else:
        cur.execute(
            f"INSERT INTO sessions (feature, started_at) VALUES ({P},{P})",
            (feature, now)
        )
        session_id = cur.lastrowid
    conn.commit()
    conn.close()
    return session_id


def session_end(session_id: int, readings: list, ended_at: str = None):
    conn = get_db()
    cur  = conn.cursor()
    now  = ended_at or datetime.now(timezone.utc).isoformat()

    cur.execute(f"SELECT started_at FROM sessions WHERE id={P}", (session_id,))
    row = cur.fetchone()
    duration = None
    if row:
        try:
            from datetime import datetime as dt
            start    = dt.fromisoformat(row[0])
            duration = (dt.fromisoformat(now) - start).total_seconds()
        except Exception:
            pass

    if readings:
        if USE_PG:
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO imu_readings (session_id, t, yaw, pitch, roll) VALUES %s",
                [(session_id, r.get("t", 0), r.get("yaw", 0), r.get("pitch", 0), r.get("roll", 0))
                 for r in readings]
            )
        else:
            cur.executemany(
                f"INSERT INTO imu_readings (session_id, t, yaw, pitch, roll) VALUES ({P},{P},{P},{P},{P})",
                [(session_id, r.get("t", 0), r.get("yaw", 0), r.get("pitch", 0), r.get("roll", 0))
                 for r in readings]
            )

    cur.execute(
        f"UPDATE sessions SET ended_at={P}, duration_s={P}, reading_count={P} WHERE id={P}",
        (now, duration, len(readings), session_id)
    )
    conn.commit()
    conn.close()


def sessions_list():
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM sessions ORDER BY id DESC LIMIT 100")
    rows = _fetchall(cur)
    conn.close()
    return rows


def session_get(session_id: int):
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(f"SELECT * FROM sessions WHERE id={P}", (session_id,))
    session = _fetchone(cur)
    if not session:
        conn.close()
        return None
    cur.execute(
        f"SELECT t, yaw, pitch, roll FROM imu_readings WHERE session_id={P} ORDER BY t",
        (session_id,)
    )
    readings = _fetchall(cur)
    cur.execute(
        f"SELECT t, event_type, payload FROM session_events WHERE session_id={P} ORDER BY t",
        (session_id,)
    )
    events = _fetchall(cur)
    conn.close()
    return {"session": session, "readings": readings, "events": events}
