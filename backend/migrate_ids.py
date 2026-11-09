import sqlite3
from datetime import datetime
import re

def generate_significant_id(prefix, seed=None, context=None, existing_ids=None):
    if existing_ids is None:
        existing_ids = set()

    now = datetime.now()
    if prefix == "USR":
        seed_val = str(seed)[-4:] if seed else "0000"
        context_val = now.strftime("%j")
    elif prefix == "CAT":
        seed_val = now.strftime("%y%m")
        context_val = "00"
    elif prefix == "PRO":
        seed_val = str(seed)[:4] if seed else "0000"
        context_val = now.strftime("%m%d")
    elif prefix == "VEN":
        seed_val = now.strftime("%y%m%d")
        context_val = now.strftime("%H%M")
    else:
        seed_val = now.strftime("%y%m%d")
        context_val = "00"

    base_id = f"{prefix}-{seed_val}-{context_val}"
    counter = 1
    final_id = base_id
    while final_id in existing_ids:
        final_id = f"{base_id}-{counter:02d}"
        counter += 1
    return final_id

def migrate():
    conn = sqlite3.connect('backend/data/inventario.sqlite3')
    cur = conn.cursor()
    cur.execute('PRAGMA foreign_keys = OFF')

    # 1. Migrate Users
    print("Migrating Users...")
    cur.execute('SELECT id, username, name, role, is_active, password_hash, created_at FROM users')
    users = cur.fetchall()
    user_map = {}
    user_ids = set()
    for u in users:
        old_id = u[0]
        new_id = generate_significant_id("USR", seed=old_id, existing_ids=user_ids)
        user_ids.add(new_id)
        user_map[old_id] = new_id
        cur.execute('UPDATE users SET id = ?, cedula = ? WHERE id = ?', (new_id, old_id, old_id))

    # 2. Migrate Categories
    print("Migrating Categories...")
    cur.execute('SELECT id, name, description, created_at FROM categories')
    cats = cur.fetchall()
    cat_map = {}
    cat_ids = set()
    for c in cats:
        old_id = c[0]
        new_id = generate_significant_id("CAT", existing_ids=cat_ids)
        cat_ids.add(new_id)
        cat_map[old_id] = new_id
        cur.execute('UPDATE categories SET id = ? WHERE id = ?', (new_id, old_id))

    # 3. Migrate Products
    print("Migrating Products...")
    cur.execute('SELECT id, name, description, category_id, unit, current_stock, min_stock, price, expiry_date, created_at FROM products')
    prods = cur.fetchall()
    prod_map = {}
    prod_ids = set()
    for p in prods:
        old_id = p[0]
        cat_id = p[3]
        new_id = generate_significant_id("PRO", seed=cat_id, existing_ids=prod_ids)
        prod_ids.add(new_id)
        prod_map[old_id] = new_id
        new_cat_id = cat_map.get(cat_id, cat_id)
        cur.execute('UPDATE products SET id = ?, category_id = ? WHERE id = ?', (new_id, new_cat_id, old_id))

    # 4. Migrate Movements
    print("Migrating Movements...")
    cur.execute('SELECT id, product_id, type, quantity, previous_stock, new_stock, notes, created_by, created_at FROM movements')
    movs = cur.fetchall()
    mov_ids = set()
    for m in movs:
        old_id = m[0]
        prod_id = m[1]
        user_id = m[7]
        new_id = generate_significant_id("MOV", existing_ids=mov_ids)
        mov_ids.add(new_id)
        new_prod_id = prod_map.get(prod_id, prod_id)
        new_user_id = user_map.get(user_id, user_id)
        cur.execute('UPDATE movements SET id = ?, product_id = ?, created_by = ? WHERE id = ?', (new_id, new_prod_id, new_user_id, old_id))

    # 5. Migrate Sales
    print("Migrating Sales...")
    cur.execute('SELECT id, total, notes, customer_info, status, created_by, created_at FROM sales')
    sales = cur.fetchall()
    sale_map = {}
    sale_ids = set()
    for s in sales:
        old_id = s[0]
        user_id = s[5]
        new_id = generate_significant_id("VEN", existing_ids=sale_ids)
        sale_ids.add(new_id)
        sale_map[old_id] = new_id
        new_user_id = user_map.get(user_id, user_id)
        cur.execute('UPDATE sales SET id = ?, created_by = ? WHERE id = ?', (new_id, new_user_id, old_id))

    # 6. Migrate Sale Items
    print("Migrating Sale Items...")
    cur.execute('SELECT id, sale_id, product_id, quantity, unit_price, subtotal FROM sale_items')
    items = cur.fetchall()
    item_ids = set()
    for i in items:
        old_id = i[0]
        sale_id = i[1]
        prod_id = i[2]
        new_id = generate_significant_id("DET", existing_ids=item_ids)
        item_ids.add(new_id)
        new_sale_id = sale_map.get(sale_id, sale_id)
        new_prod_id = prod_map.get(prod_id, prod_id)
        cur.execute('UPDATE sale_items SET id = ?, sale_id = ?, product_id = ? WHERE id = ?', (new_id, new_sale_id, new_prod_id, old_id))

    # 7. Migrate Audit Logs
    print("Migrating Audit Logs...")
    cur.execute('SELECT id, user_id, username, user_role, action, description, session_key, created_at FROM audit_logs')
    logs = cur.fetchall()
    log_ids = set()
    for l in logs:
        old_id = l[0]
        user_id = l[1]
        new_id = generate_significant_id("AUD", existing_ids=log_ids)
        log_ids.add(new_id)
        new_user_id = user_map.get(user_id, user_id)
        cur.execute('UPDATE audit_logs SET id = ?, user_id = ? WHERE id = ?', (new_id, new_user_id, old_id))

    conn.commit()
    cur.execute('PRAGMA foreign_keys = ON')
    conn.close()
    print("Migration completed successfully!")

if __name__ == "__main__":
    migrate()
