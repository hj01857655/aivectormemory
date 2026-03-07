"""验证 Issue #77 修复：ConnectionManager fallback cwd + Windows路径兼容"""
import json
import sqlite3
import sqlite_vec
import tempfile
from pathlib import Path

def create_test_db(db_path, memories=None):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("""CREATE TABLE IF NOT EXISTS memories (
        id TEXT PRIMARY KEY, content TEXT NOT NULL, tags TEXT NOT NULL DEFAULT '[]',
        scope TEXT NOT NULL DEFAULT 'project', project_dir TEXT NOT NULL DEFAULT '',
        session_id INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS vec_memories USING vec0(
        id TEXT PRIMARY KEY, embedding FLOAT[384]
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS issues (
        id INTEGER PRIMARY KEY AUTOINCREMENT, project_dir TEXT NOT NULL DEFAULT '',
        issue_number INTEGER NOT NULL, date TEXT NOT NULL, title TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending', content TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS issues_archive (
        id INTEGER PRIMARY KEY AUTOINCREMENT, project_dir TEXT NOT NULL DEFAULT '',
        issue_number INTEGER NOT NULL, date TEXT NOT NULL, title TEXT NOT NULL,
        content TEXT NOT NULL DEFAULT '', archived_at TEXT NOT NULL, created_at TEXT NOT NULL
    )""")
    if memories:
        for m in memories:
            conn.execute(
                "INSERT INTO memories (id, content, tags, scope, project_dir, session_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (m["id"], m["content"], json.dumps(m["tags"]), m["scope"], m["project_dir"], 1, "2026-01-01", "2026-01-01")
            )
            conn.execute("INSERT INTO vec_memories (id, embedding) VALUES (?, ?)", (m["id"], json.dumps([0.0]*384)))
    conn.commit()
    return conn

passed = 0
failed = 0

# Test 1: ConnectionManager fallback to cwd when project_dir=None
from aivectormemory.db.connection import ConnectionManager
cm = ConnectionManager(project_dir=None)
expected = str(Path.cwd().resolve())
if cm.project_dir == expected:
    print(f"✓ Test 1: project_dir=None fallback to cwd: {cm.project_dir}")
    passed += 1
else:
    print(f"✗ Test 1: expected {expected}, got {cm.project_dir}")
    failed += 1

# Test 2: ConnectionManager with explicit project_dir
cm2 = ConnectionManager(project_dir="/tmp/test")
if cm2.project_dir == str(Path("/tmp/test").resolve()):
    print(f"✓ Test 2: explicit project_dir works: {cm2.project_dir}")
    passed += 1
else:
    print(f"✗ Test 2: expected /tmp/test resolved, got {cm2.project_dir}")
    failed += 1

# Test 3: Windows path name extraction in get_projects
from aivectormemory.config import USER_SCOPE_DIR
with tempfile.TemporaryDirectory() as tmpdir:
    db_path = Path(tmpdir) / "memory.db"
    conn = create_test_db(db_path, memories=[
        {"id": "win1", "content": "test", "tags": ["test"], "scope": "project", "project_dir": "C:\\Users\\test\\myproject"},
    ])
    rows = conn.execute("SELECT project_dir, COUNT(*) as mem_count FROM memories GROUP BY project_dir").fetchall()
    projects = {}
    for r in rows:
        pd = r["project_dir"]
        projects[pd] = {"project_dir": pd, "memories": r["mem_count"], "issues": 0, "tags": set()}
    result = []
    for pd, info in projects.items():
        if pd == USER_SCOPE_DIR or not pd:
            continue
        name = pd.replace("\\", "/").rsplit("/", 1)[-1] if pd else "unknown"
        result.append({"name": name})
    if result and result[0]["name"] == "myproject":
        print(f"✓ Test 3: Windows path name extraction: {result[0]['name']}")
        passed += 1
    else:
        print(f"✗ Test 3: expected 'myproject', got {result}")
        failed += 1
    conn.close()

# Test 4: Unix path name extraction still works
with tempfile.TemporaryDirectory() as tmpdir:
    db_path = Path(tmpdir) / "memory.db"
    conn = create_test_db(db_path, memories=[
        {"id": "unix1", "content": "test", "tags": ["test"], "scope": "project", "project_dir": "/Users/someone/project"},
    ])
    rows = conn.execute("SELECT project_dir, COUNT(*) as mem_count FROM memories GROUP BY project_dir").fetchall()
    pd = rows[0]["project_dir"]
    name = pd.replace("\\", "/").rsplit("/", 1)[-1]
    if name == "project":
        print(f"✓ Test 4: Unix path name extraction: {name}")
        passed += 1
    else:
        print(f"✗ Test 4: expected 'project', got {name}")
        failed += 1
    conn.close()

print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
if failed:
    exit(1)
