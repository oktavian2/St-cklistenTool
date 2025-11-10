"""Einfache Tkinter-basierte Oberfläche für das Stücklisten-Tool."""

from __future__ import annotations

import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Optional

from .operations import (
    ORDER_STATUSES,
    Part,
    PartOrder,
    Product,
    add_order,
    add_part,
    add_product,
    fetch_requirements,
    fetch_supplier_requirements,
    get_product_requirement,
    list_bom_entries,
    list_orders,
    list_parts,
    list_product_requirements,
    list_products,
    remove_bom_entry,
    remove_order,
    remove_part,
    remove_product,
    remove_requirement,
    set_bom_entry,
    set_product_requirement,
    update_order,
    update_part,
    update_product,
)


def parse_decimal(text: str) -> float:
    value = text.strip().replace(" ", "")
    if not value:
        raise ValueError("Wert darf nicht leer sein")
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError("Wert muss eine Zahl sein") from exc


def format_decimal(value: float) -> str:
    return f"{value:,.2f}".replace(".", "X").replace(",", ".").replace("X", ",")


def format_decimal_entry(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.2f}".replace(".", ",")


def format_currency(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{format_decimal(value)} €"


class Application(ttk.Frame):
    """Tkinter-Anwendung zur Verwaltung von Teilen, Produkten und Anforderungen."""

    def __init__(self, master: tk.Misc, conn: sqlite3.Connection, db_path: Path) -> None:
        super().__init__(master, padding=10)
        self.conn = conn
        self.db_path = Path(db_path)

        master.title("Stücklisten-Tool")
        master.geometry("1050x650")

        self.pack(fill="both", expand=True)

        # Data caches & sort state
        self.parts_data: list[dict[str, Any]] = []
        self.products_data: list[dict[str, Any]] = []
        self.bom_data: list[dict[str, Any]] = []
        self.requirements_data: list[dict[str, Any]] = []
        self.supplier_data: list[dict[str, Any]] = []
        self.orders_data: list[dict[str, Any]] = []

        self.parts_sort_column = "beschreibung"
        self.parts_sort_reverse = False
        self.products_sort_column = "name"
        self.products_sort_reverse = False
        self.bom_sort_column = "part_number"
        self.bom_sort_reverse = False
        self.requirements_sort_column = "part_number"
        self.requirements_sort_reverse = False
        self.supplier_sort_column = "lieferant"
        self.supplier_sort_reverse = False
        self.orders_sort_column = "order_date"
        self.orders_sort_reverse = False

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self._build_parts_tab()
        self._build_products_tab()
        self._build_analysis_tab()
        self._build_orders_tab()

        status = ttk.Label(self, text=f"Datenbank: {self.db_path}")
        status.pack(anchor="w", pady=(6, 0))

        self.refresh_all()

    # ------------------------------------------------------------------
    # Tabs & Layout
    def _build_parts_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Teile")

        filter_frame = ttk.Frame(tab)
        filter_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        filter_frame.columnconfigure(1, weight=1)
        ttk.Label(filter_frame, text="Filter:").grid(row=0, column=0, sticky="w")
        self.part_filter_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.part_filter_var).grid(row=0, column=1, sticky="ew")
        self.part_filter_var.trace_add("write", lambda *_: self._render_parts())

        columns = ("part_number", "beschreibung", "hersteller", "lieferant", "preis", "store")
        headings = {
            "part_number": "Teilenummer",
            "beschreibung": "Beschreibung",
            "hersteller": "Hersteller",
            "lieferant": "Lieferant",
            "preis": "Preis",
            "store": "Shop-Link",
        }
        self.parts_tree = ttk.Treeview(tab, columns=columns, show="headings", height=18)
        for column, label in headings.items():
            self.parts_tree.heading(column, text=label, command=lambda c=column: self._sort_parts(c))
        self.parts_tree.column("part_number", width=140)
        self.parts_tree.column("beschreibung", width=220)
        self.parts_tree.column("hersteller", width=160)
        self.parts_tree.column("lieferant", width=160)
        self.parts_tree.column("preis", width=100, anchor="e")
        self.parts_tree.column("store", width=220)

        y_scroll = ttk.Scrollbar(tab, orient="vertical", command=self.parts_tree.yview)
        self.parts_tree.configure(yscrollcommand=y_scroll.set)
        self.parts_tree.grid(row=1, column=0, sticky="nsew")
        y_scroll.grid(row=1, column=1, sticky="ns")

        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        button_frame = ttk.Frame(tab)
        button_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        for column in range(4):
            button_frame.columnconfigure(column, weight=1)

        ttk.Button(button_frame, text="Neu", command=self.on_add_part).grid(row=0, column=0, padx=4)
        ttk.Button(button_frame, text="Bearbeiten", command=self.on_edit_part).grid(row=0, column=1, padx=4)
        ttk.Button(button_frame, text="Löschen", command=self.on_delete_part).grid(row=0, column=2, padx=4)
        ttk.Button(button_frame, text="Aktualisieren", command=self.refresh_parts).grid(row=0, column=3, padx=4)

    def _build_products_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Produkte & Stücklisten")

        top_frame = ttk.Frame(tab)
        top_frame.pack(fill="both", expand=True)

        filter_frame = ttk.Frame(top_frame)
        filter_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        filter_frame.columnconfigure(1, weight=1)
        ttk.Label(filter_frame, text="Filter:").grid(row=0, column=0, sticky="w")
        self.product_filter_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.product_filter_var).grid(row=0, column=1, sticky="ew")
        self.product_filter_var.trace_add("write", lambda *_: self._render_products())

        product_columns = ("name", "beschreibung", "bedarf")
        self.products_tree = ttk.Treeview(top_frame, columns=product_columns, show="headings", height=12)
        self.products_tree.heading("name", text="Name", command=lambda c="name": self._sort_products(c))
        self.products_tree.heading("beschreibung", text="Beschreibung", command=lambda c="beschreibung": self._sort_products(c))
        self.products_tree.heading("bedarf", text="Losgröße", command=lambda c="bedarf": self._sort_products(c))
        self.products_tree.column("name", width=180)
        self.products_tree.column("beschreibung", width=280)
        self.products_tree.column("bedarf", width=120, anchor="e")
        self.products_tree.bind("<<TreeviewSelect>>", lambda _event: self.refresh_product_details())

        product_scroll = ttk.Scrollbar(top_frame, orient="vertical", command=self.products_tree.yview)
        self.products_tree.configure(yscrollcommand=product_scroll.set)
        self.products_tree.grid(row=1, column=0, sticky="nsew")
        product_scroll.grid(row=1, column=1, sticky="ns")

        top_frame.columnconfigure(0, weight=1)
        top_frame.rowconfigure(1, weight=1)

        product_buttons = ttk.Frame(tab)
        product_buttons.pack(fill="x", pady=(10, 0))
        for column in range(5):
            product_buttons.columnconfigure(column, weight=1)

        ttk.Button(product_buttons, text="Neu", command=self.on_add_product).grid(row=0, column=0, padx=4)
        ttk.Button(product_buttons, text="Bearbeiten", command=self.on_edit_product).grid(row=0, column=1, padx=4)
        ttk.Button(product_buttons, text="Löschen", command=self.on_delete_product).grid(row=0, column=2, padx=4)
        ttk.Button(product_buttons, text="Bedarf setzen", command=self.on_set_requirement).grid(row=0, column=3, padx=4)
        ttk.Button(product_buttons, text="Bedarf entfernen", command=self.on_remove_requirement).grid(row=0, column=4, padx=4)

        self.demand_var = tk.StringVar(value="Keine Losgröße hinterlegt")
        ttk.Label(tab, textvariable=self.demand_var, font=("", 10, "italic")).pack(anchor="w", pady=(10, 0))

        bom_frame = ttk.LabelFrame(tab, text="Stückliste")
        bom_frame.pack(fill="both", expand=True, pady=(10, 0))

        bom_filter_frame = ttk.Frame(bom_frame)
        bom_filter_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(4, 8))
        bom_filter_frame.columnconfigure(1, weight=1)
        ttk.Label(bom_filter_frame, text="Filter:").grid(row=0, column=0, sticky="w")
        self.bom_filter_var = tk.StringVar()
        ttk.Entry(bom_filter_frame, textvariable=self.bom_filter_var).grid(row=0, column=1, sticky="ew")
        self.bom_filter_var.trace_add("write", lambda *_: self._render_bom())

        bom_columns = ("part_number", "beschreibung", "hersteller", "lieferant", "preis", "menge")
        self.bom_tree = ttk.Treeview(bom_frame, columns=bom_columns, show="headings", height=10)
        self.bom_tree.heading("part_number", text="Teilenummer", command=lambda c="part_number": self._sort_bom(c))
        self.bom_tree.heading("beschreibung", text="Beschreibung", command=lambda c="beschreibung": self._sort_bom(c))
        self.bom_tree.heading("hersteller", text="Hersteller", command=lambda c="hersteller": self._sort_bom(c))
        self.bom_tree.heading("lieferant", text="Lieferant", command=lambda c="lieferant": self._sort_bom(c))
        self.bom_tree.heading("preis", text="Preis", command=lambda c="preis": self._sort_bom(c))
        self.bom_tree.heading("menge", text="Menge pro Produkt", command=lambda c="menge": self._sort_bom(c))
        self.bom_tree.column("part_number", width=140)
        self.bom_tree.column("beschreibung", width=240)
        self.bom_tree.column("hersteller", width=160)
        self.bom_tree.column("lieferant", width=160)
        self.bom_tree.column("preis", width=100, anchor="e")
        self.bom_tree.column("menge", width=140, anchor="e")

        bom_scroll = ttk.Scrollbar(bom_frame, orient="vertical", command=self.bom_tree.yview)
        self.bom_tree.configure(yscrollcommand=bom_scroll.set)
        self.bom_tree.grid(row=1, column=0, sticky="nsew")
        bom_scroll.grid(row=1, column=1, sticky="ns")

        bom_frame.columnconfigure(0, weight=1)
        bom_frame.rowconfigure(1, weight=1)

        bom_buttons = ttk.Frame(bom_frame)
        bom_buttons.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        for column in range(3):
            bom_buttons.columnconfigure(column, weight=1)

        ttk.Button(bom_buttons, text="Teil zuordnen", command=self.on_add_bom).grid(row=0, column=0, padx=4)
        ttk.Button(bom_buttons, text="Menge ändern", command=self.on_edit_bom).grid(row=0, column=1, padx=4)
        ttk.Button(bom_buttons, text="Entfernen", command=self.on_remove_bom).grid(row=0, column=2, padx=4)

    def _build_analysis_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Auswertung")

        req_container = ttk.Frame(tab)
        req_container.pack(fill="both", expand=True)

        req_header = ttk.Frame(req_container)
        req_header.pack(fill="x")
        ttk.Label(req_header, text="Aggregierter Teilebedarf", font=("", 11, "bold")).pack(side="left")
        ttk.Label(req_header, text="Filter:").pack(side="left", padx=(12, 4))
        self.requirement_filter_var = tk.StringVar()
        ttk.Entry(req_header, textvariable=self.requirement_filter_var, width=30).pack(side="left", fill="x", expand=True)
        self.requirement_filter_var.trace_add("write", lambda *_: self._render_requirements())

        req_columns = (
            "part_number",
            "beschreibung",
            "hersteller",
            "lieferant",
            "preis",
            "gesamtmenge",
            "gesamtkosten",
        )
        self.requirements_tree = ttk.Treeview(req_container, columns=req_columns, show="headings", height=10)
        self.requirements_tree.heading("part_number", text="Teilenummer", command=lambda c="part_number": self._sort_requirements(c))
        self.requirements_tree.heading("beschreibung", text="Beschreibung", command=lambda c="beschreibung": self._sort_requirements(c))
        self.requirements_tree.heading("hersteller", text="Hersteller", command=lambda c="hersteller": self._sort_requirements(c))
        self.requirements_tree.heading("lieferant", text="Lieferant", command=lambda c="lieferant": self._sort_requirements(c))
        self.requirements_tree.heading("preis", text="Einzelpreis", command=lambda c="preis": self._sort_requirements(c))
        self.requirements_tree.heading("gesamtmenge", text="Gesamtmenge", command=lambda c="gesamtmenge": self._sort_requirements(c))
        self.requirements_tree.heading("gesamtkosten", text="Gesamtkosten", command=lambda c="gesamtkosten": self._sort_requirements(c))
        self.requirements_tree.column("part_number", width=140)
        self.requirements_tree.column("beschreibung", width=220)
        self.requirements_tree.column("hersteller", width=160)
        self.requirements_tree.column("lieferant", width=160)
        self.requirements_tree.column("preis", width=100, anchor="e")
        self.requirements_tree.column("gesamtmenge", width=140, anchor="e")
        self.requirements_tree.column("gesamtkosten", width=140, anchor="e")

        req_scroll = ttk.Scrollbar(req_container, orient="vertical", command=self.requirements_tree.yview)
        self.requirements_tree.configure(yscrollcommand=req_scroll.set)
        self.requirements_tree.pack(fill="both", expand=True, pady=(8, 0))
        req_scroll.pack(fill="y", side="right")

        supplier_container = ttk.Frame(tab)
        supplier_container.pack(fill="both", expand=True, pady=(16, 0))

        supplier_header = ttk.Frame(supplier_container)
        supplier_header.pack(fill="x")
        ttk.Label(supplier_header, text="Bedarf nach Lieferanten", font=("", 11, "bold")).pack(side="left")
        ttk.Label(supplier_header, text="Filter:").pack(side="left", padx=(12, 4))
        self.supplier_filter_var = tk.StringVar()
        ttk.Entry(supplier_header, textvariable=self.supplier_filter_var, width=30).pack(side="left", fill="x", expand=True)
        self.supplier_filter_var.trace_add("write", lambda *_: self._render_supplier_summary())

        supplier_columns = ("lieferant", "gesamtmenge", "gesamtkosten")
        self.supplier_tree = ttk.Treeview(supplier_container, columns=supplier_columns, show="headings", height=8)
        self.supplier_tree.heading("lieferant", text="Lieferant", command=lambda c="lieferant": self._sort_supplier(c))
        self.supplier_tree.heading("gesamtmenge", text="Gesamtmenge", command=lambda c="gesamtmenge": self._sort_supplier(c))
        self.supplier_tree.heading("gesamtkosten", text="Gesamtkosten", command=lambda c="gesamtkosten": self._sort_supplier(c))
        self.supplier_tree.column("lieferant", width=220)
        self.supplier_tree.column("gesamtmenge", width=140, anchor="e")
        self.supplier_tree.column("gesamtkosten", width=140, anchor="e")

        supplier_scroll = ttk.Scrollbar(supplier_container, orient="vertical", command=self.supplier_tree.yview)
        self.supplier_tree.configure(yscrollcommand=supplier_scroll.set)
        self.supplier_tree.pack(fill="both", expand=True, pady=(8, 0))
        supplier_scroll.pack(fill="y", side="right")

        ttk.Button(tab, text="Aktualisieren", command=self.refresh_analysis).pack(anchor="e", pady=(10, 0))

    def _build_orders_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Bestellungen")

        filter_frame = ttk.Frame(tab)
        filter_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        filter_frame.columnconfigure(1, weight=1)
        ttk.Label(filter_frame, text="Filter:").grid(row=0, column=0, sticky="w")
        self.order_filter_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.order_filter_var).grid(row=0, column=1, sticky="ew")
        self.order_filter_var.trace_add("write", lambda *_: self._render_orders())

        columns = (
            "id",
            "part_number",
            "beschreibung",
            "hersteller",
            "lieferant",
            "menge",
            "order_date",
            "delivery_date",
            "status",
        )
        headings = {
            "id": "ID",
            "part_number": "Teilenummer",
            "beschreibung": "Beschreibung",
            "hersteller": "Hersteller",
            "lieferant": "Lieferant",
            "menge": "Bestellmenge",
            "order_date": "Bestelldatum",
            "delivery_date": "Lieferdatum",
            "status": "Status",
        }
        self.orders_tree = ttk.Treeview(tab, columns=columns, show="headings", height=18)
        for column, label in headings.items():
            self.orders_tree.heading(column, text=label, command=lambda c=column: self._sort_orders(c))
        self.orders_tree.column("id", width=60, anchor="center")
        self.orders_tree.column("part_number", width=140)
        self.orders_tree.column("beschreibung", width=220)
        self.orders_tree.column("hersteller", width=140)
        self.orders_tree.column("lieferant", width=160)
        self.orders_tree.column("menge", width=120, anchor="e")
        self.orders_tree.column("order_date", width=120)
        self.orders_tree.column("delivery_date", width=120)
        self.orders_tree.column("status", width=140)

        y_scroll = ttk.Scrollbar(tab, orient="vertical", command=self.orders_tree.yview)
        self.orders_tree.configure(yscrollcommand=y_scroll.set)
        self.orders_tree.grid(row=1, column=0, sticky="nsew")
        y_scroll.grid(row=1, column=1, sticky="ns")

        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        button_frame = ttk.Frame(tab)
        button_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        for idx in range(4):
            button_frame.columnconfigure(idx, weight=1)

        ttk.Button(button_frame, text="Neu", command=self.on_add_order).grid(row=0, column=0, padx=4)
        ttk.Button(button_frame, text="Bearbeiten", command=self.on_edit_order).grid(row=0, column=1, padx=4)
        ttk.Button(button_frame, text="Löschen", command=self.on_delete_order).grid(row=0, column=2, padx=4)
        ttk.Button(button_frame, text="Aktualisieren", command=self.refresh_orders).grid(row=0, column=3, padx=4)

    # ------------------------------------------------------------------
    # Helpers
    def refresh_all(self) -> None:
        self.refresh_parts()
        self.refresh_products()
        self.refresh_analysis()
        self.refresh_orders()

    def refresh_parts(self) -> None:
        selection = self.get_selected_part()
        self.parts_data = [
            {
                "part_number": row["part_number"],
                "description": row["description"] or "",
                "supplier": row["supplier"] or "",
                "manufacturer": row["manufacturer"] or "",
                "price": row["price"],
                "store_link": row["store_link"] or "",
            }
            for row in list_parts(self.conn)
        ]
        self._render_parts(selection)

    def _render_parts(self, preferred: Optional[str] = None) -> None:
        if preferred is None:
            preferred = self.get_selected_part()
        filter_text = self.part_filter_var.get().strip().lower() if hasattr(self, "part_filter_var") else ""
        data = self.parts_data
        if filter_text:
            data = [
                part
                for part in data
                if filter_text in part["part_number"].lower()
                or filter_text in part["description"].lower()
                or filter_text in part["supplier"].lower()
                or filter_text in part["manufacturer"].lower()
                or filter_text in part["store_link"].lower()
            ]

        column = self.parts_sort_column
        column_map = {
            "beschreibung": "description",
            "hersteller": "manufacturer",
            "lieferant": "supplier",
            "preis": "price",
            "store": "store_link",
        }
        data_key = column_map.get(column, column)
        reverse = self.parts_sort_reverse

        def sort_key(part: dict[str, Any]):
            if data_key == "price":
                value = part["price"]
                return (value is None, value if value is not None else 0.0)
            value = part.get(data_key)
            return value.lower() if isinstance(value, str) else value

        data = sorted(data, key=sort_key, reverse=reverse)

        for row in self.parts_tree.get_children():
            self.parts_tree.delete(row)
        for part in data:
            self.parts_tree.insert(
                "",
                "end",
                iid=part["part_number"],
                values=(
                    part["part_number"],
                    part["description"] or "-",
                    part["manufacturer"] or "-",
                    part["supplier"] or "-",
                    format_currency(part["price"]),
                    part["store_link"] or "-",
                ),
            )
        if preferred and self.parts_tree.exists(preferred):
            self.parts_tree.selection_set(preferred)
            self.parts_tree.focus(preferred)
            self.parts_tree.see(preferred)
        else:
            self.parts_tree.selection_remove(self.parts_tree.selection())

    def _toggle_sort(self, prefix: str, column: str) -> None:
        current = getattr(self, f"{prefix}_sort_column")
        reverse = getattr(self, f"{prefix}_sort_reverse")
        if current == column:
            reverse = not reverse
        else:
            current = column
            reverse = False
        setattr(self, f"{prefix}_sort_column", current)
        setattr(self, f"{prefix}_sort_reverse", reverse)

    def _sort_parts(self, column: str) -> None:
        self._toggle_sort("parts", column)
        self._render_parts()

    def refresh_products(self) -> None:
        selection = self.get_selected_product()
        requirement_lookup = {
            row["name"]: row["quantity"] for row in list_product_requirements(self.conn)
        }
        self.products_data = [
            {
                "name": row["name"],
                "description": row["description"] or "",
                "requirement": requirement_lookup.get(row["name"]),
            }
            for row in list_products(self.conn)
        ]
        self._render_products(selection)
        self.refresh_product_details()

    def _render_products(self, preferred: Optional[str] = None) -> None:
        if preferred is None:
            preferred = self.get_selected_product()
        filter_text = self.product_filter_var.get().strip().lower() if hasattr(self, "product_filter_var") else ""
        data = self.products_data
        if filter_text:
            data = [
                product
                for product in data
                if filter_text in product["name"].lower()
                or filter_text in product["description"].lower()
            ]

        column = self.products_sort_column
        column_map = {
            "beschreibung": "description",
            "bedarf": "requirement",
        }
        data_key = column_map.get(column, column)
        reverse = self.products_sort_reverse

        def sort_key(product: dict[str, Any]):
            if data_key == "requirement":
                value = product["requirement"]
                return (value is None, value if value is not None else 0.0)
            value = product.get(data_key)
            return value.lower() if isinstance(value, str) else value

        data = sorted(data, key=sort_key, reverse=reverse)

        for row in self.products_tree.get_children():
            self.products_tree.delete(row)
        for product in data:
            requirement = product["requirement"]
            display_qty = "-" if requirement is None else format_decimal(requirement)
            self.products_tree.insert(
                "",
                "end",
                iid=product["name"],
                values=(product["name"], product["description"] or "-", display_qty),
            )
        if preferred and self.products_tree.exists(preferred):
            self.products_tree.selection_set(preferred)
            self.products_tree.focus(preferred)
            self.products_tree.see(preferred)
        else:
            self.products_tree.selection_remove(self.products_tree.selection())

    def _sort_products(self, column: str) -> None:
        self._toggle_sort("products", column)
        self._render_products()

    def refresh_product_details(self) -> None:
        self.bom_data = []
        product = self.get_selected_product()
        if not product:
            self.demand_var.set("Keine Losgröße hinterlegt")
            self._render_bom()
            return
        try:
            requirement = get_product_requirement(self.conn, product)
        except ValueError:
            self.demand_var.set("Keine Losgröße hinterlegt")
            self._render_bom()
            return
        if requirement is None:
            self.demand_var.set("Keine Losgröße hinterlegt")
        else:
            self.demand_var.set(f"Losgröße: {format_decimal(requirement)}")
        try:
            rows = list_bom_entries(self.conn, product)
        except ValueError as exc:
            messagebox.showerror("Fehler", str(exc))
            return
        self.bom_data = [
            {
                "part_number": row["part_number"],
                "description": row["description"] or "",
                "supplier": row["supplier"] or "",
                "manufacturer": row["manufacturer"] or "",
                "price": row["price"],
                "quantity": row["quantity"],
            }
            for row in rows
        ]
        self._render_bom()

    def _render_bom(self) -> None:
        filter_text = self.bom_filter_var.get().strip().lower() if hasattr(self, "bom_filter_var") else ""
        data = self.bom_data
        if filter_text:
            data = [
                entry
                for entry in data
                if filter_text in entry["part_number"].lower()
                or filter_text in entry["description"].lower()
                or filter_text in entry["supplier"].lower()
                or filter_text in entry["manufacturer"].lower()
            ]

        column = self.bom_sort_column
        column_map = {
            "beschreibung": "description",
            "hersteller": "manufacturer",
            "lieferant": "supplier",
            "preis": "price",
            "menge": "quantity",
        }
        data_key = column_map.get(column, column)
        reverse = self.bom_sort_reverse

        def sort_key(entry: dict[str, Any]):
            if data_key == "price":
                value = entry["price"]
                return (value is None, value if value is not None else 0.0)
            if data_key == "quantity":
                return entry["quantity"]
            value = entry.get(data_key)
            return value.lower() if isinstance(value, str) else value

        data = sorted(data, key=sort_key, reverse=reverse)

        selected = self.get_selected_bom_part()
        for row in self.bom_tree.get_children():
            self.bom_tree.delete(row)
        for entry in data:
            self.bom_tree.insert(
                "",
                "end",
                iid=entry["part_number"],
                values=(
                    entry["part_number"],
                    entry["description"] or "-",
                    entry["manufacturer"] or "-",
                    entry["supplier"] or "-",
                    format_currency(entry["price"]),
                    format_decimal(entry["quantity"]),
                ),
            )
        if selected and self.bom_tree.exists(selected):
            self.bom_tree.selection_set(selected)
            self.bom_tree.focus(selected)
            self.bom_tree.see(selected)
        else:
            self.bom_tree.selection_remove(self.bom_tree.selection())

    def _sort_bom(self, column: str) -> None:
        self._toggle_sort("bom", column)
        self._render_bom()

    def refresh_analysis(self) -> None:
        self.requirements_data = [
            {
                "part_number": req.part_number,
                "description": req.description or "",
                "supplier": req.supplier or "",
                "manufacturer": req.manufacturer or "",
                "price": req.price,
                "total_quantity": req.total_quantity,
                "total_cost": req.total_cost,
            }
            for req in fetch_requirements(self.conn)
        ]
        self._render_requirements()

        self.supplier_data = [
            {
                "supplier": summary.supplier or "",
                "total_quantity": summary.total_quantity,
                "total_cost": summary.total_cost,
            }
            for summary in fetch_supplier_requirements(self.conn)
        ]
        self._render_supplier_summary()

    def refresh_orders(self) -> None:
        selection = self.get_selected_order()
        self.orders_data = [
            {
                "id": row["id"],
                "part_number": row["part_number"],
                "description": row["description"] or "",
                "manufacturer": row["manufacturer"] or "",
                "supplier": row["supplier"] or "",
                "quantity": row["quantity"],
                "order_date": row["order_date"] or "",
                "delivery_date": row["delivery_date"] or "",
                "status": row["status"],
            }
            for row in list_orders(self.conn)
        ]
        self._render_orders(selection)

    def _render_requirements(self) -> None:
        filter_text = self.requirement_filter_var.get().strip().lower() if hasattr(self, "requirement_filter_var") else ""
        data = self.requirements_data
        if filter_text:
            data = [
                entry
                for entry in data
                if filter_text in entry["part_number"].lower()
                or filter_text in entry["description"].lower()
                or filter_text in entry["supplier"].lower()
                or filter_text in entry["manufacturer"].lower()
            ]

        column = self.requirements_sort_column
        column_map = {
            "beschreibung": "description",
            "hersteller": "manufacturer",
            "lieferant": "supplier",
            "preis": "price",
            "gesamtmenge": "total_quantity",
            "gesamtkosten": "total_cost",
        }
        data_key = column_map.get(column, column)
        reverse = self.requirements_sort_reverse

        def sort_key(entry: dict[str, Any]):
            if data_key == "price":
                value = entry["price"]
                return (value is None, value if value is not None else 0.0)
            if data_key == "total_quantity":
                return entry["total_quantity"]
            if data_key == "total_cost":
                value = entry["total_cost"]
                return (value is None, value if value is not None else 0.0)
            value = entry.get(data_key)
            return value.lower() if isinstance(value, str) else value

        data = sorted(data, key=sort_key, reverse=reverse)

        for row in self.requirements_tree.get_children():
            self.requirements_tree.delete(row)
        for entry in data:
            self.requirements_tree.insert(
                "",
                "end",
                iid=entry["part_number"],
                values=(
                    entry["part_number"],
                    entry["description"] or "-",
                    entry["manufacturer"] or "-",
                    entry["supplier"] or "-",
                    format_currency(entry["price"]),
                    format_decimal(entry["total_quantity"]),
                    format_currency(entry["total_cost"]),
                ),
            )

    def _sort_requirements(self, column: str) -> None:
        self._toggle_sort("requirements", column)
        self._render_requirements()

    def _render_supplier_summary(self) -> None:
        filter_text = self.supplier_filter_var.get().strip().lower() if hasattr(self, "supplier_filter_var") else ""
        data = self.supplier_data
        if filter_text:
            data = [
                entry for entry in data if filter_text in entry["supplier"].lower()
            ]

        column = self.supplier_sort_column
        column_map = {
            "lieferant": "supplier",
            "gesamtmenge": "total_quantity",
            "gesamtkosten": "total_cost",
        }
        data_key = column_map.get(column, column)
        reverse = self.supplier_sort_reverse

        def sort_key(entry: dict[str, Any]):
            if data_key == "total_quantity":
                return entry["total_quantity"]
            if data_key == "total_cost":
                value = entry["total_cost"]
                return (value is None, value if value is not None else 0.0)
            value = entry.get(data_key)
            return value.lower() if isinstance(value, str) else value

        data = sorted(data, key=sort_key, reverse=reverse)

        for row in self.supplier_tree.get_children():
            self.supplier_tree.delete(row)
        for entry in data:
            iid = entry["supplier"] or "-"
            self.supplier_tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    entry["supplier"] or "-",
                    format_decimal(entry["total_quantity"]),
                    format_currency(entry["total_cost"]),
                ),
            )

    def _sort_supplier(self, column: str) -> None:
        self._toggle_sort("supplier", column)
        self._render_supplier_summary()

    def _render_orders(self, preferred: Optional[int] = None) -> None:
        if preferred is None:
            preferred = self.get_selected_order()
        filter_text = self.order_filter_var.get().strip().lower() if hasattr(self, "order_filter_var") else ""
        data = self.orders_data
        if filter_text:
            data = [
                entry
                for entry in data
                if filter_text in str(entry["id"]).lower()
                or filter_text in entry["part_number"].lower()
                or filter_text in entry["description"].lower()
                or filter_text in entry["manufacturer"].lower()
                or filter_text in entry["supplier"].lower()
                or filter_text in entry["status"].lower()
                or filter_text in entry["order_date"].lower()
                or filter_text in entry["delivery_date"].lower()
            ]

        column = self.orders_sort_column
        column_map = {
            "beschreibung": "description",
            "hersteller": "manufacturer",
            "lieferant": "supplier",
            "menge": "quantity",
        }
        data_key = column_map.get(column, column)
        reverse = self.orders_sort_reverse

        def sort_key(entry: dict[str, Any]):
            if data_key == "id":
                return entry["id"]
            if data_key == "quantity":
                return entry["quantity"]
            if data_key in {"order_date", "delivery_date"}:
                value = entry[data_key]
                return (value == "", value)
            value = entry.get(data_key)
            return value.lower() if isinstance(value, str) else value

        data = sorted(data, key=sort_key, reverse=reverse)

        for row in self.orders_tree.get_children():
            self.orders_tree.delete(row)
        for entry in data:
            self.orders_tree.insert(
                "",
                "end",
                iid=str(entry["id"]),
                values=(
                    entry["id"],
                    entry["part_number"],
                    entry["description"] or "-",
                    entry["manufacturer"] or "-",
                    entry["supplier"] or "-",
                    format_decimal(entry["quantity"]),
                    entry["order_date"] or "-",
                    entry["delivery_date"] or "-",
                    entry["status"],
                ),
            )
        if preferred is not None and self.orders_tree.exists(str(preferred)):
            iid = str(preferred)
            self.orders_tree.selection_set(iid)
            self.orders_tree.focus(iid)
            self.orders_tree.see(iid)
        else:
            self.orders_tree.selection_remove(self.orders_tree.selection())

    def _sort_orders(self, column: str) -> None:
        self._toggle_sort("orders", column)
        self._render_orders()

    def get_selected_part(self) -> Optional[str]:
        selection = self.parts_tree.selection()
        if not selection:
            return None
        return selection[0]

    def get_selected_product(self) -> Optional[str]:
        selection = self.products_tree.selection()
        if not selection:
            return None
        return selection[0]

    def get_selected_bom_part(self) -> Optional[str]:
        selection = self.bom_tree.selection()
        if not selection:
            return None
        return selection[0]

    def get_selected_order(self) -> Optional[int]:
        if not hasattr(self, "orders_tree"):
            return None
        selection = self.orders_tree.selection()
        if not selection:
            return None
        try:
            return int(selection[0])
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Event Handler Parts
    def on_add_part(self) -> None:
        dialog = PartDialog(self, title="Teil anlegen")
        if dialog.result is None:
            return
        try:
            add_part(
                self.conn,
                Part(
                    part_number=dialog.result["part_number"],
                    description=dialog.result.get("description"),
                    supplier=dialog.result.get("supplier"),
                    manufacturer=dialog.result.get("manufacturer"),
                    price=dialog.result.get("price"),
                    store_link=dialog.result.get("store_link"),
                ),
            )
        except sqlite3.IntegrityError as exc:
            messagebox.showerror("Fehler", f"Teil konnte nicht angelegt werden: {exc}")
        else:
            self.refresh_parts()

    def on_edit_part(self) -> None:
        part_number = self.get_selected_part()
        if not part_number:
            messagebox.showinfo("Hinweis", "Bitte zuerst ein Teil auswählen.")
            return
        current = next((part for part in self.parts_data if part["part_number"] == part_number), None)
        if current is None:
            messagebox.showerror("Fehler", "Teil konnte nicht geladen werden.")
            return
        dialog = PartDialog(self, title="Teil bearbeiten", part=current, allow_part_number_edit=False)
        if dialog.result is None:
            return
        try:
            update_part(
                self.conn,
                Part(
                    part_number=part_number,
                    description=dialog.result.get("description"),
                    supplier=dialog.result.get("supplier"),
                    manufacturer=dialog.result.get("manufacturer"),
                    price=dialog.result.get("price"),
                    store_link=dialog.result.get("store_link"),
                ),
            )
        except ValueError as exc:
            messagebox.showerror("Fehler", str(exc))
        else:
            self.refresh_parts()
            self.refresh_product_details()
            self.refresh_analysis()
            self.refresh_orders()

    def on_delete_part(self) -> None:
        part_number = self.get_selected_part()
        if not part_number:
            messagebox.showinfo("Hinweis", "Bitte zuerst ein Teil auswählen.")
            return
        if not messagebox.askyesno("Löschen", f"Soll Teil {part_number} wirklich gelöscht werden?"):
            return
        try:
            remove_part(self.conn, part_number)
        except ValueError as exc:
            messagebox.showerror("Fehler", str(exc))
        else:
            self.refresh_all()

    # ------------------------------------------------------------------
    # Event Handler Products
    def on_add_product(self) -> None:
        dialog = ProductDialog(self, title="Produkt anlegen")
        if dialog.result is None:
            return
        try:
            add_product(
                self.conn,
                Product(name=dialog.result["name"], description=dialog.result.get("description")),
            )
        except sqlite3.IntegrityError as exc:
            messagebox.showerror("Fehler", f"Produkt konnte nicht angelegt werden: {exc}")
        else:
            self.refresh_products()

    def on_edit_product(self) -> None:
        product = self.get_selected_product()
        if not product:
            messagebox.showinfo("Hinweis", "Bitte zuerst ein Produkt auswählen.")
            return
        item = self.products_tree.item(product)
        dialog = ProductDialog(
            self,
            title="Produkt bearbeiten",
            product={"name": product, "description": item["values"][0] if item["values"][0] != "-" else ""},
            allow_name_edit=False,
        )
        if dialog.result is None:
            return
        try:
            update_product(
                self.conn,
                Product(name=product, description=dialog.result.get("description")),
            )
        except ValueError as exc:
            messagebox.showerror("Fehler", str(exc))
        else:
            self.refresh_products()

    def on_delete_product(self) -> None:
        product = self.get_selected_product()
        if not product:
            messagebox.showinfo("Hinweis", "Bitte zuerst ein Produkt auswählen.")
            return
        if not messagebox.askyesno("Löschen", f"Soll Produkt {product} wirklich gelöscht werden?"):
            return
        try:
            remove_product(self.conn, product)
        except ValueError as exc:
            messagebox.showerror("Fehler", str(exc))
        else:
            self.refresh_all()

    def on_set_requirement(self) -> None:
        product = self.get_selected_product()
        if not product:
            messagebox.showinfo("Hinweis", "Bitte zuerst ein Produkt auswählen.")
            return
        value = simpledialog.askfloat("Losgröße", f"Losgröße für {product}:", minvalue=0.0, parent=self)
        if value is None:
            return
        try:
            set_product_requirement(self.conn, product, float(value))
        except ValueError as exc:
            messagebox.showerror("Fehler", str(exc))
        else:
            self.refresh_products()
            self.refresh_analysis()

    def on_remove_requirement(self) -> None:
        product = self.get_selected_product()
        if not product:
            messagebox.showinfo("Hinweis", "Bitte zuerst ein Produkt auswählen.")
            return
        try:
            remove_requirement(self.conn, product)
        except ValueError as exc:
            messagebox.showerror("Fehler", str(exc))
        else:
            self.refresh_products()
            self.refresh_analysis()

    def on_add_bom(self) -> None:
        product = self.get_selected_product()
        if not product:
            messagebox.showinfo("Hinweis", "Bitte zuerst ein Produkt auswählen.")
            return
        dialog = BomDialog(self, self.conn, title="Teil zuordnen")
        if dialog.result is None:
            return
        try:
            set_bom_entry(self.conn, product, dialog.result["part_number"], dialog.result["quantity"])
        except ValueError as exc:
            messagebox.showerror("Fehler", str(exc))
        else:
            self.refresh_product_details()
            self.refresh_analysis()

    def on_edit_bom(self) -> None:
        product = self.get_selected_product()
        part_number = self.get_selected_bom_part()
        if not product or not part_number:
            messagebox.showinfo("Hinweis", "Bitte zuerst einen Stücklisteneintrag auswählen.")
            return
        entry = next((item for item in self.bom_data if item["part_number"] == part_number), None)
        if entry is None:
            messagebox.showerror("Fehler", "Eintrag konnte nicht geladen werden.")
            return
        dialog = BomDialog(
            self,
            self.conn,
            title="Menge anpassen",
            entry={"part_number": part_number, "quantity": entry["quantity"]},
            allow_part_edit=False,
        )
        if dialog.result is None:
            return
        try:
            set_bom_entry(self.conn, product, part_number, dialog.result["quantity"])
        except ValueError as exc:
            messagebox.showerror("Fehler", str(exc))
        else:
            self.refresh_product_details()
            self.refresh_analysis()

    def on_remove_bom(self) -> None:
        product = self.get_selected_product()
        part_number = self.get_selected_bom_part()
        if not product or not part_number:
            messagebox.showinfo("Hinweis", "Bitte zuerst einen Stücklisteneintrag auswählen.")
            return
        if not messagebox.askyesno("Entfernen", f"Soll Teil {part_number} aus {product} entfernt werden?"):
            return
        try:
            remove_bom_entry(self.conn, product, part_number)
        except ValueError as exc:
            messagebox.showerror("Fehler", str(exc))
        else:
            self.refresh_product_details()
            self.refresh_analysis()

    # ------------------------------------------------------------------
    # Event Handler Orders
    def on_add_order(self) -> None:
        dialog = OrderDialog(self, self.conn, title="Bestellung anlegen")
        if dialog.result is None:
            return
        try:
            order_id = add_order(
                self.conn,
                PartOrder(
                    id=None,
                    part_number=dialog.result["part_number"],
                    quantity=dialog.result["quantity"],
                    order_date=dialog.result.get("order_date"),
                    delivery_date=dialog.result.get("delivery_date"),
                    status=dialog.result["status"],
                ),
            )
        except ValueError as exc:
            messagebox.showerror("Fehler", str(exc))
        else:
            self.refresh_orders()
            messagebox.showinfo("Erfolg", f"Bestellung {order_id} wurde gespeichert.")

    def on_edit_order(self) -> None:
        order_id = self.get_selected_order()
        if order_id is None:
            messagebox.showinfo("Hinweis", "Bitte zuerst eine Bestellung auswählen.")
            return
        current = next((order for order in self.orders_data if order["id"] == order_id), None)
        if current is None:
            messagebox.showerror("Fehler", "Bestellung konnte nicht geladen werden.")
            return
        dialog = OrderDialog(self, self.conn, title="Bestellung bearbeiten", order=current)
        if dialog.result is None:
            return
        try:
            update_order(
                self.conn,
                PartOrder(
                    id=order_id,
                    part_number=dialog.result["part_number"],
                    quantity=dialog.result["quantity"],
                    order_date=dialog.result.get("order_date"),
                    delivery_date=dialog.result.get("delivery_date"),
                    status=dialog.result["status"],
                ),
            )
        except ValueError as exc:
            messagebox.showerror("Fehler", str(exc))
        else:
            self.refresh_orders()

    def on_delete_order(self) -> None:
        order_id = self.get_selected_order()
        if order_id is None:
            messagebox.showinfo("Hinweis", "Bitte zuerst eine Bestellung auswählen.")
            return
        if not messagebox.askyesno("Löschen", f"Soll Bestellung {order_id} wirklich gelöscht werden?"):
            return
        try:
            remove_order(self.conn, order_id)
        except ValueError as exc:
            messagebox.showerror("Fehler", str(exc))
        else:
            self.refresh_orders()

    # ------------------------------------------------------------------
    def on_close(self) -> None:
        try:
            self.conn.close()
        finally:
            self.master.destroy()


