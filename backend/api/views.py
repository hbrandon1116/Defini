import json
import re
import bcrypt
from decimal import Decimal
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction, connection
from django.utils import timezone

from .models import User, Category, Product, Movement, Sale, SaleItem, AuditLog


def _f(v):
    if v is None:
        return None
    return float(v)


def _body(request):
    try:
        return json.loads(request.body) if request.body else {}
    except Exception:
        return {}


CEDULA_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{4,19}$")


def _normalize_cedula(value):
    return re.sub(r"\s+", "", str(value or "")).upper()


def _valid_cedula(value):
    return bool(CEDULA_RE.fullmatch(value))


def _generate_significant_id(model, prefix, seed=None, context=None):
    """
    Genera un ID con significado, numérico/alfanumérico, evitando colisiones.
    """
    from datetime import datetime

    # 1. Definir el núcleo del ID basado en el tipo de modelo
    if prefix == "USR":
        # Basado en los últimos 4 dígitos de la cédula y el día del año
        seed_val = str(seed)[-4:] if seed else "0000"
        context_val = datetime.now().strftime("%j") # Día del año (001-366)
    elif prefix == "CAT":
        # Basado en año y mes
        seed_val = datetime.now().strftime("%y%m")
        context_val = "00"
    elif prefix == "PRO":
        # Basado en la categoría y un código breve
        seed_val = str(seed)[:4] if seed else "0000"
        context_val = datetime.now().strftime("%m%d")
    elif prefix == "VEN":
        # Basado en fecha y hora compacta
        seed_val = datetime.now().strftime("%y%m%d")
        context_val = datetime.now().strftime("%H%M")
    else:
        # Genérico para MOV, DET, AUD
        seed_val = datetime.now().strftime("%y%m%d")
        context_val = "00"

    base_id = f"{prefix}-{seed_val}-{context_val}"

    # 2. Resolución de colisiones mediante persistencia
    counter = 1
    final_id = base_id
    while model.objects.filter(pk=final_id).exists():
        final_id = f"{base_id}-{counter:02d}"
        counter += 1

    return final_id

def _next_code(model, prefix, width):
    # Se mantiene por compatibilidad temporal, pero se recomienda usar _generate_significant_id
    return _generate_significant_id(model, prefix)


def _user_dict(session):
    return {
        "id": session.get("user_id"),
        "username": session.get("user_username"),
        "name": session.get("user_name"),
        "role": session.get("user_role"),
    }


def auth_required(f):
    @wraps(f)
    def wrapper(request, *args, **kwargs):
        if not request.session.get("user_id"):
            return JsonResponse({"error": "No autenticado"}, status=401)
        return f(request, *args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(request, *args, **kwargs):
        if not request.session.get("user_id"):
            return JsonResponse({"error": "No autenticado"}, status=401)
        if request.session.get("user_role") != "admin":
            return JsonResponse({"error": "Acceso denegado"}, status=403)
        return f(request, *args, **kwargs)
    return wrapper


def log_action(request, action, description):
    user_id = request.session.get("user_id")
    if not user_id:
        return
    session_key = request.session.session_key or ""
    try:
        AuditLog(
            id=_next_code(AuditLog, "AUD", 6),
            user_id=user_id,
            username=request.session.get("user_username", ""),
            user_role=request.session.get("user_role", ""),
            action=action,
            description=description,
            session_key=session_key,
        ).save()
    except Exception:
        pass


def fmt_product(p, category_name=None):
    from datetime import date, timedelta
    current_stock = _f(p.current_stock)
    min_stock = _f(p.min_stock)
    today = date.today()
    expiry = p.expiry_date if p.expiry_date else None
    is_expired = expiry is not None and expiry < today
    is_expiring_soon = expiry is not None and not is_expired and expiry <= today + timedelta(days=7)
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "categoryId": p.category_id,
        "categoryName": category_name if category_name is not None else None,
        "unit": p.unit,
        "currentStock": current_stock,
        "minStock": min_stock,
        "price": _f(p.price),
        "isLowStock": current_stock <= min_stock,
        "expiryDate": expiry.isoformat() if expiry else None,
        "isExpired": is_expired,
        "isExpiringSoon": is_expiring_soon,
        "createdAt": p.created_at.isoformat() if p.created_at else None,
    }


