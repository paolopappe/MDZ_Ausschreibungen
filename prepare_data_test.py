import os
import io
import re
import unicodedata
import unidecode
import json
from PyPDF2 import PdfReader
import openai
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from typing import Union
from dotenv import load_dotenv

load_dotenv()

# API-Key aus Umgebungsvariablen laden und OpenAI-Client konfigurieren
openai.api_key = os.getenv("OPENAI_API_KEY")

# Muster definieren, die entfernt werden sollen
PATTERNS_TO_REMOVE = [
	# Fußzeile mit Druckdatum und Seitenzahl (variabel für unterschiedliche Daten und Seitenzahlen)
	r'^Druckdatum:\s+[\d\.]+\s+Seite:\s+\d+$',
	# Zeilen mit 'Prusseit', 'Reiss' und 'Bauplanungsbüro GmbH'
	r'^Prusseit\s+u\.\s+R\s*eiss\s+Bauplanungsbüro\s+GmbH$',
	# Zeilen mit 'Gutenbergstr.', 'Garbsen', 'Telefon' und 'Telefax'
	r'Gutenbergstr\..*Garbsen.*Telefon.*Telefax',
	# Zeilen mit 'e-mail:' und 'info@prusseitundreiss.de'
	r'e-mail:\s*info@prusseitundreiss\.de',
	# Zeilen mit '(Ort, Datum, Unterschrift und Stempel)'
	r'\(Ort, Datum, Unterschrift und Stempel\)',
	# Zeile mit 'Leistungsverzeichnis Kurz- und Langtext'
	r'^Leistungsverzeichnis\s+Kurz-\s*und\s+Langtext$',
	# Zeile mit 'Ordnungszahl Leistungsbeschreibung Menge ME Einheitspreis Gesamtbetrag'
	r'^Ordnungszahl\s+Leistungsbeschreibung\s+Menge\s+ME\s+Einheit\s*spreis\s+Gesamtbetrag$',
	# Zeile mit 'in EUR in EUR'
	r'^in\s+EUR\s+in\s+EUR$'
]

# Kompiliere die regulären Ausdrücke mit re.IGNORECASE für Groß-/Kleinschreibung
COMPILED_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in PATTERNS_TO_REMOVE]

# Definiere die Schlüsselwörter
KEYWORDS = ["Hallenanbau", "Lagerhalle", "Vertriebsniederlassung", "Schwimmbad"]

# Prompt für Zusammenfassung
SUMMARY_PROMPT = """\
You are given a text that you need to summarize as a sequence of keywords.\
The keywords summaries will be used later to do a search over text by these\
so make sure to capture the most relevant topics of the text so that\
the text can be found later by them. Return only a sequence of search keywords for the text.


The text is below
=================
{text}
"""

SUMMARY_TEMPLATE = ChatPromptTemplate.from_template(SUMMARY_PROMPT)

# Pipeline für Zusammefassung
LLM = ChatOpenAI(model="gpt-4o-mini", temperature=0)
SUMMARIZER = SUMMARY_TEMPLATE | LLM


def clean_metadata(metadata):
	cleaned_metadata = {}
	for key, value in metadata.items():
		if isinstance(value, str):
			# Unicode-Zeichen normalisieren
			normalized = unicodedata.normalize('NFKD', value)
			# In ASCII enkodieren, nicht-ASCII-Zeichen ignorieren
			cleaned_value = normalized.encode('ascii', 'ignore').decode('ascii')
			cleaned_metadata[key] = cleaned_value
		else:
			# Nicht-String-Werte in Strings umwandeln
			cleaned_metadata[key] = str(value)
	return cleaned_metadata


