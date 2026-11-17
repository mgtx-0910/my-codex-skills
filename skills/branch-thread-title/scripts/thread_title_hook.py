"""Inject the fixed-prefix, latest-task thread naming rule on user prompts."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
STATE_DIR = CODEX_HOME / "thread-title-state"
STATE_DB = CODEX_HOME / "state_5.sqlite"
LOG_PATH = CODEX_HOME / "hooks" / "thread-title-hook.log"
SESSION_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")


def emit(additional_context: str | None = None) -> None:
    # UserPromptSubmit only needs hookSpecificOutput. Unsupported generic
    # fields such as suppressOutput can make the hook response be treated as
    # failed before additionalContext reaches the model.
    result: dict[str, Any] = {}
    if additional_context:
        result["hookSpecificOutput"] = {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": additional_context,
        }
    # ASCII-only output avoids Windows console code-page conversion before
    # Codex parses the hook response.
    print(json.dumps(result, ensure_ascii=True))


def log(message: str) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as stream:
            stream.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}\n")
    except OSError:
        pass


def read_thread_row(session_id: str) -> dict[str, Any]:
    if not STATE_DB.exists():
        return {}

    try:
        uri = f"file:{STATE_DB.as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=0.75) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "select id, title, git_branch, rollout_path, first_user_message, "
                "created_at, updated_at from threads where id = ?",
                (session_id,),
            ).fetchone()
            return dict(row) if row else {}
    except (OSError, sqlite3.Error):
        return {}


def current_branch(cwd: str) -> str:
    if not cwd:
        return ""
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "branch", "--show-current"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def session_history(rollout_path: str, session_id: str) -> tuple[str, str]:
    """Return the first and latest confirmed titles for this thread."""
    path = Path(rollout_path) if rollout_path else None
    if not path or not path.exists():
        return "", ""
    title_calls: set[str] = set()
    titles: list[str] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = event.get("payload") or {}
                if event.get("type") != "response_item":
                    continue
                if payload.get("type") == "function_call" and payload.get("name") == "set_thread_title":
                    title_calls.add(str(payload.get("call_id") or ""))
                elif payload.get("type") == "function_call_output" and str(payload.get("call_id") or "") in title_calls:
                    output = payload.get("output")
                    for part in output if isinstance(output, list) else [output]:
                        text = part.get("text", "") if isinstance(part, dict) else part
                        if not isinstance(text, str):
                            continue
                        try:
                            result = json.loads(text)
                        except (json.JSONDecodeError, TypeError):
                            continue
                        if isinstance(result, dict) and result.get("threadId") == session_id:
                            title = result.get("title")
                            if isinstance(title, str) and title.strip():
                                titles.append(title.strip())
    except OSError:
        pass
    return (titles[0], titles[-1]) if titles else ("", "")


def latest_index_title(session_id: str) -> str:
    """Read the desktop's append-only title index; the threads table can be stale."""
    title = ""
    try:
        with (CODEX_HOME / "session_index.jsonl").open("r", encoding="utf-8", errors="replace") as stream:
            for line in stream:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict) and item.get("id") == session_id and isinstance(item.get("thread_name"), str):
                    title = item["thread_name"].strip()
    except OSError:
        pass
    return title


def state_path(session_id: str) -> Path:
    safe_id = SESSION_ID_RE.sub("_", session_id).strip(".") or "unknown"
    return STATE_DIR / f"{safe_id}.json"


def load_state(session_id: str) -> dict[str, Any]:
    try:
        with state_path(session_id).open("r", encoding="utf-8") as stream:
            value = json.load(stream)
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(session_id: str, value: dict[str, Any]) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        target = state_path(session_id)
        temporary = target.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=True, indent=2)
            stream.write("\n")
        temporary.replace(target)
    except OSError:
        pass


def expected_prefix(branch: str) -> str:
    return f"{branch} | " if branch else ""


def is_placeholder_title(title: str, branch: str) -> bool:
    normalized = title.strip().strip("`").replace(" ", "")
    placeholders = {
        "简短任务名",
        "首次分支|简短任务名",
        "首次取分支|简短任务名",
        "分支名|简短任务名",
    }
    if normalized in placeholders:
        return True
    return bool(branch) and normalized == f"{branch}|简短任务名"


def extract_task_request(prompt: str) -> str:
    """Keep only the user's request for the model's title synthesis."""

    value = prompt.strip()
    for marker in ("## My request:", "My request:"):
        if marker in value:
            value = value.split(marker, 1)[1]
            break

    for marker in ("\n<environment_context>", "\n# environment_context", "\nenvironment_context"):
        if marker in value:
            value = value.split(marker, 1)[0]

    value = re.sub(r"\s+", " ", value).strip()
    return value[:1600]


