# prepare_data.py

import os
import io
import re
import unicodedata
import unidecode
import json
from typing import List, Dict, Union

from dotenv import load_dotenv

# PyPDF2 und openai / langchain_openai
import openai
from PyPDF2 import PdfReader
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate

# -------------------------------------------------------------------------
# Laden der Umgebungsvariablen und OpenAI-API-Key
# -------------------------------------------------------------------------
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# -------------------------------------------------------------------------
# Prompt-Template für die Zusammenfassung
# -------------------------------------------------------------------------
SUMMARY_PROMPT = """\
Hier sind ein Text und einige Metadaten.

TEXT:
{text}

METADATEN:
{metadata}

AUFGABE:
- Prüfe die Länge des obigen Textes.
- Falls der Text weniger als 300 Tokens hat, gibt den ursprünglichen Text und die Metadaten unverändert zurück.
- Falls der Text 300 Tokens oder mehr hat, schreibe eine prägnante und vollständige Zusammenfassung in 350-400 Tokens,
  die alle relevanten Aspekte aus Text und Metadaten abdeckt.
  Achte darauf, alle wichtigen Informationen klar wiederzugeben.
  Die Zusammenfassung soll den ursprünglichen Inhalt möglichst gut repräsentieren.
  Schreibe direkt die Zusammenfassung ohne davor mitzuteilen, wie viele Token der Text hat. Starte mit "Zusammenfassung:"


=================
"""

SUMMARY_TEMPLATE = ChatPromptTemplate.from_template(SUMMARY_PROMPT)

LLM = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    openai_api_key=openai.api_key
)

SUMMARIZER = SUMMARY_TEMPLATE | LLM

# ------------------------------------------------------------------------------
# Muster / Zeilen entfernen (angepasst an Ihre Anforderung)
# ------------------------------------------------------------------------------
PATTERNS_TO_REMOVE = [
    r'^Druckdatum:\s+[\d\.]+\s+Seite:\s+\d+$',
    r'^Prusseit\s+u\.\s+R\s*eiss\s+Bauplanungsbüro\s+GmbH$',
    r'Gutenbergstr\..*Garbsen.*Telefon.*Telefax',
    r'e-mail:\s*info@prusseitundreiss\.de',
    r'\(Ort, Datum, Unterschrift und Stempel\)',
    r'^Leistungsverzeichnis\s+Kurz-\s*und\s+Langtext$',
    r'^Ordnungszahl\s+Leistungsbeschreibung\s+Menge\s+ME\s+Einheit\s*spreis\s+Gesamtbetrag$',
    r'^in\s+EUR\s+in\s+EUR$'
]
COMPILED_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in PATTERNS_TO_REMOVE]

# ------------------------------------------------------------------------------
# Hilfsfunktionen
# ------------------------------------------------------------------------------
def clean_metadata(metadata: Dict) -> Dict:
    """Säubert Metadaten (Unicode-Entfernung)."""
    cleaned_metadata = {}
    for key, value in metadata.items():
        if isinstance(value, str):
            normalized = unicodedata.normalize('NFKD', value)
            cleaned_value = normalized.encode('ascii', 'ignore').decode('ascii')
            cleaned_metadata[key] = cleaned_value
        else:
            cleaned_metadata[key] = str(value)
    return cleaned_metadata