def process_pdf(pdf_path: Union[str, bytes]):
	project_info = None
	lv_info = None
	cleaned_pages = []

	try:

		if isinstance(pdf_path, str):
			pdf_file = open(pdf_path, 'rb')
		elif isinstance(pdf_path, bytes):
			# convert static bytes to IO
			pdf_file = io.BytesIO(pdf_path)

		reader = PdfReader(pdf_file)
		num_pages = len(reader.pages)

		for i in range(num_pages):
			page = reader.pages[i]
			page_text = page.extract_text() or ""
			lines = page_text.split('\n')
			cleaned_lines = []

			for line in lines:
				# Zeile normalisieren (zusätzliche Leerzeichen entfernen)
				normalized_line = ' '.join(line.split())

				# Überprüfen, ob die Zeile mit 'Projekt:' beginnt
				if normalized_line.startswith('Projekt:'):
					# Extrahiere die Information nach 'Projekt:'
					info = normalized_line[len('Projekt:'):].strip()
					# Speichere die Information nur, wenn sie noch nicht gespeichert wurde
					if project_info is None:
						project_info = info
					continue  # Zeile nicht zu cleaned_lines hinzufügen

				# Überprüfen, ob die Zeile mit 'LV:' beginnt
				if normalized_line.startswith('LV:'):
					# Extrahiere die Information nach 'LV:'
					info = normalized_line[len('LV:'):].strip()
					# Speichere die Information nur, wenn sie noch nicht gespeichert wurde
					if lv_info is None:
						lv_info = info
					continue  # Zeile nicht zu cleaned_lines hinzufügen

				# Prüfen, ob die Zeile einem der Muster entspricht
				if any(pattern.search(normalized_line) for pattern in COMPILED_PATTERNS):
					continue  # Unerwünschte Zeile überspringen

				cleaned_lines.append(line)

			# Bereinigten Seitentext rekonstruieren
			cleaned_page_text = '\n'.join(cleaned_lines)
			cleaned_pages.append(cleaned_page_text)

		# Zusammenführen aller bereinigten Seiten
		full_cleaned_text = '\n'.join(cleaned_pages)

		# Bereinigen der Metadaten
		metadata = {
			'Projekt': project_info,
			'LV': lv_info,
			'Dateiname': os.path.basename(pdf_path)
		}
		cleaned_metadata = clean_metadata(metadata)
		
		pdf_file.close()

		return {
			'text': full_cleaned_text,
			'metadata': cleaned_metadata
		}

	except Exception as e:
		print(f"Fehler beim Verarbeiten der Datei {pdf_path}: {e}")
		return None


# def process_all_pdfs(folder_path):
# 	if not os.path.exists(folder_path):
# 		print(f"Fehler: Der Ordner '{folder_path}' existiert nicht.")
# 		return []

# 	# Liste aller PDF-Dateien im Ordner
# 	pdf_files = [file for file in os.listdir(folder_path) if file.lower().endswith('.pdf')]

# 	if not pdf_files:
# 		print(f"Keine PDF-Dateien im Ordner '{folder_path}' gefunden.")
# 		return []

# 	processed_documents = []

# 	for pdf_filename in pdf_files:
# 		pdf_path = os.path.join(folder_path, pdf_filename)
# 		print(f"Verarbeite Datei: {pdf_filename}")
# 		result = process_pdf(pdf_path)
# 		if result:
# 			processed_documents.append(result)
# 			print(f"Erfolgreich verarbeitet: {pdf_filename}\n")
# 		else:
# 			print(f"Verarbeitung fehlgeschlagen: {pdf_filename}\n")

# 	return processed_documents


# def extract_keyword(filename):
# 	prompt = f"""
# Ordne dem folgenden Text genau ein Schlüsselwort aus der Liste zu:

# Text: "{filename}"

# Schlüsselwörter: {", ".join(KEYWORDS)}

# Gib nur das passende Schlüsselwort zurück. Wenn keines passt, gib "Unbekannt" zurück.
# """

# 	response = openai.chat.completions.create(
# 		model="gpt-4o-mini",
# 		messages = [
# 			{"role": "system", "content": "Du bist ein hilfreicher Assistent."},
# 			{"role": "user", "content": prompt}
# 		],
# 		max_tokens=10,
# 		n=1,
# 		stop=None,
# 		temperature=0,
# 	)

# 	keyword = response.choices[0].message.content.strip()
# 	return keyword


# def process_documents(documents):

# 	for doc in documents:
# 		filename = doc.get('metadata', {}).get('Dateiname', '')
# 		if filename:
# 			keyword = extract_keyword(filename)
# 			# Speichere das extrahierte Schlüsselwort in den Metadaten
# 			doc['metadata']['keyword'] = keyword
# 			print(f"Dateiname: {filename}, keyword: {keyword}")
# 		else:
# 			print("Kein 'Dateiname' im Dokument gefunden.")
	
