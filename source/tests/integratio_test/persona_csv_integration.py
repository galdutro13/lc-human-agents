import unittest
import tempfile
import os
import json

# Import the classes from your modules
# Adjust the import paths as necessary
# from your_module.persona import Persona
# from your_module.csv_to_json import CSVtoJSONConverter

# For the purpose of this example, I'll define the classes here.
# Remove these definitions when using actual imports.
from source.persona.persona import Persona
from source.scripts.csv_to_json import CSVtoJSONConverter

class TestPersonaCSVIntegration(unittest.TestCase):
    def setUp(self):
        # Create a temporary CSV file with sample persona data
        self.temp_csv = tempfile.NamedTemporaryFile(mode='w+', delete=False, newline='', encoding='utf-8')
        self.csv_file_path = self.temp_csv.name

        # Write sample data to the CSV file
        self.sample_data = [
            {'name': 'Alice', 'age': '30', 'city': 'New York'},
            {'name': 'Bob', 'age': '25', 'city': 'Los Angeles'},
            {'name': 'Charlie', 'age': '35', 'city': 'Chicago'},
        ]

        # Write headers
        fieldnames = ['name', 'age', 'city']
        self.temp_csv.write(','.join(fieldnames) + '\n')

        # Write rows
        for row in self.sample_data:
            self.temp_csv.write(','.join([row['name'], row['age'], row['city']]) + '\n')

        self.temp_csv.seek(0)
        self.temp_csv.close()

    def tearDown(self):
        # Remove the temporary CSV file
        os.unlink(self.csv_file_path)

    def test_csv_to_persona_integration(self):
        """Test the integration between CSVtoJSONConverter and Persona."""
        # Step 1: Convert CSV to JSON strings
        converter = CSVtoJSONConverter(self.csv_file_path)
        json_strings = converter.convert_entire_file()

        # Step 2: Create Persona instances from JSON strings
        personas = [Persona(json_str) for json_str in json_strings]

        # Step 3: Assert that data in Persona instances matches original data
        for i, persona in enumerate(personas):
            persona_data = persona.dados_to_json()
            original_data = self.sample_data[i]

            self.assertEqual(persona_data, original_data)

    def test_individual_persona_creation(self):
        """Test creating individual Persona from a single CSV record."""
        converter = CSVtoJSONConverter(self.csv_file_path)

        for i in range(len(self.sample_data)):
            # Step 1: Convert single CSV record to JSON string
            json_str = converter.convert_single_record(i)

            # Step 2: Create Persona instance
            persona = Persona(json_str)

            # Step 3: Assert data matches
            persona_data = persona.dados_to_json()
            original_data = self.sample_data[i]

            self.assertEqual(persona_data, original_data)

if __name__ == '__main__':
    unittest.main()
