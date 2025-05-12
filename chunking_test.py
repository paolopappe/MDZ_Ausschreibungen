#!/usr/bin/env python3
import argparse
import json
import os

# Importiere die Pipeline-Funktion aus deinem Modul.
# Stelle sicher, dass sich pipeline.py im selben Verzeichnis befindet oder im Python-Pfad liegt.
from prepare_data_test import prepare_data

def main():
    parser = argparse.ArgumentParser(
        description="Liest eine PDF ein, verarbeitet sie und speichert die resultierenden Chunks als JSON."
    )
    parser.add_argument(
        "pdf_path",
        help="Pfad zur PDF-Datei, die verarbeitet werden soll."
    )
    parser.add_argument(
        "--output",
        "-o",
        default="chunks.json",
        help="Pfad zur Ausgabedatei (JSON). Standard: chunks.json"
    )
    args = parser.parse_args()

    # Überprüfen, ob die PDF-Datei existiert
    if not os.path.exists(args.pdf_path):
        print(f"Die Datei {args.pdf_path} wurde nicht gefunden.")
        exit(1)

    # Verarbeite die PDF-Datei mithilfe der Pipeline-Funktion
    print(f"Verarbeite {args.pdf_path} ...")
    chunks = prepare_data(args.pdf_path)

    # Speichere die resultierenden Chunks als JSON-Datei
    try:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=4)
        print(f"Die Chunks wurden erfolgreich in '{args.output}' gespeichert.")
    except Exception as e:
        print(f"Fehler beim Speichern der Ergebnisse: {e}")

if __name__ == '__main__':
    main()