# 	return documents
		

def extract_inhaltsverzeichnis(text):
	"""
	Extrahiert das Inhaltsverzeichnis aus dem gegebenen Text.
	Sucht nach "Inhaltsverzeichnis" und extrahiert bis "Zusammenstellung" inklusive.
	"""
	# Muster für den Start des Inhaltsverzeichnisses
	pattern_start = re.compile(r'Inhaltsverzeichnis', re.IGNORECASE)
	# Muster für das Ende des Inhaltsverzeichnisses
	pattern_end = re.compile(r'Zusammenstellung.*(?:\n|$)', re.IGNORECASE)
	
	start_match = pattern_start.search(text)
	if not start_match:
		return None, text  # Kein Inhaltsverzeichnis gefunden
	
	start_index = start_match.start()
	
	end_match = pattern_end.search(text, start_match.end())
	if end_match:
		end_index = end_match.end()
	else:
		# Falls "Zusammenstellung" nicht gefunden, bis Ende des Textes
		end_index = len(text)
	
	inhaltsverzeichnis = text[start_index:end_index]
	rest_text = text[:start_index] + text[end_index:]
	
	return inhaltsverzeichnis.strip(), rest_text.strip()

def process_json(documents):
	"""
	Verarbeitet die JSON-Datei, extrahiert das Inhaltsverzeichnis und speichert es als neuen Chunk.
	Fügt dem Inhaltsverzeichnis-Chunks ein Metadatenfeld hinzu, das es als Inhaltsverzeichnis kennzeichnet.
	"""
	
	# Annahme: data ist eine Liste von Objekten
	new_data = []
	for doc in documents:
		text = doc.get('text', '')
		metadata = doc.get('metadata', {})
		
		inhaltsverzeichnis, rest_text = extract_inhaltsverzeichnis(text)
		
		if inhaltsverzeichnis:
			# Erstelle einen neuen Chunk für das Inhaltsverzeichnis
			chunk_vz = {
				'text': inhaltsverzeichnis,
				'metadata': {
					**metadata,  # Kopiere bestehende Metadaten
					'section': 'Inhaltsverzeichnis'  # Füge neues Metadatenfeld hinzu
				}
			}
			new_data.append(chunk_vz)
			
			# Aktualisiere den Originaleintrag mit dem restlichen Text
			doc['text'] = rest_text
		# Füge das (eventuell modifizierte) Original-Entry hinzu
		new_data.append(doc)

	return new_data


def extract_vorbemerkungen(text):
	"""
	Extrahiert die "Zusätzlichen Vorbemerkungen" aus dem gegebenen Text.
	Sucht nach "Zusätzliche Vorbemerkungen" und extrahiert die Auflistungspunkte bis "Baubeschreibung" inklusive.
	Gibt eine Liste von Tupeln (Nummer, Text) und den restlichen Text zurück.
	"""
	# Muster für den Start der Vorbemerkungen
	pattern_start = re.compile(r'Zusätzliche\s+Vorbemerkungen', re.IGNORECASE)
	# Muster für das Ende der Vorbemerkungen
	pattern_end = re.compile(r'Baubeschreibung', re.IGNORECASE)
	
	start_match = pattern_start.search(text)
	if not start_match:
		return [], text  # Keine Vorbemerkungen gefunden
	
	start_index = start_match.end()
	
	end_match = pattern_end.search(text, start_index)
	if end_match:
		end_index = end_match.start()
	else:
		# Falls "Baubeschreibung" nicht gefunden, bis Ende des Textes
		end_index = len(text)
	
	vorbemerkungen_text = text[start_index:end_index]
	
	# Vorverarbeitung: Entferne Zeilenumbrüche und überflüssige Leerzeichen
	vorbemerkungen_text = re.sub(r'\s+', ' ', vorbemerkungen_text)
	
	# Muster zur Extraktion der Auflistungspunkte (z.B., 1. Text, 2. Text, ...)
	# Erfasst die Nummer und den zugehörigen Text
	list_item_pattern = re.compile(r'(\d+)\.\s+(.*?)(?=\s+\d+\.|\Z)', re.DOTALL)
	vorbemerkungen_matches = list_item_pattern.findall(vorbemerkungen_text)
	
	# Entferne die Vorbemerkungen aus dem Originaltext
	rest_text = text[:start_match.start()] + text[end_index:]
	
	# Bereinige die extrahierten Vorbemerkungen und speichere Nummer und Text
	vorbemerkungen_clean = []
	for number, item in vorbemerkungen_matches:
		# Ersetze Zeilenumbrüche und multiple Leerzeichen durch ein einzelnes Leerzeichen
		clean_item = re.sub(r'\s+', ' ', item).strip()
		vorbemerkungen_clean.append((number, clean_item))
	
	return vorbemerkungen_clean, rest_text.strip()


