"""MSSQL database service for incident source data."""

import logging
from typing import Any, Optional
from datetime import datetime
from contextlib import contextmanager

import pyodbc

from app.config import get_settings

logger = logging.getLogger(__name__)


class MSSQLService:
    """Service for MSSQL database operations."""

    _connection: Optional[pyodbc.Connection] = None

    def __init__(self):
        self.settings = get_settings().mssql
        self._connection_string = (
            f"DRIVER={{{self.settings.driver}}};"
            f"SERVER={self.settings.host},{self.settings.port};"
            f"DATABASE={self.settings.database};"
            f"UID={self.settings.username};"
            f"PWD={self.settings.password};"
            "TrustServerCertificate=yes;"
        )

    def connect(self) -> pyodbc.Connection:
        """Establish connection to MSSQL."""
        if self._connection is None:
            self._connection = pyodbc.connect(self._connection_string)
            logger.info(f"Connected to MSSQL at {self.settings.host}:{self.settings.port}")
        return self._connection

    def close(self) -> None:
        """Close MSSQL connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Closed MSSQL connection")

    @contextmanager
    def cursor(self):
        """Get a database cursor context manager."""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

    def execute(self, query: str, params: Optional[tuple] = None) -> list[dict[str, Any]]:
        """Execute a query and return results as dictionaries.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of result rows as dictionaries
        """
        with self.cursor() as cursor:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            columns = [column[0] for column in cursor.description] if cursor.description else []
            results = []

            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))

            return results

    def get_changed_records(
        self,
        since: datetime,
        batch_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """Get records changed since a timestamp.

        Args:
            since: Timestamp to get changes from
            batch_size: Maximum records to return

        Returns:
            List of changed records
        """
        query = f"""
            SELECT TOP {batch_size} *
            FROM {self.settings.table}
            WHERE updated_at > ?
            ORDER BY updated_at ASC
        """

        return self.execute(query, (since,))

    def get_all_records(self, batch_size: int = 1000, offset: int = 0) -> list[dict[str, Any]]:
        """Get all records with pagination.

        Args:
            batch_size: Number of records per batch
            offset: Starting offset

        Returns:
            List of records
        """
        query = f"""
            SELECT *
            FROM {self.settings.table}
            ORDER BY id
            OFFSET {offset} ROWS
            FETCH NEXT {batch_size} ROWS ONLY
        """

        return self.execute(query)

    def get_record_count(self) -> int:
        """Get total record count.

        Returns:
            Total number of records
        """
        query = f"SELECT COUNT(*) as count FROM {self.settings.table}"
        result = self.execute(query)
        return result[0]["count"] if result else 0

    def get_columns(self) -> list[dict[str, Any]]:
        """Get column information for the incidents table.

        Returns:
            List of column definitions
        """
        query = """
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                CHARACTER_MAXIMUM_LENGTH,
                IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
        """

        return self.execute(query, (self.settings.table,))

    def get_sample_values(
        self,
        column: str,
        limit: int = 10,
    ) -> list[Any]:
        """Get sample distinct values for a column.

        Args:
            column: Column name
            limit: Maximum samples

        Returns:
            List of distinct sample values
        """
        query = f"""
            SELECT DISTINCT TOP {limit} [{column}]
            FROM {self.settings.table}
            WHERE [{column}] IS NOT NULL
        """

        try:
            results = self.execute(query)
            return [r[column] for r in results]
        except Exception as e:
            logger.warning(f"Error getting samples for {column}: {e}")
            return []

    def get_aggregations(
        self,
        group_by: str,
        date_filter: Optional[tuple[datetime, datetime]] = None,
    ) -> list[dict[str, Any]]:
        """Get aggregations grouped by a column.

        Args:
            group_by: Column to group by
            date_filter: Optional (start, end) date filter

        Returns:
            List of aggregations
        """
        where_clause = ""
        params = ()

        if date_filter:
            where_clause = "WHERE created_at BETWEEN ? AND ?"
            params = date_filter

        query = f"""
            SELECT
                [{group_by}] as group_value,
                COUNT(*) as count
            FROM {self.settings.table}
            {where_clause}
            GROUP BY [{group_by}]
            ORDER BY count DESC
        """

        return self.execute(query, params) if params else self.execute(query)

    def discover_schema(self) -> dict[str, Any]:
        """Discover schema from MSSQL table.

        Returns:
            Dictionary containing schema information
        """
        # Get columns
        columns = self.get_columns()

        # Categorize columns
        location_fields = []
        status_fields = []
        time_fields = []
        properties = []

        location_keywords = ["location", "address", "building", "floor", "area", "zone", "room"]
        status_keywords = ["status", "state", "active", "enabled"]
        time_keywords = ["date", "time", "created", "updated", "timestamp", "at"]

        for col in columns:
            col_name = col["COLUMN_NAME"].lower()
            col_type = col["DATA_TYPE"]

            # Categorize based on name patterns
            if any(kw in col_name for kw in location_keywords):
                location_fields.append(col["COLUMN_NAME"])
            elif any(kw in col_name for kw in status_keywords):
                status_fields.append(col["COLUMN_NAME"])
            elif any(kw in col_name for kw in time_keywords) or col_type in ("datetime", "datetime2", "date"):
                time_fields.append(col["COLUMN_NAME"])

            # Get sample values
            samples = self.get_sample_values(col["COLUMN_NAME"], 5)

            properties.append({
                "name": col["COLUMN_NAME"],
                "type": col["DATA_TYPE"],
                "max_length": col["CHARACTER_MAXIMUM_LENGTH"],
                "nullable": col["IS_NULLABLE"] == "YES",
                "samples": samples,
            })

        return {
            "table": self.settings.table,
            "columns": columns,
            "properties": properties,
            "location_fields": location_fields,
            "status_fields": status_fields,
            "time_fields": time_fields,
            "record_count": self.get_record_count(),
        }

    def health_check(self) -> bool:
        """Check if MSSQL is accessible."""
        try:
            result = self.execute("SELECT 1 as health")
            return result[0]["health"] == 1
        except Exception as e:
            logger.error(f"MSSQL health check failed: {e}")
            return False
