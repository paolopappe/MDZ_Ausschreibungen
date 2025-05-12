# Prusseit und Reiss - Suchtool für Ausschreibungstexte

* [Übersicht](#übersicht)
* [Installation](#installation)
* [Benutzung](#benutzung)


## Übersicht

Dieses Suchtool hilft mittels Ähnlichkeitssuche relevante Informationen aus Ausschreibungstexten zu extrahieren und bereitzustellen.

Funktionsweise:

1. Die Ausschreibungstexte liegen als PDFs vor und werden folgendermaßen vorverarbeitet: 
Kapitel bzw. Unterkapitel werden als Textbausteine (Chunks) aus der PDF extrahiert. Mithilfe eines LLMs werden für jeden Chunk zusätzlich Stichwörter, sogenannte Metadaten, abgespeichert. Diese Metadaten enhalten Projektnamen, Kapitelüberschrift etc.
Zusätzlich werden mithilfe eines LLMs stichwortartige Zusammenfassungen pro Chunktextinhalt generiert.
2. Das Tool ist in der Lage eine Suchanfrage anzunehmen und aus der Anfrage die relevanten Stichwörter zu extrahieren..
3. Die von der Anfrage extrahierten und in den vorbereiteten Chunks liegenden Stichwörter (Zusammenfassungen) werden nach semantischer Ähnlichkeit abgeglichen. Dem/der Nutzer*in werden die Chunks ausgegeben, die am ehesten zur Anfrage passen.

Weitere Informationen zum Ansatz finden Sie in der [Präsentation](./Prusseit_u_Reiss_aktueller_Stand.pptx).


## Installation

### Voraussetzungen

1. Installation Git: Installieren Sie Git; laden Sie es bitte unter https://git-scm.com herunter und folgen Sie den Installationsanweisungen.
2. Installation Docker Desktop App: Installieren sie die Docker Desktop App; laden Sie es bitte unter https://www.docker.com/products/docker-desktop/ herunter und folgen Sie den Installationsanweisungen.
3. Zu Verwendung des Suchtools benötigen Zugang zum OpenAI GPT-4o Modell. Hierfür müssen Sie einen OpenAI-Account erstellen.  Gehen sie auf https://platform.openai.com/docs/overview und erstellen Sie sich einen Account.
Um ein Modell verwenden zu können, müssen Sie über mittels einer Kreditkarte Guthaben hochladen. Folgen Sie hierbei den Anweisungen von OpenAI. Anschließend können Sie sich einen API-Key erstellen lassen (https://platform.openai.com/settings/organization/api-keys) **Diesen API-Key sollten Sie in keinem Fall an Dritte weitergegeben!**


### Installationsschritte

1. Die Docker Desktop App starten.

2. Das github-Repo (s.u.) auf Ihr Gerät klonen. 
Dazu öffnen/erstellen Sie in Ihrem Windows-Explorer unter dem gewünschten Pfad einen Ordner, unter dem Sie das Suchtool speichern möchten.
Machen Sie dort (in diesem Explorer-Fenster) einen Rechtsklick und öffnen Sie die Git Bash (vielleicht unter weitere Optionen). 
Geben Sie in Git Bash nacheinander die folgenden Befehle ein (jeweils danach mit der Enter-Taste bestätigen).
(Ggf. funktioniert Str+v zum hineinkopieren nicht. Stattdessen Rechtsklick + Einfügen):

```bash

git clone https://github.com/paolopappe/MDZ_Ausschreibung_LLM.git

cd MDZ_Ausschreibung_LLM
```

3. Den API-Key, den Sie zuvor auf der OpenAI-Platform generiert haben, müssen Sie nun in der _env.template_ - Datei einsetzen. Der API-Key kann nur 1mal erstellt und kopiert werden, ansonsten müssen sie einen neuen Key erstellen.
Benennen Sie die Datei anschließend in _.env_ um.

4. Erstellen Sie nun ein Docker-Image: Hierbei wird eine Kopie des Suchtools auf Ihrem Gerät erstellt. Geben Sie in der Git Bash folgenden Command ein:

```bash
docker build -t prusseit_reiss_suchtool:latest . 
```

Warten Sie nun ein paar Minuten.

5. Nun können Sie das Suchtool mit folgendem Befehl starten:

```bash
docker run -p 8501:8501 --env-file .env --volume prusseit_reiss:/ausschreibungen_storage prusseit_reiss_suchtool:latest
```

6. Nachdem Sie den letzten Command ausgeführt haben, können Sie das Suchtool auf Ihrem Endgerät verwenden. Um darauf zuzugreifen, öffnen Sie einen beliebigen Browser und geben Sie folgendes in die Adressleiste ein:

```text
http://localhost:8501
```


## Benutzung

1. Im ersten Schritt müssen Sie unter "Datenverwaltung" die Ausschreibungen per Drag & Drop hochladen. Während des Hochladens werden die Dokumente vorverarbeitet. Die kann ein paar Minuten dauern. **Das Hochladen von Dokumenten muss nur einmal erfolgen.** Zu einem späteren Zeitpunkt können Sie weitere Aussschreibungen hinzufügen oder alte Ausschreibungen löschen. 

2. Nach der Befüllung der "Datenbanke" können Sie unter "Suche" Ihre Anfrage eingeben.

3. Nach der Benutzung stoppen Sie den Container, indem Sie in der git Bash _Ctrl+C_ clicken.

4. Für die wiederholte Benutzung des Suchtools, müssen Sie nach der Installation nur noch die Punkte 5 und 6 durchführen.