def process_vorbemerkungen(documents):
	"""
	Verarbeitet die JSON-Datei, extrahiert die "Zusätzlichen Vorbemerkungen" und speichert sie als neue Chunks.
	Jeder Vorbemerkungspunkt wird als eigener Chunk mit der Nummerierung in den Metadaten gespeichert.
	"""
	
	new_data = []
	for doc in documents:
		# Überprüfen, ob der Eintrag bereits eine Section hat (z.B., "Inhaltsverzeichnis")
		if 'section' in doc and 'Inhaltsverzeichnis' in doc["metadata"]["keywords"]:
			# Behalte den Inhaltsverzeichnis-Chunk unverändert
			new_data.append(doc)
			continue
		
		text = doc.get('text', '')
		metadata = doc.get('metadata', {})
		
		vorbemerkungen, rest_text = extract_vorbemerkungen(text)
		
		if vorbemerkungen:
			# Für jede Vorbemerkung einen neuen Chunk erstellen
			for number, vorbemerkung in vorbemerkungen:
				chunk_vb = {
					'text': vorbemerkung,
					'metadata': {
						**metadata,  # Kopiere bestehende Metadaten
						'section': 'Zusätzliche Vorbemerkungen',  # Füge neues Metadatenfeld hinzu
						'number': number  # Füge die Nummer der Auflistung hinzu
					}
				}
				new_data.append(chunk_vb)
			
			# Aktualisiere den Originaleintrag mit dem restlichen Text
			doc['text'] = rest_text
		
		# Füge das (eventuell modifizierte) Original-Entry hinzu
		new_data.append(doc)

	return new_data


def extract_inhaltsverzeichnis_headings(documents):
	"""
	Extrahiert die Hauptüberschriften aus dem "Inhaltsverzeichnis" Abschnitt.
	Gibt eine Liste der Überschriften zurück.

	Args:
		data (list): Liste der Dokumente (Dictionaries) aus der JSON-Datei.

	Returns:
		list: Liste der extrahierten Überschriften im Format "Nummer. Titel".
	"""
	headings = []
	for doc in documents:
		# Überprüfen, ob der Eintrag die Section "Inhaltsverzeichnis" in den Metadaten enthält
		if 'metadata' in doc and 'section' in doc['metadata'] and doc['metadata']['section'].strip().lower() == 'inhaltsverzeichnis':
			text = doc.get('text', '')
			# Ersetzen von Zeilenumbrüchen durch Leerzeichen, um mehrzeilige Titel zu handhaben
			text = text.replace('\n', ' ')
			
			# Regex-Pattern zur Extraktion der Kapitelüberschriften
			# Geändertes Pattern: Erlaubt Punkte innerhalb des Titels
			pattern = re.compile(r'(\d+(?:\.\d+)*)\.\s+(.+?)\s*\.+\s*\d+', re.MULTILINE)
			matches = pattern.findall(text)
			
			for match in matches:
				number = match[0].strip()
				title = match[1].strip()
				headings.append(f"{number}. {title}")
			
			break  # Nur den ersten Inhaltsverzeichnis-Eintrag verarbeiten
	return headings


