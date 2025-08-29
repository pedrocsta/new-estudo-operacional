# db.py — versão compatível com PostgreSQL (Supabase) e fallback para SQLite
from __future__ import annotations

import os
from typing import Optional, Dict, Any
from datetime import datetime, date, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

DB_URL = os.getenv("DATABASE_URL", "sqlite:///studies.db")

# se for Postgres sem driver explícito, troca para psycopg (v3)
if DB_URL.startswith("postgresql://"):
    DB_URL = DB_URL.replace("postgresql://", "postgresql+psycopg://", 1)


# Cria o engine (pool_pre_ping ajuda a reciclar conexões "mortas" na nuvem)
engine: Engine = create_engine(DB_URL, pool_pre_ping=True, future=True)

def _is_sqlite() -> bool:
    return engine.dialect.name == "sqlite"

# ------------------------------- Schema -------------------------------- #

def init_db() -> None:
    """
    Cria as tabelas se não existirem.
    Usa DDL específico para SQLite e PostgreSQL, garantindo portabilidade.
    """
    if _is_sqlite():
        ddl = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash BLOB NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS study_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                study_date TEXT NOT NULL,           -- YYYY-MM-DD
                category TEXT NOT NULL,
                subject TEXT NOT NULL,
                topic TEXT,
                duration_sec INTEGER NOT NULL,
                hits INTEGER,
                mistakes INTEGER,
                page_start INTEGER,
                page_end INTEGER,
                comment TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS weekly_goals (
                user_id INTEGER PRIMARY KEY,
                target_hours INTEGER NOT NULL DEFAULT 0,
                target_questions INTEGER NOT NULL DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS subject_colors (
                user_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                color_hex TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, subject),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """,
        ]
    else:
        # PostgreSQL (Supabase/Neon/etc.)
        ddl = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash BYTEA NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS study_records (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                study_date DATE NOT NULL,           -- YYYY-MM-DD
                category TEXT NOT NULL,
                subject TEXT NOT NULL,
                topic TEXT,
                duration_sec INTEGER NOT NULL,
                hits INTEGER,
                mistakes INTEGER,
                page_start INTEGER,
                page_end INTEGER,
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS weekly_goals (
                user_id INTEGER PRIMARY KEY REFERENCES users(id),
                target_hours INTEGER NOT NULL DEFAULT 0,
                target_questions INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS subject_colors (
                user_id INTEGER NOT NULL REFERENCES users(id),
                subject TEXT NOT NULL,
                color_hex TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, subject)
            );
            """,
        ]

    with engine.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))

# ------------------------------- Helpers -------------------------------- #

def _row_to_dict(row) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    d = dict(row)
    # Ajuste para Postgres: BYTEA pode vir como memoryview
    if "password_hash" in d and isinstance(d["password_hash"], memoryview):
        d["password_hash"] = bytes(d["password_hash"])
    return d

# ------------------------------- Users ---------------------------------- #

def create_user(first_name: str, last_name: str, email: str, password_hash: bytes) -> int:
    sql = text("""
        INSERT INTO users (first_name, last_name, email, password_hash)
        VALUES (:fn, :ln, :em, :ph)
        RETURNING id
    """)
    # Em SQLite, RETURNING existe nas versões novas; se falhar, fazemos SELECT last_insert_rowid()
    try:
        with engine.begin() as conn:
            res = conn.execute(sql, {"fn": first_name.strip(), "ln": last_name.strip(),
                                     "em": email.strip().lower(), "ph": password_hash})
            row = res.mappings().fetchone()
            if row and "id" in row:
                return int(row["id"])
    except Exception:
        if _is_sqlite():
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO users (first_name, last_name, email, password_hash)
                    VALUES (:fn, :ln, :em, :ph)
                """), {"fn": first_name.strip(), "ln": last_name.strip(),
                       "em": email.strip().lower(), "ph": password_hash})
                rid = conn.execute(text("SELECT last_insert_rowid() AS id")).mappings().fetchone()
                return int(rid["id"])
        raise
    # fallback defensivo
    with engine.connect() as conn:
        row = conn.execute(text("SELECT id FROM users WHERE email=:em"),
                           {"em": email.strip().lower()}).mappings().fetchone()
        return int(row["id"]) if row else 0

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM users WHERE email = :em"),
                           {"em": email.strip().lower()}).mappings().fetchone()
        return _row_to_dict(row)

# ---------------------------- Study Records ----------------------------- #

def create_study_record(
    user_id: int,
    study_date: str,
    category: str,
    subject: str,
    topic: Optional[str],
    duration_sec: int,
    hits: Optional[int],
    mistakes: Optional[int],
    page_start: Optional[int],
    page_end: Optional[int],
    comment: Optional[str],
) -> int:
    sql = text("""
        INSERT INTO study_records
            (user_id, study_date, category, subject, topic, duration_sec, hits, mistakes, page_start, page_end, comment)
        VALUES
            (:uid, :sdate, :cat, :subj, :top, :dur, :hit, :mis, :pstart, :pend, :comm)
        RETURNING id
    """)
    params = {
        "uid": int(user_id),
        "sdate": study_date,  # YYYY-MM-DD
        "cat": category.strip(),
        "subj": subject.strip(),
        "top": (topic or "").strip() or None,
        "dur": int(duration_sec),
        "hit": None if hits is None else int(hits),
        "mis": None if mistakes is None else int(mistakes),
        "pstart": None if page_start in (None, "") else int(page_start),
        "pend": None if page_end in (None, "") else int(page_end),
        "comm": (comment or "").strip() or None,
    }
    try:
        with engine.begin() as conn:
            row = conn.execute(sql, params).mappings().fetchone()
            return int(row["id"]) if row and "id" in row else 0
    except Exception:
        if _is_sqlite():
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO study_records
                        (user_id, study_date, category, subject, topic, duration_sec, hits, mistakes, page_start, page_end, comment)
                    VALUES
                        (:uid, :sdate, :cat, :subj, :top, :dur, :hit, :mis, :pstart, :pend, :comm)
                """), params)
                rid = conn.execute(text("SELECT last_insert_rowid() AS id")).mappings().fetchone()
                return int(rid["id"])
        raise

