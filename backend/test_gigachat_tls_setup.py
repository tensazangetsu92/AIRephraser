from pathlib import Path
import unittest


class GigaChatTlsSetupTests(unittest.TestCase):
    def test_docker_image_installs_russian_trusted_root_ca(self):
        dockerfile = Path(__file__).resolve().parent.parent / "Dockerfile"
        contents = dockerfile.read_text(encoding="utf-8")

        self.assertIn("russian_trusted_root_ca_pem.crt", contents)
        self.assertIn("update-ca-certificates", contents)
        self.assertIn("import certifi", contents)