def extract_baubeschreibung(text, inhaltsverzeichnis_headings):
	"""
	Extrahiert die "Baubeschreibung" aus dem gegebenen Text.
	Sucht nach "Baubeschreibung" und extrahiert die Untersektionen bis zur ersten Überschrift aus dem Inhaltsverzeichnis.
	Gibt eine Liste von Tupeln (Nummer, Überschrift, Text) und den restlichen Text zurück.
	"""
	# Muster für den Start der Baubeschreibung
	pattern_start = re.compile(r'Baubeschreibung', re.IGNORECASE)

	start_match = pattern_start.search(text)
	if not start_match:
		return [], text  # Keine Baubeschreibung gefunden

	start_index = start_match.end()

	# Extrahiere nur die Nummerierung aus den Inhaltsverzeichnis-Überschriften
	numbering_patterns = []
	pattern_number = re.compile(r'^(\d+(?:\.\d+)*)\.')

	for heading in inhaltsverzeichnis_headings:
		match = pattern_number.match(heading)
		if match:
			# Escape die Punkte für die Regex
			number = re.escape(match.group(1) + '.')
			numbering_patterns.append(number)

	if not numbering_patterns:
		end_index = len(text)
	else:
		# Erstelle ein kombiniertes Regex-Muster für alle Nummerierungen
		combined_pattern = re.compile(r'(' + '|'.join(numbering_patterns) + r')\s', re.MULTILINE)
		end_match = combined_pattern.search(text, start_index)
		if end_match:
			end_index = end_match.start()
		else:
			end_index = len(text)

	baubeschreibung_text = text[start_index:end_index]

	# Vorverarbeitung: Entferne Zeilenumbrüche und überflüssige Leerzeichen
	baubeschreibung_text = re.sub(r'\s+', ' ', baubeschreibung_text)

	# Muster zur Extraktion der Untersektionen (z.B., 1.01 Überschrift: Text, 1.02 ...)
	# Erfasst die Nummer, Überschrift und den zugehörigen Text
	# Beispiel: 1.01 Lage des Gebäudes: Text
	subsection_pattern = re.compile(r'(\d+\.\d+)\s+([^:]+):\s+(.*?)(?=\s+\d+\.\d+\s+[^:]+:|\Z)', re.DOTALL)
	subsections = subsection_pattern.findall(baubeschreibung_text)

	# Entferne die Baubeschreibung aus dem Originaltext
	rest_text = text[:start_match.start()] + text[end_index:]

	# Bereinige die extrahierten Untersektionen
	baubeschreibung_clean = []
	for number, header, item in subsections:
		# Ersetze Zeilenumbrüche und multiple Leerzeichen durch ein einzelnes Leerzeichen
		clean_item = re.sub(r'\s+', ' ', item).strip()
		baubeschreibung_clean.append((number, header.strip(), clean_item))

	return baubeschreibung_clean, rest_text.strip()


def process_baubeschreibung(documents):
	"""
	Verarbeitet die JSON-Datei, extrahiert die "Baubeschreibung" und speichert sie als neue Chunks.
	Jeder Untersektion wird als eigener Chunk mit den entsprechenden Metadaten gespeichert.
	"""

	# Schritt 1: Extrahiere die Überschriften aus dem Inhaltsverzeichnis
	inhaltsverzeichnis_headings = extract_inhaltsverzeichnis_headings(documents)
	print("Inhaltsverzeichnis-Überschriften:", inhaltsverzeichnis_headings)

	if not inhaltsverzeichnis_headings:
		print("Keine Überschriften im Inhaltsverzeichnis gefunden. Bitte überprüfen Sie das Inhaltsverzeichnis.")
		return

	# Schritt 2: Verarbeite jede Eintragung und extrahiere die Baubeschreibung
	new_data = []
	for doc in documents:
		text = doc.get('text', '')
		metadata = doc.get('metadata', {})

		baubeschreibung, rest_text = extract_baubeschreibung(text, inhaltsverzeichnis_headings)

		if baubeschreibung:
			# Für jede Untersektion einen neuen Chunk erstellen
			for number, header, beschreibung in baubeschreibung:
				chunk_bb = {
					'text': beschreibung,
					'metadata': {
						**metadata,  # Kopiere bestehende Metadaten
						'section': 'Baubeschreibung',  # Füge neues Metadatenfeld hinzu
						'number': number,              # Füge die Nummer der Untersektion hinzu
						'Überschrift': header           # Füge die Überschrift der Untersektion hinzu
					}
				}
				new_data.append(chunk_bb)

			# Aktualisiere den Originaleintrag mit dem restlichen Text
			doc['text'] = rest_text

		# Füge das (eventuell modifizierte) Original-Entry hinzu
		new_data.append(doc)

	print(f"Baubeschreibung erfolgreich extrahiert.")
	return new_data


