import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

user = os.getenv("DB_USER", "postgres")
password = os.getenv("DB_PASSWORD", "")
host = os.getenv("DB_HOST", "localhost")
port = int(os.getenv("DB_PORT", "5432"))
target_db = os.getenv("TEST_DB_NAME", "chat_app_tests")

# Connect to the default 'postgres' database (or existing app db) with autocommit enabled
conn_info = f"host={host} port={port} user={user} password={password} dbname=postgres"

try:
    conn = psycopg.connect(conn_info, autocommit=True)
except Exception:
    # Fallback to connecting to the main DB if 'postgres' database is restricted
    main_db = os.getenv("DB_NAME", "teamwork_llm_db")
    conn_info = f"host={host} port={port} user={user} password={password} dbname={main_db}"
    conn = psycopg.connect(conn_info, autocommit=True)

with conn:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
        exists = cur.fetchone()
        if exists:
            print(f"Database '{target_db}' already exists.")
        else:
            cur.execute(f'CREATE DATABASE "{target_db}"')
            print(f"Database '{target_db}' created successfully!")
