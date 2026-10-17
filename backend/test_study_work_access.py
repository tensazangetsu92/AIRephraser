import unittest
from unittest.mock import patch

from app.routers import study_work_routes


class StudyWorkAccessTests(unittest.TestCase):
    def test_used_trial_does_not_block_word_balance_path(self):
        with patch.object(study_work_routes, "reserve_study_work_trial", return_value=False) as reserve_trial:
            uses_trial = study_work_routes.reserve_study_work_trial_if_available(object(), 42)

        self.assertFalse(uses_trial)
        reserve_trial.assert_called_once()
