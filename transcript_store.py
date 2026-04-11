"""Transcript warehouse abstraction for pushing raw transcripts and summaries.

This module defines an abstract TranscriptStore interface with pluggable
backends. Swap DuckDBTranscriptStore for SnowflakeTranscriptStore (or any
other warehouse) without touching the rest of the app.

Usage:
    from transcript_store import get_transcript_store
    store = get_transcript_store()
    store.push_transcript(meeting_id, client_name, transcript, summary, meeting)
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path

import streamlit as st


class TranscriptStore(ABC):
    """Abstract interface for any transcript warehouse backend."""

    @abstractmethod
    def push_transcript(
        self,
        meeting_id: str,
        client_name: str,
        transcript: list[dict],
        summary: dict,
        meeting: dict,
    ) -> None:
        """Persist a raw transcript + generated summary to the warehouse."""

    @abstractmethod
    def get_all_transcripts(self) -> list[dict]:
        """Return all stored transcript rows (for verification / debugging)."""

    @abstractmethod
    def get_transcript(self, meeting_id: str) -> dict | None:
        """Return a single stored row by meeting_id, or None if not found."""


class DuckDBTranscriptStore(TranscriptStore):
    """Local DuckDB-backed store — a free, Snowflake-compatible SQL mock.

    DuckDB uses a SQL dialect very close to Snowflake's, so the schema
    and queries written here will largely work on real Snowflake with
    minimal changes (e.g., VARIANT vs JSON, TIMESTAMP_NTZ vs TIMESTAMP).

    Storage: a single .duckdb file under data/. Safe to delete at any
    time — it will be recreated on next write.

    Note: Streamlit Cloud has an ephemeral filesystem, so the file will
    not persist across app restarts in deployment. Use SnowflakeTranscriptStore
    for durable cloud storage.
    """

    DEFAULT_PATH = Path(__file__).parent / "data" / "transcripts.duckdb"

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS raw_transcripts (
        meeting_id       VARCHAR PRIMARY KEY,
        client_name      VARCHAR,
        client_contact   VARCHAR,
        deal_name        VARCHAR,
        deal_stage       VARCHAR,
        deal_value       VARCHAR,
        meeting_type     VARCHAR,
        meeting_date     VARCHAR,
        transcript       JSON,
        summary          JSON,
        created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """

    def __init__(self, db_path: Path | str | None = None):
        import duckdb  # imported lazily so the app runs even if unused

        self._duckdb = duckdb
        self.db_path = Path(db_path) if db_path else self.DEFAULT_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create the table once at startup
        with self._connect() as con:
            con.execute(self.SCHEMA)

    def _connect(self):
        return self._duckdb.connect(str(self.db_path))

    def push_transcript(
        self,
        meeting_id: str,
        client_name: str,
        transcript: list[dict],
        summary: dict,
        meeting: dict,
    ) -> None:
        transcript_json = json.dumps(transcript)
        summary_json = json.dumps(summary)

        with self._connect() as con:
            # Upsert: delete existing row then insert fresh (DuckDB supports
            # ON CONFLICT but this stays compatible with more backends)
            con.execute(
                "DELETE FROM raw_transcripts WHERE meeting_id = ?",
                [meeting_id],
            )
            con.execute(
                """
                INSERT INTO raw_transcripts (
                    meeting_id, client_name, client_contact,
                    deal_name, deal_stage, deal_value,
                    meeting_type, meeting_date,
                    transcript, summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    meeting_id,
                    client_name,
                    meeting.get("client_contact"),
                    meeting.get("deal_name"),
                    meeting.get("deal_stage"),
                    meeting.get("deal_value"),
                    meeting.get("type"),
                    meeting.get("date"),
                    transcript_json,
                    summary_json,
                ],
            )

    def get_all_transcripts(self) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT meeting_id, client_name, deal_name, created_at "
                "FROM raw_transcripts ORDER BY created_at DESC"
            ).fetchall()
        return [
            {
                "meeting_id": r[0],
                "client_name": r[1],
                "deal_name": r[2],
                "created_at": str(r[3]),
            }
            for r in rows
        ]

    def get_transcript(self, meeting_id: str) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT meeting_id, client_name, transcript, summary, created_at "
                "FROM raw_transcripts WHERE meeting_id = ?",
                [meeting_id],
            ).fetchone()
        if not row:
            return None
        return {
            "meeting_id": row[0],
            "client_name": row[1],
            "transcript": json.loads(row[2]) if row[2] else None,
            "summary": json.loads(row[3]) if row[3] else None,
            "created_at": str(row[4]),
        }


class SnowflakeTranscriptStore(TranscriptStore):
    """Snowflake warehouse client (stub).

    To implement:
    1. pip install snowflake-connector-python
    2. Add to .streamlit/secrets.toml:
       SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD (or PRIVATE_KEY),
       SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE, SNOWFLAKE_SCHEMA
    3. Create the target table in Snowflake:

       CREATE TABLE IF NOT EXISTS raw_transcripts (
           meeting_id       VARCHAR PRIMARY KEY,
           client_name      VARCHAR,
           client_contact   VARCHAR,
           deal_name        VARCHAR,
           deal_stage       VARCHAR,
           deal_value       VARCHAR,
           meeting_type     VARCHAR,
           meeting_date     VARCHAR,
           transcript       VARIANT,
           summary          VARIANT,
           created_at       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
           updated_at       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
       );

    4. Use snowflake.connector to execute inserts using PARSE_JSON() for
       the VARIANT columns:

       import snowflake.connector
       con = snowflake.connector.connect(
           account=st.secrets["SNOWFLAKE_ACCOUNT"],
           user=st.secrets["SNOWFLAKE_USER"],
           password=st.secrets["SNOWFLAKE_PASSWORD"],
           warehouse=st.secrets["SNOWFLAKE_WAREHOUSE"],
           database=st.secrets["SNOWFLAKE_DATABASE"],
           schema=st.secrets["SNOWFLAKE_SCHEMA"],
       )
       cur = con.cursor()
       cur.execute(
           "INSERT INTO raw_transcripts SELECT %s, %s, ..., PARSE_JSON(%s), PARSE_JSON(%s)",
           [meeting_id, client_name, ..., transcript_json, summary_json],
       )

    Sign up for a free 30-day trial with $400 credits:
    https://signup.snowflake.com/
    """

    def __init__(self, **kwargs):
        raise NotImplementedError(
            "SnowflakeTranscriptStore is a stub. Set WAREHOUSE_BACKEND=duckdb "
            "in secrets or implement the Snowflake connection here."
        )

    def push_transcript(
        self,
        meeting_id: str,
        client_name: str,
        transcript: list[dict],
        summary: dict,
        meeting: dict,
    ) -> None:
        raise NotImplementedError

    def get_all_transcripts(self) -> list[dict]:
        raise NotImplementedError

    def get_transcript(self, meeting_id: str) -> dict | None:
        raise NotImplementedError


@st.cache_resource
def get_transcript_store() -> TranscriptStore:
    """Return the configured transcript warehouse client.

    Selection is controlled by the WAREHOUSE_BACKEND secret:
    - "duckdb" (default): local .duckdb file — free, Snowflake-compatible SQL
    - "snowflake": real Snowflake warehouse via snowflake-connector-python
    """
    backend = st.secrets.get("WAREHOUSE_BACKEND", "duckdb").lower()

    if backend == "snowflake":
        return SnowflakeTranscriptStore(
            account=st.secrets["SNOWFLAKE_ACCOUNT"],
            user=st.secrets["SNOWFLAKE_USER"],
            password=st.secrets["SNOWFLAKE_PASSWORD"],
            warehouse=st.secrets["SNOWFLAKE_WAREHOUSE"],
            database=st.secrets["SNOWFLAKE_DATABASE"],
            schema=st.secrets["SNOWFLAKE_SCHEMA"],
        )

    return DuckDBTranscriptStore()