class PartDialog(simpledialog.Dialog):
    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        part: Optional[dict[str, Any]] = None,
        allow_part_number_edit: bool = True,
    ) -> None:
        self._initial = part or {}
        self._allow_part_number_edit = allow_part_number_edit
        super().__init__(parent, title)

    def body(self, master: tk.Misc) -> tk.Widget:
        ttk.Label(master, text="Teilenummer:").grid(row=0, column=0, sticky="w")
        self.part_number_var = tk.StringVar(value=self._initial.get("part_number", ""))
        entry_part = ttk.Entry(master, textvariable=self.part_number_var, width=40)
        entry_part.grid(row=0, column=1, sticky="ew")
        if not self._allow_part_number_edit:
            entry_part.configure(state="disabled")

        ttk.Label(master, text="Beschreibung:").grid(row=1, column=0, sticky="w")
        self.description_var = tk.StringVar(value=self._initial.get("description", ""))
        ttk.Entry(master, textvariable=self.description_var, width=40).grid(row=1, column=1, sticky="ew")

        ttk.Label(master, text="Lieferant:").grid(row=2, column=0, sticky="w")
        self.supplier_var = tk.StringVar(value=self._initial.get("supplier", ""))
        ttk.Entry(master, textvariable=self.supplier_var, width=40).grid(row=2, column=1, sticky="ew")

        ttk.Label(master, text="Hersteller:").grid(row=3, column=0, sticky="w")
        self.manufacturer_var = tk.StringVar(value=self._initial.get("manufacturer", ""))
        ttk.Entry(master, textvariable=self.manufacturer_var, width=40).grid(row=3, column=1, sticky="ew")

        ttk.Label(master, text="Preis (€):").grid(row=4, column=0, sticky="w")
        price_value = self._initial.get("price")
        initial_price = None
        if isinstance(price_value, str) and price_value.endswith("€"):
            initial_price = price_value[:-1].strip()
        elif isinstance(price_value, (int, float)):
            initial_price = format_decimal_entry(float(price_value))
        self.price_var = tk.StringVar(value=initial_price or "")
        ttk.Entry(master, textvariable=self.price_var, width=40).grid(row=4, column=1, sticky="ew")

        ttk.Label(master, text="Shop-Link:").grid(row=5, column=0, sticky="w")
        self.store_var = tk.StringVar(value=self._initial.get("store_link", ""))
        ttk.Entry(master, textvariable=self.store_var, width=40).grid(row=5, column=1, sticky="ew")

        master.columnconfigure(1, weight=1)
        return entry_part

    def validate(self) -> bool:
        part_number = self.part_number_var.get().strip()
        if not part_number:
            messagebox.showerror("Fehler", "Teilenummer darf nicht leer sein.", parent=self)
            return False
        price_text = self.price_var.get().replace("€", "").strip()
        if price_text:
            try:
                parse_decimal(price_text)
            except ValueError:
                messagebox.showerror("Fehler", "Preis muss eine Zahl sein.", parent=self)
                return False
        return True

    def apply(self) -> None:
        price_text = self.price_var.get().replace("€", "").strip()
        price_value = parse_decimal(price_text) if price_text else None
        self.result = {
            "part_number": self.part_number_var.get().strip(),
            "description": self.description_var.get().strip() or None,
            "supplier": self.supplier_var.get().strip() or None,
            "manufacturer": self.manufacturer_var.get().strip() or None,
            "price": price_value,
            "store_link": self.store_var.get().strip() or None,
        }


