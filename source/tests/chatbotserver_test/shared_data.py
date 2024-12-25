# shared_data.py
import sqlite3
from threading import RLock

# A lock for concurrency control on DB writes
db_lock = RLock()

# Create a shared connection to the database in WAL mode for better concurrency
db_connection = sqlite3.connect("checkpoints.db", check_same_thread=False)
db_connection.execute("PRAGMA journal_mode=WAL;")
db_connection.commit()