# ------------------------------------------------------------------------------
# Schritt 1: PDF lesen + bereinigen (Pfad ODER Bytes)
# ------------------------------------------------------------------------------
def read_and_clean_pdf(pdf_input: Union[str, bytes, tuple]) -> List[Dict]:
    if isinstance(pdf_input, tuple):
        pdf_path, pdf_bytes = pdf_input
        fileobj = io.BytesIO(pdf_bytes)
        dateiname = os.path.basename(pdf_path)

    elif isinstance(pdf_input, str):
        # -> Pfad
        pdf_path = pdf_input
        fileobj = open(pdf_path, "rb")
        dateiname = os.path.basename(pdf_path)

    else:
        # -> Bytes, ohne Pfad
        pdf_bytes = pdf_input
        fileobj = io.BytesIO(pdf_bytes)
        dateiname = "uploaded_file.pdf"  # Fallback

    # Dann wie gehabt Auslesen via PyPDF2
    reader = PdfReader(fileobj)
    cleaned_pages = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        lines = page_text.split('\n')
        cleaned_lines = []
        for line in lines:
            normalized_line = ' '.join(line.split())
            if any(pattern.search(normalized_line) for pattern in COMPILED_PATTERNS):
                continue
            cleaned_lines.append(line)
        cleaned_pages.append('\n'.join(cleaned_lines))

    fileobj.close()

    # Text zusammenführen + Metadaten bereinigen
    full_text = "\n".join(cleaned_pages)
    metadata = {"Dateiname": dateiname}
    cleaned_metadata = clean_metadata(metadata)

    return [{
        "text": full_text,
        "metadata": cleaned_metadata
    }]


# ------------------------------------------------------------------------------
#  Schritt 2: Inhaltsverzeichnis extrahieren
# ------------------------------------------------------------------------------
def extract_inhaltsverzeichnis(text: str):
    pattern_start = re.compile(r'Inhaltsverzeichnis', re.IGNORECASE)
    pattern_end = re.compile(r'Zusammenstellung.*(?:\n|$)', re.IGNORECASE)

    start_match = pattern_start.search(text)
    if not start_match:
        return None, text

    start_index = start_match.start()
    end_match = pattern_end.search(text, start_match.end())
    end_index = end_match.end() if end_match else len(text)

    ivz = text[start_index:end_index].strip()
    rest = (text[:start_index] + text[end_index:]).strip()
    return ivz, rest

def process_inhaltsverzeichnis(docs: List[Dict]) -> List[Dict]:
    new_data = []
    for doc in docs:
        text = doc.get('text', '')
        metadata = doc.get('metadata', {})

        ivz, rest_text = extract_inhaltsverzeichnis(text)
        if ivz:
            new_data.append({
                'text': ivz,
                'metadata': {**metadata, 'section': 'Inhaltsverzeichnis'}
            })
            doc['text'] = rest_text

        new_data.append(doc)
    return new_data

# ------------------------------------------------------------------------------
#  Schritt 3: Zusätzliche Vorbemerkungen extrahieren
# ------------------------------------------------------------------------------
def extract_vorbemerkungen(text: str):
    pattern_start = re.compile(r'Zusätzliche\s+Vorbemerkungen', re.IGNORECASE)
    pattern_end = re.compile(r'Baubeschreibung', re.IGNORECASE)

    start_match = pattern_start.search(text)
    if not start_match:
        return [], text

    start_index = start_match.end()
    end_match = pattern_end.search(text, start_index)
    end_index = end_match.start() if end_match else len(text)

    segment_vorbem = text[start_match.end():end_index]
    rest_text = text[:start_match.start()] + text[end_index:]

    segment_vorbem = re.sub(r'\s+', ' ', segment_vorbem)
    list_item_pattern = re.compile(r'(\d+)\.\s+(.*?)(?=\s+\d+\.|\Z)', re.DOTALL)
    matches = list_item_pattern.findall(segment_vorbem)

    vorbem_extracted = []
    for number, txt in matches:
        clean_item = re.sub(r'\s+', ' ', txt).strip()
        vorbem_extracted.append((number, clean_item))

    return vorbem_extracted, rest_text.strip()

def process_vorbemerkungen(docs: List[Dict]) -> List[Dict]:
    new_data = []
    for doc in docs:
        text = doc.get('text', '')
        metadata = doc.get('metadata', {})

        vorbem, rest = extract_vorbemerkungen(text)
        if vorbem:
            for number, content in vorbem:
                new_data.append({
                    'text': content,
                    'metadata': {**metadata, 'section': 'Zusätzliche Vorbemerkungen'}
                })
            doc['text'] = rest

        new_data.append(doc)
    return new_data

