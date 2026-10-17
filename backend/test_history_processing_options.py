from pathlib import Path
import unittest

from app.database import UserHistory
from app.routers.user_routes import normalize_history_processing_options


class HistoryProcessingOptionsTests(unittest.TestCase):
    def test_humanizer_options_are_preserved_when_valid(self):
        options = normalize_history_processing_options(
            "humanizer",
            {"style": "academic", "target_language": "en", "unexpected": "ignored"},
        )

        self.assertEqual(options, {"style": "academic", "target_language": "en"})

    def test_invalid_options_are_not_stored(self):
        options = normalize_history_processing_options(
            "paraphraser",
            {"style": "unsupported"},
        )

        self.assertEqual(options, {})

    def test_history_model_and_migration_have_processing_options(self):
        self.assertIn("processing_options", UserHistory.__table__.columns)
        migration = Path(__file__).resolve().parent / "alembic" / "versions" / "20261018_0004_history_processing_options.py"
        self.assertIn("processing_options", migration.read_text(encoding="utf-8"))
