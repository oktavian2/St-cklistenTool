"""High level operations on top of the database schema."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import List, Sequence

from .database import transaction


@dataclass
class Part:
    part_number: str
    description: str | None
    supplier: str | None
    price: float | None
    store_link: str | None


@dataclass
class Product:
    name: str
    description: str | None


@dataclass
class Requirement:
    part_number: str
    description: str | None
    supplier: str | None
    price: float | None
    total_quantity: float
    total_cost: float | None


def add_part(conn: sqlite3.Connection, part: Part) -> None:
    with transaction(conn) as cur:
        cur.execute(
            """
            INSERT INTO parts(part_number, description, supplier, price, store_link)
            VALUES (?, ?, ?, ?, ?)
            """,
            (part.part_number, part.description, part.supplier, part.price, part.store_link),
        )


def update_part(conn: sqlite3.Connection, part: Part) -> None:
    # Sicherstellen, dass das Teil existiert, damit ein unveränderter Datensatz
    # nicht fälschlicherweise als "nicht gefunden" gewertet wird.
    get_part_id(conn, part.part_number)
    with transaction(conn) as cur:
        cur.execute(
            """
            UPDATE parts
               SET description = ?, supplier = ?, price = ?, store_link = ?
             WHERE part_number = ?
            """,
            (part.description, part.supplier, part.price, part.store_link, part.part_number),
        )


def get_part_id(conn: sqlite3.Connection, part_number: str) -> int:
    row = conn.execute(
        "SELECT id FROM parts WHERE part_number = ?",
        (part_number,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Teil {part_number!r} ist unbekannt")
    return int(row[0])


def get_product_id(conn: sqlite3.Connection, product_name: str) -> int:
    row = conn.execute(
        "SELECT id FROM products WHERE name = ?",
        (product_name,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Produkt {product_name!r} ist unbekannt")
    return int(row[0])


def add_product(conn: sqlite3.Connection, product: Product) -> None:
    with transaction(conn) as cur:
        cur.execute(
            "INSERT INTO products(name, description) VALUES (?, ?)",
            (product.name, product.description),
        )


def update_product(conn: sqlite3.Connection, product: Product) -> None:
    # Sicherstellen, dass das Produkt existiert (auch wenn keine Änderung erfolgt).
    get_product_id(conn, product.name)
    with transaction(conn) as cur:
        cur.execute(
            "UPDATE products SET description = ? WHERE name = ?",
            (product.description, product.name),
        )


def list_parts(conn: sqlite3.Connection) -> Sequence[sqlite3.Row]:
    return conn.execute(
        """
        SELECT part_number, description, supplier, price, store_link
          FROM parts
         ORDER BY part_number
        """
    ).fetchall()


def list_products(conn: sqlite3.Connection) -> Sequence[sqlite3.Row]:
    return conn.execute(
        """
        SELECT p.name,
               p.description,
               IFNULL(r.quantity, 0) AS requirement
          FROM products AS p
          LEFT JOIN product_requirements AS r ON r.product_id = p.id
         ORDER BY p.name
        """
    ).fetchall()


def set_bom_entry(conn: sqlite3.Connection, product: str, part: str, quantity: float) -> None:
    product_id = get_product_id(conn, product)
    part_id = get_part_id(conn, part)
    with transaction(conn) as cur:
        cur.execute(
            """
            INSERT INTO bill_of_materials(product_id, part_id, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(product_id, part_id) DO UPDATE SET quantity = excluded.quantity
            """,
            (product_id, part_id, quantity),
        )


def set_product_requirement(conn: sqlite3.Connection, product: str, quantity: float) -> None:
    product_id = get_product_id(conn, product)
    with transaction(conn) as cur:
        cur.execute(
            """
            INSERT INTO product_requirements(product_id, quantity)
            VALUES (?, ?)
            ON CONFLICT(product_id) DO UPDATE SET quantity = excluded.quantity
            """,
            (product_id, quantity),
        )


def list_product_requirements(conn: sqlite3.Connection) -> Sequence[sqlite3.Row]:
    return conn.execute(
        """
        SELECT p.name, r.quantity
          FROM product_requirements AS r
          JOIN products AS p ON p.id = r.product_id
         ORDER BY p.name
        """
    ).fetchall()


def get_product_requirement(conn: sqlite3.Connection, product: str) -> float | None:
    """Return the stored demand for a product or ``None`` if not set."""
    product_id = get_product_id(conn, product)
    row = conn.execute(
        "SELECT quantity FROM product_requirements WHERE product_id = ?",
        (product_id,),
    ).fetchone()
    return None if row is None else float(row["quantity"])


def list_bom_entries(conn: sqlite3.Connection, product: str) -> Sequence[sqlite3.Row]:
    """List all bill-of-material entries for the given product."""
    product_id = get_product_id(conn, product)
    return conn.execute(
        """
        SELECT parts.part_number,
               parts.description,
               parts.supplier,
               parts.price,
               parts.store_link,
               bom.quantity
          FROM bill_of_materials AS bom
          JOIN parts ON parts.id = bom.part_id
         WHERE bom.product_id = ?
         ORDER BY parts.part_number
        """,
        (product_id,),
    ).fetchall()


def fetch_requirements(conn: sqlite3.Connection) -> List[Requirement]:
    rows = conn.execute(
        """
        SELECT parts.part_number,
               parts.description,
               parts.supplier,
               parts.price,
               SUM(bom.quantity * req.quantity) AS total_quantity
          FROM bill_of_materials AS bom
          JOIN product_requirements AS req ON req.product_id = bom.product_id
          JOIN parts ON parts.id = bom.part_id
         GROUP BY parts.id
         ORDER BY parts.part_number
        """
    ).fetchall()
    requirements: List[Requirement] = []
    for row in rows:
        price = row["price"]
        total_qty = row["total_quantity"] or 0.0
        total_cost = price * total_qty if price is not None else None
        requirements.append(
            Requirement(
                part_number=row["part_number"],
                description=row["description"],
                supplier=row["supplier"],
                price=price,
                total_quantity=total_qty,
                total_cost=total_cost,
            )
        )
    return requirements


def clone_bom(conn: sqlite3.Connection, source_product: str, target_product: str, scale: float = 1.0) -> None:
    if scale <= 0:
        raise ValueError("Scale muss größer 0 sein")
    source_id = get_product_id(conn, source_product)
    target_id = get_product_id(conn, target_product)
    rows = conn.execute(
        "SELECT part_id, quantity FROM bill_of_materials WHERE product_id = ?",
        (source_id,),
    ).fetchall()
    if not rows:
        raise ValueError(f"Produkt {source_product!r} hat keine Stückliste")
    with transaction(conn) as cur:
        for row in rows:
            cur.execute(
                """
                INSERT INTO bill_of_materials(product_id, part_id, quantity)
                VALUES (?, ?, ?)
                ON CONFLICT(product_id, part_id)
                DO UPDATE SET quantity = excluded.quantity
                """,
                (target_id, row["part_id"], row["quantity"] * scale),
            )


def create_version(conn: sqlite3.Connection, name: str, note: str | None = None) -> None:
    with transaction(conn) as cur:
        cur.execute("INSERT INTO versions(name, note) VALUES (?, ?)", (name, note))
        version_id = cur.lastrowid
        cur.execute(
            """
            INSERT INTO version_items(
                version_id, product_name, part_number, part_description,
                supplier, price, quantity
            )
            SELECT ?, prod.name, part.part_number, part.description, part.supplier, part.price, bom.quantity
              FROM bill_of_materials AS bom
              JOIN products AS prod ON prod.id = bom.product_id
              JOIN parts AS part ON part.id = bom.part_id
            """,
            (version_id,),
        )
        cur.execute(
            """
            INSERT INTO version_demands(version_id, product_name, quantity)
            SELECT ?, prod.name, req.quantity
              FROM product_requirements AS req
              JOIN products AS prod ON prod.id = req.product_id
            """,
            (version_id,),
        )


def list_versions(conn: sqlite3.Connection) -> Sequence[sqlite3.Row]:
    return conn.execute(
        "SELECT id, name, note, created_at FROM versions ORDER BY created_at DESC"
    ).fetchall()


def get_version_details(conn: sqlite3.Connection, name: str) -> tuple[Sequence[sqlite3.Row], Sequence[sqlite3.Row]]:
    version = conn.execute(
        "SELECT id FROM versions WHERE name = ?",
        (name,),
    ).fetchone()
    if version is None:
        raise ValueError(f"Version {name!r} existiert nicht")
    version_id = version["id"]
    items = conn.execute(
        """
        SELECT product_name, part_number, part_description, supplier, price, quantity
          FROM version_items
         WHERE version_id = ?
         ORDER BY product_name, part_number
        """,
        (version_id,),
    ).fetchall()
    demands = conn.execute(
        """
        SELECT product_name, quantity
          FROM version_demands
         WHERE version_id = ?
         ORDER BY product_name
        """,
        (version_id,),
    ).fetchall()
    return items, demands


def remove_part(conn: sqlite3.Connection, part_number: str) -> None:
    with transaction(conn) as cur:
        result = cur.execute("DELETE FROM parts WHERE part_number = ?", (part_number,))
        if result.rowcount == 0:
            raise ValueError(f"Teil {part_number!r} existiert nicht")


def remove_product(conn: sqlite3.Connection, product_name: str) -> None:
    with transaction(conn) as cur:
        result = cur.execute("DELETE FROM products WHERE name = ?", (product_name,))
        if result.rowcount == 0:
            raise ValueError(f"Produkt {product_name!r} existiert nicht")


def remove_bom_entry(conn: sqlite3.Connection, product: str, part: str) -> None:
    product_id = get_product_id(conn, product)
    part_id = get_part_id(conn, part)
    with transaction(conn) as cur:
        result = cur.execute(
            "DELETE FROM bill_of_materials WHERE product_id = ? AND part_id = ?",
            (product_id, part_id),
        )
        if result.rowcount == 0:
            raise ValueError("Eintrag nicht gefunden")


def remove_requirement(conn: sqlite3.Connection, product: str) -> None:
    product_id = get_product_id(conn, product)
    with transaction(conn) as cur:
        result = cur.execute(
            "DELETE FROM product_requirements WHERE product_id = ?",
            (product_id,),
        )
        if result.rowcount == 0:
            raise ValueError(f"Für Produkt {product!r} ist keine Losgröße hinterlegt")
