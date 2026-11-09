import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { AlertCircle, AlertTriangle, Boxes, Check, PackagePlus, Plus, Search, X } from "lucide-react";
import { getListProductsQueryKey, useCreateProduct, useListCategories, useListProducts } from "@/api-client";
import type { CreateProductRequest } from "@/api-client";
import { LoadingRows, PageHeader } from "@/components/app-shell";
import { useAuth } from "@/hooks/use-auth";

const schema = z.object({
  name: z.string().trim().min(1, "El nombre es obligatorio."),
  description: z.string().optional(),
  categoryId: z.string().min(1, "Selecciona un tipo de producto."),
  unit: z.string().trim().min(1, "La unidad es obligatoria."),
  currentStock: z.coerce.number({ invalid_type_error: "Ingresa una cantidad válida." }).min(0, "La existencia no puede ser negativa."),
  minStock: z.coerce.number({ invalid_type_error: "Ingresa una cantidad válida." }).min(0, "El mínimo no puede ser negativo."),
  price: z.number({ invalid_type_error: "Ingresa un precio válido." }).min(0, "El precio no puede ser negativo.").optional(),
});
type ProductFields = z.infer<typeof schema>;
type Feedback = { type: "success" | "error"; text: string };

function apiMessage(error: unknown) {
  const issue = error as { message?: string; response?: { data?: { error?: string; detail?: string } } };
  return issue?.response?.data?.error || issue?.response?.data?.detail || issue?.message || "No se pudo completar la solicitud. Intenta de nuevo.";
}

