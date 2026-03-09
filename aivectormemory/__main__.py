import argparse
import io
import sys


def _ensure_utf8_stdio():
    """确保 stdin/stdout 使用 UTF-8 编码（Windows pipe 默认可能是 GBK/CP936）"""
    stdin_enc = (sys.stdin.encoding or "").lower().replace("-", "")
    stdout_enc = (sys.stdout.encoding or "").lower().replace("-", "")
    stderr_enc = (sys.stderr.encoding or "").lower().replace("-", "")
    if stdin_enc != "utf8":
        sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
    if stdout_enc != "utf8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if stderr_enc != "utf8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


def main():
    _ensure_utf8_stdio()
    parser = argparse.ArgumentParser(prog="run", description="AIVectorMemory MCP Server")
    parser.add_argument("--project-dir", default=None, help="项目根目录，默认当前目录")
    sub = parser.add_subparsers(dest="command")

    web_parser = sub.add_parser("web", help="启动 Web 看板")
    web_parser.add_argument("--port", type=int, default=9080, help="Web 看板端口")
    web_parser.add_argument("--bind", default="127.0.0.1", help="绑定地址，默认 127.0.0.1")
    web_parser.add_argument("--token", default=None, help="API 保护 token，启用后所有 API 请求需带 X-AVM-Server-Token 请求头")
    web_parser.add_argument("--quiet", action="store_true", default=False, help="屏蔽请求日志")
    web_parser.add_argument("--daemon", action="store_true", default=False, help="后台运行（macOS/Linux）")
    web_parser.add_argument("--allow-insecure-public-bind", action="store_true", default=False, help="允许无 token 绑定非回环地址（不安全）")
    web_parser.add_argument("--project-dir", dest="web_project_dir", default=None)

    install_parser = sub.add_parser("install", help="为当前项目配置 MCP")
    install_parser.add_argument("--project-dir", dest="install_project_dir", default=None)

    regen_parser = sub.add_parser("regenerate", help="切换语言并重新生成所有项目的规则文件")
    regen_parser.add_argument("--lang", required=True, help="目标语言 (zh-CN/zh-TW/en/es/de/fr/ja)")

    doctor_parser = sub.add_parser("doctor", help="运行环境自检")
    doctor_sub = doctor_parser.add_subparsers(dest="doctor_command")
    doctor_codex = doctor_sub.add_parser("codex", help="检查 Codex CLI MCP 配置与连通性")
    doctor_codex.add_argument("--server-name", default="aivectormemory", help="MCP 服务名，默认 aivectormemory")
    doctor_codex.add_argument("--no-probe", action="store_true", default=False, help="仅检查 codex 配置，不做 stdio 探针")
    doctor_codex.add_argument("--timeout", type=int, default=25, help="子进程超时秒数，默认 25")
    doctor_codex.add_argument("--json", action="store_true", default=False, help="输出 JSON 报告")

    migrate_parser = sub.add_parser("migrate-project", help="迁移项目目录（重命名场景）对应的分区数据")
    migrate_parser.add_argument("--from", dest="from_dir", required=True, help="旧项目目录")
    migrate_parser.add_argument("--to", dest="to_dir", required=True, help="新项目目录")
    migrate_parser.add_argument("--dry-run", action="store_true", default=False, help="演练模式，不落库")
    migrate_parser.add_argument("--no-backup", action="store_true", default=False, help="跳过自动备份（非 dry-run 时默认备份）")
    migrate_parser.add_argument("--json", action="store_true", default=False, help="输出 JSON 报告")

    args = parser.parse_args()

    if args.command == "web":
        project_dir = args.web_project_dir or args.project_dir
        from aivectormemory.web.app import run_web
        run_web(
            project_dir=project_dir,
            port=args.port,
            bind=args.bind,
            token=args.token,
            quiet=args.quiet,
            daemon=args.daemon,
            allow_insecure_public_bind=args.allow_insecure_public_bind,
        )
    elif args.command == "install":
        project_dir = args.install_project_dir or args.project_dir
        from aivectormemory.install import run_install
        run_install(project_dir)
    elif args.command == "regenerate":
        from aivectormemory.regenerate import run_regenerate
        run_regenerate(args.lang)
    elif args.command == "doctor":
        if args.doctor_command == "codex":
            from aivectormemory.doctor import run_doctor_codex
            rc = run_doctor_codex(
                server_name=args.server_name,
                no_probe=args.no_probe,
                timeout_sec=args.timeout,
                json_output=args.json,
            )
            raise SystemExit(rc)
        parser.error("doctor 需要子命令，例如：doctor codex")
    elif args.command == "migrate-project":
        from aivectormemory.project_migration import run_migrate_project
        rc = run_migrate_project(
            source_dir=args.from_dir,
            target_dir=args.to_dir,
            dry_run=args.dry_run,
            no_backup=args.no_backup,
            json_output=args.json,
        )
        raise SystemExit(rc)
    else:
        from aivectormemory.server import run_server
        run_server(project_dir=args.project_dir)


if __name__ == "__main__":
    main()
