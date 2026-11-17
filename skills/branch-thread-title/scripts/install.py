"""Install or inspect the branch-thread-title UserPromptSubmit hook."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import sys
import tempfile
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SOURCE = SKILL_DIR / "scripts" / "thread_title_hook.py"
HOME = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser().resolve()
DEST = HOME / "hooks" / "branch-thread-title.py"
CONFIG = HOME / "hooks.json"
MARKERS = ("branch-thread-title.py", "thread-title-hook.py", "thread_title_hook.py")


def command_arg(path: Path) -> str:
    value = str(path.resolve())
    if os.name == "nt":
        # The hook runner executes a command string. Reject shell syntax that
        # cannot be represented safely across Windows command interpreters.
        value = value.replace("\\", "/")
        if any(c in value for c in '\"%&|<>^!`$\r\n'):
            raise ValueError("Python 或 Codex 路径含有不支持的命令特殊字符")
        return f'"{value}"'
    return shlex.quote(value)


def read_config() -> dict:
    if not CONFIG.exists():
        return {}
    data = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("hooks.json 顶层必须是 JSON 对象")
    return data


def find_matches(config: dict) -> list[str]:
    hooks = config.get("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("hooks.json 的 hooks 必须是对象")
    groups = hooks.get("UserPromptSubmit", [])
    if not isinstance(groups, list):
        raise ValueError("UserPromptSubmit 必须是数组")
    matches = []
    for group in groups:
        if not isinstance(group, dict):
            raise ValueError("UserPromptSubmit 配置项必须是对象")
        commands = group.get("hooks", [])
        if not isinstance(commands, list):
            raise ValueError("钩子组的 hooks 必须是数组")
        for entry in commands:
            if not isinstance(entry, dict):
                raise ValueError("钩子配置项必须是对象")
            command = entry.get("command", "")
            if isinstance(command, str) and any(m in command.lower() for m in MARKERS):
                matches.append(command)
    return matches


def atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description="安装或检查会话标题钩子")
    parser.add_argument("action", choices=("install", "check"))
    args = parser.parse_args()
    try:
        if sys.version_info < (3, 10):
            raise ValueError("需要 Python 3.10 或更高版本")
        config = read_config()
        matches = find_matches(config)
        expected = f"{command_arg(Path(sys.executable))} {command_arg(DEST)}"
        if matches:
            # Do not rewrite another installation or duplicate it. Its runtime
            # and trust approval may be managed independently.
            if len(matches) == 1 and matches[0] == expected and DEST.exists():
                if digest(DEST) == digest(SOURCE):
                    print("已安装，脚本与技能包一致；钩子信任状态请在 Codex 中核实。")
                    return 0
                print("已注册但脚本与技能包不同；为保留现有安装未覆盖，请先检查差异。")
                return 1
            print("检测到已有标题钩子，未添加重复配置，也未覆盖现有脚本：")
            for match in matches:
                print("  " + match)
            return 1
        if args.action == "check":
            print("尚未注册标题钩子。")
            return 1
        if DEST.exists() and digest(DEST) != digest(SOURCE):
            raise ValueError(f"目标脚本已存在且内容不同：{DEST}；为避免覆盖已停止")
        hooks = config.setdefault("hooks", {})
        groups = hooks.setdefault("UserPromptSubmit", [])
        groups.append({"hooks": [{"type": "command", "command": expected, "timeout": 10}]})
        encoded = (json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if CONFIG.exists():
            stamp = time.strftime("%Y%m%d-%H%M%S")
            backup = CONFIG.with_name(f"hooks.json.branch-thread-title.{stamp}.bak")
            if backup.exists():
                raise ValueError(f"备份文件已存在：{backup}")
            shutil.copy2(CONFIG, backup)
            print(f"已备份原配置：{backup}")
        atomic_bytes(DEST, SOURCE.read_bytes())
        atomic_bytes(CONFIG, encoded)
        print(f"已安装脚本：{DEST}")
        print(f"已合并配置：{CONFIG}")
        print("请在 Codex 中检查并信任新增钩子；若当前会话未加载配置，请重新打开会话或重启 Codex 后验证。")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"安装或检查未完成：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