class ProductDialog(simpledialog.Dialog):
    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        product: Optional[dict[str, Any]] = None,
        allow_name_edit: bool = True,
    ) -> None:
        self._initial = product or {}
        self._allow_name_edit = allow_name_edit
        super().__init__(parent, title)

    def body(self, master: tk.Misc) -> tk.Widget:
        ttk.Label(master, text="Name:").grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar(value=self._initial.get("name", ""))
        entry_name = ttk.Entry(master, textvariable=self.name_var, width=40)
        entry_name.grid(row=0, column=1, sticky="ew")
        if not self._allow_name_edit:
            entry_name.configure(state="disabled")

        ttk.Label(master, text="Beschreibung:").grid(row=1, column=0, sticky="w")
        self.description_var = tk.StringVar(value=self._initial.get("description", ""))
        ttk.Entry(master, textvariable=self.description_var, width=40).grid(row=1, column=1, sticky="ew")

        master.columnconfigure(1, weight=1)
        return entry_name

    def validate(self) -> bool:
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Fehler", "Produktname darf nicht leer sein.", parent=self)
            return False
        return True

    def apply(self) -> None:
        self.result = {
            "name": self.name_var.get().strip(),
            "description": self.description_var.get().strip() or None,
        }


class BomDialog(simpledialog.Dialog):
    def __init__(
        self,
        parent: tk.Misc,
        conn: sqlite3.Connection,
        title: str,
        entry: Optional[dict[str, Any]] = None,
        allow_part_edit: bool = True,
    ) -> None:
        self._initial = entry or {}
        self._allow_part_edit = allow_part_edit
        self._parts = [
            {
                "part_number": row["part_number"],
                "description": row["description"] or "",
                "supplier": row["supplier"] or "",
                "manufacturer": row["manufacturer"] or "",
            }
            for row in list_parts(conn)
        ]
        self._filtered_parts: list[dict[str, str]] = []
        self._updating_from_selection = False
        super().__init__(parent, title)

    def body(self, master: tk.Misc) -> tk.Widget:
        ttk.Label(master, text="Teilenummer:").grid(row=0, column=0, sticky="w")
        self.part_var = tk.StringVar(value=self._initial.get("part_number", ""))
        entry_part = ttk.Entry(master, textvariable=self.part_var, width=40)
        entry_part.grid(row=0, column=1, sticky="ew")
        if not self._allow_part_edit:
            entry_part.configure(state="disabled")

        ttk.Label(master, text="Menge pro Produkt:").grid(row=1, column=0, sticky="w")
        quantity = self._initial.get("quantity")
        formatted_quantity = "" if quantity is None else format_decimal_entry(float(quantity))
        self.quantity_var = tk.StringVar(value=formatted_quantity)
        ttk.Entry(master, textvariable=self.quantity_var, width=40).grid(row=1, column=1, sticky="ew")

        if self._allow_part_edit:
            self.part_var.trace_add("write", self._on_part_var_change)

            columns = ("part_number", "description", "manufacturer", "supplier")
            self.parts_tree = ttk.Treeview(
                master,
                columns=columns,
                show="headings",
                height=8,
            )
            self.parts_tree.heading("part_number", text="Teilenummer")
            self.parts_tree.heading("description", text="Beschreibung")
            self.parts_tree.heading("manufacturer", text="Hersteller")
            self.parts_tree.heading("supplier", text="Lieferant")
            self.parts_tree.column("part_number", width=140, anchor="w")
            self.parts_tree.column("description", width=220, anchor="w")
            self.parts_tree.column("manufacturer", width=160, anchor="w")
            self.parts_tree.column("supplier", width=160, anchor="w")
            self.parts_tree.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(8, 0))

            y_scroll = ttk.Scrollbar(master, orient="vertical", command=self.parts_tree.yview)
            self.parts_tree.configure(yscrollcommand=y_scroll.set)
            y_scroll.grid(row=2, column=2, sticky="ns", pady=(8, 0))

            self.parts_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
            self.parts_tree.bind("<Double-1>", self._on_tree_double_click)
            self.parts_tree.bind("<Return>", self._on_tree_double_click)

            master.columnconfigure(1, weight=1)
            master.rowconfigure(2, weight=1)
            self._refresh_filtered_parts()
        else:
            master.columnconfigure(1, weight=1)

        return entry_part

    def validate(self) -> bool:
        part_number = self.part_var.get().strip()
        if not part_number:
            messagebox.showerror("Fehler", "Teilenummer darf nicht leer sein.", parent=self)
            return False
        try:
            quantity = parse_decimal(self.quantity_var.get().strip())
        except ValueError:
            messagebox.showerror("Fehler", "Menge muss eine Zahl sein.", parent=self)
            return False
        if quantity <= 0:
            messagebox.showerror("Fehler", "Menge muss größer 0 sein.", parent=self)
            return False
        return True

    def apply(self) -> None:
        self.result = {
            "part_number": self.part_var.get().strip(),
            "quantity": parse_decimal(self.quantity_var.get().strip()),
        }

    # ------------------------------------------------------------------
    def _on_part_var_change(self, *_: Any) -> None:
        if self._updating_from_selection:
            return
        self._refresh_filtered_parts()

    def _refresh_filtered_parts(self) -> None:
        query = self.part_var.get().strip().lower()
        if not query:
            self._filtered_parts = list(self._parts)
        else:
            self._filtered_parts = [
                part
                for part in self._parts
                if query in part["part_number"].lower()
                or query in part["description"].lower()
                or query in part["supplier"].lower()
                or query in part["manufacturer"].lower()
            ]

        for item in self.parts_tree.get_children():
            self.parts_tree.delete(item)

        for part in self._filtered_parts:
            self.parts_tree.insert(
                "",
                "end",
                iid=part["part_number"],
                values=(
                    part["part_number"],
                    part["description"],
                    part["manufacturer"],
                    part["supplier"],
                ),
            )

        current = self.part_var.get().strip()
        if current and self.parts_tree.exists(current):
            self.parts_tree.selection_set(current)
            self.parts_tree.see(current)
        else:
            self.parts_tree.selection_remove(self.parts_tree.selection())

    def _on_tree_select(self, _event: tk.Event) -> None:
        selection = self.parts_tree.selection()
        if not selection:
            return
        part_number = selection[0]
        self._updating_from_selection = True
        self.part_var.set(part_number)
        self._updating_from_selection = False

    def _on_tree_double_click(self, _event: tk.Event) -> None:
        if self.parts_tree.selection():
            self.ok()


