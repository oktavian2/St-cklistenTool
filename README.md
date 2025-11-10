# Stücklisten-Tool

Ein einfaches Terminalwerkzeug, um Stücklisten (Bill of Materials, BOM) und Produktionsbedarfe für HiL-Schränke zu verwalten. Die Daten werden in einer SQLite-Datei gespeichert.

## Installation & Ausführung

Python 3.11 oder neuer wird empfohlen. Abhängigkeiten außerhalb der Standardbibliothek sind nicht erforderlich.

1. Öffne ein Terminal **im Projektordner** (z. B. `cd C:\Repos\St-cklistenTool` unter Windows oder `cd /pfad/zu/St-cklistenTool` unter Linux/macOS).
2. Führe `python -m stuecklisten_tool --help` aus, um alle verfügbaren Befehle zu sehen.

> 💡 Wenn die Meldung `ModuleNotFoundError: No module named 'stuecklisten_tool'` erscheint, bist du höchstwahrscheinlich nicht im Projektverzeichnis. Navigiere in den Ordner, der den Unterordner `stuecklisten_tool` enthält, oder rufe alternativ `python stuecklisten_tool/cli.py --help` auf.

Optional kannst du das Projekt auch lokal installieren, um den Befehl systemweit zu nutzen:

```bash
python -m pip install -e .
stuecklisten-tool --help
```

## Grafische Oberfläche

Neben dem Terminal-Interface gibt es eine Oberfläche auf Basis von Tkinter. Alle Tabellen besitzen Suchfelder und lassen sich per Spaltenkopf sortieren – so findest du auch bei großen Datenbeständen schnell die passenden Einträge. Zusätzlich zur Pflege von Teilen, Produkten und Stücklisten bietet der Auswertungsbereich nun:

- einen Überblick über den aggregierten Teilebedarf inklusive Hersteller- und Lieferanteninformationen,
- eine zweite Übersicht, die den Gesamtbedarf pro Lieferant aufschlüsselt,
- einen Reiter „Bestellungen“ zum Erfassen, Aktualisieren und Verfolgen von Bestellungen – inklusive Mehrfach-Positionen sowie Kalender- bzw. Heute-Schaltflächen für Bestell- und Lieferdatum.

```bash
python -m stuecklisten_tool gui
# oder nach Installation:
stuecklisten-tool gui
```

Per Dropdown „Datenbank“ (`--db`) kann wie gewohnt eine alternative SQLite-Datei angegeben werden:

```bash
python -m stuecklisten_tool --db pfad/zur/datei.db gui
```

## Datenbank

Standardmäßig legt das Programm eine Datei `stuecklisten.db` im aktuellen Verzeichnis an. Mit `--db` kann ein anderer Speicherort gewählt werden. Der Befehl `init-db` erzeugt das Schema manuell, alle anderen Befehle initialisieren die Datenbank automatisch.

## Wichtige Befehle

| Befehl | Beschreibung |
| --- | --- |
| `init-db` | Datenbankschema anlegen |
| `add-part` / `update-part` / `remove-part` | Teile (inkl. Herstellerinformationen) verwalten |
| `add-product` / `update-product` / `remove-product` | Produkte (HiL-Schränke) verwalten |
| `set-bom-entry` | Teil mit Menge einer Stückliste zuordnen |
| `set-demand` | Produktionsbedarf für ein Produkt hinterlegen |
| `calculate-requirements` | Gesamte Teilebedarfe und Kosten über alle Produkte berechnen |
| `supplier-summary` | Aggregierte Bedarfe pro Lieferant anzeigen |
| `predict-bom` | Stückliste eines bestehenden Produkts kopieren (optional mit Skalierung) |
| `create-version`, `list-versions`, `show-version` | Momentaufnahme der aktuellen Daten speichern und anzeigen |
| `add-order` / `update-order` / `remove-order` | Bestellungen zu Teilen verwalten |
| `list-orders` | Alle Bestellungen auflisten |

Alle Befehle besitzen weitere Optionen. Die vollständige Übersicht liefert `python -m stuecklisten_tool --help` oder `python -m stuecklisten_tool <befehl> --help`.

## Beispielablauf

```bash
# Datenbank initialisieren
python -m stuecklisten_tool init-db

# Teil und Produkt anlegen
python -m stuecklisten_tool add-part T1 --description "Netzteil" --manufacturer "ACME Energy" --supplier "ACME" --price 49,90
python -m stuecklisten_tool add-product "HiL Schrank 1" --description "Standardausführung"

# Stückliste und Bedarf erfassen
python -m stuecklisten_tool set-bom-entry "HiL Schrank 1" T1 3
python -m stuecklisten_tool set-demand "HiL Schrank 1" 2

# Gesamten Teilebedarf berechnen
python -m stuecklisten_tool calculate-requirements

# Bedarf pro Lieferant anzeigen
python -m stuecklisten_tool supplier-summary

# Bestellung anlegen und verwalten
python -m stuecklisten_tool add-order --item T1=6 --item T2=3 --order-date 2024-05-01 --status "Bestellt"
python -m stuecklisten_tool list-orders
```

## Bestellungen & Lieferübersichten

Mit dem Bestellmodul kannst du komplette Aufträge mit beliebig vielen Positionen erfassen. Im Terminal gibst du jede Position über `--item TEIL=MENGE` an; die GUI erlaubt das komfortable Hinzufügen, Bearbeiten und Entfernen mehrerer Teile pro Bestellung und bietet für beide Datumsfelder eine Kalenderauswahl sowie eine „Heute“-Schaltfläche. Die Auswertung zeigt zusätzlich, wie viele Teile pro Lieferant insgesamt benötigt werden – so hast du sowohl Bedarf als auch offene Bestellungen jederzeit im Blick.

## Versionierung

`create-version` erstellt eine Momentaufnahme der aktuellen Stücklisten und Bedarfe. Mit `show-version` können die Inhalte später nachgeschlagen werden. Die Daten werden in der gleichen SQLite-Datei gespeichert.

## JSON-Schnittstellen

Für den Datenaustausch stehen JSON-Ausgaben zur Verfügung:

- `calculate-requirements --as-json`
- `show-version --as-json`

Damit lassen sich Daten einfach in andere Systeme importieren oder für weitere Analysen verwenden.
