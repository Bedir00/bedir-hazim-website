"""SQLite-Speicher für Kunden (CI-Profile) und Speisekarten-Prüfungen."""

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    ci_json TEXT NOT NULL,
    logo_path TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS menus (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    source TEXT NOT NULL,
    file_path TEXT,
    status TEXT NOT NULL,
    stage TEXT,
    error TEXT,
    score INTEGER,
    fails INTEGER,
    warns INTEGER,
    report_json TEXT,
    redesign_notes TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS menus_client ON menus(client_id, created_at);
CREATE INDEX IF NOT EXISTS menus_status ON menus(status);
"""


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class Database:
    def __init__(self, path: Path):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript(SCHEMA)
        self._lock = threading.Lock()

    def close(self) -> None:
        self._conn.close()

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock, self._conn:
            return self._conn.execute(sql, params)

    def _all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(row) for row in self._conn.execute(sql, params).fetchall()]

    def _one(self, sql: str, params: tuple = ()) -> dict | None:
        rows = self._all(sql, params)
        return rows[0] if rows else None

    # ---- Kunden ---------------------------------------------------------

    def create_client(self, name: str, ci: dict) -> dict:
        now = time.time()
        client_id = new_id()
        self._execute(
            "INSERT INTO clients (id, name, ci_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (client_id, name, json.dumps(ci, ensure_ascii=False), now, now),
        )
        return self.get_client(client_id)

    def update_client(self, client_id: str, name: str, ci: dict) -> dict | None:
        self._execute(
            "UPDATE clients SET name = ?, ci_json = ?, updated_at = ? WHERE id = ?",
            (name, json.dumps(ci, ensure_ascii=False), time.time(), client_id),
        )
        return self.get_client(client_id)

    def set_client_logo(self, client_id: str, logo_path: str | None) -> None:
        self._execute("UPDATE clients SET logo_path = ?, updated_at = ? WHERE id = ?", (logo_path, time.time(), client_id))

    def delete_client(self, client_id: str) -> None:
        self._execute("DELETE FROM clients WHERE id = ?", (client_id,))

    def get_client(self, client_id: str) -> dict | None:
        row = self._one("SELECT * FROM clients WHERE id = ?", (client_id,))
        return _client(row) if row else None

    def find_client_by_name(self, name: str) -> dict | None:
        row = self._one("SELECT * FROM clients WHERE lower(name) = lower(?)", (name.strip(),))
        return _client(row) if row else None

    def list_clients(self) -> list[dict]:
        rows = self._all(
            """
            SELECT c.*,
                   COUNT(m.id) AS menu_count,
                   SUM(CASE WHEN m.status = 'done' THEN 1 ELSE 0 END) AS done_count,
                   ROUND(AVG(m.score)) AS avg_score
            FROM clients c LEFT JOIN menus m ON m.client_id = c.id
            GROUP BY c.id ORDER BY c.name COLLATE NOCASE
            """
        )
        return [_client(row) for row in rows]

    # ---- Speisekarten ---------------------------------------------------

    def create_menu(self, client_id: str, source_type: str, source: str, file_path: str | None) -> dict:
        now = time.time()
        menu_id = new_id()
        self._execute(
            """INSERT INTO menus (id, client_id, source_type, source, file_path, status, stage, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'queued', 'Wartet', ?, ?)""",
            (menu_id, client_id, source_type, source, file_path, now, now),
        )
        return self.get_menu(menu_id)

    def update_menu(self, menu_id: str, **fields) -> None:
        if "report" in fields:
            report = fields.pop("report")
            fields["report_json"] = json.dumps(report, ensure_ascii=False) if report is not None else None
            checks = (report or {}).get("checks", [])
            fields["fails"] = sum(c["status"] == "fail" for c in checks)
            fields["warns"] = sum(c["status"] == "warn" for c in checks)
        if "redesign_notes" in fields and fields["redesign_notes"] is not None:
            fields["redesign_notes"] = json.dumps(fields["redesign_notes"], ensure_ascii=False)
        fields["updated_at"] = time.time()
        columns = ", ".join(f"{key} = ?" for key in fields)
        self._execute(f"UPDATE menus SET {columns} WHERE id = ?", (*fields.values(), menu_id))

    def get_menu(self, menu_id: str) -> dict | None:
        row = self._one("SELECT * FROM menus WHERE id = ?", (menu_id,))
        return _menu(row) if row else None

    def list_menus(self, client_id: str | None = None) -> list[dict]:
        if client_id:
            rows = self._all("SELECT * FROM menus WHERE client_id = ? ORDER BY created_at DESC", (client_id,))
        else:
            rows = self._all("SELECT * FROM menus ORDER BY created_at DESC")
        return [_menu(row, include_report=False) for row in rows]

    def list_menus_with_reports(self, client_id: str | None = None) -> list[dict]:
        if client_id:
            rows = self._all("SELECT * FROM menus WHERE client_id = ? ORDER BY created_at", (client_id,))
        else:
            rows = self._all("SELECT * FROM menus ORDER BY client_id, created_at")
        return [_menu(row) for row in rows]

    def menus_by_status(self, *statuses: str) -> list[dict]:
        marks = ", ".join("?" for _ in statuses)
        rows = self._all(f"SELECT * FROM menus WHERE status IN ({marks}) ORDER BY created_at", statuses)
        return [_menu(row, include_report=False) for row in rows]

    def delete_menu(self, menu_id: str) -> None:
        self._execute("DELETE FROM menus WHERE id = ?", (menu_id,))


def _client(row: dict) -> dict:
    row = dict(row)
    row["ci"] = json.loads(row.pop("ci_json"))
    return row


def _menu(row: dict, include_report: bool = True) -> dict:
    row = dict(row)
    report = row.pop("report_json")
    notes = row.pop("redesign_notes")
    if include_report:
        row["report"] = json.loads(report) if report else None
    row["redesign_notes"] = json.loads(notes) if notes else []
    return row
