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

Neben dem Terminal-Interface gibt es eine einfache Oberfläche auf Basis von Tkinter. Sie zeigt Teile, Produkte, Stücklisten sowie den aggregierten Teilebedarf an und erlaubt das Bearbeiten der wichtigsten Daten.

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
| `add-part` / `update-part` / `remove-part` | Teile verwalten |
| `add-product` / `update-product` / `remove-product` | Produkte (HiL-Schränke) verwalten |
| `set-bom-entry` | Teil mit Menge einer Stückliste zuordnen |
| `set-demand` | Produktionsbedarf für ein Produkt hinterlegen |
| `calculate-requirements` | Gesamte Teilebedarfe und Kosten über alle Produkte berechnen |
| `predict-bom` | Stückliste eines bestehenden Produkts kopieren (optional mit Skalierung) |
| `create-version`, `list-versions`, `show-version` | Momentaufnahme der aktuellen Daten speichern und anzeigen |

Alle Befehle besitzen weitere Optionen. Die vollständige Übersicht liefert `python -m stuecklisten_tool --help` oder `python -m stuecklisten_tool <befehl> --help`.

## Beispielablauf

```bash
# Datenbank initialisieren
python -m stuecklisten_tool init-db

# Teil und Produkt anlegen
python -m stuecklisten_tool add-part T1 --description "Netzteil" --supplier "ACME" --price 49.9
python -m stuecklisten_tool add-product "HiL Schrank 1" --description "Standardausführung"

# Stückliste und Bedarf erfassen
python -m stuecklisten_tool set-bom-entry "HiL Schrank 1" T1 3
python -m stuecklisten_tool set-demand "HiL Schrank 1" 2

# Gesamten Teilebedarf berechnen
python -m stuecklisten_tool calculate-requirements
```

## Versionierung

`create-version` erstellt eine Momentaufnahme der aktuellen Stücklisten und Bedarfe. Mit `show-version` können die Inhalte später nachgeschlagen werden. Die Daten werden in der gleichen SQLite-Datei gespeichert.

## JSON-Schnittstellen

Für den Datenaustausch stehen JSON-Ausgaben zur Verfügung:

- `calculate-requirements --as-json`
- `show-version --as-json`

Damit lassen sich Daten einfach in andere Systeme importieren oder für weitere Analysen verwenden.
