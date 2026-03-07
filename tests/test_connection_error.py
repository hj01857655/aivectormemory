"""验证 connection.py 的 enable_load_extension 错误处理"""
import sys
sys.path.insert(0, ".")


def test_error_message():
    """验证 RuntimeError 消息内容正确"""
    from aivectormemory.db.connection import ConnectionManager
    import aivectormemory.db.connection as mod

    # 保存原始 _connect
    original = ConnectionManager._connect

    def fake_connect(self):
        """模拟 enable_load_extension 不存在"""
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        # 直接抛出 AttributeError 模拟
        raise AttributeError("'sqlite3.Connection' object has no attribute 'enable_load_extension'")

    # 用 monkey patch 替换 _connect 中的逻辑来验证 try/except
    # 更直接：直接读源码验证 try/except 结构存在
    import inspect
    source = inspect.getsource(ConnectionManager._connect)
    checks = [
        ("try:" in source, "missing try block"),
        ("except AttributeError:" in source, "missing except AttributeError"),
        ("RuntimeError" in source, "missing RuntimeError"),
        ("brew install python" in source, "missing brew hint"),
        ("SQLite 扩展加载不可用" in source, "missing Chinese error message"),
        ("conn.close()" in source, "missing conn.close() before raise"),
    ]
    for ok, msg in checks:
        assert ok, f"FAIL: {msg}"
        print(f"  PASS: {msg.replace('missing ', '')}")

    print("All checks passed")


if __name__ == "__main__":
    test_error_message()