class OrderDialog(simpledialog.Dialog):
    def __init__(
        self,
        parent: tk.Misc,
        conn: sqlite3.Connection,
        title: str,
        order: Optional[dict[str, Any]] = None,
    ) -> None:
        self._initial = order or {}
        self._parts = [
            {
                "part_number": row["part_number"],
                "description": row["description"] or "",
                "manufacturer": row["manufacturer"] or "",
                "supplier": row["supplier"] or "",
            }
            for row in list_parts(conn)
        ]
        self._filtered_parts: list[dict[str, str]] = []
        self._updating_from_selection = False
        super().__init__(parent, title)

    def body(self, master: tk.Misc) -> tk.Widget:
        ttk.Label(master, text="Teil:").grid(row=0, column=0, sticky="w")
        self.part_var = tk.StringVar(value=self._initial.get("part_number", ""))
        entry_part = ttk.Entry(master, textvariable=self.part_var, width=40)
        entry_part.grid(row=0, column=1, sticky="ew")

        ttk.Label(master, text="Menge:").grid(row=1, column=0, sticky="w")
        quantity = self._initial.get("quantity")
        self.quantity_var = tk.StringVar(
            value="" if quantity is None else format_decimal_entry(float(quantity))
        )
        ttk.Entry(master, textvariable=self.quantity_var, width=40).grid(row=1, column=1, sticky="ew")

        ttk.Label(master, text="Bestelldatum:").grid(row=2, column=0, sticky="w")
        self.order_date_var = tk.StringVar(value=self._initial.get("order_date", ""))
        ttk.Entry(master, textvariable=self.order_date_var, width=40).grid(row=2, column=1, sticky="ew")

        ttk.Label(master, text="Lieferdatum:").grid(row=3, column=0, sticky="w")
        self.delivery_date_var = tk.StringVar(value=self._initial.get("delivery_date", ""))
        ttk.Entry(master, textvariable=self.delivery_date_var, width=40).grid(row=3, column=1, sticky="ew")

        ttk.Label(master, text="Status:").grid(row=4, column=0, sticky="w")
        self.status_var = tk.StringVar(value=self._initial.get("status", ORDER_STATUSES[0]))
        status_box = ttk.Combobox(master, textvariable=self.status_var, values=ORDER_STATUSES, state="readonly")
        status_box.grid(row=4, column=1, sticky="ew")

        self.part_var.trace_add("write", self._on_part_change)

        columns = ("part_number", "description", "manufacturer", "supplier")
        self.parts_tree = ttk.Treeview(master, columns=columns, show="headings", height=8)
        self.parts_tree.heading("part_number", text="Teilenummer")
        self.parts_tree.heading("description", text="Beschreibung")
        self.parts_tree.heading("manufacturer", text="Hersteller")
        self.parts_tree.heading("supplier", text="Lieferant")
        self.parts_tree.column("part_number", width=140, anchor="w")
        self.parts_tree.column("description", width=220, anchor="w")
        self.parts_tree.column("manufacturer", width=160, anchor="w")
        self.parts_tree.column("supplier", width=160, anchor="w")
        self.parts_tree.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=(8, 0))

        y_scroll = ttk.Scrollbar(master, orient="vertical", command=self.parts_tree.yview)
        self.parts_tree.configure(yscrollcommand=y_scroll.set)
        y_scroll.grid(row=5, column=2, sticky="ns", pady=(8, 0))

        self.parts_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.parts_tree.bind("<Double-1>", self._on_tree_double_click)
        self.parts_tree.bind("<Return>", self._on_tree_double_click)

        master.columnconfigure(1, weight=1)
        master.rowconfigure(5, weight=1)

        self._refresh_parts()
        return entry_part

    def validate(self) -> bool:
        part_number = self.part_var.get().strip()
        if not part_number:
            messagebox.showerror("Fehler", "Bitte eine Teilenummer auswählen.", parent=self)
            return False
        try:
            quantity = parse_decimal(self.quantity_var.get().strip())
        except ValueError:
            messagebox.showerror("Fehler", "Menge muss eine Zahl sein.", parent=self)
            return False
        if quantity <= 0:
            messagebox.showerror("Fehler", "Menge muss größer 0 sein.", parent=self)
            return False
        status = self.status_var.get().strip()
        if status not in ORDER_STATUSES:
            messagebox.showerror("Fehler", "Bitte einen gültigen Status wählen.", parent=self)
            return False
        return True

    def apply(self) -> None:
        self.result = {
            "part_number": self.part_var.get().strip(),
            "quantity": parse_decimal(self.quantity_var.get().strip()),
            "order_date": self.order_date_var.get().strip() or None,
            "delivery_date": self.delivery_date_var.get().strip() or None,
            "status": self.status_var.get().strip(),
        }

    # ------------------------------------------------------------------
    def _on_part_change(self, *_: Any) -> None:
        if self._updating_from_selection:
            return
        self._refresh_parts()

    def _refresh_parts(self) -> None:
        query = self.part_var.get().strip().lower()
        if not query:
            self._filtered_parts = list(self._parts)
        else:
            self._filtered_parts = [
                part
                for part in self._parts
                if query in part["part_number"].lower()
                or query in part["description"].lower()
                or query in part["manufacturer"].lower()
                or query in part["supplier"].lower()
            ]

        for item in self.parts_tree.get_children():
            self.parts_tree.delete(item)

        for part in self._filtered_parts:
            self.parts_tree.insert(
                "",
                "end",
                iid=part["part_number"],
                values=(
                    part["part_number"],
                    part["description"],
                    part["manufacturer"],
                    part["supplier"],
                ),
            )

        current = self.part_var.get().strip()
        if current and self.parts_tree.exists(current):
            self.parts_tree.selection_set(current)
            self.parts_tree.see(current)
        else:
            self.parts_tree.selection_remove(self.parts_tree.selection())

    def _on_tree_select(self, _event: tk.Event) -> None:
        selection = self.parts_tree.selection()
        if not selection:
            return
        part_number = selection[0]
        self._updating_from_selection = True
        self.part_var.set(part_number)
        self._updating_from_selection = False

    def _on_tree_double_click(self, _event: tk.Event) -> None:
        if self.parts_tree.selection():
            self.ok()

def launch_gui(conn: sqlite3.Connection, db_path: Path | str) -> None:
    """Startet die Tkinter-Oberfläche."""

    root = tk.Tk()
    app = Application(root, conn, Path(db_path))
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