def delete_study_record(record_id: int, user_id: int) -> bool:
    with engine.begin() as conn:
        res = conn.execute(text(
            "DELETE FROM study_records WHERE id = :rid AND user_id = :uid"
        ), {"rid": int(record_id), "uid": int(user_id)})
        # Em alguns drivers, rowcount pode ser -1; garantimos bool assim:
        return (res.rowcount or 0) > 0

def get_study_records_by_user(user_id: int):
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT *
            FROM study_records
            WHERE user_id = :uid
            ORDER BY study_date DESC, created_at DESC
        """), {"uid": int(user_id)}).mappings().fetchall()
        return [dict(r) for r in rows]

# ------------------------------ Summaries ------------------------------- #

def get_user_created_date(user_id: int) -> Optional[str]:
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT DATE(created_at) AS created_date FROM users WHERE id = :uid"
        ), {"uid": int(user_id)}).mappings().fetchone()
        return row["created_date"] if row and row["created_date"] else None

def get_study_presence_since_signup(user_id: int) -> list[dict]:
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT DATE(created_at) AS created_date FROM users WHERE id = :uid"
        ), {"uid": int(user_id)}).mappings().fetchone()
        if not row or not row["created_date"]:
            return []

        start = datetime.strptime(row["created_date"], "%Y-%m-%d").date()
        end = date.today()

        q = text("""
            SELECT study_date, COALESCE(SUM(duration_sec), 0) AS total_sec
            FROM study_records
            WHERE user_id = :uid
              AND study_date BETWEEN :start AND :end
            GROUP BY study_date
        """)
        totals_rows = conn.execute(q, {
            "uid": int(user_id),
            "start": start.isoformat(),
            "end": end.isoformat()
        }).mappings().fetchall()
        totals = {r["study_date"]: int((r["total_sec"] or 0) // 60) for r in totals_rows}

    days = (end - start).days + 1
    out = []
    for i in range(days):
        d = (start + timedelta(days=i)).isoformat()
        mins = totals.get(d, 0)
        out.append({"date": d, "minutes": mins, "has_study": mins > 0})
    return out

def get_total_minutes_by_date_range(user_id: int, start_date: str, end_date: str) -> dict[str, int]:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT study_date, COALESCE(SUM(duration_sec), 0) AS total_sec
            FROM study_records
            WHERE user_id = :uid
              AND study_date BETWEEN :start AND :end
            GROUP BY study_date
        """), {"uid": int(user_id), "start": start_date, "end": end_date}).mappings().fetchall()
        return {r["study_date"]: int((r["total_sec"] or 0) // 60) for r in rows}

def get_questions_breakdown_by_date_range(user_id: int, start_date: str, end_date: str) -> dict[str, dict[str, int]]:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                study_date,
                COALESCE(SUM(COALESCE(hits, 0)), 0)      AS total_hits,
                COALESCE(SUM(COALESCE(mistakes, 0)), 0)  AS total_mistakes
            FROM study_records
            WHERE user_id = :uid
              AND study_date BETWEEN :start AND :end
            GROUP BY study_date
        """), {"uid": int(user_id), "start": start_date, "end": end_date}).mappings().fetchall()
        out: dict[str, dict[str, int]] = {}
        for r in rows:
            out[r["study_date"]] = {
                "hits": int(r["total_hits"] or 0),
                "mistakes": int(r["total_mistakes"] or 0),
            }
        return out

def get_disciplinas_resumo(user_id: int) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT 
                subject,
                COALESCE(SUM(duration_sec), 0)           AS total_sec,
                COALESCE(SUM(COALESCE(hits,0)), 0)       AS total_hits,
                COALESCE(SUM(COALESCE(mistakes,0)), 0)   AS total_mistakes
            FROM study_records
            WHERE user_id = :uid
            GROUP BY subject
            ORDER BY subject
        """), {"uid": int(user_id)}).mappings().fetchall()

    out = []
    for r in rows:
        hits = int(r["total_hits"] or 0)
        mistakes = int(r["total_mistakes"] or 0)
        total_q = hits + mistakes
        pct = int(hits * 100 / total_q) if total_q else 0
        total_sec = int(r["total_sec"] or 0)
        out.append({
            "subject": r["subject"],
            "total_sec": total_sec,
            "total_min": total_sec // 60,
            "hits": hits,
            "mistakes": mistakes,
            "total": total_q,
            "pct": pct,
        })
    return out

