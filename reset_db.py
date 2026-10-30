"""Reset the working database: copies data/campus_customs.db -> data/campus_customs_new.db.

Run this before every full ticket run:  python reset_db.py
The original campus_customs.db is never modified.
"""
from mcp_server.shop_db import reset_database

if __name__ == "__main__":
    print(reset_database())
