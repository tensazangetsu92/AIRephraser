"""Interactively replace Robokassa passwords in the local production env file.

Run on the server from /opt/humary: python3 deploy/set_robokassa_passwords.py
This script does not reload the running app; recreate it after the update.
"""

import getpass
import os
from pathlib import Path
import re
import stat
import tempfile


ENV_FILE = Path(__file__).with_name("production.env")
KEYS = ("ROBOKASSA_PASSWORD1", "ROBOKASSA_PASSWORD2")


def replace_passwords(path: Path, passwords: dict[str, str]) -> None:
    for key in KEYS:
        value = passwords[key]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError(f"{key}: пароль содержит символы, требующие отдельной настройки env-файла")

    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    counts = {key: 0 for key in KEYS}
    updated = []
    for line in lines:
        key = line.split("=", 1)[0]
        if key in counts:
            counts[key] += 1
            newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            updated.append(f"{key}={passwords[key]}{newline}")
        else:
            updated.append(line)
    if any(count != 1 for count in counts.values()):
        raise ValueError("В production.env должен быть ровно один экземпляр каждого ROBOKASSA_PASSWORD")

    mode = stat.S_IMODE(path.stat().st_mode)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write("".join(updated))
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> int:
    if not ENV_FILE.is_file():
        print("Файл deploy/production.env не найден. Запустите скрипт на сервере из /opt/humary.")
        return 1
    passwords = {
        "ROBOKASSA_PASSWORD1": getpass.getpass("Новый пароль Robokassa №1: "),
        "ROBOKASSA_PASSWORD2": getpass.getpass("Новый пароль Robokassa №2: "),
    }
    try:
        replace_passwords(ENV_FILE, passwords)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"Пароли не изменены: {error}")
        return 1
    print("Пароли в production.env обновлены. Пересоздайте контейнер app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
