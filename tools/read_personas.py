from source.scripts.csv_to_json import CSVtoJSONConverter

def main():
    csv_reader: CSVtoJSONConverter = CSVtoJSONConverter("data/Personas.CSV")

    for i in range(0, 60):
        record = csv_reader.convert_single_record(i)
        with open(f"data/extracted/persona{i}.json", "w", encoding="utf-8") as f:
            f.write(record)

if __name__ == "__main__":
    main()