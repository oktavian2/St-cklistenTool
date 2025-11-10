"""High level operations on top of the database schema."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Sequence

from .database import transaction


@dataclass
class Part:
    part_number: str
    description: str | None
    supplier: str | None
    manufacturer: str | None
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
    manufacturer: str | None
    price: float | None
    total_quantity: float
    total_cost: float | None


@dataclass
class SupplierRequirement:
    supplier: str | None
    total_quantity: float
    total_cost: float | None


@dataclass
class OrderItem:
    part_number: str
    quantity: float


@dataclass
class Order:
    id: int | None
    order_date: str | None
    delivery_date: str | None
    status: str
    items: List[OrderItem]


@dataclass
class OrderItemDetail:
    part_number: str
    description: str | None
    manufacturer: str | None
    supplier: str | None
    quantity: float


@dataclass
class OrderSummary:
    id: int
    order_date: str | None
    delivery_date: str | None
    status: str
    created_at: str
    items: List[OrderItemDetail]


def add_part(conn: sqlite3.Connection, part: Part) -> None:
    with transaction(conn) as cur:
        cur.execute(
            """
            INSERT INTO parts(part_number, description, supplier, manufacturer, price, store_link)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                part.part_number,
                part.description,
                part.supplier,
                part.manufacturer,
                part.price,
                part.store_link,
            ),
        )


def update_part(conn: sqlite3.Connection, part: Part) -> None:
    # Sicherstellen, dass das Teil existiert, damit ein unveränderter Datensatz
    # nicht fälschlicherweise als "nicht gefunden" gewertet wird.
    get_part_id(conn, part.part_number)
    with transaction(conn) as cur:
        cur.execute(
            """
            UPDATE parts
               SET description = ?, supplier = ?, manufacturer = ?, price = ?, store_link = ?
             WHERE part_number = ?
            """,
            (
                part.description,
                part.supplier,
                part.manufacturer,
                part.price,
                part.store_link,
                part.part_number,
            ),
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
        SELECT part_number, description, supplier, manufacturer, price, store_link
          FROM parts
         ORDER BY description COLLATE NOCASE, part_number COLLATE NOCASE
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
               parts.manufacturer,
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
               parts.manufacturer,
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
                manufacturer=row["manufacturer"],
                price=price,
                total_quantity=total_qty,
                total_cost=total_cost,
            )
        )
    return requirements


def fetch_supplier_requirements(conn: sqlite3.Connection) -> List[SupplierRequirement]:
    rows = conn.execute(
        """
        SELECT parts.supplier,
               SUM(bom.quantity * req.quantity) AS total_quantity,
               SUM(
                   CASE WHEN parts.price IS NOT NULL
                        THEN parts.price * bom.quantity * req.quantity
                        ELSE NULL
                   END
               ) AS total_cost
          FROM bill_of_materials AS bom
          JOIN product_requirements AS req ON req.product_id = bom.product_id
          JOIN parts ON parts.id = bom.part_id
         GROUP BY parts.supplier
         ORDER BY parts.supplier COLLATE NOCASE
        """
    ).fetchall()
    summaries: List[SupplierRequirement] = []
    for row in rows:
        total_quantity = row["total_quantity"] or 0.0
        total_cost = row["total_cost"]
        summaries.append(
            SupplierRequirement(
                supplier=row["supplier"],
                total_quantity=total_quantity,
                total_cost=total_cost,
            )
        )
    return summaries


ORDER_STATUSES = ("Offen", "Bestellt", "In Zulieferung", "Geliefert", "Im Lager")


def add_order(conn: sqlite3.Connection, order: Order) -> int:
    if order.status not in ORDER_STATUSES:
        raise ValueError("Ungültiger Bestellstatus")
    if not order.items:
        raise ValueError("Eine Bestellung benötigt mindestens ein Teil")

    items = _resolve_order_items(conn, order.items)
    with transaction(conn) as cur:
        cursor = cur.execute(
            "INSERT INTO orders(order_date, delivery_date, status) VALUES (?, ?, ?)",
            (order.order_date, order.delivery_date, order.status),
        )
        order_id = int(cursor.lastrowid)
        _write_order_items(cur, order_id, items)
        return order_id


