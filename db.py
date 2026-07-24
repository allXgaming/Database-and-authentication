# db.py

import sqlite3
from typing import Optional, List, Dict, Any

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


class UniversalDataManager:
    """সাধারণ SQLite ডেটা ম্যানেজার (ইনসার্ট, আপডেট, ডিলিট, কোয়েরি)"""

    def __init__(
        self,
        db_file: str = "data.db",
        table_name: str = "records",
        primary_key: str = "id",
        columns: Optional[Dict[str, str]] = None,
    ):
        self.db_file = db_file
        self.table_name = table_name
        self.primary_key = primary_key
        self.columns = columns or {
            "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        }
        self._init_table()

    def connect(self):
        return sqlite3.connect(self.db_file)

    def _init_table(self):
        col_sql = ", ".join(f"{name} {dtype}" for name, dtype in self.columns.items())
        with self.connect() as conn:
            conn.execute(f"CREATE TABLE IF NOT EXISTS {self.table_name} ({col_sql})")
            conn.commit()

    def insert(self, data: Dict[str, Any]) -> bool:
        if not data:
            return False
        cols = list(data.keys())
        q = f"INSERT INTO {self.table_name} ({', '.join(cols)}) VALUES ({', '.join(['?']*len(cols))})"
        try:
            with self.connect() as conn:
                conn.execute(q, [data[c] for c in cols])
                conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Insert Error: {e}")
            return False

    def insert_many(self, data_list: List[Dict[str, Any]]) -> int:
        if not data_list:
            return 0
        cols = list(data_list[0].keys())
        q = f"INSERT INTO {self.table_name} ({', '.join(cols)}) VALUES ({', '.join(['?']*len(cols))})"
        values = [[d.get(c) for c in cols] for d in data_list]
        try:
            with self.connect() as conn:
                cur = conn.executemany(q, values)
                conn.commit()
                return cur.rowcount
        except sqlite3.Error as e:
            print(f"Insert Many Error: {e}")
            return 0

    def upsert(self, data: Dict[str, Any], conflict_column: Optional[str] = None) -> bool:
        if not data:
            return False
        conflict_column = conflict_column or self.primary_key
        cols = list(data.keys())
        update_cols = [c for c in cols if c != conflict_column]
        set_clause = ", ".join(f"{c}=excluded.{c}" for c in update_cols)
        q = f"""
            INSERT INTO {self.table_name} ({', '.join(cols)})
            VALUES ({', '.join(['?']*len(cols))})
            ON CONFLICT({conflict_column}) DO UPDATE SET {set_clause}
        """
        try:
            with self.connect() as conn:
                conn.execute(q, [data[c] for c in cols])
                conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Upsert Error: {e}")
            return False

    def get_one(self, column: str, value: Any) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(f"SELECT * FROM {self.table_name} WHERE {column}=?", (value,)).fetchone()
            return dict(row) if row else None

    def get_many(self, column: Optional[str] = None, value: Any = None,
                 limit: Optional[int] = None, order_by: Optional[str] = None,
                 descending: bool = False) -> List[Dict[str, Any]]:
        q = f"SELECT * FROM {self.table_name}"
        params = []
        if column is not None:
            q += f" WHERE {column}=?"
            params.append(value)
        if order_by:
            q += f" ORDER BY {order_by} {'DESC' if descending else 'ASC'}"
        if limit:
            q += " LIMIT ?"
            params.append(limit)
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(q, params).fetchall()
            return [dict(r) for r in rows]

    def get_all(self) -> List[Dict[str, Any]]:
        return self.get_many()

    def update(self, where_column: str, where_value: Any, data: Dict[str, Any]) -> bool:
        if not data:
            return False
        set_clause = ", ".join(f"{k}=?" for k in data.keys())
        q = f"UPDATE {self.table_name} SET {set_clause} WHERE {where_column}=?"
        try:
            with self.connect() as conn:
                conn.execute(q, list(data.values()) + [where_value])
                conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Update Error: {e}")
            return False

    def delete(self, column: str, value: Any) -> bool:
        try:
            with self.connect() as conn:
                conn.execute(f"DELETE FROM {self.table_name} WHERE {column}=?", (value,))
                conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Delete Error: {e}")
            return False

    def count(self) -> int:
        with self.connect() as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {self.table_name}").fetchone()[0]

    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """কাস্টম SELECT কোয়েরি চালানোর জন্য"""
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def execute_write(self, query: str, params: tuple = ()) -> bool:
        """INSERT/UPDATE/DELETE এর জন্য"""
        try:
            with self.connect() as conn:
                conn.execute(query, params)
                conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Write Error: {e}")
            return False

    # Excel/CSV import (প্যান্ডাস থাকলে)
    def import_excel(self, file_path: str, sheet_name: Optional[str] = 0) -> int:
        if not PANDAS_AVAILABLE:
            print("pandas ইনস্টল নেই")
            return 0
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            return self.insert_many(df.to_dict(orient="records"))
        except Exception as e:
            print(f"Excel Import Error: {e}")
            return 0

    def import_csv(self, file_path: str) -> int:
        if not PANDAS_AVAILABLE:
            print("pandas ইনস্টল নেই")
            return 0
        try:
            df = pd.read_csv(file_path)
            return self.insert_many(df.to_dict(orient="records"))
        except Exception as e:
            print(f"CSV Import Error: {e}")
            return 0


class GameDataManager(UniversalDataManager):
    """Wingo বটের জন্য বিশেষায়িত ডেটা ম্যানেজার"""

    def __init__(self, db_file: str = "predictions.db"):
        super().__init__(
            db_file=db_file,
            table_name="rounds",
            primary_key="period",
            columns={
                "period": "TEXT PRIMARY KEY",
                "number": "INTEGER",
                "size": "TEXT",
                "prediction": "TEXT",
                "result": "TEXT",
                "range_pred": "TEXT",
                "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            },
        )
        self._init_auth_table()

    def _init_auth_table(self):
        with self.connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS authorized_users (user_id INTEGER PRIMARY KEY)"
            )
            conn.commit()

    # ---------- rounds ----------
    def save_round(self, period: str, number: int, size: str,
                   prediction: str, result: str, range_pred: str) -> bool:
        return self.upsert(
            {
                "period": str(period),
                "number": number,
                "size": size,
                "prediction": prediction,
                "result": result,
                "range_pred": range_pred,
            },
            conflict_column="period",
        )

    def get_recent_history(self, limit: int = 300) -> List[Dict[str, Any]]:
        rows = self.execute_query(
            f"SELECT * FROM {self.table_name} ORDER BY period DESC LIMIT ?",
            (limit,),
        )
        return rows

    def get_last_round(self) -> Optional[Dict[str, Any]]:
        rows = self.execute_query(
            f"SELECT * FROM {self.table_name} ORDER BY period DESC LIMIT 1"
        )
        return rows[0] if rows else None

    # ---------- authorized_users ----------
    def add_authorized_user(self, user_id: int) -> bool:
        return self.execute_write(
            "INSERT OR IGNORE INTO authorized_users (user_id) VALUES (?)",
            (user_id,),
        )

    def remove_authorized_user(self, user_id: int) -> bool:
        return self.execute_write(
            "DELETE FROM authorized_users WHERE user_id = ?",
            (user_id,),
        )

    def get_authorized_users(self) -> List[int]:
        rows = self.execute_query("SELECT user_id FROM authorized_users")
        return [r["user_id"] for r in rows]

    def is_authorized_db(self, user_id: int) -> bool:
        rows = self.execute_query(
            "SELECT 1 FROM authorized_users WHERE user_id = ? LIMIT 1",
            (user_id,),
        )
        return len(rows) > 0