# ------------------------------------------------------------------------------
#  Schritt 4: Baubeschreibung extrahieren
# ------------------------------------------------------------------------------
def extract_inhaltsverzeichnis_headings(docs: List[Dict]) -> List[str]:
    headings = []
    for doc in docs:
        if doc['metadata'].get('section', '').lower() == 'inhaltsverzeichnis':
            text = doc['text'].replace('\n', ' ')
            pattern = re.compile(r'(\d+(?:\.\d+)*)\.\s+(.+?)\s*\.+\s*\d+')
            found = pattern.findall(text)
            for num, title in found:
                headings.append(f"{num}. {title.strip()}")
            break
    return headings

def extract_baubeschreibung(text: str, headings_level1: List[str]):
    pattern_start = re.compile(r'Baubeschreibung', re.IGNORECASE)
    start_match = pattern_start.search(text)
    if not start_match:
        return [], text

    start_index = start_match.end()

    numbering_patterns = []
    pattern_number = re.compile(r'^(\d+(?:\.\d+)*)\.')
    for heading in headings_level1:
        match = pattern_number.match(heading)
        if match:
            number = re.escape(match.group(1) + '.')
            numbering_patterns.append(number)

    if not numbering_patterns:
        end_index = len(text)
    else:
        combined = re.compile(r'(' + '|'.join(numbering_patterns) + r')\s')
        end_match = combined.search(text, start_index)
        end_index = end_match.start() if end_match else len(text)

    bb_text = text[start_index:end_index]
    rest_text = text[:start_match.start()] + text[end_index:]

    bb_text = re.sub(r'\s+', ' ', bb_text)
    subsection_pattern = re.compile(
        r'(\d+\.\d+)\s+([^:]+):\s+(.*?)(?=\s+\d+\.\d+\s+[^:]+:|\Z)',
        re.DOTALL
    )
    subsections = subsection_pattern.findall(bb_text)

    cleaned_baubeschreibung = []
    for number, header, inhalt in subsections:
        clean_item = re.sub(r'\s+', ' ', inhalt).strip()
        cleaned_baubeschreibung.append((number, header.strip(), clean_item))

    return cleaned_baubeschreibung, rest_text.strip()

def process_baubeschreibung(docs: List[Dict]) -> List[Dict]:
    headings = extract_inhaltsverzeichnis_headings(docs)
    new_data = []

    for doc in docs:
        text = doc.get('text', '')
        metadata = doc.get('metadata', {})

        bb, rest = extract_baubeschreibung(text, headings)
        if bb:
            for number, header, inhalt in bb:
                new_data.append({
                    'text': inhalt,
                    'metadata': {**metadata, 'section': 'Baubeschreibung'}
                })
            doc['text'] = rest

        new_data.append(doc)
    return new_data

# ------------------------------------------------------------------------------
#  Schritt 5: Ausschreibungstext extrahieren
# ------------------------------------------------------------------------------
def extract_inhaltsverzeichnis_headings_level1(docs: List[Dict]) -> List[str]:
    headings = []
    for doc in docs:
        if doc['metadata'].get('section', '').lower() == 'inhaltsverzeichnis':
            text = re.sub(r'\s+', ' ', doc['text'])
            pattern = re.compile(r'(\d+)\.\s+(.+?)\s*\.+\s*\d+')
            found = pattern.findall(text)
            for num, title in found:
                headings.append(f"{num}. {title.strip()}")
            break
    return headings

def extract_ausschreibungstext(text: str, headings_level1: List[str]):
    if not headings_level1:
        return None, text

    patterns = []
    for heading in headings_level1:
        pat = re.escape(heading).replace(r'\ ', r'\s+')
        patterns.append(pat)
    combined_pattern = re.compile(r'(' + '|'.join(patterns) + r')', re.IGNORECASE)

    match = combined_pattern.search(text)
    if not match:
        return None, text

    start_index = match.start()
    ausschreibung = text[start_index:].strip()
    rest = text[:start_index].strip()

    return ausschreibung, rest

