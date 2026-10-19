from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent


class DeploymentTopologyTests(unittest.TestCase):
    def test_production_caddy_routes_to_isolated_app_aliases(self):
        caddyfile = (ROOT / "deploy" / "Caddyfile.production").read_text(encoding="utf-8")

        self.assertIn("{$SITE_DOMAIN}", caddyfile)
        self.assertIn("{$WWW_SITE_DOMAIN}", caddyfile)
        self.assertIn("{$STAGING_SITE_DOMAIN}", caddyfile)
        self.assertIn("reverse_proxy humary-production-app:8000", caddyfile)
        self.assertIn("reverse_proxy humary-staging-app:8000", caddyfile)
        self.assertIn("redir https://{$SITE_DOMAIN}{uri} permanent", caddyfile)

    def test_compose_uses_a_shared_private_proxy_network(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        self.assertIn("humary_proxy:", compose)
        self.assertIn("external: true", compose)
        self.assertIn("${PROXY_NETWORK_NAME:-humary-proxy}", compose)
        self.assertIn("${PROXY_APP_ALIAS:-humary-app}", compose)
        self.assertIn("${CADDYFILE:-./deploy/Caddyfile}", compose)

    def test_environment_examples_select_distinct_app_aliases(self):
        staging = (ROOT / "deploy" / "compose.staging.env.example").read_text(encoding="utf-8")
        production = (ROOT / "deploy" / "compose.production.env.example").read_text(encoding="utf-8")

        self.assertIn("PROXY_APP_ALIAS=humary-staging-app", staging)
        self.assertIn("PROXY_APP_ALIAS=humary-production-app", production)
        self.assertIn("CADDYFILE=./deploy/Caddyfile.production", production)


if __name__ == "__main__":
    unittest.main()