def extract_inhaltsverzeichnis_headings_level1(data):
	"""
	Extrahiert die Hauptüberschriften der Ebene 1 aus dem "Inhaltsverzeichnis" Abschnitt.
	Gibt eine Liste der Überschriften zurück.

	Args:
		data (list): Liste der Dokumente (Dictionaries) aus der JSON-Datei.

	Returns:
		list: Liste der extrahierten Überschriften im Format "Nummer. Titel".
	"""
	headings = []
	for entry in data:
		# Überprüfen, ob der Eintrag die Section "Inhaltsverzeichnis" in den Metadaten enthält
		if 'metadata' in entry and 'section' in entry['metadata'] and entry['metadata']['section'].strip().lower() == 'inhaltsverzeichnis':
			text = entry.get('text', '')
			# Ersetzen von mehrfachen Leerzeichen
			text_for_heading_extraction = re.sub(r'\s+', ' ', text)
			print("Verarbeiteter Inhaltsverzeichnis-Text:", text_for_heading_extraction)

			# Regex-Pattern zur Extraktion der Kapitelüberschriften der Ebene 1 (z.B., 1., 2., 3., ...)
			pattern = re.compile(r'(\d+)\.\s+(.+?)\s*\.+\s*\d+', re.MULTILINE)
			matches = pattern.findall(text_for_heading_extraction)
			print("Gefundene Überschriften im Inhaltsverzeichnis:", matches)

			for match in matches:
				number = match[0].strip()
				title = match[1].strip()
				headings.append(f"{number}. {title}")

			break  # Nur den ersten Inhaltsverzeichnis-Eintrag verarbeiten
	print("Extrahierte Ebene 1 Überschriften:", headings)
	return headings


def extract_ausschreibungstext(text, inhaltsverzeichnis_headings):
	"""
	Extrahiert den "Ausschreibungstext" aus dem gegebenen Text.
	Sucht nach der Überschrift der ersten Ebene aus dem Inhaltsverzeichnis und extrahiert bis zum Ende des Textes.
	Gibt den Ausschreibungstext und den restlichen Text zurück.
	"""
	# Kombiniere die Überschriften der ersten Ebene zu einem Regex-Muster
	heading_patterns = []
	for heading in inhaltsverzeichnis_headings:
		# Escape Sonderzeichen und erlauben flexible Leerzeichen
		pattern_heading = re.escape(heading).replace(r'\ ', r'\s+')
		heading_patterns.append(pattern_heading)

	if not heading_patterns:
		print("Keine Überschriften der ersten Ebene gefunden.")
		return None, text

	# Erstelle ein kombiniertes Regex-Muster für die Überschriften
	combined_pattern = re.compile(r'(' + '|'.join(heading_patterns) + r')', re.IGNORECASE | re.DOTALL)
	print("Verwendetes Überschriften-Muster:", combined_pattern.pattern)

	# Suche nach der Überschrift im Text
	match = combined_pattern.search(text)
	if not match:
		print("Keine passende Überschrift im Text gefunden.")
		return None, text

	start_index = match.start()
	print(f"Überschrift gefunden an Position {start_index}: '{match.group(0)}'")

	ausschreibungstext = text[start_index:]
	rest_text = text[:start_index]

	return ausschreibungstext.strip(), rest_text.strip()


