"""
Postgres connection helper. Local dev default assumes a peer-auth Postgres
on the default socket (matches `createdb codexbpsc` with no user/password
setup) -- override with DATABASE_URL for any other environment.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.environ.get("DATABASE_URL", "dbname=codexbpsc")


@contextmanager
def get_connection():
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