def is_explicit_manual_rename(prompt: str) -> bool:
    normalized = re.sub(r"\s+", "", prompt.lower()).replace("'", "").replace("’", "")
    markers = (
        "不要改名",
        "别改名",
        "不改名",
        "不要自动命名",
        "不要自动改名",
        "保持标题",
        "保持当前标题",
        "保持会话标题",
        "保持任务标题",
        "会话标题改为",
        "任务标题改为",
        "重命名会话为",
        "重命名任务为",
        "renamethreadas",
        "renamechatas",
        "dontrename",
        "keepthistitle",
        "keepcurrenttitle",
    )
    return any(marker in normalized for marker in markers)


def naming_context(branch: str, first_prompt: str, first_title: str, task_request: str, current_title: str) -> str:
    first_summary = first_title.split(" | ", 1)[0].strip() if first_title else ""
    fixed = branch or first_summary
    prefix_line = f"固定前缀：`{fixed}`，必须原样使用。" if fixed else (
        "当前会话首次没有分支，固定前缀尚未生成。请从以下首次任务提炼简洁中文摘要作为固定前缀："
        f"`{extract_task_request(first_prompt) or '根据首次用户消息提炼'}`。"
        "第一次命名时，前缀和最新任务摘要可以相同。"
    )
    current_line = f"当前标题：`{current_title}`。" if current_title else "当前标题不可确认。"
    return f"""
【会话标题：固定前缀 + 最新任务】
先根据以下规则判断标题是否需要更新，再继续工作。
- {current_line}
- 首次尚未形成符合规则的标题时，调用 Codex 应用的 `set_thread_title` 设置标题。
- 已有符合规则的标题时，仅在用户明确切换到明显不同的任务，且需要修改右侧摘要时，调用 `set_thread_title`。闲聊、问候、感谢，以及同一任务的补充、纠正、确认、进度询问和相关追问都保留现有标题，不调用标题工具。无法确定是否切换任务时，保留现有标题。
- 即使判断需要更新，也先将生成的完整标题与当前标题比较；完全相同则跳过调用。
- {prefix_line}
- 标题严格使用 `固定前缀 | 最新任务摘要`，其中分隔符是空格、竖线、空格。首次分支优先作为固定前缀；无分支时使用首次任务摘要。固定前缀在整个会话中不随切换分支或后续任务变化。
- 右侧概括当前任务，用户明显切换任务时更新；保持简洁，中文优先使用动宾短语。结合当前对话理解 `最新用户消息`，不要复制整段消息、路径或附件包装。
- 最新用户消息：`{task_request or '根据当前用户消息和上下文提炼'}`。
- title 必须是已经填入真实内容的最终标题，不可包含占位词。若用户明确要求保留标题或指定标题，遵从用户要求。
""".strip()


def main() -> None:
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        emit()
        return
    if not isinstance(payload, dict):
        emit()
        return
    event_name = payload.get("hook_event_name") or payload.get("event")
    if event_name and event_name != "UserPromptSubmit":
        emit()
        return
    session_id = str(payload.get("session_id") or payload.get("thread_id") or "").strip()
    prompt = str(payload.get("prompt") or "").strip()
    cwd = str(payload.get("cwd") or "").strip()
    if not session_id or not prompt:
        emit()
        return
    state = load_state(session_id)
    if is_explicit_manual_rename(prompt):
        state.update({"session_id": session_id, "status": "manual"})
        save_state(session_id, state)
        emit()
        return
    if state.get("status") == "manual":
        emit()
        return
    row = read_thread_row(session_id)
    if "first_branch" not in state:
        state["first_branch"] = str(row.get("git_branch") or current_branch(cwd)).strip()
    if not state.get("first_prompt"):
        state["first_prompt"] = str(row.get("first_user_message") or prompt)[:4000]
    state.setdefault("session_id", session_id)
    state.setdefault("created_at", time.time())
    first_title, latest_title = session_history(str(row.get("rollout_path") or ""), session_id)
    index_title = latest_index_title(session_id)
    previously_seen = str(state.get("last_index_title") or "")
    if latest_title and index_title and previously_seen and index_title != previously_seen and index_title != latest_title:
        state.update({"status": "manual", "last_index_title": index_title})
        save_state(session_id, state)
        log(f"session={session_id} preserving manual title change")
        emit()
        return
    if index_title:
        state["last_index_title"] = index_title
    state["status"] = "active"
    save_state(session_id, state)
    log(f"session={session_id} checking task title branch={state['first_branch']!r}")
    emit(naming_context(str(state["first_branch"]), str(state["first_prompt"]), first_title, extract_task_request(prompt), index_title or latest_title))


if __name__ == "__main__":
    main()