def extract_subchapters(ausschreibungstext, metadata):
	"""
	Extrahiert Unterkapitel der Ebenen 2 und 3 aus dem Ausschreibungstext und erstellt Chunks für jedes Unterkapitel.
	Gibt eine Liste von Chunks zurück.

	Args:
		ausschreibungstext (str): Der Ausschreibungstext.
		metadata (dict): Die Metadaten des Ausschreibungstextes.

	Returns:
		list: Liste von Chunks mit Unterkapiteln der Ebenen 2 und 3.
	"""
	chunks = []

	# Regex-Pattern zur Erkennung von Level 2 und Level 3 Überschriften
	# Level 2: z.B., 1.1. Überschrift
	# Level 3: z.B., 1.1.1. Überschrift
	heading_pattern = re.compile(
		r'(?P<level>(\d+\.\d+\.\d+\.|\d+\.\d+\.))\s*(?P<title>[^\n]+)(?:\r?\n)+',
		re.MULTILINE
	)

	# Finden aller Überschriften und deren Positionen
	matches = list(heading_pattern.finditer(ausschreibungstext))
	print("Gefundene Überschriften:", [(m.group('level'), m.group('title')) for m in matches])

	# Falls keine Überschriften gefunden wurden, gesamten Text als einen Chunk zurückgeben
	if not matches:
		chunk = {
			'text': ausschreibungstext.strip(),
			'metadata': {
				**metadata,
				'subsection': None,       # Keine Unterkapitelüberschrift Ebene 2
				'subsubsection': None     # Keine Unterkapitelüberschrift Ebene 3
			}
		}
		chunks.append(chunk)
		return chunks

	# Initialisierung von Variablen zur Verfolgung der aktuellen Überschriften
	current_subsection = None
	current_subsubsection = None
	last_index = 0

	# for idx, match in enumerate(matches):
	for match in matches:
		level = match.group('level').strip()
		title = match.group('title').strip()
		start_index = match.start()
		# end_index = matches[idx + 1].start() if idx + 1 < len(matches) else len(ausschreibungstext)

		# Bestimmen der Hierarchieebene anhand der Anzahl der Punkte
		level_depth = level.count('.')

		if level_depth == 2:
			# Ebene 2 Überschrift (Format z.B. "1.1.")
			# Speichere den vorherigen Abschnitt, falls vorhanden
			if last_index < start_index:
				subchapter_text = ausschreibungstext[last_index:start_index].strip()
				if subchapter_text:
					chunk = {
						'text': subchapter_text,
						'metadata': {
							**metadata,
							'subsection': current_subsection,
							'subsubsection': current_subsubsection
						}
					}
					chunks.append(chunk)
			# Update der aktuellen Überschrift
			current_subsection = f"{level} {title}"
			current_subsubsection = None  # Zurücksetzen der Ebene 3 Überschrift
			last_index = start_index
		elif level_depth == 3:
			# Ebene 3 Überschrift (Format z.B. "1.1.1.")
			# Speichere den vorherigen Abschnitt, falls vorhanden
			if last_index < start_index:
				subchapter_text = ausschreibungstext[last_index:start_index].strip()
				if subchapter_text:
					chunk = {
						'text': subchapter_text,
						'metadata': {
							**metadata,
							'subsection': current_subsection,
							'subsubsection': current_subsubsection
						}
					}
					chunks.append(chunk)
			# Update der aktuellen Ebene 3 Überschrift
			current_subsubsection = f"{level} {title}"
			last_index = start_index

	# Den restlichen Text nach der letzten Überschrift hinzufügen
	if last_index < len(ausschreibungstext):
		subchapter_text = ausschreibungstext[last_index:].strip()
		if subchapter_text:
			chunk = {
				'text': subchapter_text,
				'metadata': {
					**metadata,
					'subsection': current_subsection,
					'subsubsection': current_subsubsection
				}
			}
			chunks.append(chunk)

	return chunks


def process_ausschreibungstext(documents):
	"""
	Verarbeitet die JSON-Datei, extrahiert den "Ausschreibungstext" sowie die Unterkapitel der Ebenen 2 und 3,
	und speichert sie als neue Chunks mit entsprechenden Metadaten.
	"""

	# Schritt 1: Extrahiere die Überschriften der ersten Ebene aus dem Inhaltsverzeichnis
	inhaltsverzeichnis_headings = extract_inhaltsverzeichnis_headings_level1(documents)

	new_data = []
	for doc in documents:
		metadata = doc.get('metadata', {})

		# Überspringe bereits verarbeitete Sektionen
		if 'section' in metadata and metadata['section'] in ['Inhaltsverzeichnis', 'Zusätzliche Vorbemerkungen', 'Baubeschreibung']:
			print(f"Überspringe Eintrag mit Section '{metadata['section']}'")
			new_data.append(doc)
			continue

		text = doc.get('text', '')
		if not text.strip():
			print("Leerer Text im Eintrag, überspringe.")
			continue

		print("Verarbeite neuen Eintrag...")

		ausschreibungstext, rest_text = extract_ausschreibungstext(text, inhaltsverzeichnis_headings)

		if ausschreibungstext:
			# Extrahiere Unterkapitel der Ebenen 2 und 3
			subchapter_chunks = extract_subchapters(ausschreibungstext, {**metadata, 'section': 'Ausschreibungstext'})
			new_data.extend(subchapter_chunks)

			# Aktualisiere den Originaleintrag mit dem restlichen Text, falls vorhanden
			if rest_text:
				doc['text'] = rest_text
				new_data.append(doc)
		else:
			# Falls kein Ausschreibungstext gefunden wurde, füge den Eintrag unverändert hinzu
			print("Kein Ausschreibungstext im Eintrag gefunden.")
			new_data.append(doc)

	print(f"Ausschreibungstext und Unterkapitel erfolgreich extrahiert.")
	return new_data