def get_day_subject_breakdown(user_id: int, day_iso: str) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT subject, COALESCE(SUM(duration_sec), 0) AS total_sec
            FROM study_records
            WHERE user_id = :uid AND study_date = :day
            GROUP BY subject
            ORDER BY subject
        """), {"uid": int(user_id), "day": day_iso}).mappings().fetchall()
        return [{"subject": r["subject"], "total_sec": int(r["total_sec"] or 0)} for r in rows]

# --------------------------- Weekly Goals ------------------------------- #

def get_weekly_goal(user_id: int) -> Optional[Dict[str, int]]:
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT target_hours, target_questions
            FROM weekly_goals
            WHERE user_id = :uid
        """), {"uid": int(user_id)}).mappings().fetchone()
        return {"target_hours": int(row["target_hours"]), "target_questions": int(row["target_questions"])} if row else None

def upsert_weekly_goal(user_id: int, target_hours: int, target_questions: int) -> None:
    if _is_sqlite():
        sql = text("""
            INSERT INTO weekly_goals (user_id, target_hours, target_questions)
            VALUES (:uid, :th, :tq)
            ON CONFLICT(user_id) DO UPDATE SET
                target_hours=excluded.target_hours,
                target_questions=excluded.target_questions,
                updated_at=CURRENT_TIMESTAMP
        """)
    else:
        # Em Postgres usamos UPSERT com ON CONFLICT
        sql = text("""
            INSERT INTO weekly_goals (user_id, target_hours, target_questions)
            VALUES (:uid, :th, :tq)
            ON CONFLICT (user_id) DO UPDATE SET
                target_hours = EXCLUDED.target_hours,
                target_questions = EXCLUDED.target_questions,
                updated_at = CURRENT_TIMESTAMP
        """)
    with engine.begin() as conn:
        conn.execute(sql, {"uid": int(user_id), "th": int(target_hours), "tq": int(target_questions)})

# --------------------------- Subject Colors ----------------------------- #

def get_subject_colors(user_id: int) -> dict[str, str]:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT subject, color_hex
            FROM subject_colors
            WHERE user_id = :uid
        """), {"uid": int(user_id)}).mappings().fetchall()
        return {r["subject"]: r["color_hex"] for r in rows}

def upsert_subject_color(user_id: int, subject: str, color_hex: str) -> None:
    if _is_sqlite():
        sql = text("""
            INSERT INTO subject_colors (user_id, subject, color_hex)
            VALUES (:uid, :subj, :hex)
            ON CONFLICT(user_id, subject) DO UPDATE SET
                color_hex=excluded.color_hex,
                updated_at=CURRENT_TIMESTAMP
        """)
    else:
        sql = text("""
            INSERT INTO subject_colors (user_id, subject, color_hex)
            VALUES (:uid, :subj, :hex)
            ON CONFLICT (user_id, subject) DO UPDATE SET
                color_hex = EXCLUDED.color_hex,
                updated_at = CURRENT_TIMESTAMP
        """)
    with engine.begin() as conn:
        conn.execute(sql, {"uid": int(user_id), "subj": subject.strip(), "hex": color_hex.strip().upper()})
