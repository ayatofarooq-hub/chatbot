"""Regression tests for the offline startup path."""

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from app import main as app_main


class MainOfflineTests(unittest.TestCase):
    def test_main_handles_offline_database_without_crashing(self):
        with patch.object(app_main, "create_data_directories") as create_data_directories, patch.object(app_main, "create_database_engine", return_value=None), patch.object(app_main, "connection_identity", return_value=("offline", "json")):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                app_main.main()

        create_data_directories.assert_called_once_with()
        self.assertIn("Offline", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
