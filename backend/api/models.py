from django.db import models


class User(models.Model):
    # El ID es una clave técnica inmutable generada al crear el usuario.
    id = models.CharField(primary_key=True, max_length=50)
    # La cédula es un dato informativo y editable.
    cedula = models.CharField(max_length=20)
    username = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    password_hash = models.TextField()
    role = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users"
        managed = False


class Category(models.Model):
    # Código legible: CAT-001, CAT-002...
    id = models.CharField(primary_key=True, max_length=20)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "categories"
        managed = False


class Product(models.Model):
    # Código legible: PRO-0001, PRO-0002...
    id = models.CharField(primary_key=True, max_length=20)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="category_id",
    )
    unit = models.CharField(max_length=50)
    current_stock = models.DecimalField(max_digits=12, decimal_places=4)
    min_stock = models.DecimalField(max_digits=12, decimal_places=4)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "products"
        managed = False


class Movement(models.Model):
    # Código legible: MOV-000001, MOV-000002...
    id = models.CharField(primary_key=True, max_length=20)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        db_column="product_id",
    )
    type = models.CharField(max_length=50)
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    previous_stock = models.DecimalField(max_digits=12, decimal_places=4)
    new_stock = models.DecimalField(max_digits=12, decimal_places=4)
    notes = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="created_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "movements"
        managed = False


class Sale(models.Model):
    # Código legible: VEN-000001, VEN-000002...
    id = models.CharField(primary_key=True, max_length=20)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    notes = models.TextField(null=True, blank=True)
    customer_info = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=50, default="activa")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="created_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sales"
        managed = False


class SaleItem(models.Model):
    # Código legible: DET-000001, DET-000002...
    id = models.CharField(primary_key=True, max_length=20)
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        db_column="sale_id",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        db_column="product_id",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        db_table = "sale_items"
        managed = False


class AuditLog(models.Model):
    # Código legible: AUD-000001, AUD-000002...
    id = models.CharField(primary_key=True, max_length=20)
    user_id = models.CharField(max_length=20, db_column="user_id")
    username = models.CharField(max_length=255)
    user_role = models.CharField(max_length=50)
    action = models.CharField(max_length=100)
    description = models.TextField()
    session_key = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_logs"
        managed = False
