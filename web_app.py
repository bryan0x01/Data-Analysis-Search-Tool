from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import load_records, norm_email, norm_phone_key, norm_name

DATA_DIR = Path("./my_exports").resolve()
DB_PATH = Path("./app.db").resolve()

app = FastAPI(title="User Search", version="1.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            id TEXT PRIMARY KEY,
            source_file TEXT,
            row_num INTEGER,

            first_name TEXT,
            last_name TEXT,
            full_name TEXT,

            email TEXT,
            email_norm TEXT,

            phone TEXT,
            phone_key TEXT,

            event_name TEXT,
            activity_type TEXT,
            activity_date TEXT,
            payment_status TEXT,
            proceeds_amount TEXT,

            raw_json TEXT
        )
        """
    )

    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_norm ON records(email_norm)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_phone_key ON records(phone_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_full_name ON records(full_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_name ON records(event_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_payment_status ON records(payment_status)")
    conn.commit()


_money_re = re.compile(r"[^0-9.\-]+")


def to_float_amount(s: Any) -> Optional[float]:
    if s is None:
        return None
    cleaned = _money_re.sub("", str(s)).strip()
    if cleaned == "":
        return None
    try:
        return float(cleaned)
    except Exception:
        return None


def records_to_dataframe(records) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for r in records:
        raw = r.raw or {}
        rows.append(
            {
                "id": f"{r.source_file}::{r.row_num}",
                "source_file": r.source_file,
                "row_num": r.row_num,
                "first_name": r.first_name,
                "last_name": r.last_name,
                "full_name": r.full_name,
                "email": r.email,
                "email_norm": norm_email(r.email),
                "phone": r.phone,
                "phone_key": norm_phone_key(r.phone),
                "event_name": getattr(r, "event_name", "") or "",
                "activity_type": getattr(r, "activity_type", "") or "",
                "activity_date": getattr(r, "activity_date", "") or "",
                "payment_status": getattr(r, "payment_status", "") or "",
                "proceeds_amount": getattr(r, "proceeds_amount", "") or "",
                "raw_json": json.dumps(raw, ensure_ascii=False),
            }
        )
    return pd.DataFrame(rows)


def refresh_database(conn: sqlite3.Connection) -> Dict[str, Any]:
    records = load_records(DATA_DIR)
    df = records_to_dataframe(records)

    conn.execute("DELETE FROM records")

    if not df.empty:
        conn.executemany(
            """
            INSERT INTO records (
                id, source_file, row_num,
                first_name, last_name, full_name,
                email, email_norm,
                phone, phone_key,
                event_name, activity_type, activity_date, payment_status, proceeds_amount,
                raw_json
            ) VALUES (
                :id, :source_file, :row_num,
                :first_name, :last_name, :full_name,
                :email, :email_norm,
                :phone, :phone_key,
                :event_name, :activity_type, :activity_date, :payment_status, :proceeds_amount,
                :raw_json
            )
            """,
            df.to_dict(orient="records"),
        )

    conn.commit()
    return {"rows_loaded": int(len(df)), "db_path": str(DB_PATH), "data_dir": str(DATA_DIR)}


_df_cache: Optional[pd.DataFrame] = None


@app.on_event("startup")
def startup() -> None:
    global _df_cache
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    conn = connect_db()
    create_schema(conn)
    info = refresh_database(conn)
    _df_cache = pd.read_sql_query("SELECT * FROM records", conn)
    conn.close()

    print("Startup loaded:", info)


@app.get("/")
def home():
    return FileResponse("static/index.html")


@app.get("/api/reload")
def api_reload():
    global _df_cache
    conn = connect_db()
    create_schema(conn)
    info = refresh_database(conn)
    _df_cache = pd.read_sql_query("SELECT * FROM records", conn)
    conn.close()
    return {"ok": True, **info}


@app.get("/api/search")
def api_search(q: str = Query(..., min_length=1), limit: int = 25):
    q_raw = q.strip()
    limit = max(1, min(int(limit), 100))

    # If query is only spaces, return no matches instead of broad "match all" behavior.
    if not q_raw:
        return {"query": q_raw, "count": 0, "results": []}

    q_email = norm_email(q_raw)
    q_phone = norm_phone_key(q_raw)
    q_name = norm_name(q_raw)

    digits = re.sub(r"\D+", "", q_raw)

    sql = ""
    params: Tuple[Any, ...] = ()

    if len(digits) >= 7:
        sql = """
            SELECT id, full_name, email, phone, source_file, row_num,
                   event_name, activity_type, payment_status, proceeds_amount
            FROM records
            WHERE phone_key LIKE ?
            LIMIT ?
        """
        params = (f"%{q_phone}%", limit)

    elif "@" in q_raw and "." in q_raw:
        sql = """
            SELECT id, full_name, email, phone, source_file, row_num,
                   event_name, activity_type, payment_status, proceeds_amount
            FROM records
            WHERE email_norm LIKE ?
            LIMIT ?
        """
        params = (f"%{q_email}%", limit)

    else:
        # Only include phone search clause when query has digits.
        # This avoids `LIKE '%%'` returning every row.
        if q_phone:
            sql = """
                SELECT id, full_name, email, phone, source_file, row_num,
                       event_name, activity_type, payment_status, proceeds_amount
                FROM records
                WHERE LOWER(full_name) LIKE ?
                   OR email_norm LIKE ?
                   OR phone_key LIKE ?
                LIMIT ?
            """
            params = (f"%{q_name}%", f"%{q_email}%", f"%{q_phone}%", limit)
        else:
            sql = """
                SELECT id, full_name, email, phone, source_file, row_num,
                       event_name, activity_type, payment_status, proceeds_amount
                FROM records
                WHERE LOWER(full_name) LIKE ?
                   OR email_norm LIKE ?
                LIMIT ?
            """
            params = (f"%{q_name}%", f"%{q_email}%", limit)

    conn = connect_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    results: List[Dict[str, Any]] = []
    for r in rows:
        results.append(
            {
                "id": r["id"],
                "name": r["full_name"] or "",
                "email": r["email"] or "",
                "phone": r["phone"] or "",
                "source": f'{r["source_file"]}:{r["row_num"]}',
                "event_name": r["event_name"] or "",
                "activity_type": r["activity_type"] or "",
                "payment_status": r["payment_status"] or "",
                "amount": r["proceeds_amount"] or "",
            }
        )

    return {"query": q_raw, "count": len(results), "results": results}


@app.get("/api/record")
def api_record(record_id: str):
    conn = connect_db()
    row = conn.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
    conn.close()

    if not row:
        return {"error": "Not found"}

    raw: Dict[str, Any] = {}
    try:
        raw = json.loads(row["raw_json"] or "{}")
    except Exception:
        raw = {}

    return {
        "id": row["id"],
        "source_file": row["source_file"],
        "row_num": row["row_num"],
        "name": row["full_name"] or "",
        "email": row["email"] or "",
        "phone": row["phone"] or "",
        "event_name": row["event_name"] or "",
        "activity_type": row["activity_type"] or "",
        "activity_date": row["activity_date"] or "",
        "payment_status": row["payment_status"] or "",
        "amount": row["proceeds_amount"] or "",
        "raw": raw,
    }


@app.get("/api/insights")
def api_insights():
    global _df_cache

    if _df_cache is None:
        conn = connect_db()
        _df_cache = pd.read_sql_query("SELECT * FROM records", conn)
        conn.close()

    df = _df_cache.copy()
    total = int(len(df))

    # Treat null and blank/whitespace strings as missing.
    email_missing = df["email"].isna() | df["email"].astype(str).str.strip().eq("")
    phone_missing = df["phone"].isna() | df["phone"].astype(str).str.strip().eq("")
    missing_email_pct = float(email_missing.mean() * 100) if total else 0.0
    missing_phone_pct = float(phone_missing.mean() * 100) if total else 0.0

    # Duplicate counts should ignore empty keys.
    email_keys = df["email_norm"].fillna("").astype(str).str.strip()
    phone_keys = df["phone_key"].fillna("").astype(str).str.strip()
    dup_email = int(email_keys[email_keys.ne("")].duplicated().sum()) if total else 0
    dup_phone = int(phone_keys[phone_keys.ne("")].duplicated().sum()) if total else 0

    df["amount_num"] = df["proceeds_amount"].apply(to_float_amount)
    total_amount = float(df["amount_num"].fillna(0).sum()) if total else 0.0

    top_events = df["event_name"].fillna("(none)").value_counts().head(6).to_dict() if total else {}
    status_counts = df["payment_status"].fillna("(none)").value_counts().head(6).to_dict() if total else {}

    return {
        "total_records": total,
        "total_amount": round(total_amount, 2),
        "missing_email_pct": round(missing_email_pct, 1),
        "missing_phone_pct": round(missing_phone_pct, 1),
        "duplicate_emails": dup_email,
        "duplicate_phones": dup_phone,
        "top_events": top_events,
        "top_payment_status": status_counts,
    }