export default function Inventory() {
  const { user } = useAuth();
  const client = useQueryClient();
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const params = useMemo(() => ({
    ...(search.trim() ? { search: search.trim() } : {}),
    ...(categoryFilter ? { categoryId: categoryFilter } : {}),
  }), [search, categoryFilter]);
  const productsQuery = useListProducts(params, { request: { credentials: "include" } });
  const categoriesQuery = useListCategories({ request: { credentials: "include" } });
  const createProduct = useCreateProduct({ request: { credentials: "include" } });
  const form = useForm<ProductFields>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", description: "", categoryId: "", unit: "unidad", currentStock: 0, minStock: 0 },
  });
  const isAdmin = user?.role === "admin";

  const openCreate = () => {
    createProduct.reset();
    setFeedback(null);
    form.reset({ name: "", description: "", categoryId: "", unit: "unidad", currentStock: 0, minStock: 0, price: undefined });
    setModalOpen(true);
  };
  const submit = form.handleSubmit((values) => {
    const payload: CreateProductRequest = {
      name: values.name.trim(),
      description: values.description?.trim() || undefined,
      categoryId: values.categoryId,
      unit: values.unit.trim(),
      currentStock: values.currentStock,
      minStock: values.minStock,
      price: values.price,
    };
    createProduct.mutate({ data: payload }, {
      onSuccess: () => {
        void client.invalidateQueries({ queryKey: getListProductsQueryKey() });
        setModalOpen(false);
        setFeedback({ type: "success", text: "Producto agregado al inventario." });
      },
      onError: (error) => setFeedback({ type: "error", text: apiMessage(error) }),
    });
  });
  const products = productsQuery.data ?? [];

  return <div className="inventory-page">
    <PageHeader eyebrow="CONTROL DE EXISTENCIAS" title="Inventario" subtitle="Consulta productos, categorías y niveles de stock." action={isAdmin ? <button className="primary-button" onClick={openCreate} data-testid="button-create-product"><Plus size={17} /> Nuevo producto</button> : undefined} />
    {feedback && <div className={`notice-banner ${feedback.type}`} role={feedback.type === "error" ? "alert" : "status"} data-testid="status-product-feedback"><span className="notice-icon">{feedback.type === "success" ? <Check size={17} /> : <AlertCircle size={17} />}</span><span>{feedback.text}</span><button onClick={() => setFeedback(null)} aria-label="Cerrar mensaje" data-testid="button-dismiss-product-feedback"><X size={16} /></button></div>}
    <div className="inventory-toolbar">
      <label className="inventory-search" style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <Search size={16} aria-hidden="true" />
        <input aria-label="Buscar producto" placeholder="Buscar por nombre…" value={search} onChange={(event) => setSearch(event.target.value)} data-testid="input-search-products" style={{ border: 0, outline: 0, minWidth: 0, flex: 1, background: "transparent", color: "inherit" }} />
      </label>
      <select className="inventory-search" aria-label="Filtrar por tipo" value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)} data-testid="select-product-category-filter">
        <option value="">Todos los tipos</option>
        {(categoriesQuery.data ?? []).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
      </select>
    </div>
    {categoriesQuery.isError && <div className="inline-query-error" role="alert" data-testid="status-product-categories-error"><AlertCircle size={15} /> No se pudieron cargar los tipos de producto. <button type="button" className="text-link" onClick={() => categoriesQuery.refetch()} data-testid="button-retry-product-categories">Reintentar</button></div>}
    <section className="users-card" aria-label="Productos" data-testid="panel-product-list">
      <div className="list-heading"><div><h2>Productos</h2><p>Existencias registradas para tu equipo.</p></div><span className="count-pill" data-testid="text-product-count">{productsQuery.isLoading ? "Cargando" : `${products.length} ${products.length === 1 ? "producto" : "productos"}`}</span></div>
      {productsQuery.isLoading ? <LoadingRows count={5} /> : productsQuery.isError ? <div className="state-panel error-state" role="alert" data-testid="state-products-error"><div className="state-icon"><AlertCircle size={22} /></div><h3>No fue posible cargar el inventario</h3><p>{apiMessage(productsQuery.error)}</p><button className="secondary-button" onClick={() => productsQuery.refetch()} data-testid="button-retry-products">Reintentar</button></div> : products.length === 0 ? <div className="state-panel empty-state" data-testid="state-products-empty"><div className="state-icon"><Boxes size={22} /></div><h3>{search || categoryFilter ? "No hay coincidencias" : "El inventario está vacío"}</h3><p>{search || categoryFilter ? "Prueba con otra búsqueda o tipo de producto." : "Los productos que registres aparecerán en esta lista."}</p>{isAdmin && !search && !categoryFilter && <button className="secondary-button" onClick={openCreate} data-testid="button-empty-create-product"><Plus size={16} /> Agregar primer producto</button>}</div> : <div className="user-table-wrap">
        <table className="inventory-table">
          <thead><tr><th>CÓDIGO</th><th>PRODUCTO</th><th>TIPO</th><th>EXISTENCIAS</th><th>MÍNIMO</th><th>PRECIO</th></tr></thead>
          <tbody>{products.map((product) => <tr key={product.id} data-testid={`row-product-${product.id}`}>
            <td><span className="username-cell">{product.id}</span></td>
            <td><div className="inventory-product"><strong data-testid={`text-product-name-${product.id}`}>{product.name}</strong><small>{product.description || "Sin descripción"}</small></div></td>
            <td>{product.categoryName || "Sin tipo"}</td>
            <td><span className={`stock-value ${product.isLowStock ? "low" : ""}`} data-testid={`text-product-stock-${product.id}`}>{product.currentStock} {product.unit} {product.isLowStock && <AlertTriangle size={13} aria-label="Existencia baja" />}</span></td>
            <td>{product.minStock} {product.unit}</td>
            <td>{product.price == null ? "—" : new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 2 }).format(product.price)}</td>
          </tr>)}</tbody>
        </table>
      </div>}
    </section>

    {modalOpen && <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !createProduct.isPending) setModalOpen(false); }}>
      <section className="user-modal" role="dialog" aria-modal="true" aria-labelledby="product-modal-title">
        <header className="modal-heading"><div><div className="modal-kicker">ALTA DE INVENTARIO</div><h2 id="product-modal-title">Nuevo producto</h2><p>Completa los datos para incorporarlo a la lista.</p></div><button className="icon-button modal-close" onClick={() => setModalOpen(false)} disabled={createProduct.isPending} aria-label="Cerrar" data-testid="button-close-product-modal"><X size={19} /></button></header>
        <form onSubmit={submit} noValidate>
          <div className="modal-body">
            <div className="form-field"><label htmlFor="product-name">Nombre <span>*</span></label><input id="product-name" {...form.register("name")} aria-invalid={!!form.formState.errors.name} data-testid="input-product-name" />{form.formState.errors.name && <small className="field-error">{form.formState.errors.name.message}</small>}</div>
            <div className="form-field"><label htmlFor="product-description">Descripción</label><textarea id="product-description" {...form.register("description")} data-testid="input-product-description" /></div>
            <div className="inventory-form-grid">
              <div className="form-field"><label htmlFor="product-category">Tipo de producto <span>*</span></label><select id="product-category" {...form.register("categoryId")} aria-invalid={!!form.formState.errors.categoryId} data-testid="select-product-category"><option value="">Selecciona un tipo</option>{(categoriesQuery.data ?? []).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select>{form.formState.errors.categoryId && <small className="field-error">{form.formState.errors.categoryId.message}</small>}{categoriesQuery.isError && <small className="field-error">No se pudieron cargar los tipos. <button type="button" className="text-link" onClick={() => categoriesQuery.refetch()} data-testid="button-retry-product-categories-modal">Reintentar</button></small>}</div>
              <div className="form-field"><label htmlFor="product-unit">Unidad <span>*</span></label><input id="product-unit" {...form.register("unit")} placeholder="unidad, kg…" aria-invalid={!!form.formState.errors.unit} data-testid="input-product-unit" />{form.formState.errors.unit && <small className="field-error">{form.formState.errors.unit.message}</small>}</div>
              <div className="form-field"><label htmlFor="product-current-stock">Existencias iniciales <span>*</span></label><input id="product-current-stock" type="number" min="0" step="any" {...form.register("currentStock", { valueAsNumber: true })} aria-invalid={!!form.formState.errors.currentStock} data-testid="input-product-current-stock" />{form.formState.errors.currentStock && <small className="field-error">{form.formState.errors.currentStock.message}</small>}</div>
              <div className="form-field"><label htmlFor="product-min-stock">Stock mínimo <span>*</span></label><input id="product-min-stock" type="number" min="0" step="any" {...form.register("minStock", { valueAsNumber: true })} aria-invalid={!!form.formState.errors.minStock} data-testid="input-product-min-stock" />{form.formState.errors.minStock && <small className="field-error">{form.formState.errors.minStock.message}</small>}</div>
              <div className="form-field"><label htmlFor="product-price">Precio unitario (COP)</label><input id="product-price" type="number" min="0" step="0.01" {...form.register("price", { setValueAs: (value: string) => value === "" ? undefined : Number(value) })} aria-invalid={!!form.formState.errors.price} data-testid="input-product-price" />{form.formState.errors.price && <small className="field-error">{form.formState.errors.price.message}</small>}</div>
            </div>
            {createProduct.isError && <div className="form-api-error" role="alert" data-testid="status-create-product-error"><AlertCircle size={16} />{apiMessage(createProduct.error)}</div>}
          </div>
          <footer className="modal-footer"><button type="button" className="secondary-button" onClick={() => setModalOpen(false)} disabled={createProduct.isPending} data-testid="button-cancel-product">Cancelar</button><button className="primary-button" type="submit" disabled={createProduct.isPending} data-testid="button-save-product">{createProduct.isPending ? <><span className="button-spinner" /> Guardando</> : <><PackagePlus size={16} /> Crear producto</>}</button></footer>
        </form>
      </section>
    </div>}
  </div>;
}
