"""Probe the live Robokassa shop with a minimal, unpaid checkout request.

Run on the production server with ``python3 deploy/robokassa_probe.py``.
The credentials are read from the already running app container and never
printed or stored in this script's output.
"""

import hashlib
import html
import json
import re
import secrets
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


CONTAINER = "humary-production-app-1"
CHECKOUT_URL = "https://auth.robokassa.ru/Merchant/Index.aspx"


def running_app_environment() -> dict[str, str]:
    inspected = subprocess.run(
        ["docker", "inspect", CONTAINER, "--format", "{{json .Config.Env}}"],
        check=True,
        capture_output=True,
        text=True,
    )
    values = {}
    for entry in json.loads(inspected.stdout):
        name, _, value = entry.partition("=")
        values[name] = value
    return values


def main() -> int:
    try:
        environment = running_app_environment()
    except (OSError, ValueError, subprocess.CalledProcessError):
        print("Не удалось прочитать настройки работающего контейнера.")
        return 1

    enabled = environment.get("PAYMENTS_ENABLED", "").lower() in {"1", "true", "yes", "on"}
    is_test = environment.get("ROBOKASSA_IS_TEST", "").lower() in {"1", "true", "yes", "on"}
    algorithm = environment.get("ROBOKASSA_HASH_ALGORITHM", "md5").strip().lower()
    login = environment.get("ROBOKASSA_MERCHANT_LOGIN", "").strip()
    password = environment.get("ROBOKASSA_PASSWORD1", "").strip()
    if not enabled or is_test or algorithm != "md5" or not login or not password:
        print("Ожидались включённые платежи, боевой режим и MD5 в работающем контейнере.")
        return 1

    amount = "1.00"
    invoice = str(secrets.randbelow(9_000_000_000_000_000_000) + 1)
    signature = hashlib.md5(f"{login}:{amount}:{invoice}:{password}".encode("utf-8")).hexdigest()
    form = urlencode({
        "MerchantLogin": login,
        "OutSum": amount,
        "InvId": invoice,
        "SignatureValue": signature,
    }).encode("ascii")
    request = Request(
        CHECKOUT_URL,
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            status = response.status
            final_url = response.url
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as error:
        status = error.code
        final_url = error.url
        body = error.read().decode("utf-8", errors="replace")
    except URLError as error:
        print(f"Сетевой запрос не выполнен: {type(error.reason).__name__}")
        return 1

    visible_text = html.unescape(re.sub(r"<[^>]+>", " ", body))
    visible_text = " ".join(visible_text.split())
    code = re.search(r"(?:Код\s+ошибки|Error\s+code)\s*:\s*(\d+)", visible_text, re.I)
    address = urlsplit(final_url)
    print(f"HTTP: {status}")
    print(f"Код Robokassa: {code.group(1) if code else 'не найден'}")
    print(f"Страница: {address.netloc}{address.path}")
    print(f"Номер неоплаченного счёта: {invoice}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
