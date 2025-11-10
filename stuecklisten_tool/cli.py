"""Command line interface for the Stücklisten-Tool."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import database
from .operations import (
    Part,
    Product,
    clone_bom,
    create_version,
    fetch_requirements,
    list_parts,
    list_product_requirements,
    list_products,
    list_versions,
    remove_bom_entry,
    remove_part,
    remove_product,
    remove_requirement,
    set_bom_entry,
    set_product_requirement,
    update_part,
    update_product,
    add_part,
    add_product,
    get_version_details,
)

DEFAULT_DB_PATH = Path("stuecklisten.db")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verwaltung von Stücklisten und Anforderungen")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Pfad zur SQLite-Datenbank (Standard: {DEFAULT_DB_PATH})",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Initialisiert das Datenbankschema")

    part_parser = subparsers.add_parser("add-part", help="Neues Teil anlegen")
    part_parser.add_argument("part_number")
    part_parser.add_argument("--description")
    part_parser.add_argument("--supplier")
    part_parser.add_argument("--price", type=float)
    part_parser.add_argument("--store-link")

    update_part_parser = subparsers.add_parser("update-part", help="Teil aktualisieren")
    update_part_parser.add_argument("part_number")
    update_part_parser.add_argument("--description")
    update_part_parser.add_argument("--supplier")
    update_part_parser.add_argument("--price", type=float)
    update_part_parser.add_argument("--store-link")

    subparsers.add_parser("list-parts", help="Alle Teile anzeigen")

    delete_part_parser = subparsers.add_parser("remove-part", help="Teil löschen")
    delete_part_parser.add_argument("part_number")

    product_parser = subparsers.add_parser("add-product", help="Produkt anlegen")
    product_parser.add_argument("name")
    product_parser.add_argument("--description")

    update_product_parser = subparsers.add_parser("update-product", help="Produkt aktualisieren")
    update_product_parser.add_argument("name")
    update_product_parser.add_argument("--description")

    subparsers.add_parser("list-products", help="Produkte und aktuelle Bedarfe anzeigen")

    delete_product_parser = subparsers.add_parser("remove-product", help="Produkt löschen")
    delete_product_parser.add_argument("name")

    bom_parser = subparsers.add_parser("set-bom-entry", help="Teil zu Produkt mit Menge zuordnen")
    bom_parser.add_argument("product")
    bom_parser.add_argument("part")
    bom_parser.add_argument("quantity", type=float)

    remove_bom_parser = subparsers.add_parser("remove-bom-entry", help="Eintrag aus Stückliste löschen")
    remove_bom_parser.add_argument("product")
    remove_bom_parser.add_argument("part")

    demand_parser = subparsers.add_parser("set-demand", help="Losgröße/Bedarf eines Produkts festlegen")
    demand_parser.add_argument("product")
    demand_parser.add_argument("quantity", type=float)

    remove_demand_parser = subparsers.add_parser("remove-demand", help="Bedarfseintrag löschen")
    remove_demand_parser.add_argument("product")

    subparsers.add_parser("list-demands", help="Alle Bedarfe anzeigen")

    requirements_parser = subparsers.add_parser("calculate-requirements", help="Gesamtbedarf und Kosten berechnen")
    requirements_parser.add_argument(
        "--as-json",
        action="store_true",
        help="Ergebnis als JSON ausgeben",
    )

    clone_parser = subparsers.add_parser("predict-bom", help="Stückliste eines Produkts auf ein anderes kopieren")
    clone_parser.add_argument("source_product")
    clone_parser.add_argument("target_product")
    clone_parser.add_argument("--scale", type=float, default=1.0, help="Skalierungsfaktor für die Mengen")

    version_parser = subparsers.add_parser("create-version", help="Aktuellen Stand versionieren")
    version_parser.add_argument("name")
    version_parser.add_argument("--note")

    subparsers.add_parser("list-versions", help="Alle Versionen auflisten")

    version_details = subparsers.add_parser("show-version", help="Details einer Version anzeigen")
    version_details.add_argument("name")
    version_details.add_argument("--as-json", action="store_true")

    return parser


def load_connection(path: Path) -> Any:
    conn = database.get_connection(path)
    database.initialize_database(conn)
    return conn


def format_money(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def command_init_db(conn, _args) -> None:
    database.initialize_database(conn)
    print("Datenbank ist bereit.")


def command_add_part(conn, args) -> None:
    add_part(
        conn,
        Part(
            part_number=args.part_number,
            description=args.description,
            supplier=args.supplier,
            price=args.price,
            store_link=args.store_link,
        ),
    )
    print(f"Teil {args.part_number} angelegt.")


def command_update_part(conn, args) -> None:
    update_part(
        conn,
        Part(
            part_number=args.part_number,
            description=args.description,
            supplier=args.supplier,
            price=args.price,
            store_link=args.store_link,
        ),
    )
    print(f"Teil {args.part_number} aktualisiert.")


def command_list_parts(conn, _args) -> None:
    rows = list_parts(conn)
    if not rows:
        print("Keine Teile vorhanden.")
        return
    for row in rows:
        price = format_money(row["price"])
        print(f"{row['part_number']}: {row['description'] or '-'} | Lieferant: {row['supplier'] or '-'} | Preis: {price}")
        if row["store_link"]:
            print(f"    Link: {row['store_link']}")


def command_remove_part(conn, args) -> None:
    remove_part(conn, args.part_number)
    print(f"Teil {args.part_number} entfernt.")


def command_add_product(conn, args) -> None:
    add_product(conn, Product(name=args.name, description=args.description))
    print(f"Produkt {args.name} angelegt.")


def command_update_product(conn, args) -> None:
    update_product(conn, Product(name=args.name, description=args.description))
    print(f"Produkt {args.name} aktualisiert.")


def command_list_products(conn, _args) -> None:
    rows = list_products(conn)
    if not rows:
        print("Keine Produkte vorhanden.")
        return
    for row in rows:
        qty = row["requirement"] or 0
        print(f"{row['name']}: {row['description'] or '-'} | Bedarf: {qty}")


def command_remove_product(conn, args) -> None:
    remove_product(conn, args.name)
    print(f"Produkt {args.name} entfernt.")


def command_set_bom_entry(conn, args) -> None:
    set_bom_entry(conn, args.product, args.part, args.quantity)
    print(f"Teil {args.part} ist nun mit {args.quantity} Stück in {args.product} hinterlegt.")


def command_remove_bom_entry(conn, args) -> None:
    remove_bom_entry(conn, args.product, args.part)
    print("Eintrag gelöscht.")


def command_set_demand(conn, args) -> None:
    set_product_requirement(conn, args.product, args.quantity)
    print(f"Bedarf für {args.product}: {args.quantity}")


def command_remove_demand(conn, args) -> None:
    remove_requirement(conn, args.product)
    print(f"Bedarf für {args.product} entfernt.")


def command_list_demands(conn, _args) -> None:
    rows = list_product_requirements(conn)
    if not rows:
        print("Keine Bedarfe hinterlegt.")
        return
    for row in rows:
        print(f"{row['name']}: {row['quantity']}")


def command_calculate_requirements(conn, args) -> None:
    requirements = fetch_requirements(conn)
    if args.as_json:
        payload = [
            {
                "part_number": req.part_number,
                "description": req.description,
                "supplier": req.supplier,
                "price": req.price,
                "total_quantity": req.total_quantity,
                "total_cost": req.total_cost,
            }
            for req in requirements
        ]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if not requirements:
        print("Keine Bedarfe berechnet. Lege zuerst Stücklisten und Anforderungen fest.")
        return

    total_cost = 0.0
    print("Teil | Menge gesamt | Einzelpreis | Gesamtkosten")
    print("-" * 72)
    for req in requirements:
        total_cost += req.total_cost or 0.0
        print(
            f"{req.part_number}: {req.description or '-'} | {req.total_quantity} | "
            f"{format_money(req.price)} | {format_money(req.total_cost)}"
        )
    print("-" * 72)
    print(f"Summe: {format_money(total_cost)}")


def command_predict_bom(conn, args) -> None:
    clone_bom(conn, args.source_product, args.target_product, args.scale)
    print(
        "Stückliste von {src} wurde auf {dest} übertragen (Skalierung {scale}).".format(
            src=args.source_product,
            dest=args.target_product,
            scale=args.scale,
        )
    )


def command_create_version(conn, args) -> None:
    create_version(conn, args.name, args.note)
    print(f"Version {args.name} gespeichert.")


def command_list_versions(conn, _args) -> None:
    rows = list_versions(conn)
    if not rows:
        print("Keine Versionen gespeichert.")
        return
    for row in rows:
        note = f" – {row['note']}" if row["note"] else ""
        print(f"{row['name']} ({row['created_at']}){note}")


def command_show_version(conn, args) -> None:
    items, demands = get_version_details(conn, args.name)
    if args.as_json:
        payload = {
            "name": args.name,
            "items": [
                {
                    "product_name": item["product_name"],
                    "part_number": item["part_number"],
                    "description": item["part_description"],
                    "supplier": item["supplier"],
                    "price": item["price"],
                    "quantity": item["quantity"],
                }
                for item in items
            ],
            "demands": [
                {"product_name": demand["product_name"], "quantity": demand["quantity"]}
                for demand in demands
            ],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if not items:
        print("Version enthält keine Stücklisten.")
    else:
        print("Stücklisten-Inhalte:")
        for item in items:
            print(
                f"{item['product_name']} -> {item['part_number']} ({item['part_description'] or '-'}) "
                f"Menge: {item['quantity']}"
            )

    if demands:
        print("\nGespeicherte Bedarfe:")
        for demand in demands:
            print(f"{demand['product_name']}: {demand['quantity']}")


COMMANDS = {
    "init-db": command_init_db,
    "add-part": command_add_part,
    "update-part": command_update_part,
    "list-parts": command_list_parts,
    "remove-part": command_remove_part,
    "add-product": command_add_product,
    "update-product": command_update_product,
    "list-products": command_list_products,
    "remove-product": command_remove_product,
    "set-bom-entry": command_set_bom_entry,
    "remove-bom-entry": command_remove_bom_entry,
    "set-demand": command_set_demand,
    "remove-demand": command_remove_demand,
    "list-demands": command_list_demands,
    "calculate-requirements": command_calculate_requirements,
    "predict-bom": command_predict_bom,
    "create-version": command_create_version,
    "list-versions": command_list_versions,
    "show-version": command_show_version,
}


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    conn = load_connection(args.db)
    command = COMMANDS.get(args.command)
    try:
        command(conn, args)
    except ValueError as exc:
        parser.exit(status=1, message=f"Fehler: {exc}\n")


if __name__ == "__main__":
    main()
