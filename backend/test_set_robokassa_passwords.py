import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "set_robokassa_passwords.py"
SPEC = importlib.util.spec_from_file_location("set_robokassa_passwords", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SetRobokassaPasswordsTests(unittest.TestCase):
    def test_updates_only_passwords(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "production.env"
            path.write_text("OTHER=keep\nROBOKASSA_PASSWORD1=old1\nROBOKASSA_PASSWORD2=old2\n", encoding="utf-8")

            MODULE.replace_passwords(path, {"ROBOKASSA_PASSWORD1": "new1_ABC", "ROBOKASSA_PASSWORD2": "new2-XYZ"})

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "OTHER=keep\nROBOKASSA_PASSWORD1=new1_ABC\nROBOKASSA_PASSWORD2=new2-XYZ\n",
            )

    def test_rejects_missing_key_without_modifying_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "production.env"
            original = "OTHER=keep\nROBOKASSA_PASSWORD1=old1\n"
            path.write_text(original, encoding="utf-8")

            with self.assertRaises(ValueError):
                MODULE.replace_passwords(path, {"ROBOKASSA_PASSWORD1": "new1", "ROBOKASSA_PASSWORD2": "new2"})

            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
