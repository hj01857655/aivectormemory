"""Local authentication routes for web dashboard."""
import hashlib
import hmac
import os
import re
import time
from datetime import datetime

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
SESSION_TTL_SECONDS = 12 * 60 * 60
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 5 * 60
RATE_WINDOW_SECONDS = 10 * 60


def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, bytes]:
    if salt is None:
        salt = os.urandom(32)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return (salt + h).hex(), salt


def _verify_password(password: str, stored_hex: str) -> bool:
    raw = bytes.fromhex(stored_hex)
    salt, stored_hash = raw[:32], raw[32:]
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return hmac.compare_digest(h, stored_hash)


def _generate_token() -> str:
    return os.urandom(32).hex()


def _validate_password_strength(password: str) -> str | None:
    if len(password) < 12:
        return "password must be at least 12 characters"
    if not any(ch.islower() for ch in password):
        return "password must contain a lowercase letter"
    if not any(ch.isupper() for ch in password):
        return "password must contain an uppercase letter"
    if not any(ch.isdigit() for ch in password):
        return "password must contain a digit"
    if not any(not ch.isalnum() for ch in password):
        return "password must contain a symbol"
    return None


def _client_ip(handler) -> str:
    try:
        return handler.client_address[0] or "unknown"
    except Exception:
        return "unknown"


def _login_key(username: str, ip: str) -> str:
    return f"{ip}:{username.lower()}"


def _prune_auth_state(conn, now_ts: float):
    conn.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (now_ts,))
    conn.execute(
        """
        DELETE FROM auth_login_limits
        WHERE lock_until < ? AND (? - window_start) > ?
        """,
        (now_ts, now_ts, RATE_WINDOW_SECONDS),
    )


def _is_locked(conn, key: str, now_ts: float) -> int:
    row = conn.execute(
        "SELECT lock_until FROM auth_login_limits WHERE login_key = ?",
        (key,),
    ).fetchone()
    if not row:
        return 0
    lock_until = int(row["lock_until"])
    if lock_until > now_ts:
        return lock_until - int(now_ts)
    return 0


def _record_failed_login(conn, key: str, now_ts: float):
    row = conn.execute(
        """
        SELECT window_start, attempt_count
        FROM auth_login_limits
        WHERE login_key = ?
        """,
        (key,),
    ).fetchone()
    if not row or (now_ts - float(row["window_start"])) > RATE_WINDOW_SECONDS:
        window_start = now_ts
        attempt_count = 0
    else:
        window_start = float(row["window_start"])
        attempt_count = int(row["attempt_count"])
    attempt_count += 1
    lock_until = int(now_ts + LOCKOUT_SECONDS) if attempt_count >= MAX_LOGIN_ATTEMPTS else 0
    conn.execute(
        """
        INSERT INTO auth_login_limits (login_key, window_start, attempt_count, lock_until, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(login_key) DO UPDATE SET
            window_start = excluded.window_start,
            attempt_count = excluded.attempt_count,
            lock_until = excluded.lock_until,
            updated_at = excluded.updated_at
        """,
        (key, window_start, attempt_count, lock_until, now_ts),
    )


def _clear_failed_login(conn, key: str):
    conn.execute("DELETE FROM auth_login_limits WHERE login_key = ?", (key,))


def register(handler, cm, read_body):
    body = read_body(handler)
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    if not username or not password:
        return {"error": "username and password required"}
    if not USERNAME_RE.fullmatch(username):
        return {"error": "username must be 3-32 chars: letters, numbers, ., _, -"}
    password_error = _validate_password_strength(password)
    if password_error:
        return {"error": password_error}

    conn = cm.conn
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        return {"error": "username already exists"}

    pw_hash, _ = _hash_password(password)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, pw_hash, now),
    )
    conn.commit()
    return {"success": True}


def login(handler, cm, read_body):
    body = read_body(handler)
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    if not username or not password:
        return {"error": "username and password required"}

    conn = cm.conn
    now_ts = time.time()
    _prune_auth_state(conn, now_ts)
    login_key = _login_key(username, _client_ip(handler))
    retry_after = _is_locked(conn, login_key, now_ts)
    if retry_after > 0:
        return {"error": f"too many attempts, retry in {retry_after}s"}

    row = conn.execute(
        "SELECT id, password_hash FROM users WHERE username = ?", (username,)
    ).fetchone()

    if not row or not _verify_password(password, row[1]):
        _record_failed_login(conn, login_key, now_ts)
        conn.commit()
        return {"error": "invalid username or password"}

    _clear_failed_login(conn, login_key)
    token = _generate_token()
    conn.execute(
        """
        INSERT INTO auth_sessions (token, username, created_at, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (token, username, now_ts, now_ts + SESSION_TTL_SECONDS),
    )

    conn.execute(
        "UPDATE users SET last_login = ? WHERE id = ?",
        (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), row[0]),
    )
    conn.commit()

    return {"token": token, "username": username, "expires_in": SESSION_TTL_SECONDS}


def logout(handler, cm):
    token = getattr(handler, "auth_session_token", None)
    if token:
        cm.conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
        cm.conn.commit()
    return {"success": True}


def verify_token(token: str, conn) -> str | None:
    """Return username if token is valid, else None."""
    now_ts = time.time()
    row = conn.execute(
        "SELECT username, expires_at FROM auth_sessions WHERE token = ?",
        (token,),
    ).fetchone()
    if not row:
        return None
    expires_at = float(row["expires_at"])
    if expires_at <= now_ts:
        conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
        conn.commit()
        return None
    return row["username"]


def get_current_user(handler):
    username = getattr(handler, "auth_username", None)
    if not username:
        return {"error": "invalid token"}
    return {"username": username}


def change_password(handler, cm, read_body):
    body = read_body(handler)
    current_pw = body.get("current_password") or ""
    new_pw = body.get("new_password") or ""

    username = getattr(handler, "auth_username", None)
    if not username:
        return {"error": "invalid token"}
    if not current_pw or not new_pw:
        return {"error": "current and new password required"}
    password_error = _validate_password_strength(new_pw)
    if password_error:
        return {"error": password_error}

    conn = cm.conn
    row = conn.execute(
        "SELECT id, password_hash FROM users WHERE username = ?", (username,)
    ).fetchone()
    if not row or not _verify_password(current_pw, row[1]):
        return {"error": "current password is incorrect"}

    pw_hash, _ = _hash_password(new_pw)
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, row[0]))
    # 密码变更后，吊销该用户所有已签发会话，避免旧 token 继续可用。
    conn.execute("DELETE FROM auth_sessions WHERE username = ?", (username,))
    conn.commit()
    return {"success": True}
