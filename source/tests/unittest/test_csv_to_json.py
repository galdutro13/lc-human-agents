import unittest
import tempfile
import os
import json
import csv
from typing import List, Dict

from source.scripts.csv_to_json import CSVtoJSONConverter

class TestCSVtoJSONConverter(unittest.TestCase):
    def setUp(self):
        # Create a temporary CSV file with sample data
        self.temp_csv = tempfile.NamedTemporaryFile(mode='w+', delete=False, newline='', encoding='utf-8')
        self.csv_file_path = self.temp_csv.name
        self.temp_csv.write('name,age,city\n')
        self.temp_csv.write('Alice,30,New York\n')
        self.temp_csv.write('Bob,25,Los Angeles\n')
        self.temp_csv.write('Charlie,35,Chicago\n')
        self.temp_csv.seek(0)
        self.temp_csv.close()

    def tearDown(self):
        # Remove the temporary CSV file
        os.unlink(self.csv_file_path)

    def test_convert_entire_file(self):
        """Test converting the entire CSV file to JSON strings."""
        converter = CSVtoJSONConverter(self.csv_file_path)
        json_strings = converter.convert_entire_file()
        expected_json_strings = [
            json.dumps({'name': 'Alice', 'age': '30', 'city': 'New York'}),
            json.dumps({'name': 'Bob', 'age': '25', 'city': 'Los Angeles'}),
            json.dumps({'name': 'Charlie', 'age': '35', 'city': 'Chicago'}),
        ]
        self.assertEqual(json_strings, expected_json_strings)

    def test_convert_single_record_valid(self):
        """Test converting a valid single record to a JSON string."""
        converter = CSVtoJSONConverter(self.csv_file_path)
        json_string = converter.convert_single_record(1)  # Index 1 corresponds to Bob
        expected_json_string = json.dumps({'name': 'Bob', 'age': '25', 'city': 'Los Angeles'})
        self.assertEqual(json_string, expected_json_string)

    def test_convert_single_record_invalid_index(self):
        """Test that an IndexError is raised for an invalid record index."""
        converter = CSVtoJSONConverter(self.csv_file_path)
        with self.assertRaises(IndexError):
            converter.convert_single_record(10)  # Index out of range

    def test_file_not_found(self):
        """Test that a FileNotFoundError is raised when the CSV file does not exist."""
        converter = CSVtoJSONConverter('non_existent_file.csv')
        with self.assertRaises(FileNotFoundError):
            converter.convert_entire_file()

    def test_malformed_csv(self):
        """Testa se um ValueError é levantado quando uma linha tem campos faltantes."""
        # Cria um arquivo CSV com campos faltantes
        malformed_csv = tempfile.NamedTemporaryFile(mode='w+', delete=False, newline='', encoding='utf-8')
        malformed_csv.write('name,age,city\n')
        malformed_csv.write('Alice,30\n')  # Falta o campo 'city'
        malformed_csv.seek(0)
        malformed_csv.close()

        converter = CSVtoJSONConverter(malformed_csv.name)
        with self.assertRaises(ValueError):
            converter.convert_entire_file()

        # Remove o arquivo CSV malformado
        os.unlink(malformed_csv.name)


if __name__ == '__main__':
    unittest.main()
