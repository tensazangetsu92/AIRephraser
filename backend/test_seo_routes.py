import asyncio
import unittest

from app.config import FRONTEND_URL
from app.routers.pages import SITEMAP_PUBLIC_PATHS, _sitemap_xml, robots_txt, templates


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

    def test_guides_are_listed_in_sitemap_and_have_templates(self):
        guide_paths = (
            "/guides",
            "/guides/humanize-text",
            "/guides/paraphrase-study-text",
            "/guides/ai-text-detectors",
            "/guides/study-work-word",
            "/guides/make-text-clearer",
            "/guides/improve-text-uniqueness",
            "/guides/introduction-coursework",
            "/guides/reference-list-coursework",
            "/guides/shorten-text-without-losing-meaning",
            "/guides/conclusion-coursework",
        )
        template_names = (
            "guides.html",
            "guide-humanize-text.html",
            "guide-paraphrase-study-text.html",
            "guide-ai-text-detectors.html",
            "guide-study-work-word.html",
            "guide-make-text-clearer.html",
            "guide-improve-text-uniqueness.html",
            "guide-introduction-coursework.html",
            "guide-reference-list-coursework.html",
            "guide-shorten-text-without-losing-meaning.html",
            "guide-conclusion-coursework.html",
        )

        for path in guide_paths:
            self.assertIn(path, SITEMAP_PUBLIC_PATHS)
        for name in template_names:
            self.assertIsNotNone(templates.get_template(name))


if __name__ == "__main__":
    unittest.main()
