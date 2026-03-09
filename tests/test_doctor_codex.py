from aivectormemory.doctor import evaluate_codex_transport


def _find(checks, name: str):
    for c in checks:
        if c.name == name:
            return c
    raise AssertionError(f"missing check: {name}")


def test_evaluate_codex_transport_uvx_dynamic_ok():
    checks = evaluate_codex_transport(
        {
            "type": "stdio",
            "command": "uvx",
            "args": [
                "-q",
                "--no-progress",
                "--from",
                "aivectormemory@latest",
                "run",
                "--project-dir",
                ".",
            ],
        }
    )
    assert _find(checks, "transport.command").status == "pass"
    assert _find(checks, "uvx.quiet").status == "pass"
    assert _find(checks, "uvx.from").status == "pass"
    assert _find(checks, "project_dir.value").status == "pass"


def test_evaluate_codex_transport_fixed_project_dir_warns():
    checks = evaluate_codex_transport(
        {
            "type": "stdio",
            "command": "run",
            "args": ["--project-dir", r"E:\VSCodeSpace\aivectormemory"],
        }
    )
    assert _find(checks, "transport.command").status == "warn"
    assert _find(checks, "project_dir.value").status == "warn"


def test_evaluate_codex_transport_missing_project_dir_fails():
    checks = evaluate_codex_transport({"type": "stdio", "command": "uvx", "args": ["run"]})
    assert _find(checks, "project_dir.arg").status == "fail"

