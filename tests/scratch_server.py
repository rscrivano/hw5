"""Start the desk API against a SCRATCH copy of the database and audit trail (for testing).

Leaves data/campus_customs_new.db and output/audit_trail.json untouched.
    .venv\Scripts\python.exe tests\scratch_server.py [port]
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
scratch = Path(tempfile.gettempdir()) / "campus_customs_scratch"
scratch.mkdir(exist_ok=True)
db = scratch / "campus_customs_new.db"
if not db.exists():
    sys.path.insert(0, str(ROOT))
    os.environ["CC_WORKING_DB"] = str(db)
    from mcp_server.shop_db import reset_database
    reset_database()
env = {**os.environ, "CC_WORKING_DB": str(db), "CC_AUDIT_TRAIL": str(scratch / "audit_trail.json")}
port = sys.argv[1] if len(sys.argv) > 1 else "8001"
print(f"scratch DB: {db}", flush=True)
sys.exit(subprocess.call([sys.executable, "-m", "uvicorn", "main:app", "--port", port],
                         cwd=ROOT / "backend", env=env))
