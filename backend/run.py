#!/usr/bin/env python3
import json
import os
import secrets
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(
    os.environ.get("INVENTARIO_DATA_DIR", BACKEND_DIR / "data")
).expanduser().resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "inventario.settings")
os.environ.setdefault("INVENTARIO_DATA_DIR", str(DATA_DIR))
sys.path.insert(0, str(BACKEND_DIR))

if not os.environ.get("SESSION_SECRET"):
    session_secret_file = DATA_DIR / ".session_secret"
    if session_secret_file.exists():
        os.environ["SESSION_SECRET"] = session_secret_file.read_text(encoding="utf-8").strip()
    else:
        generated_secret = secrets.token_urlsafe(48)
        try:
            descriptor = os.open(
                session_secret_file,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(descriptor, "w", encoding="utf-8") as secret_file:
                secret_file.write(generated_secret)
            os.environ["SESSION_SECRET"] = generated_secret
        except FileExistsError:
            os.environ["SESSION_SECRET"] = session_secret_file.read_text(
                encoding="utf-8"
            ).strip()

import bcrypt
import django

django.setup()

from django.core.management import call_command, execute_from_command_line
from django.db import connection

call_command("migrate", interactive=False, verbosity=1)

# El ID de cada tabla es un código legible, no un autoincremental:
#   users          -> cédula de la persona (ej. V-12345678)
#   categories     -> CAT-001
#   products       -> PRO-0001
#   movements      -> MOV-000001
#   sales          -> VEN-000001
#   sale_items     -> DET-000001
#   audit_logs     -> AUD-000001
schema_statements = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id VARCHAR(20) PRIMARY KEY,
        username VARCHAR(255) NOT NULL UNIQUE,
        name VARCHAR(255) NOT NULL,
        password_hash TEXT NOT NULL,
        role VARCHAR(50) NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS categories (
        id VARCHAR(20) PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        description TEXT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS products (
        id VARCHAR(20) PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        description TEXT NULL,
        category_id VARCHAR(20) NULL REFERENCES categories(id)
            ON DELETE SET NULL ON UPDATE CASCADE,
        unit VARCHAR(50) NOT NULL,
        current_stock DECIMAL(12, 4) NOT NULL DEFAULT 0,
        min_stock DECIMAL(12, 4) NOT NULL DEFAULT 0,
        price DECIMAL(12, 2) NULL,
        expiry_date DATE NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS movements (
        id VARCHAR(20) PRIMARY KEY,
        product_id VARCHAR(20) NOT NULL REFERENCES products(id)
            ON DELETE CASCADE ON UPDATE CASCADE,
        type VARCHAR(50) NOT NULL,
        quantity DECIMAL(12, 4) NOT NULL,
        previous_stock DECIMAL(12, 4) NOT NULL,
        new_stock DECIMAL(12, 4) NOT NULL,
        notes TEXT NULL,
        created_by VARCHAR(20) NULL REFERENCES users(id)
            ON DELETE SET NULL ON UPDATE CASCADE,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sales (
        id VARCHAR(20) PRIMARY KEY,
        total DECIMAL(14, 2) NOT NULL,
        notes TEXT NULL,
        customer_info TEXT NULL,
        status VARCHAR(50) NOT NULL DEFAULT 'activa',
        created_by VARCHAR(20) NULL REFERENCES users(id)
            ON DELETE SET NULL ON UPDATE CASCADE,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sale_items (
        id VARCHAR(20) PRIMARY KEY,
        sale_id VARCHAR(20) NOT NULL REFERENCES sales(id)
            ON DELETE CASCADE ON UPDATE CASCADE,
        product_id VARCHAR(20) NOT NULL REFERENCES products(id)
            ON DELETE CASCADE ON UPDATE CASCADE,
        quantity DECIMAL(12, 4) NOT NULL,
        unit_price DECIMAL(12, 2) NOT NULL,
        subtotal DECIMAL(14, 2) NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
        id VARCHAR(20) PRIMARY KEY,
        user_id VARCHAR(20) NOT NULL,
        username VARCHAR(255) NOT NULL,
        user_role VARCHAR(50) NOT NULL,
        action VARCHAR(100) NOT NULL,
        description TEXT NOT NULL,
        session_key VARCHAR(40) NOT NULL DEFAULT '',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
]


def _map_legacy_id(value, prefix, width):
    """Convierte un id numérico viejo (1, 2...) en un código legible."""
    if value is None:
        return None
    text = str(value)
    if text.isdigit():
        return f"{prefix}-{int(text):0{width}d}"
    return text


def _table_exists(cursor, table):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", [table]
    )
    return cursor.fetchone() is not None


def _rows(cursor, table):
    if not _table_exists(cursor, table):
        return []
    cursor.execute(f"SELECT * FROM {table}")
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def migrate_legacy_ids():
    """Pasa una base vieja de ids numéricos a ids con significado lógico.

    Solo actúa una vez: si users.id ya es texto, no hace nada.
    Antes de tocar nada guarda una copia de seguridad del archivo SQLite.
    """
    db_path = Path(connection.settings_dict["NAME"])

    with connection.cursor() as cursor:
        if not _table_exists(cursor, "users"):
            return
        cursor.execute("PRAGMA table_info(users)")
        id_type = ""
        for column in cursor.fetchall():
            if column[1] == "id":
                id_type = (column[2] or "").upper()
                break

    if "INT" not in id_type:
        return

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = db_path.with_name(f"{db_path.name}.bak-{stamp}")
    connection.close()
    shutil.copy2(db_path, backup_path)
    print(f"Copia de seguridad de la base creada en {backup_path.name}")

    raw = sqlite3.connect(str(db_path))
    raw.row_factory = sqlite3.Row
    raw.isolation_level = None
    cursor = raw.cursor()
    cursor.execute("PRAGMA foreign_keys = OFF")
    cursor.execute("BEGIN")
    try:
        users = _rows(cursor, "users")
        categories = _rows(cursor, "categories")
        products = _rows(cursor, "products")
        movements = _rows(cursor, "movements")
        sales = _rows(cursor, "sales")
        sale_items = _rows(cursor, "sale_items")
        audit_logs = _rows(cursor, "audit_logs")

        user_map = {row["id"]: _map_legacy_id(row["id"], "V", 8) for row in users}
        category_map = {
            row["id"]: _map_legacy_id(row["id"], "CAT", 3) for row in categories
        }
        product_map = {
            row["id"]: _map_legacy_id(row["id"], "PRO", 4) for row in products
        }
        movement_map = {
            row["id"]: _map_legacy_id(row["id"], "MOV", 6) for row in movements
        }
        sale_map = {row["id"]: _map_legacy_id(row["id"], "VEN", 6) for row in sales}
        sale_item_map = {
            row["id"]: _map_legacy_id(row["id"], "DET", 6) for row in sale_items
        }
        audit_map = {
            row["id"]: _map_legacy_id(row["id"], "AUD", 6) for row in audit_logs
        }

        for table in (
            "audit_logs",
            "sale_items",
            "movements",
            "sales",
            "products",
            "categories",
            "users",
        ):
            cursor.execute(f"DROP TABLE IF EXISTS {table}")

        for statement in schema_statements:
            cursor.execute(statement)

        for row in users:
            cursor.execute(
                """
                INSERT INTO users
                    (id, username, name, password_hash, role, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    user_map[row["id"]],
                    row["username"],
                    row["name"],
                    row["password_hash"],
                    row["role"],
                    row["is_active"],
                    row["created_at"],
                ],
            )

        for row in categories:
            cursor.execute(
                """
                INSERT INTO categories (id, name, description, created_at)
                VALUES (?, ?, ?, ?)
                """,
                [
                    category_map[row["id"]],
                    row["name"],
                    row["description"],
                    row["created_at"],
                ],
            )

        for row in products:
            cursor.execute(
                """
                INSERT INTO products
                    (id, name, description, category_id, unit, current_stock,
                     min_stock, price, expiry_date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    product_map[row["id"]],
                    row["name"],
                    row["description"],
                    category_map.get(row["category_id"]),
                    row["unit"],
                    row["current_stock"],
                    row["min_stock"],
                    row["price"],
                    row["expiry_date"],
                    row["created_at"],
                ],
            )

        for row in movements:
            cursor.execute(
                """
                INSERT INTO movements
                    (id, product_id, type, quantity, previous_stock, new_stock,
                     notes, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    movement_map[row["id"]],
                    product_map.get(row["product_id"]),
                    row["type"],
                    row["quantity"],
                    row["previous_stock"],
                    row["new_stock"],
                    row["notes"],
                    user_map.get(row["created_by"]),
                    row["created_at"],
                ],
            )

        for row in sales:
            cursor.execute(
                """
                INSERT INTO sales
                    (id, total, notes, customer_info, status, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    sale_map[row["id"]],
                    row["total"],
                    row["notes"],
                    row["customer_info"],
                    row["status"],
                    user_map.get(row["created_by"]),
                    row["created_at"],
                ],
            )

        for row in sale_items:
            cursor.execute(
                """
                INSERT INTO sale_items
                    (id, sale_id, product_id, quantity, unit_price, subtotal)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    sale_item_map[row["id"]],
                    sale_map.get(row["sale_id"]),
                    product_map.get(row["product_id"]),
                    row["quantity"],
                    row["unit_price"],
                    row["subtotal"],
                ],
            )

        for row in audit_logs:
            cursor.execute(
                """
                INSERT INTO audit_logs
                    (id, user_id, username, user_role, action, description,
                     session_key, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    audit_map[row["id"]],
                    user_map.get(row["user_id"], str(row["user_id"])),
                    row["username"],
                    row["user_role"],
                    row["action"],
                    row["description"],
                    row["session_key"],
                    row["created_at"],
                ],
            )

        cursor.execute("COMMIT")
    except Exception:
        cursor.execute("ROLLBACK")
        raise
    finally:
        raw.close()

    print(
        "Ids migrados a formato legible: "
        f"{len(users)} usuarios, {len(categories)} tipos, {len(products)} productos."
    )


migrate_legacy_ids()

with connection.cursor() as cursor:
    for statement in schema_statements:
        cursor.execute(statement)

from api.models import User


def load_seed_snapshot() -> None:
    seed_file = BACKEND_DIR / "seed_data.json"
    if not seed_file.is_file():
        return

    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] > 0:
            return

    snapshot = json.loads(seed_file.read_text(encoding="utf-8"))
    from django.db import transaction

    with transaction.atomic():
        with connection.cursor() as cursor:
            for user in snapshot.get("users", []):
                cursor.execute(
                    """
                    INSERT INTO users
                        (id, username, name, password_hash, role, is_active, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        user["id"],
                        user["username"],
                        user["name"],
                        user["password_hash"],
                        user["role"],
                        user["is_active"],
                        user["created_at"],
                    ],
                )
            for category in snapshot.get("categories", []):
                cursor.execute(
                    """
                    INSERT INTO categories (id, name, description, created_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    [
                        category["id"],
                        category["name"],
                        category["description"],
                        category["created_at"],
                    ],
                )
            for product in snapshot.get("products", []):
                cursor.execute(
                    """
                    INSERT INTO products
                        (id, name, description, category_id, unit, current_stock,
                         min_stock, price, created_at, expiry_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        product["id"],
                        product["name"],
                        product["description"],
                        product["category_id"],
                        product["unit"],
                        product["current_stock"],
                        product["min_stock"],
                        product["price"],
                        product["created_at"],
                        product["expiry_date"],
                    ],
                )
    print(
        "Datos de prueba importados: "
        f"{len(snapshot.get('users', []))} usuarios, "
        f"{len(snapshot.get('categories', []))} tipos y "
        f"{len(snapshot.get('products', []))} productos."
    )


load_seed_snapshot()

if not User.objects.filter(username="admin").exists():
    initial_password = secrets.token_urlsafe(12)
    User.objects.create(
        id="V-00000000",
        username="admin",
        name="Administrador",
        password_hash=bcrypt.hashpw(
            initial_password.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8"),
        role="admin",
        is_active=True,
    )
    print("\nCuenta inicial creada")
    print("Usuario: admin")
    print(f"Contraseña temporal: {initial_password}")
    print("Guárdala: solo se muestra en este primer inicio.\n")

if os.environ.get("INVENTARIO_INIT_ONLY") == "1":
    print("Base de datos inicializada.")
    raise SystemExit(0)

port = os.environ.get("PORT", "8080")
print(f"API disponible en http://127.0.0.1:{port}/api/")
print("En desarrollo, ejecuta el frontend Vite en el puerto 5173.")
print("Para acceso por LAN, abre el frontend en la IP de este computador.")
print("No configures reenvío de puertos del router ni expongas el sistema a Internet.")
execute_from_command_line(
    ["manage.py", "runserver", f"0.0.0.0:{port}", "--noreload"]
)
