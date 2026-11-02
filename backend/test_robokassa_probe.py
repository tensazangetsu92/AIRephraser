"""Keep the production diagnostic limited to an unsigned-invoice probe."""

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
    def test_minimal_request_omits_receipt_and_does_not_print_secrets(self) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.url = "https://auth.robokassa.ru/Merchant/Index.aspx"
        response.read.return_value = "<html>Код ошибки: 29</html>".encode("utf-8")
        output = StringIO()
        settings = {
            "PAYMENTS_ENABLED": "true",
            "ROBOKASSA_IS_TEST": "false",
            "ROBOKASSA_HASH_ALGORITHM": "md5",
            "ROBOKASSA_MERCHANT_LOGIN": "Humary",
            "ROBOKASSA_PASSWORD1": "test-secret",
        }

        with patch.object(probe, "running_app_environment", return_value=settings), \
                patch.object(probe.secrets, "randbelow", return_value=123), \
                patch.object(probe, "urlopen", return_value=response) as send, \
                redirect_stdout(output):
            self.assertEqual(probe.main(), 0)

        request = send.call_args.args[0]
        fields = parse_qs(request.data.decode("ascii"))
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(set(fields), {"MerchantLogin", "OutSum", "InvId", "SignatureValue"})
        self.assertEqual(fields["SignatureValue"], [
            hashlib.md5(b"Humary:1.00:124:test-secret").hexdigest()
        ])
        self.assertIn("Код Robokassa: 29", output.getvalue())
        self.assertNotIn("test-secret", output.getvalue())
        self.assertNotIn(fields["SignatureValue"][0], output.getvalue())


if __name__ == "__main__":
    unittest.main()
