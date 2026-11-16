import base64
import json
import subprocess
import sys
from pathlib import Path

import pytest
from guards import evaluate

GUARD = Path(__file__).resolve().parent.parent / "plugins" / "linden" / "hooks" / "guard.py"


def encoded(script: str) -> str:
    return base64.b64encode(script.encode("utf-16-le")).decode()


DENY = [
    "rm -rf build",
    "rm -r -f build",
    "rm --recursive build",
    "cd src && rm -rf ../build",
    "rm \\\n  -rf build",
    "/bin/rm -rf build",
    "Remove-Item -Recurse -Force C:\\tmp\\x",
    "Remove-Item C:\\tmp\\x -r",
    "ri x -Recurse:$true",
    "rd /s /q build",
    "rmdir /s/q build",
    "find . -name '*.o' -delete",
    "find . -type d -exec rm -r {} +",
    "find . -name x | xargs rm -r",
    "git clean -fdx",
    "git rm -r src",
    "python -c \"import shutil; shutil.rmtree('build')\"",
    "node -e \"fs.rmSync('x', { recursive: true })\"",
    "robocopy empty target /MIR",
    "rsync -a --delete src/ dst/",
    "Clear-RecycleBin -Force",
    "gio trash --empty",
    "trash-empty",
    "rm ~/.local/share/Trash/files/x",
    "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory('C:\\x', 'DeleteAllContents')",
    "[System.IO.Directory]::Delete('C:\\x', $true)",
    f"pwsh -NoProfile -EncodedCommand {encoded('Remove-Item -Recurse C:/x')}",
    'git commit -m "Fix\n\nCo-Authored-By: Claude <noreply@anthropic.com>"',
    'git commit --trailer "Co-authored-by=Someone <a@b.c>" -m x',
    'gh pr create --title x --body "Co-authored-by: Claude"',
    "git reset --hard && rm -rf build",  # the most severe verdict wins
]

ASK = [
    "git reset --hard HEAD~1",
    "git push --force",
    "git push -f origin main",
    "git push --force-with-lease",
    "git push origin +main",
    "git push origin :old-branch",
    "git push origin --delete old-branch",
    "git clean -f",
    "git checkout -- .",
    "git checkout .",
    "git checkout -f main",
    "git restore .",
    "git restore --worktree --staged .",
    "git branch -D feature",
    "git branch --delete --force feature",
    "git stash clear",
    "git stash drop",
    "psql -c 'DROP TABLE users'",
    "sqlite3 db 'truncate table events'",
]

ALLOW = [
    "rm file.txt",
    "rm -f file.txt",
    "git rm --cached -r src",
    "git rm file.txt",
    "git clean -n -d",
    "git clean -fdn",
    "Remove-Item C:\\tmp\\file.txt",
    "Remove-Item -Recurse:$false C:\\tmp\\x",
    "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory('C:\\x', 'OnlyErrorDialogs', 'SendToRecycleBin')",
    "gio trash /home/me/scratch",
    "ls -R",
    "git commit -m 'Fix the parser'",
    "git checkout main",
    "git checkout -b feature",
    "git restore --staged .",
    "git restore src/app.py",
    "git push origin main",
    "git push -u origin feature",
    "git branch -d merged-feature",
    "git stash pop",
    "git reset --soft HEAD~1",
    "echo 'co-authored-by: is a trailer name'",
    "grep -ri 'drop table' docs/",
]


@pytest.mark.parametrize("command", DENY)
def test_denied(command):
    decision = evaluate(command)
    assert decision is not None and decision.verdict == "deny", decision


@pytest.mark.parametrize("command", ASK)
def test_asked(command):
    decision = evaluate(command)
    assert decision is not None and decision.verdict == "ask", decision


@pytest.mark.parametrize("command", ALLOW)
def test_allowed(command):
    assert evaluate(command) is None


def test_commit_message_file_is_read(tmp_path):
    (tmp_path / "msg.txt").write_text("Fix\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n", encoding="utf-8")
    (tmp_path / "clean.txt").write_text("Fix\n", encoding="utf-8")
    assert evaluate("git commit -F msg.txt", cwd=str(tmp_path)).verdict == "deny"
    assert evaluate("git commit -F clean.txt", cwd=str(tmp_path)) is None


def run_hook(payload: dict) -> str:
    result = subprocess.run(
        [sys.executable, str(GUARD)], input=json.dumps(payload), capture_output=True, text=True, check=True
    )
    return result.stdout


def test_hook_prints_decision():
    out = json.loads(run_hook({"tool_name": "Bash", "tool_input": {"command": "rm -rf x"}, "cwd": "."}))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"


def test_hook_is_silent_when_allowed_or_not_a_command():
    assert run_hook({"tool_name": "Bash", "tool_input": {"command": "ls"}}) == ""
    assert run_hook({"tool_name": "Read", "tool_input": {"file_path": "x"}}) == ""
