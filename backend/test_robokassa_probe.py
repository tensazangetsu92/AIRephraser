"""Check that the production probe isolates Robokassa signature fields."""

from contextlib import redirect_stdout
from io import StringIO
import hashlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs


SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "robokassa_probe.py"
SPEC = importlib.util.spec_from_file_location("robokassa_probe", SCRIPT)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class RobokassaProbeTests(unittest.TestCase):
    def test_requests_isolate_signed_fields_and_do_not_print_secrets(self) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.url = "https://auth.robokassa.ru/Merchant/Index.aspx"
        response.headers.get_content_charset.return_value = "windows-1251"
        response.read.return_value = "<html>Код ошибки: 29</html>".encode("cp1251")
        output = StringIO()
        settings = {
            "PAYMENTS_ENABLED": "true",
            "ROBOKASSA_IS_TEST": "false",
            "ROBOKASSA_HASH_ALGORITHM": "md5",
            "ROBOKASSA_MERCHANT_LOGIN": "Humary",
            "ROBOKASSA_PASSWORD1": "test-secret",
        }

        with patch.object(probe, "running_app_environment", return_value=settings), \
                patch.object(probe.secrets, "randbelow", side_effect=[123, 124, 125, 126]), \
                patch.object(probe, "urlopen", return_value=response) as send, \
                redirect_stdout(output):
            self.assertEqual(probe.main(), 0)

        requests = [call.args[0] for call in send.call_args_list]
        self.assertEqual(len(requests), 4)
        for request, has_receipt, has_order in zip(
                requests, (False, True, False, True), (False, False, True, True)
        ):
            fields = {key: value[0] for key, value in parse_qs(request.data.decode("ascii")).items()}
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual("Receipt" in fields, has_receipt)
            self.assertEqual("Shp_order" in fields, has_order)
            parts = [fields["MerchantLogin"], fields["OutSum"], fields["InvId"]]
            if has_receipt:
                parts.append(fields["Receipt"])
            parts.append("test-secret")
            if has_order:
                parts.append(f"Shp_order={fields['Shp_order']}")
            self.assertEqual(fields["SignatureValue"], hashlib.md5(":".join(parts).encode()).hexdigest())
            self.assertNotIn(fields["SignatureValue"], output.getvalue())
        self.assertEqual(output.getvalue().count("код=29"), 4)
        self.assertNotIn("test-secret", output.getvalue())


if __name__ == "__main__":
    unittest.main()
