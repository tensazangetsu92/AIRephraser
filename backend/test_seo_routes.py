import asyncio
import unittest

from app.config import FRONTEND_URL
from app.routers.pages import SITEMAP_PUBLIC_PATHS, _sitemap_xml, robots_txt


class SeoRoutesTests(unittest.TestCase):
    def test_sitemap_contains_only_public_canonical_urls(self):
        sitemap = _sitemap_xml()

        self.assertIn('xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"', sitemap)
        for path in SITEMAP_PUBLIC_PATHS:
            self.assertIn(f"<loc>{FRONTEND_URL}{path}</loc>", sitemap)
        self.assertNotIn("/profile", sitemap)
        self.assertNotIn("/history", sitemap)

    def test_robots_references_sitemap_and_excludes_private_routes(self):
        response = asyncio.run(robots_txt())
        robots = response.body.decode("utf-8")

        self.assertIn(f"Sitemap: {FRONTEND_URL}/sitemap.xml", robots)
        self.assertIn("Disallow: /profile", robots)
        self.assertIn("Disallow: /history", robots)
        self.assertIn("Disallow: /humanize/", robots)


if __name__ == "__main__":
    unittest.main()
