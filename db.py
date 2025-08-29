from pathlib import Path
import sqlite3
from typing import Optional, Dict, Any
from utils import fmt_horas

DB_PATH = Path("studies.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    # Tabela de usuários (já existia)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash BLOB NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    # Registros de estudo
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS study_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            study_date TEXT NOT NULL,           -- YYYY-MM-DD
            category TEXT NOT NULL,             -- "Teoria", "Revisão", etc.
            subject TEXT NOT NULL,              -- disciplina
            topic TEXT,                         -- conteúdo
            duration_sec INTEGER NOT NULL,      -- tempo total em segundos
            hits INTEGER,                       -- acertos
            mistakes INTEGER,                   -- erros
            page_start INTEGER,                 -- início
            page_end INTEGER,                   -- fim
            comment TEXT,                       -- comentário
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )
    # Metas semanais
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS weekly_goals (
            user_id INTEGER PRIMARY KEY,
            target_hours INTEGER NOT NULL DEFAULT 0,
            target_questions INTEGER NOT NULL DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )
    # NOVA: cores por disciplina
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS subject_colors (
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            color_hex TEXT NOT NULL,            -- "#RRGGBB"
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, subject),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )
    conn.commit()
    conn.close()

def create_user(first_name: str, last_name: str, email: str, password_hash: bytes) -> int:
    conn = get_conn()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO users (first_name, last_name, email, password_hash)
                VALUES (?, ?, ?, ?)
                """,
                (first_name.strip(), last_name.strip(), email.strip().lower(), password_hash),
            )
            return cur.lastrowid
    finally:
        conn.close()

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.strip().lower(),)
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

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
    conn = get_conn()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO study_records
                (user_id, study_date, category, subject, topic, duration_sec, hits, mistakes, page_start, page_end, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(user_id),
                    study_date,
                    category.strip(),
                    subject.strip(),
                    (topic or "").strip() or None,
                    int(duration_sec),
                    None if hits is None else int(hits),
                    None if mistakes is None else int(mistakes),
                    None if page_start in (None, "") else int(page_start),
                    None if page_end in (None, "") else int(page_end),
                    (comment or "").strip() or None,
                ),
            )
            return cur.lastrowid
    finally:
        conn.close()


from datetime import datetime, date, timedelta

def get_study_presence_since_signup(user_id: int) -> list[dict]:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT DATE(created_at) AS created_date FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        if not row or not row["created_date"]:
            return []

        start = datetime.strptime(row["created_date"], "%Y-%m-%d").date()
        end = date.today()

        cur = conn.execute(
            """
            SELECT study_date, COALESCE(SUM(duration_sec), 0) AS total_sec
            FROM study_records
            WHERE user_id = ?
              AND study_date BETWEEN ? AND ?
            GROUP BY study_date
            """,
            (user_id, start.isoformat(), end.isoformat())
        )
        totals = {r["study_date"]: int(r["total_sec"] // 60) for r in cur.fetchall()}

        days = (end - start).days + 1
        out = []
        for i in range(days):
            d = (start + timedelta(days=i)).isoformat()
            mins = totals.get(d, 0)
            out.append({"date": d, "minutes": mins, "has_study": mins > 0})
        return out
    finally:
        conn.close()

def delete_study_record(record_id: int, user_id: int) -> bool:
    conn = get_conn()
    try:
        with conn:
            cur = conn.execute(
                "DELETE FROM study_records WHERE id = ? AND user_id = ?",
                (int(record_id), int(user_id)),
            )
            return cur.rowcount > 0
    finally:
        conn.close()

def get_user_created_date(user_id: int) -> Optional[str]:
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT DATE(created_at) as created_date FROM users WHERE id = ?",
            (user_id,)
        )
        row = cur.fetchone()
        return row["created_date"] if row else None
    finally:
        conn.close()

def get_total_minutes_by_date_range(user_id: int, start_date: str, end_date: str) -> dict[str, int]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT study_date, COALESCE(SUM(duration_sec), 0) AS total_sec
            FROM study_records
            WHERE user_id = ?
              AND study_date BETWEEN ? AND ?
            GROUP BY study_date
            """,
            (int(user_id), start_date, end_date)
        )
        rows = cur.fetchall()
        return {r["study_date"]: int(r["total_sec"] // 60) for r in rows}
    finally:
        conn.close()

def get_questions_breakdown_by_date_range(user_id: int, start_date: str, end_date: str) -> dict[str, dict[str, int]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT
                study_date,
                COALESCE(SUM(COALESCE(hits, 0)), 0)      AS total_hits,
                COALESCE(SUM(COALESCE(mistakes, 0)), 0)  AS total_mistakes
            FROM study_records
            WHERE user_id = ?
              AND study_date BETWEEN ? AND ?
            GROUP BY study_date
            """,
            (int(user_id), start_date, end_date)
        )
        rows = cur.fetchall()
        out = {}
        for r in rows:
            out[r["study_date"]] = {
                "hits": int(r["total_hits"]),
                "mistakes": int(r["total_mistakes"]),
            }
        return out
    finally:
        conn.close()

def get_study_records_by_user(user_id: int):
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT *
            FROM study_records
            WHERE user_id = ?
            ORDER BY study_date DESC, created_at DESC
            """,
            (user_id,)
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

# ======== METAS SEMANAIS ========

def get_weekly_goal(user_id: int) -> Optional[Dict[str, int]]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT target_hours, target_questions
            FROM weekly_goals
            WHERE user_id = ?
            """,
            (int(user_id),)
        )
        row = cur.fetchone()
        return {"target_hours": int(row["target_hours"]), "target_questions": int(row["target_questions"])} if row else None
    finally:
        conn.close()

def upsert_weekly_goal(user_id: int, target_hours: int, target_questions: int) -> None:
    conn = get_conn()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO weekly_goals (user_id, target_hours, target_questions)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    target_hours=excluded.target_hours,
                    target_questions=excluded.target_questions,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (int(user_id), int(target_hours), int(target_questions))
            )
    finally:
        conn.close()

# ======== RESUMOS ========

def get_disciplinas_resumo(user_id: int) -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT 
                subject,
                COALESCE(SUM(duration_sec), 0)      AS total_sec,
                COALESCE(SUM(COALESCE(hits,0)), 0)  AS total_hits,
                COALESCE(SUM(COALESCE(mistakes,0)), 0) AS total_mistakes
            FROM study_records
            WHERE user_id = ?
            GROUP BY subject
            ORDER BY subject COLLATE NOCASE
            """,
            (int(user_id),),
        )
        out = []
        for r in cur.fetchall():
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
    finally:
        conn.close()

def get_day_subject_breakdown(user_id: int, day_iso: str) -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT
                subject,
                COALESCE(SUM(duration_sec), 0) AS total_sec
            FROM study_records
            WHERE user_id = ?
              AND study_date = ?
            GROUP BY subject
            ORDER BY subject COLLATE NOCASE
            """,
            (int(user_id), day_iso),
        )
        rows = cur.fetchall()
        return [{"subject": r["subject"], "total_sec": int(r["total_sec"] or 0)} for r in rows]
    finally:
        conn.close()

# ======== CORES POR DISCIPLINA ========

def get_subject_colors(user_id: int) -> dict[str, str]:
    """
    Retorna {subject: '#RRGGBB'} para o usuário.
    """
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT subject, color_hex
            FROM subject_colors
            WHERE user_id = ?
            """,
            (int(user_id),)
        )
        return {r["subject"]: r["color_hex"] for r in cur.fetchall()}
    finally:
        conn.close()

def upsert_subject_color(user_id: int, subject: str, color_hex: str) -> None:
    """
    Insere/atualiza a cor de uma disciplina.
    """
    conn = get_conn()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO subject_colors (user_id, subject, color_hex)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, subject) DO UPDATE SET
                    color_hex=excluded.color_hex,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (int(user_id), subject.strip(), color_hex.strip().upper()),
            )
    finally:
        conn.close()
