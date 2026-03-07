"""Incident history database — SQLite for local tracking."""

import sqlite3
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "history.db"


class IncidentHistoryDB:
    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL UNIQUE,
                service_name TEXT NOT NULL,
                alert_name TEXT NOT NULL,
                domain TEXT,
                severity TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                analysis TEXT,
                proposed_tool TEXT,
                action_parameters TEXT,
                status TEXT DEFAULT 'pending',
                pir_report TEXT,
                report_path TEXT
            )
        """)
        self._conn.commit()

    def log_incident(self, incident_id: str, service_name: str, alert_name: str,
                     domain: str = "", severity: str = "", analysis: str = "",
                     proposed_action: dict = None, status: str = "plan_ready",
                     report_path: str = ""):
        try:
            tool = (proposed_action or {}).get("tool", "unknown")
            params = json.dumps((proposed_action or {}).get("parameters", {}))
            self._conn.execute("""
                INSERT OR REPLACE INTO incidents
                (incident_id, service_name, alert_name, domain, severity,
                 analysis, proposed_tool, action_parameters, status, report_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (incident_id, service_name, alert_name, domain, severity,
                  analysis, tool, params, status, report_path))
            self._conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to log incident: {e}")

    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        try:
            row = self._conn.execute(
                "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)
            ).fetchone()
            if row:
                d = dict(row)
                try:
                    d["action_parameters"] = json.loads(d.get("action_parameters", "{}"))
                except (json.JSONDecodeError, TypeError):
                    pass
                return d
        except sqlite3.Error as e:
            logger.error(f"Failed to fetch incident: {e}")
        return None

    def update_status(self, incident_id: str, status: str):
        self._conn.execute(
            "UPDATE incidents SET status = ? WHERE incident_id = ?",
            (status, incident_id)
        )
        self._conn.commit()

    def save_pir(self, incident_id: str, report: str):
        self._conn.execute(
            "UPDATE incidents SET pir_report = ? WHERE incident_id = ?",
            (report, incident_id)
        )
        self._conn.commit()

    def get_recent_incidents(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            rows = self._conn.execute(
                "SELECT * FROM incidents ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
            results = []
            for row in rows:
                d = dict(row)
                try:
                    d["action_parameters"] = json.loads(d.get("action_parameters", "{}"))
                except (json.JSONDecodeError, TypeError):
                    pass
                results.append(d)
            return results
        except sqlite3.Error as e:
            logger.error(f"Failed to fetch incidents: {e}")
            return []
