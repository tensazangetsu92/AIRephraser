"""Compare unpaid Robokassa checkout requests with and without signed fields.

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
from uuid import uuid4
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlencode, urlsplit
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


def make_request(login: str, password: str, *, receipt: bool, order: bool) -> tuple[Request, str]:
    amount = "1.00"
    invoice = str(secrets.randbelow(9_000_000_000_000_000_000) + 1)
    parts = [login, amount, invoice]
    fields = {
        "MerchantLogin": login,
        "OutSum": amount,
        "InvId": invoice,
        "Description": "Humary: тариф pro на 30 дней",
        "Email": "diagnostic@example.com",
        "Culture": "ru",
    }
    if receipt:
        item = {
            "items": [{
                "name": "Humary: тариф pro на 30 дней",
                "quantity": 1,
                "sum": 1.0,
                "payment_method": "full_payment",
                "payment_object": "service",
                "tax": "none",
            }],
        }
        encoded_receipt = quote_plus(json.dumps(item, ensure_ascii=True, separators=(",", ":")))
        fields["Receipt"] = encoded_receipt
        parts.append(encoded_receipt)
    parts.append(password)
    if order:
        order_id = str(uuid4())
        fields["Shp_order"] = order_id
        parts.append(f"Shp_order={order_id}")
    fields["SignatureValue"] = hashlib.md5(":".join(parts).encode("utf-8")).hexdigest()
    request = Request(
        CHECKOUT_URL,
        data=urlencode(fields).encode("ascii"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    return request, invoice


def _decode_response(body: bytes, headers: object) -> str:
    charset = headers.get_content_charset() or "utf-8"
    try:
        return body.decode(charset)
    except (LookupError, UnicodeError):
        return body.decode("cp1251", errors="replace")


def send_probe(request: Request) -> tuple[int, str, str, bool, bool, int]:
    try:
        with urlopen(request, timeout=20) as response:
            status = response.status
            final_url = response.url
            body = _decode_response(response.read(), response.headers)
    except HTTPError as error:
        status = error.code
        final_url = error.url
        body = _decode_response(error.read(), error.headers)

    visible_text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", body, flags=re.I | re.S)
    visible_text = html.unescape(re.sub(r"<[^>]+>", " ", visible_text))
    visible_text = " ".join(visible_text.split())
    code = re.search(r"(?:Код\s+ошибки|Error\s+code)\s*:\s*(\d+)", visible_text, re.I)
    address = urlsplit(final_url)
    unavailable = "оплата счетов недоступна" in visible_text.casefold()
    has_error_text = "ошибка" in visible_text.casefold() or "error" in visible_text.casefold()
    return status, code.group(1) if code else "не найден", f"{address.netloc}{address.path}", unavailable, has_error_text, len(body)


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

    cases = [
        ("базовый", False, False),
        ("только Receipt", True, False),
        ("только Shp_order", False, True),
        ("Receipt + Shp_order", True, True),
    ]
    for label, receipt, order in cases:
        request, invoice = make_request(login, password, receipt=receipt, order=order)
        try:
            status, code, page, unavailable, has_error_text, body_size = send_probe(request)
        except URLError as error:
            print(f"Сетевой запрос не выполнен: {type(error.reason).__name__}")
            return 1
        print(f"{label}: HTTP={status}, код={code}, недоступно={unavailable}, текст_ошибки={has_error_text}, размер={body_size}, страница={page}, счёт={invoice}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
