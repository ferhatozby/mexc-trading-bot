"""Basit SQLite katmanı: işler (jobs) ve işlem geçmişi (logs) burada tutulur."""
import sqlite3
import os
import sys

# .exe olarak paketlendiğinde veriler exe'nin YANINDA kalıcı olmalı
# (PyInstaller'ın geçici açılış klasöründe değil, o her çalıştırmada silinir).
if getattr(sys, "frozen", False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(_BASE_DIR, "bot.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,           -- 'long' / 'short' / 'auto'
            leverage INTEGER NOT NULL,
            margin_usdt REAL NOT NULL,
            start_time TEXT NOT NULL,     -- 'HH:MM'
            end_time TEXT NOT NULL,       -- 'HH:MM'
            days TEXT NOT NULL,           -- 'daily' veya 'mon,tue,...' veya 'once:2026-10-01'
            active INTEGER NOT NULL DEFAULT 1,
            open_quantity REAL,
            resolved_side TEXT,           -- side='auto' iken o gün gerçekte açılan yön ('long'/'short')
            candle_timeframe TEXT NOT NULL DEFAULT '1d',  -- 'auto' yön hesabında bakılan mumun zaman dilimi
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    # Önceden oluşturulmuş bir bot.db dosyasında bu kolonlar yoksa ekle (geriye dönük uyumluluk).
    for ddl in (
        "ALTER TABLE jobs ADD COLUMN resolved_side TEXT",
        "ALTER TABLE jobs ADD COLUMN candle_timeframe TEXT NOT NULL DEFAULT '1d'",
    ):
        try:
            conn.execute(ddl)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # kolon zaten var
    conn.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            event TEXT NOT NULL,          -- 'open_ok','open_error','close_ok','close_error'
            detail TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def add_job(symbol, side, leverage, margin_usdt, start_time, end_time, days, candle_timeframe="1d"):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO jobs (symbol, side, leverage, margin_usdt, start_time, end_time, days, candle_timeframe) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (symbol, side, leverage, margin_usdt, start_time, end_time, days, candle_timeframe),
    )
    conn.commit()
    job_id = cur.lastrowid
    conn.close()
    return job_id


def list_jobs():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM jobs ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_job(job_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def set_job_active(job_id, active: bool):
    conn = get_conn()
    conn.execute("UPDATE jobs SET active=? WHERE id=?", (1 if active else 0, job_id))
    conn.commit()
    conn.close()


def set_open_quantity(job_id, quantity):
    conn = get_conn()
    conn.execute("UPDATE jobs SET open_quantity=? WHERE id=?", (quantity, job_id))
    conn.commit()
    conn.close()


def set_resolved_side(job_id, side):
    conn = get_conn()
    conn.execute("UPDATE jobs SET resolved_side=? WHERE id=?", (side, job_id))
    conn.commit()
    conn.close()


def delete_job(job_id):
    conn = get_conn()
    conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    conn.commit()
    conn.close()


def add_log(job_id, event, detail=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO logs (job_id, event, detail) VALUES (?,?,?)",
        (job_id, event, detail),
    )
    conn.commit()
    conn.close()


def recent_logs(limit=50):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