def extract_subchapters(ausschreibungstext: str, base_metadata: Dict) -> List[Dict]:
    chunks = []
    if not ausschreibungstext.strip():
        return [{'text': ausschreibungstext, 'metadata': base_metadata}]

    heading_pattern = re.compile(
        r'(?P<level>(\d+\.\d+\.\d+\.|\d+\.\d+\.))\s*(?P<title>[^\n]+)(?:\r?\n)+',
        re.MULTILINE
    )

    matches = list(heading_pattern.finditer(ausschreibungstext))
    if not matches:
        return [{
            'text': ausschreibungstext.strip(),
            'metadata': {**base_metadata}
        }]

    last_index = 0
    current_subsection = None
    current_subsubsection = None

    for m in matches:
        level = m.group('level').strip()
        title = m.group('title').strip()
        start_index = m.start()

        # Text bis zum Start dieser Überschrift
        if last_index < start_index:
            text_segment = ausschreibungstext[last_index:start_index].strip()
            if text_segment:
                chunks.append({
                    'text': text_segment,
                    'metadata': {
                        **base_metadata,
                        'subsection': current_subsection,
                        'subsubsection': current_subsubsection
                    }
                })

        level_depth = level.count('.')
        if level_depth == 2:
            current_subsection = f"{level} {title}"
            current_subsubsection = None
        elif level_depth == 3:
            current_subsubsection = f"{level} {title}"

        last_index = start_index

    # Den Rest anhängen
    if last_index < len(ausschreibungstext):
        text_segment = ausschreibungstext[last_index:].strip()
        if text_segment:
            chunks.append({
                'text': text_segment,
                'metadata': {
                    **base_metadata,
                    'subsection': current_subsection,
                    'subsubsection': current_subsubsection
                }
            })

    return chunks

def process_ausschreibungstext(docs: List[Dict]) -> List[Dict]:
    headings_level1 = extract_inhaltsverzeichnis_headings_level1(docs)
    new_data = []

    for doc in docs:
        md = doc.get('metadata', {})
        if md.get('section') in ['Inhaltsverzeichnis', 'Zusätzliche Vorbemerkungen', 'Baubeschreibung']:
            new_data.append(doc)
            continue

        text = doc.get('text', '')
        ausschreibung, rest = extract_ausschreibungstext(text, headings_level1)
        if ausschreibung:
            subchapters = extract_subchapters(ausschreibung, {**md, 'section': 'Ausschreibungstext'})
            new_data.extend(subchapters)

            if rest:
                doc['text'] = rest
                new_data.append(doc)
        else:
            new_data.append(doc)

    return new_data

# ------------------------------------------------------------------------------
#  Schritt 6: Nummerierungen vereinheitlichen
# ------------------------------------------------------------------------------
def extract_numbering_and_remainder(full_str: str):
    match = re.match(r'^\s*([\d\.]+)\s+(.*)', full_str)
    if match:
        numbering = match.group(1).strip()
        remainder = match.group(2).strip()
        return numbering, remainder
    return None, full_str.strip()

def unify_numberings_in_metadata(docs: List[Dict]) -> List[Dict]:
    for doc in docs:
        md = doc.get('metadata', {})
        # subsection
        if md.get('subsection'):
            num, remainder = extract_numbering_and_remainder(md['subsection'])
            if num:
                md['subsection_number'] = num
                md['subsection'] = remainder

        # subsubsection
        if md.get('subsubsection'):
            num, remainder = extract_numbering_and_remainder(md['subsubsection'])
            if num:
                md['subsubsection'] = remainder

    return docs

