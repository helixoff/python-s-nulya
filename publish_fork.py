#!/usr/bin/env python3
"""Создать настоящий GitHub-форк и отправить в него готовую книгу.

Запускается владельцем на компьютере с рабочими Git и GitHub CLI.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
UPSTREAM = "Asabeneh/30-Days-Of-Python"
FORK_NAME = "30-Days-Of-Python-RU"


def call(arguments, cwd=None, capture=False):
    result = subprocess.run(arguments, cwd=cwd, text=True, encoding="utf-8",
                            stdout=subprocess.PIPE if capture else None, check=True, timeout=180)
    return result.stdout.strip() if capture else ""


def main():
    if not shutil.which("gh") or not shutil.which("git"):
        raise RuntimeError("Установи Git и GitHub CLI, затем войди через gh auth login.")
    call(["gh", "auth", "status"])
    user = call(["gh", "api", "user", "--jq", ".login"], capture=True)
    target = f"{user}/{FORK_NAME}"
    checkout = ROOT.parent / f"{FORK_NAME}-checkout"
    if checkout.exists():
        raise RuntimeError(f"Папка уже существует: {checkout}. Она оставлена без изменений; выбери новое место для книги или переименуй эту папку.")
    print(f"Создаём форк {UPSTREAM} → {target}")
    # gh repo fork повторно использует уже существующий форк. Проверяем родителя ниже.
    call(["gh", "repo", "fork", UPSTREAM, "--fork-name", FORK_NAME, "--clone=false"])
    metadata = json.loads(call(["gh", "api", f"repos/{target}"], capture=True))
    if not metadata.get("fork") or metadata.get("parent", {}).get("full_name", "").lower() != UPSTREAM.lower():
        raise RuntimeError("Целевой репозиторий не является форком исходного курса. Отправка отменена.")
    call(["gh", "repo", "clone", target, str(checkout), "--", "--depth=1"])
    destination = checkout / "Russian" / "interactive-book"
    if destination.exists():
        raise RuntimeError(f"В форке уже есть {destination}. Копия оставлена без изменений; проверь её вручную.")
    shutil.copytree(ROOT, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git", ".venv"))
    call(["git", "add", "Russian/interactive-book"], cwd=checkout)
    call(["git", "commit", "-m", "Add Russian desktop Python book with exercises"], cwd=checkout)
    call(["git", "push", "origin", "HEAD"], cwd=checkout)
    print(f"Готово: https://github.com/{target}/tree/{metadata['default_branch']}/Russian/interactive-book")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Операция не завершена: {error}", file=sys.stderr)
        print("Уже созданный форк или локальная копия не удаляются автоматически.", file=sys.stderr)
        sys.exit(1)
