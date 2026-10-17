import unittest

from migrate_recipe_dates import extract_detail_datetime


class ExtractDetailDatetimeTests(unittest.TestCase):
    def test_extract_created_and_modified_from_details_list(self):
        details = [
            "Written by ethel",
            "Category: Informative",
            "Published: 02 July 2012",
            "Created: 02 July 2012",
            "Last Updated: 20 October 2017",
        ]

        self.assertEqual(extract_detail_datetime(details, "created"), "2012-07-02 00:00:00")
        self.assertEqual(extract_detail_datetime(details, "modified"), "2017-10-20 00:00:00")

    def test_extract_handles_iso_and_modified_variants(self):
        details = [
            "Modified: 2024-05-19T15:30:00",
            "Created: 2023-01-10 09:00",
        ]

        self.assertEqual(extract_detail_datetime(details, "created"), "2023-01-10 09:00:00")
        self.assertEqual(extract_detail_datetime(details, "modified"), "2024-05-19 15:30:00")


if __name__ == "__main__":
    unittest.main()