# ------------------------------------------------------------------------------
#  Schritt X: Junk entfernen
# ------------------------------------------------------------------------------
def remove_junk_chunks(docs: List[Dict]) -> List[Dict]:
    single_line_pattern = re.compile(
        r'^[0-9]+\.[0-9]+(\.[0-9]+)*\.?\s+.+\.+\s*$'
    )

    cleaned = []
    for doc in docs:
        txt = doc.get("text", "").strip()
        if not txt:
            cleaned.append(doc)
            continue

        lines = txt.splitlines()
        single_line_match = (
            len(lines) == 1
            and single_line_pattern.match(lines[0])
            and len(txt) < 200
        )

        has_zusammenstellung = "zusammenstellung" in txt.lower()
        has_projekt = "projekt:" in txt.lower()
        matches_numbering = bool(re.search(r'^\s*\d+\.\d+', txt, re.MULTILINE))
        is_short = len(txt) < 600

        multi_line_match = (
            has_zusammenstellung
            and has_projekt
            and matches_numbering
            and is_short
        )

        if single_line_match or multi_line_match:
            continue

        cleaned.append(doc)

    return cleaned

# ------------------------------------------------------------------------------
#  Schritt 7: ASCII-Konvertierung
# ------------------------------------------------------------------------------
def ensure_ascii_conformance(docs: List[Dict]) -> List[Dict]:
    new_data = []
    for doc in docs:
        ascii_text = unidecode.unidecode(doc['text'])
        ascii_md = {}
        for k, v in doc.get('metadata', {}).items():
            ak = unidecode.unidecode(str(k))
            av = unidecode.unidecode(str(v))
            ascii_md[ak] = av

        new_data.append({'text': ascii_text, 'metadata': ascii_md})
    return new_data

# ------------------------------------------------------------------------------
#  Schritt 8: Zusammenfassung erstellen (mit Token-Logik)
# ------------------------------------------------------------------------------
try:
    import tiktoken
    def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
        enc = tiktoken.encoding_for_model(model)
        return len(enc.encode(text))
except ImportError:
    def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
        # Fallback: sehr grobe Heuristik
        words = len(text.split())
        return int(words / 1.3)

def make_summaries(docs: List[Dict]) -> List[Dict]:
    new_docs = []
    for doc in docs:
        txt = doc.get("text", "").strip()
        md = doc.get("metadata", {})

        # Metadaten in menschenlesbarem String
        meta_str = []
        if "Dateiname" in md:
            meta_str.append(f"Dateiname: {md['Dateiname']}")
        if "section" in md:
            meta_str.append(f"section: {md['section']}")
        if "subsection" in md:
            meta_str.append(f"subsection: {md['subsection']}")
        if "subsubsection" in md:
            meta_str.append(f"subsubsection: {md['subsubsection']}")
        if "subsection_number" in md:
            meta_str.append(f"subsection_number: {md['subsection_number']}")

        meta_as_text = "\n".join(meta_str).strip()

        # Token-Zählung
        token_count = count_tokens(txt)

        # < 300 Tokens -> Originaltext inkl. Metadaten
        if token_count < 300:
            doc["summary"] = f"{txt}\n\n[METADATEN]\n{meta_as_text}"
        else:
            prompt_input = {"text": txt, "metadata": meta_as_text}
            result = SUMMARIZER.invoke(prompt_input)
            doc["summary"] = result.content

        new_docs.append(doc)
    return new_docs

# ------------------------------------------------------------------------------
#  Komplette Pipeline
# ------------------------------------------------------------------------------
def prepare_data(pdf_input: Union[str, bytes, tuple]) -> List[Dict]:
    """
    pdf_input kann sein:
    - Ein Pfad (str),
    - Nur Bytes (bytes),
    - Oder (filename, bytes) als Tuple.
    """
    documents = read_and_clean_pdf(pdf_input)

    # 2) Inhaltsverzeichnis
    documents = process_inhaltsverzeichnis(documents)

    # 3) Vorbemerkungen
    documents = process_vorbemerkungen(documents)

    # 4) Baubeschreibung
    documents = process_baubeschreibung(documents)

    # 5) Ausschreibungstext
    documents = process_ausschreibungstext(documents)

    # 6) Nummerierungen vereinheitlichen
    documents = unify_numberings_in_metadata(documents)

    # 7) Junk entfernen
    documents = remove_junk_chunks(documents)

    # 8) ASCII
    documents = ensure_ascii_conformance(documents)

    # 9) Summaries
    documents = make_summaries(documents)

    return documents
