import unittest

from scripts.validate_csv_imports import validate_all


class CsvValidationTests(unittest.TestCase):
    def test_current_seed_and_templates_pass(self) -> None:
        self.assertEqual(validate_all(), [])


if __name__ == "__main__":
    unittest.main()