@csrf_exempt
def auth_login(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    body = _body(request)
    username = body.get("username", "")
    password = body.get("password", "")
    if not username or not password:
        return JsonResponse({"error": "Usuario y contraseña requeridos"}, status=400)
    try:
        user = User.objects.get(username=username, is_active=True)
    except User.DoesNotExist:
        return JsonResponse({"error": "Credenciales inválidas"}, status=401)
    try:
        valid = bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8"))
    except Exception:
        valid = False
    if not valid:
        return JsonResponse({"error": "Credenciales inválidas"}, status=401)
    request.session["user_id"] = user.id
    request.session["user_username"] = user.username
    request.session["user_name"] = user.name
    request.session["user_role"] = user.role
    request.session.save()
    try:
        AuditLog(
            id=_next_code(AuditLog, "AUD", 6),
            user_id=user.id,
            username=user.username,
            user_role=user.role,
            action="login",
            description=f"{user.name} inició sesión",
            session_key=request.session.session_key or "",
        ).save()
    except Exception:
        pass
    return JsonResponse({"id": user.id, "username": user.username, "name": user.name, "role": user.role})


@csrf_exempt
def auth_logout(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    log_action(request, "logout", f"{request.session.get('user_name', '')} cerró sesión")
    request.session.flush()
    return JsonResponse({"message": "Sesión cerrada"})


@csrf_exempt
@auth_required
def auth_me(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    return JsonResponse(_user_dict(request.session))


@csrf_exempt
@auth_required
def categories(request):
    if request.method == "GET":
        cats = Category.objects.filter(is_deleted=False).order_by("name")
        data = [
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "productCount": Product.objects.filter(category_id=c.id, is_deleted=False).count(),
                "createdAt": c.created_at.isoformat() if c.created_at else None,
            }
            for c in cats
        ]
        return JsonResponse(data, safe=False)
    if request.method == "POST":
        if request.session.get("user_role") != "admin":
            return JsonResponse({"error": "Acceso denegado"}, status=403)
        body = _body(request)
        name = body.get("name", "").strip()
        if not name:
            return JsonResponse({"error": "El nombre es requerido"}, status=400)
        cat = Category(
            id=_next_code(Category, "CAT", 3),
            name=name,
            description=body.get("description"),
        )
        cat.save()
        log_action(request, "create_category", f"Creó categoría '{cat.name}'")
        return JsonResponse(
            {
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "productCount": 0,
                "createdAt": cat.created_at.isoformat() if cat.created_at else None,
            },
            status=201,
        )
    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@auth_required
def category_detail(request, pk):
    try:
        cat = Category.objects.get(pk=pk)
    except Category.DoesNotExist:
        return JsonResponse({"error": "Categoría no encontrada"}, status=404)
    if request.method in ("PUT", "PATCH"):
        if request.session.get("user_role") != "admin":
            return JsonResponse({"error": "Acceso denegado"}, status=403)
        body = _body(request)
        old_name = cat.name
        cat.name = body.get("name", cat.name)
        cat.description = body.get("description", cat.description)
        cat.save()
        log_action(request, "edit_category", f"Editó categoría '{old_name}'")
        return JsonResponse(
            {
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "productCount": Product.objects.filter(category_id=cat.id).count(),
                "createdAt": cat.created_at.isoformat() if cat.created_at else None,
            }
        )
    if request.method == "DELETE":
        if request.session.get("user_role") != "admin":
            return JsonResponse({"error": "Acceso denegado"}, status=403)

        # Verificar si hay productos asociados
        if Product.objects.filter(category_id=cat.id, is_deleted=False).exists():
            return JsonResponse(
                {"error": "No se puede eliminar una categoría que contiene productos activos. Mueva los productos a otra categoría primero."},
                status=400
            )

        try:
            log_action(request, "delete_category", f"Marcó como eliminada la categoría '{cat.name}'")
            cat.is_deleted = True
            cat.save()
            return JsonResponse({"message": "Categoría eliminada (lógica)"})
        except Exception as e:
            return JsonResponse({"error": f"Error al eliminar la categoría: {str(e)}"}, status=500)
    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@auth_required
def products(request):
    if request.method == "GET":
        qs = Product.objects.filter(is_deleted=False).select_related("category").order_by("name")
        search = request.GET.get("search", "")
        category_id = request.GET.get("categoryId", "")
        low_stock = request.GET.get("lowStock", "")
        if search:
            qs = qs.filter(name__icontains=search)
        if category_id:
            qs = qs.filter(category_id=category_id)
        expiring = request.GET.get("expiring", "")
        result = [fmt_product(p, p.category.name if p.category else None) for p in qs]
        if low_stock == "true":
            result = [p for p in result if p["isLowStock"]]
        if expiring == "true":
            result = [p for p in result if p["isExpired"] or p["isExpiringSoon"]]
        return JsonResponse(result, safe=False)
    if request.method == "POST":
        if request.session.get("user_role") != "admin":
            return JsonResponse({"error": "Acceso denegado"}, status=403)
        body = _body(request)
        name = body.get("name", "").strip()
        unit = body.get("unit", "").strip()
        if not name or not unit:
            return JsonResponse({"error": "Nombre y unidad son requeridos"}, status=400)
        cat_id = body.get("categoryId")
        from datetime import date as date_type
        expiry_raw = body.get("expiryDate")
        expiry = None
        if expiry_raw:
            try:
                expiry = date_type.fromisoformat(expiry_raw)
            except Exception:
                pass
        p = Product(
            id=_next_code(Product, "PRO", 4),
            name=name,
            description=body.get("description"),
            unit=unit,
            current_stock=Decimal(str(body.get("currentStock", 0))),
            min_stock=Decimal(str(body.get("minStock", 0))),
            price=Decimal(str(body.get("price"))) if body.get("price") is not None else None,
            expiry_date=expiry,
        )
        if cat_id is not None:
            p.category_id = str(cat_id)
        p.save()
        category_name = None
        if p.category_id:
            try:
                category_name = Category.objects.get(pk=p.category_id).name
            except Category.DoesNotExist:
                pass
        log_action(request, "create_product", f"Creó producto '{p.name}'")
        return JsonResponse(fmt_product(p, category_name), status=201)
    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@auth_required
def product_detail(request, pk):
    try:
        p = Product.objects.select_related("category").get(pk=pk)
    except Product.DoesNotExist:
        return JsonResponse({"error": "Producto no encontrado"}, status=404)
    if request.method == "GET":
        return JsonResponse(fmt_product(p, p.category.name if p.category else None))
    if request.method in ("PUT", "PATCH"):
        if request.session.get("user_role") != "admin":
            return JsonResponse({"error": "Acceso denegado"}, status=403)
        body = _body(request)
        old_name = p.name
        p.name = body.get("name", p.name)
        p.description = body.get("description", p.description)
        p.unit = body.get("unit", p.unit)
        if "currentStock" in body:
            p.current_stock = Decimal(str(body["currentStock"]))
        if "minStock" in body:
            p.min_stock = Decimal(str(body["minStock"]))
        if "price" in body:
            p.price = Decimal(str(body["price"])) if body["price"] is not None else None
        if "expiryDate" in body:
            from datetime import date as date_type
            expiry_raw = body["expiryDate"]
            if expiry_raw:
                try:
                    p.expiry_date = date_type.fromisoformat(expiry_raw)
                except Exception:
                    p.expiry_date = None
            else:
                p.expiry_date = None
        cat_id = body.get("categoryId", "UNCHANGED")
        if cat_id != "UNCHANGED":
            p.category_id = str(cat_id) if cat_id else None
        p.save()
        category_name = None
        if p.category_id:
            try:
                category_name = Category.objects.get(pk=p.category_id).name
            except Category.DoesNotExist:
                pass
        log_action(request, "edit_product", f"Editó producto '{old_name}'")
        return JsonResponse(fmt_product(p, category_name))
    if request.method == "DELETE":
        if request.session.get("user_role") != "admin":
            return JsonResponse({"error": "Acceso denegado"}, status=403)
        log_action(request, "delete_product", f"Eliminó producto '{p.name}'")
        p.delete()
        return JsonResponse({"message": "Producto eliminado"})
    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@auth_required
def movements(request):
    if request.method == "GET":
        limit = int(request.GET.get("limit", 200))
        qs = (
            Movement.objects.select_related("product", "created_by")
            .order_by("-created_at")[:limit]
        )
        result = [
            {
                "id": m.id,
                "productId": m.product_id,
                "productName": m.product.name if m.product else "Producto eliminado",
                "type": m.type,
                "quantity": _f(m.quantity),
                "previousStock": _f(m.previous_stock),
                "newStock": _f(m.new_stock),
                "notes": m.notes,
                "createdBy": m.created_by.name if m.created_by else None,
                "createdAt": m.created_at.isoformat() if m.created_at else None,
            }
            for m in qs
        ]
        product_id = request.GET.get("productId", "")
        type_filter = request.GET.get("type", "")
        if product_id:
            result = [m for m in result if m["productId"] == product_id]
        if type_filter:
            result = [m for m in result if m["type"] == type_filter]
        return JsonResponse(result, safe=False)
    if request.method == "POST":
        body = _body(request)
        product_id = body.get("productId")
        mov_type = body.get("type")
        quantity = body.get("quantity")
        notes = body.get("notes")
        user_id = request.session.get("user_id")
        if not product_id or not mov_type or quantity is None:
            return JsonResponse({"error": "Datos incompletos"}, status=400)
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            return JsonResponse({"error": "Producto no encontrado"}, status=404)
        previous_stock = float(product.current_stock)
        qty = float(quantity)
        if mov_type == "entrada":
            new_stock = previous_stock + qty
        elif mov_type == "salida":
            new_stock = previous_stock - qty
            if new_stock < 0:
                return JsonResponse({"error": "Stock insuficiente para la salida"}, status=400)
        elif mov_type == "ajuste":
            new_stock = qty
        else:
            return JsonResponse({"error": "Tipo de movimiento inválido"}, status=400)
        with transaction.atomic():
            product.current_stock = Decimal(str(new_stock))
            product.save()
            m = Movement(
                id=_next_code(Movement, "MOV", 6),
                product_id=product_id,
                type=mov_type,
                quantity=Decimal(str(qty)),
                previous_stock=Decimal(str(previous_stock)),
                new_stock=Decimal(str(new_stock)),
                notes=notes,
                created_by_id=user_id,
            )
            m.save()
        tipo_label = {"entrada": "Entrada", "salida": "Salida", "ajuste": "Ajuste"}.get(mov_type, mov_type)
        log_action(
            request,
            "create_movement",
            f"Registró {tipo_label} de {qty} {product.unit} en '{product.name}' (Stock: {previous_stock} → {new_stock})",
        )
        user_name = request.session.get("user_name")
        return JsonResponse(
            {
                "id": m.id,
                "productId": m.product_id,
                "productName": product.name,
                "type": m.type,
                "quantity": _f(m.quantity),
                "previousStock": _f(m.previous_stock),
                "newStock": _f(m.new_stock),
                "notes": m.notes,
                "createdBy": user_name,
                "createdAt": m.created_at.isoformat() if m.created_at else None,
            },
            status=201,
        )
    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@admin_required
def users(request):
    if request.method == "GET":
        us = User.objects.filter(is_deleted=False).order_by("name")
        data = [
            {
                "id": u.id,
                "cedula": u.cedula,
                "username": u.username,
                "name": u.name,
                "role": u.role,
                "isActive": u.is_active,
            }
            for u in us
        ]
        return JsonResponse(data, safe=False)
    if request.method == "POST":
        if request.session.get("user_role") != "admin":
            return JsonResponse({"error": "Acceso denegado"}, status=403)
        body = _body(request)
        cedula = _normalize_cedula(body.get("id") or body.get("cedula"))
        username = body.get("username", "").strip()
        name = body.get("name", "").strip()
        password = body.get("password", "")
        role = body.get("role", "").strip()
        if not cedula or not username or not name or not password or not role:
            return JsonResponse(
                {"error": "Cédula, usuario, nombre, contraseña y rol son requeridos"},
                status=400,
            )
        if not _valid_cedula(cedula):
            return JsonResponse(
                {
                    "error": (
                        "La cédula no es válida. Usa entre 5 y 20 letras, "
                        "números o guiones (ej. V-12345678)."
                    )
                },
                status=400,
            )
        if role not in ("admin", "empleado"):
            return JsonResponse({"error": "Rol inválido"}, status=400)
        if User.objects.filter(cedula=cedula).exists():
            return JsonResponse(
                {"error": "Ya existe un usuario con esa cédula"}, status=400
            )
        if User.objects.filter(username=username).exists():
            return JsonResponse({"error": "El usuario ya existe"}, status=400)
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        u = User(
            id=_generate_significant_id(User, "USR", seed=cedula),
            cedula=cedula,
            username=username,
            name=name,
            password_hash=password_hash,
            role=role,
            is_active=True,
        )
        u.save()
        log_action(request, "create_user", f"Creó usuario '{username}' ({role})")
        return JsonResponse(
            {"id": u.id, "cedula": u.cedula, "username": u.username, "name": u.name, "role": u.role, "isActive": u.is_active},
            status=201,
        )
    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@admin_required
def user_detail(request, pk):
    try:
        u = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return JsonResponse({"error": "Usuario no encontrado"}, status=404)
    if request.method in ("PUT", "PATCH"):
        body = _body(request)
        # El ID es inmutable, ignoramos cualquier intento de cambiarlo

        if "cedula" in body or "id" in body:
            new_cedula = _normalize_cedula(body.get("cedula") or body.get("id"))
            if new_cedula:
                if not _valid_cedula(new_cedula):
                    return JsonResponse(
                        {"error": "La cédula no es válida."},
                        status=400,
                    )
                # Verificar que la nueva cédula no sea usada por otro usuario
                if User.objects.filter(cedula=new_cedula).exclude(pk=u.pk).exists():
                    return JsonResponse(
                        {"error": "Ya existe otro usuario con esa cédula"}, status=400
                    )
                u.cedula = new_cedula

        if "name" in body:
            u.name = body["name"]
        if "role" in body:
            u.role = body["role"]
        if "isActive" in body:
            u.is_active = body["isActive"]
        if body.get("password"):
            u.password_hash = bcrypt.hashpw(
                body["password"].encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")
        u.save()
        log_action(request, "edit_user", f"Editó usuario '{u.username}'")
        return JsonResponse(
            {"id": u.id, "cedula": u.cedula, "username": u.username, "name": u.name, "role": u.role, "isActive": u.is_active}
        )
    if request.method == "DELETE":
        if request.session.get("user_role") != "admin":
            return JsonResponse({"error": "Acceso denegado"}, status=403)
        log_action(request, "delete_user", f"Marcó como eliminado al usuario '{u.username}'")
        u.is_deleted = True
        u.save()
        return JsonResponse({"message": "Usuario eliminado (lógica)"})
    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@auth_required
def sales(request):
    if request.method == "GET":
        qs = Sale.objects.select_related("created_by").order_by("-created_at")
        data = []
        for s in qs:
            ci = None
            if s.customer_info:
                try:
                    ci = json.loads(s.customer_info)
                except Exception:
                    pass
            data.append({
                "id": s.id,
                "total": _f(s.total),
                "notes": s.notes,
                "customerInfo": ci,
                "status": s.status,
                "createdBy": s.created_by.name if s.created_by else None,
                "createdAt": s.created_at.isoformat() if s.created_at else None,
            })
        return JsonResponse(data, safe=False)
    if request.method == "POST":
        body = _body(request)
        items = body.get("items", [])
        notes = body.get("notes")
        customer_info = body.get("customerInfo")
        user_id = request.session.get("user_id")
        if not items:
            return JsonResponse({"error": "La venta debe tener al menos un producto"}, status=400)
        with transaction.atomic():
            total = Decimal("0")
            sale_items_data = []
            for item in items:
                pid = item.get("productId")
                qty = Decimal(str(item.get("quantity", 0)))
                try:
                    product = Product.objects.select_for_update().get(pk=pid)
                except Product.DoesNotExist:
                    return JsonResponse({"error": f"Producto {pid} no encontrado"}, status=404)
                if product.current_stock < qty:
                    return JsonResponse(
                        {"error": f"Stock insuficiente para {product.name}"}, status=400
                    )
                unit_price = product.price if product.price is not None else Decimal("0")
                subtotal = unit_price * qty
                total += subtotal
                sale_items_data.append((product, qty, unit_price, subtotal))
            ci_json = json.dumps(customer_info) if customer_info else None
            sale = Sale(
                id=_next_code(Sale, "VEN", 6),
                total=total,
                notes=notes,
                customer_info=ci_json,
                status="activa",
                created_by_id=user_id,
            )
            sale.save()
            product_names = []
            for product, qty, unit_price, subtotal in sale_items_data:
                previous_stock = product.current_stock
                new_stock = previous_stock - qty
                product.current_stock = new_stock
                product.save()
                SaleItem(
                    id=_next_code(SaleItem, "DET", 6),
                    sale_id=sale.id,
                    product_id=product.id,
                    quantity=qty,
                    unit_price=unit_price,
                    subtotal=subtotal,
                ).save()
                Movement(
                    id=_next_code(Movement, "MOV", 6),
                    product_id=product.id,
                    type="salida",
                    quantity=qty,
                    previous_stock=previous_stock,
                    new_stock=new_stock,
                    notes=f"Venta #{sale.id}",
                    created_by_id=user_id,
                ).save()
                product_names.append(f"{product.name} x{float(qty)}")
        log_action(
            request,
            "create_sale",
            f"Registró venta #{sale.id} por ${float(total):.2f} ({', '.join(product_names)})",
        )
        return JsonResponse(
            {
                "id": sale.id,
                "total": _f(sale.total),
                "notes": sale.notes,
                "customerInfo": customer_info,
                "status": sale.status,
                "createdBy": request.session.get("user_name"),
                "createdAt": sale.created_at.isoformat() if sale.created_at else None,
            },
            status=201,
        )
    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@auth_required
def sale_detail(request, pk):
    try:
        sale = Sale.objects.select_related("created_by").get(pk=pk)
    except Sale.DoesNotExist:
        return JsonResponse({"error": "Venta no encontrada"}, status=404)
    if request.method == "GET":
        items = SaleItem.objects.select_related("product").filter(sale_id=pk)
        items_data = [
            {
                "id": si.id,
                "productId": si.product_id,
                "productName": si.product.name if si.product else "Producto eliminado",
                "quantity": _f(si.quantity),
                "unitPrice": _f(si.unit_price),
                "subtotal": _f(si.subtotal),
            }
            for si in items
        ]
        ci = None
        if sale.customer_info:
            try:
                ci = json.loads(sale.customer_info)
            except Exception:
                pass
        return JsonResponse(
            {
                "id": sale.id,
                "total": _f(sale.total),
                "notes": sale.notes,
                "customerInfo": ci,
                "status": sale.status,
                "createdBy": sale.created_by.name if sale.created_by else None,
                "createdAt": sale.created_at.isoformat() if sale.created_at else None,
                "items": items_data,
            }
        )
    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@auth_required
def sale_cancel(request, pk):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    try:
        sale = Sale.objects.get(pk=pk)
    except Sale.DoesNotExist:
        return JsonResponse({"error": "Venta no encontrada"}, status=404)
    if sale.status == "cancelada":
        return JsonResponse({"error": "La venta ya está cancelada"}, status=400)
    user_id = request.session.get("user_id")
    with transaction.atomic():
        items = SaleItem.objects.select_related("product").filter(sale_id=pk)
        for si in items:
            product = Product.objects.select_for_update().get(pk=si.product_id)
            previous_stock = product.current_stock
            new_stock = previous_stock + si.quantity
            product.current_stock = new_stock
            product.save()
            Movement(
                id=_next_code(Movement, "MOV", 6),
                product_id=product.id,
                type="entrada",
                quantity=si.quantity,
                previous_stock=previous_stock,
                new_stock=new_stock,
                notes=f"Devolución venta #{sale.id}",
                created_by_id=user_id,
            ).save()
        sale.status = "cancelada"
        sale.save()
    log_action(request, "cancel_sale", f"Canceló venta #{sale.id} (${float(sale.total):.2f})")
    return JsonResponse(
        {
            "id": sale.id,
            "total": _f(sale.total),
            "notes": sale.notes,
            "status": sale.status,
            "createdAt": sale.created_at.isoformat() if sale.created_at else None,
        }
    )


@csrf_exempt
@auth_required
def dashboard_stats(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    from django.db.models import Count, Sum
    from datetime import date

    total_products = Product.objects.count()
    total_categories = Category.objects.count()
    total_movements = Movement.objects.count()

    from datetime import timedelta
    all_products = Product.objects.values("current_stock", "min_stock", "price", "expiry_date")
    low_stock = 0
    total_value = 0.0
    expiring_count = 0
    today = date.today()
    threshold = today + timedelta(days=7)
    for p in all_products:
        cs = float(p["current_stock"] or 0)
        ms = float(p["min_stock"] or 0)
        pr = float(p["price"] or 0)
        if cs <= ms:
            low_stock += 1
        total_value += cs * pr
        exp = p["expiry_date"]
        if exp is not None and exp <= threshold:
            expiring_count += 1

    sales_today = Sale.objects.filter(created_at__date=today, status="activa")
    total_sales_today = sum(float(s.total) for s in sales_today)
    total_sales_count = Sale.objects.filter(status="activa").count()

    return JsonResponse(
        {
            "totalProducts": total_products,
            "lowStockProducts": low_stock,
            "expiringProducts": expiring_count,
            "totalCategories": total_categories,
            "recentMovements": total_movements,
            "totalValue": total_value,
            "totalSalesToday": total_sales_today,
            "totalSalesCount": total_sales_count,
        }
    )


# ─── AUDIT ENDPOINTS ───────────────────────────────────────────────────────────

@csrf_exempt
@admin_required
def audit_sessions(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                session_key,
                user_id,
                username,
                user_role,
                MIN(created_at) AS started_at,
                MAX(created_at) AS last_action_at,
                COUNT(*) AS total_events,
                SUM(CASE WHEN action = 'logout' THEN 1 ELSE 0 END) AS logged_out
            FROM audit_logs
            WHERE session_key != ''
            GROUP BY session_key, user_id, username, user_role
            ORDER BY MIN(created_at) DESC
            LIMIT 300
        """)
        cols = [c[0] for c in cursor.description]
        rows = cursor.fetchall()
    sessions = []
    for row in rows:
        r = dict(zip(cols, row))
        sessions.append({
            "sessionKey": r["session_key"],
            "userId": r["user_id"],
            "username": r["username"],
            "userRole": r["user_role"],
            "startedAt": r["started_at"].isoformat() if r["started_at"] else None,
            "lastActionAt": r["last_action_at"].isoformat() if r["last_action_at"] else None,
            "totalEvents": r["total_events"],
            "loggedOut": int(r["logged_out"] or 0) > 0,
        })
    return JsonResponse(sessions, safe=False)


@csrf_exempt
@admin_required
def audit_session_detail(request, session_key):
    if request.method != "GET":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    logs = AuditLog.objects.filter(session_key=session_key).order_by("created_at")
    data = [
        {
            "id": l.id,
            "action": l.action,
            "description": l.description,
            "createdAt": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]
    return JsonResponse(data, safe=False)


@csrf_exempt
@admin_required
def audit_monthly_summary(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    from datetime import date
    year = int(request.GET.get("year", date.today().year))
    month = int(request.GET.get("month", date.today().month))
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                u.id AS user_id,
                u.name AS user_name,
                u.role AS user_role,
                DATE(m.created_at) AS activity_date,
                COUNT(*) AS movement_count
            FROM movements m
            JOIN users u ON u.id = m.created_by
            WHERE EXTRACT(YEAR FROM m.created_at) = %s
              AND EXTRACT(MONTH FROM m.created_at) = %s
            GROUP BY u.id, u.name, u.role, DATE(m.created_at)
            ORDER BY u.name, DATE(m.created_at)
        """, [year, month])
        cols = [c[0] for c in cursor.description]
        rows = cursor.fetchall()
    users_map = {}
    for row in rows:
        r = dict(zip(cols, row))
        uid = r["user_id"]
        if uid not in users_map:
            users_map[uid] = {
                "userId": uid,
                "userName": r["user_name"],
                "userRole": r["user_role"],
                "days": [],
            }
        users_map[uid]["days"].append({
            "date": r["activity_date"].isoformat() if r["activity_date"] else None,
            "movementCount": r["movement_count"],
        })
    return JsonResponse(list(users_map.values()), safe=False)


@csrf_exempt
@admin_required
def audit_day_movements(request):
    if request.method != "GET":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    date_str = request.GET.get("date")
    user_id = request.GET.get("userId")
    if not date_str or not user_id:
        return JsonResponse({"error": "Parámetros requeridos: date, userId"}, status=400)
    qs = (
        Movement.objects.select_related("product", "created_by")
        .filter(created_by_id=user_id, created_at__date=date_str)
        .order_by("created_at")
    )
    data = [
        {
            "id": m.id,
            "productName": m.product.name if m.product else "Producto eliminado",
            "type": m.type,
            "quantity": _f(m.quantity),
            "previousStock": _f(m.previous_stock),
            "newStock": _f(m.new_stock),
            "notes": m.notes,
            "createdAt": m.created_at.isoformat() if m.created_at else None,
        }
        for m in qs
    ]
    return JsonResponse(data, safe=False)
