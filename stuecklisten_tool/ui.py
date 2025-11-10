"""Einfache Tkinter-basierte Oberfläche für das Stücklisten-Tool."""

from __future__ import annotations

import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Optional

from .operations import (
    Part,
    Product,
    add_part,
    add_product,
    fetch_requirements,
    get_product_requirement,
    list_bom_entries,
    list_parts,
    list_product_requirements,
    list_products,
    remove_bom_entry,
    remove_part,
    remove_product,
    remove_requirement,
    set_bom_entry,
    set_product_requirement,
    update_part,
    update_product,
)


class Application(ttk.Frame):
    """Tkinter-Anwendung zur Verwaltung von Teilen, Produkten und Anforderungen."""

    def __init__(self, master: tk.Misc, conn: sqlite3.Connection, db_path: Path) -> None:
        super().__init__(master, padding=10)
        self.conn = conn
        self.db_path = Path(db_path)

        master.title("Stücklisten-Tool")
        master.geometry("1050x650")

        self.pack(fill="both", expand=True)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self._build_parts_tab()
        self._build_products_tab()
        self._build_analysis_tab()

        status = ttk.Label(self, text=f"Datenbank: {self.db_path}")
        status.pack(anchor="w", pady=(6, 0))

        self.refresh_all()

    # ------------------------------------------------------------------
    # Tabs & Layout
    def _build_parts_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Teile")

        columns = ("beschreibung", "lieferant", "preis", "store")
        self.parts_tree = ttk.Treeview(tab, columns=columns, show="headings", height=18)
        self.parts_tree.heading("beschreibung", text="Beschreibung")
        self.parts_tree.heading("lieferant", text="Lieferant")
        self.parts_tree.heading("preis", text="Preis")
        self.parts_tree.heading("store", text="Shop-Link")
        self.parts_tree.column("beschreibung", width=220)
        self.parts_tree.column("lieferant", width=160)
        self.parts_tree.column("preis", width=80, anchor="e")
        self.parts_tree.column("store", width=260)

        y_scroll = ttk.Scrollbar(tab, orient="vertical", command=self.parts_tree.yview)
        self.parts_tree.configure(yscrollcommand=y_scroll.set)
        self.parts_tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")

        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)

        button_frame = ttk.Frame(tab)
        button_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
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

        product_columns = ("beschreibung", "bedarf")
        self.products_tree = ttk.Treeview(top_frame, columns=product_columns, show="headings", height=12)
        self.products_tree.heading("beschreibung", text="Beschreibung")
        self.products_tree.heading("bedarf", text="Losgröße")
        self.products_tree.column("beschreibung", width=280)
        self.products_tree.column("bedarf", width=100, anchor="e")
        self.products_tree.bind("<<TreeviewSelect>>", lambda _event: self.refresh_product_details())

        product_scroll = ttk.Scrollbar(top_frame, orient="vertical", command=self.products_tree.yview)
        self.products_tree.configure(yscrollcommand=product_scroll.set)
        self.products_tree.grid(row=0, column=0, sticky="nsew")
        product_scroll.grid(row=0, column=1, sticky="ns")

        top_frame.columnconfigure(0, weight=1)
        top_frame.rowconfigure(0, weight=1)

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

        bom_columns = ("beschreibung", "lieferant", "preis", "menge")
        self.bom_tree = ttk.Treeview(bom_frame, columns=bom_columns, show="headings", height=10)
        self.bom_tree.heading("beschreibung", text="Beschreibung")
        self.bom_tree.heading("lieferant", text="Lieferant")
        self.bom_tree.heading("preis", text="Preis")
        self.bom_tree.heading("menge", text="Menge pro Produkt")
        self.bom_tree.column("beschreibung", width=240)
        self.bom_tree.column("lieferant", width=160)
        self.bom_tree.column("preis", width=80, anchor="e")
        self.bom_tree.column("menge", width=120, anchor="e")

        bom_scroll = ttk.Scrollbar(bom_frame, orient="vertical", command=self.bom_tree.yview)
        self.bom_tree.configure(yscrollcommand=bom_scroll.set)
        self.bom_tree.grid(row=0, column=0, sticky="nsew")
        bom_scroll.grid(row=0, column=1, sticky="ns")

        bom_frame.columnconfigure(0, weight=1)
        bom_frame.rowconfigure(0, weight=1)

        bom_buttons = ttk.Frame(bom_frame)
        bom_buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        for column in range(3):
            bom_buttons.columnconfigure(column, weight=1)

        ttk.Button(bom_buttons, text="Teil zuordnen", command=self.on_add_bom).grid(row=0, column=0, padx=4)
        ttk.Button(bom_buttons, text="Menge ändern", command=self.on_edit_bom).grid(row=0, column=1, padx=4)
        ttk.Button(bom_buttons, text="Entfernen", command=self.on_remove_bom).grid(row=0, column=2, padx=4)

    def _build_analysis_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Auswertung")

        ttk.Label(tab, text="Aggregierter Teilebedarf", font=("", 11, "bold")).pack(anchor="w")

        columns = ("beschreibung", "lieferant", "preis", "gesamtmenge", "gesamtkosten")
        self.requirements_tree = ttk.Treeview(tab, columns=columns, show="headings", height=18)
        headings = [
            ("beschreibung", "Beschreibung"),
            ("lieferant", "Lieferant"),
            ("preis", "Einzelpreis"),
            ("gesamtmenge", "Gesamtmenge"),
            ("gesamtkosten", "Gesamtkosten"),
        ]
        for name, label in headings:
            self.requirements_tree.heading(name, text=label)
        self.requirements_tree.column("beschreibung", width=240)
        self.requirements_tree.column("lieferant", width=180)
        self.requirements_tree.column("preis", width=100, anchor="e")
        self.requirements_tree.column("gesamtmenge", width=120, anchor="e")
        self.requirements_tree.column("gesamtkosten", width=120, anchor="e")

        scroll = ttk.Scrollbar(tab, orient="vertical", command=self.requirements_tree.yview)
        self.requirements_tree.configure(yscrollcommand=scroll.set)
        self.requirements_tree.pack(fill="both", expand=True, pady=(8, 0))
        scroll.pack(fill="y", side="right")

        ttk.Button(tab, text="Aktualisieren", command=self.refresh_analysis).pack(anchor="e", pady=(10, 0))

    # ------------------------------------------------------------------
    # Helpers
    def refresh_all(self) -> None:
        self.refresh_parts()
        self.refresh_products()
        self.refresh_analysis()

    def refresh_parts(self) -> None:
        for row in self.parts_tree.get_children():
            self.parts_tree.delete(row)
        for part in list_parts(self.conn):
            price = "-" if part["price"] is None else f"{part['price']:.2f}"
            self.parts_tree.insert(
                "",
                "end",
                iid=part["part_number"],
                values=(part["description"] or "-", part["supplier"] or "-", price, part["store_link"] or "-"),
            )

    def refresh_products(self) -> None:
        selection = self.get_selected_product()
        for row in self.products_tree.get_children():
            self.products_tree.delete(row)
        requirement_lookup = {
            row["name"]: row["quantity"] for row in list_product_requirements(self.conn)
        }
        for product in list_products(self.conn):
            quantity = requirement_lookup.get(product["name"])
            display_qty = "-" if quantity is None else f"{quantity:.2f}"
            self.products_tree.insert(
                "",
                "end",
                iid=product["name"],
                values=(product["description"] or "-", display_qty),
            )
        if selection and selection in self.products_tree.get_children(""):
            self.products_tree.selection_set(selection)
            self.products_tree.focus(selection)
        else:
            self.products_tree.selection_remove(self.products_tree.selection())
        self.refresh_product_details()

    def refresh_product_details(self) -> None:
        for row in self.bom_tree.get_children():
            self.bom_tree.delete(row)
        product = self.get_selected_product()
        if not product:
            self.demand_var.set("Keine Losgröße hinterlegt")
            return
        try:
            requirement = get_product_requirement(self.conn, product)
        except ValueError:
            self.demand_var.set("Keine Losgröße hinterlegt")
            return
        if requirement is None:
            self.demand_var.set("Keine Losgröße hinterlegt")
        else:
            self.demand_var.set(f"Losgröße: {requirement:.2f}")
        try:
            rows = list_bom_entries(self.conn, product)
        except ValueError as exc:
            messagebox.showerror("Fehler", str(exc))
            return
        for row in rows:
            price = "-" if row["price"] is None else f"{row['price']:.2f}"
            self.bom_tree.insert(
                "",
                "end",
                iid=row["part_number"],
                values=(row["description"] or "-", row["supplier"] or "-", price, f"{row['quantity']:.2f}"),
            )

    def refresh_analysis(self) -> None:
        for row in self.requirements_tree.get_children():
            self.requirements_tree.delete(row)
        for req in fetch_requirements(self.conn):
            price = "-" if req.price is None else f"{req.price:.2f}"
            total_cost = "-" if req.total_cost is None else f"{req.total_cost:.2f}"
            self.requirements_tree.insert(
                "",
                "end",
                iid=req.part_number,
                values=(
                    req.description or "-",
                    req.supplier or "-",
                    price,
                    f"{req.total_quantity:.2f}",
                    total_cost,
                ),
            )

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
        item = self.parts_tree.item(part_number)
        current = {
            "part_number": part_number,
            "description": item["values"][0] if item["values"][0] != "-" else "",
            "supplier": item["values"][1] if item["values"][1] != "-" else "",
            "price": item["values"][2],
            "store_link": item["values"][3] if item["values"][3] != "-" else "",
        }
        dialog = PartDialog(self, title="Teil bearbeiten", part=current, allow_part_number_edit=False)
        if dialog.result is None:
            return
        price_value = dialog.result.get("price")
        try:
            update_part(
                self.conn,
                Part(
                    part_number=part_number,
                    description=dialog.result.get("description"),
                    supplier=dialog.result.get("supplier"),
                    price=price_value,
                    store_link=dialog.result.get("store_link"),
                ),
            )
        except ValueError as exc:
            messagebox.showerror("Fehler", str(exc))
        else:
            self.refresh_parts()
            self.refresh_product_details()
            self.refresh_analysis()

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
        item = self.bom_tree.item(part_number)
        dialog = BomDialog(
            self,
            self.conn,
            title="Menge anpassen",
            entry={"part_number": part_number, "quantity": float(item["values"][3])},
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

        ttk.Label(master, text="Preis (EUR):").grid(row=3, column=0, sticky="w")
        price_value = self._initial.get("price")
        self.price_var = tk.StringVar(value="" if price_value in (None, "-") else str(price_value))
        ttk.Entry(master, textvariable=self.price_var, width=40).grid(row=3, column=1, sticky="ew")

        ttk.Label(master, text="Shop-Link:").grid(row=4, column=0, sticky="w")
        self.store_var = tk.StringVar(value=self._initial.get("store_link", ""))
        ttk.Entry(master, textvariable=self.store_var, width=40).grid(row=4, column=1, sticky="ew")

        master.columnconfigure(1, weight=1)
        return entry_part

    def validate(self) -> bool:
        part_number = self.part_number_var.get().strip()
        if not part_number:
            messagebox.showerror("Fehler", "Teilenummer darf nicht leer sein.", parent=self)
            return False
        price_text = self.price_var.get().strip()
        if price_text:
            try:
                float(price_text)
            except ValueError:
                messagebox.showerror("Fehler", "Preis muss eine Zahl sein.", parent=self)
                return False
        return True

    def apply(self) -> None:
        price_text = self.price_var.get().strip()
        price_value = float(price_text) if price_text else None
        self.result = {
            "part_number": self.part_number_var.get().strip(),
            "description": self.description_var.get().strip() or None,
            "supplier": self.supplier_var.get().strip() or None,
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
        self.quantity_var = tk.StringVar(value="" if quantity is None else str(quantity))
        ttk.Entry(master, textvariable=self.quantity_var, width=40).grid(row=1, column=1, sticky="ew")

        if self._allow_part_edit:
            self.part_var.trace_add("write", self._on_part_var_change)

            columns = ("part_number", "description", "supplier")
            self.parts_tree = ttk.Treeview(
                master,
                columns=columns,
                show="headings",
                height=8,
            )
            self.parts_tree.heading("part_number", text="Teilenummer")
            self.parts_tree.heading("description", text="Beschreibung")
            self.parts_tree.heading("supplier", text="Lieferant")
            self.parts_tree.column("part_number", width=140, anchor="w")
            self.parts_tree.column("description", width=220, anchor="w")
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
            quantity = float(self.quantity_var.get().strip())
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
            "quantity": float(self.quantity_var.get().strip()),
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
            ]

        for item in self.parts_tree.get_children():
            self.parts_tree.delete(item)

        for part in self._filtered_parts:
            self.parts_tree.insert(
                "",
                "end",
                iid=part["part_number"],
                values=(part["part_number"], part["description"], part["supplier"]),
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