def extract_numbering(text):
	if not text:
		return None, text
	match = re.match(r'^\s*([\d\.]+)\.?\s*(.*)', text)
	if match:
		numbering = match.group(1).strip()
		text_without_numbering = match.group(2).strip()
		return numbering, text_without_numbering
	else:
		return None, text.strip()


def process_data(documents):
	for doc in documents:
		metadata = doc.get('metadata', {})
		for key in ['subsection', 'subsubsection']:
			value = metadata.get(key)
			if value:
				number, text = extract_numbering(value)
				if number:
					metadata[key + '_number'] = number
					metadata[key] = text
	return documents


def ensure_ascii_conformance(documents):
	"""
	Geht über alle Chunks in der JSON-Datei und stellt sicher, dass sie ASCII-konform sind.
	Speichert die bereinigten Chunks in einer neuen Datei.
	"""
	
	new_data = []
	for doc in documents:
		# Konvertiere den Text in ASCII
		text = doc.get('text', '')
		ascii_text = unidecode.unidecode(text)
		
		# Konvertiere die Metadaten in ASCII
		metadata = doc.get('metadata', {})
		ascii_metadata = {}
		for key, value in metadata.items():
			ascii_key = unidecode.unidecode(str(key))
			ascii_value = unidecode.unidecode(str(value))
			ascii_metadata[ascii_key] = ascii_value
		
		# Erstelle den neuen Chunk mit ASCII-konformem Text und Metadaten
		ascii_entry = {
			'text': ascii_text,
			'metadata': ascii_metadata
		}
		new_data.append(ascii_entry)
	
	print(f"Alle Chunks wurden ASCII-konform gemacht.")
	return new_data


def flatten_structure(documents):
	new_data = []
	for doc in documents:
		metadata = doc.get("metadata", {})
		keywords = [
			metadata.get("keyword", ""),
			metadata.get("section", ""),
			metadata.get("subsection", ""),
			metadata.get("subsubsection", ""),
			metadata.get("subsection_number", ""),
			metadata.get("subsubsection_number", ""),
			metadata.get("number", "")
		]
		keywords = [
			keyword for keyword in keywords
			if keyword and keyword != "None"
		]
		keywords = " ".join(keywords).split()
		doc["keywords"] = keywords
		new_data.append(doc)
	return new_data


def make_summaries(documents):
	new_docs = []
	for doc in documents:
		res = SUMMARIZER.invoke(doc["text"])	# den Text zu Zusammenfassung eingeben
		summary = res.content
		doc["summary"] = summary
		new_docs.append(doc)
	return new_docs


def save_results(documents, output_path):
	try:
		with open(output_path, 'w', encoding='utf-8') as f:
			json.dump(documents, f, ensure_ascii=False, indent=4)
		print(f"Ergebnisse erfolgreich in '{output_path}' gespeichert.")
	except Exception as e:
		print(f"Fehler beim Speichern der Ergebnisse: {e}")


def prepare_data(pdf_path):
	# TODO: refactoring
	documents = [process_pdf(pdf_path)]
	documents = process_documents(documents)
	documents = process_json(documents)
	documents = process_vorbemerkungen(documents)
	documents = process_baubeschreibung(documents)
	documents = process_ausschreibungstext(documents)
	documents = process_data(documents)
	documents = ensure_ascii_conformance(documents)
	documents = make_summaries(documents)
	documents = flatten_structure(documents)
	return documents