def update_order(conn: sqlite3.Connection, order: Order) -> None:
    if order.id is None:
        raise ValueError("Order-ID fehlt")
    if order.status not in ORDER_STATUSES:
        raise ValueError("Ungültiger Bestellstatus")
    if not order.items:
        raise ValueError("Eine Bestellung benötigt mindestens ein Teil")

    items = _resolve_order_items(conn, order.items)
    with transaction(conn) as cur:
        result = cur.execute(
            "UPDATE orders SET order_date = ?, delivery_date = ?, status = ? WHERE id = ?",
            (order.order_date, order.delivery_date, order.status, order.id),
        )
        if result.rowcount == 0:
            raise ValueError("Bestellung existiert nicht")
        cur.execute("DELETE FROM order_items WHERE order_id = ?", (order.id,))
        _write_order_items(cur, order.id, items)


def remove_order(conn: sqlite3.Connection, order_id: int) -> None:
    with transaction(conn) as cur:
        result = cur.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        if result.rowcount == 0:
            raise ValueError("Bestellung existiert nicht")


def list_orders(conn: sqlite3.Connection) -> List[OrderSummary]:
    order_rows = conn.execute(
        """
        SELECT id, order_date, delivery_date, status, created_at
          FROM orders
         ORDER BY order_date IS NULL, order_date, id
        """
    ).fetchall()
    if not order_rows:
        return []

    order_ids = [row["id"] for row in order_rows]
    placeholders = ",".join("?" for _ in order_ids)
    item_rows = conn.execute(
        f"""
        SELECT oi.order_id,
               p.part_number,
               p.description,
               p.manufacturer,
               p.supplier,
               oi.quantity
          FROM order_items AS oi
          JOIN parts AS p ON p.id = oi.part_id
         WHERE oi.order_id IN ({placeholders})
         ORDER BY oi.order_id, p.part_number COLLATE NOCASE
        """,
        order_ids,
    ).fetchall()

    items_by_order: Dict[int, List[OrderItemDetail]] = {order_id: [] for order_id in order_ids}
    for item in item_rows:
        items_by_order[item["order_id"]].append(
            OrderItemDetail(
                part_number=item["part_number"],
                description=item["description"],
                manufacturer=item["manufacturer"],
                supplier=item["supplier"],
                quantity=item["quantity"],
            )
        )

    summaries: List[OrderSummary] = []
    for row in order_rows:
        summaries.append(
            OrderSummary(
                id=row["id"],
                order_date=row["order_date"],
                delivery_date=row["delivery_date"],
                status=row["status"],
                created_at=row["created_at"],
                items=items_by_order.get(row["id"], []),
            )
        )
    return summaries


def _resolve_order_items(conn: sqlite3.Connection, items: Sequence[OrderItem]) -> List[tuple[int, float]]:
    aggregated: Dict[int, float] = {}
    for item in items:
        part_number = item.part_number.strip()
        if not part_number:
            raise ValueError("Teilenummer darf nicht leer sein")
        if item.quantity <= 0:
            raise ValueError("Mengen müssen größer 0 sein")
        part_id = get_part_id(conn, part_number)
        aggregated[part_id] = aggregated.get(part_id, 0.0) + item.quantity
    return [(part_id, quantity) for part_id, quantity in aggregated.items()]


def _write_order_items(cur: sqlite3.Connection, order_id: int, items: Sequence[tuple[int, float]]) -> None:
    for part_id, quantity in items:
        cur.execute(
            "INSERT INTO order_items(order_id, part_id, quantity) VALUES (?, ?, ?)",
            (order_id, part_id, quantity),
        )


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
