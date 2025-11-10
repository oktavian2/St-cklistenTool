# Stücklisten-Tool

Ein einfaches Terminalwerkzeug, um Stücklisten (Bill of Materials, BOM) und Produktionsbedarfe für HiL-Schränke zu verwalten. Die Daten werden in einer SQLite-Datei gespeichert.

## Installation

Python 3.11 oder neuer wird empfohlen. Abhängigkeiten außerhalb der Standardbibliothek sind nicht erforderlich.

```bash
python -m stuecklisten_tool --help
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
