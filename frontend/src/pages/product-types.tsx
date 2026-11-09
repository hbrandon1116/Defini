import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { AlertCircle, Check, Edit3, Plus, Tags, Trash2, X } from "lucide-react";
import { getListCategoriesQueryKey, getListProductsQueryKey, useCreateCategory, useDeleteCategory, useListCategories, useUpdateCategory } from "@/api-client";
import type { Category, CreateCategoryRequest } from "@/api-client";
import { LoadingRows, PageHeader } from "@/components/app-shell";

const schema = z.object({
  name: z.string().trim().min(1, "El nombre es obligatorio."),
  description: z.string().optional(),
});
type Fields = z.infer<typeof schema>;
function apiMessage(error: unknown) {
  const issue = error as { message?: string; response?: { data?: { error?: string; detail?: string } } };
  return issue?.response?.data?.error || issue?.response?.data?.detail || issue?.message || "No se pudo completar la solicitud. Intenta de nuevo.";
}

export default function ProductTypes() {
  const client = useQueryClient();
  const categoriesQuery = useListCategories({ request: { credentials: "include" } });
  const create = useCreateCategory({ request: { credentials: "include" } });
  const update = useUpdateCategory({ request: { credentials: "include" } });
  const remove = useDeleteCategory({ request: { credentials: "include" } });
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Category | null>(null);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const form = useForm<Fields>({ resolver: zodResolver(schema), defaultValues: { name: "", description: "" } });
  const busy = create.isPending || update.isPending;
  const refresh = () => {
    void client.invalidateQueries({ queryKey: getListCategoriesQueryKey() });
    void client.invalidateQueries({ queryKey: getListProductsQueryKey() });
  };
  const openCreate = () => {
    create.reset(); update.reset(); setFeedback(null); setEditing(null);
    form.reset({ name: "", description: "" });
    setModalOpen(true);
  };
  const openEdit = (category: Category) => {
    create.reset(); update.reset(); setFeedback(null); setEditing(category);
    form.reset({ name: category.name, description: category.description ?? "" });
    setModalOpen(true);
  };
  const submit = form.handleSubmit((values) => {
    const payload: CreateCategoryRequest = { name: values.name.trim(), description: values.description?.trim() || undefined };
    const callbacks = {
      onSuccess: () => {
        refresh();
        setModalOpen(false);
        setFeedback({ type: "success", message: editing ? "Tipo de producto actualizado." : "Tipo de producto creado." });
      },
      onError: (error: unknown) => setFeedback({ type: "error", message: apiMessage(error) }),
    };
    if (editing) update.mutate({ id: editing.id, data: payload }, callbacks);
    else create.mutate({ data: payload }, callbacks);
  });
  const deleteType = (category: Category) => {
    if (category.productCount > 0) {
      setFeedback({ type: "error", message: "No se puede eliminar: este tipo todavía tiene productos asociados." });
      return;
    }
    if (!window.confirm(`¿Eliminar el tipo “${category.name}”? Esta acción no se puede deshacer.`)) return;
    setFeedback(null);
    remove.mutate({ id: category.id }, {
      onSuccess: () => { refresh(); setFeedback({ type: "success", message: `Se eliminó “${category.name}”.` }); },
      onError: (error) => setFeedback({ type: "error", message: apiMessage(error) }),
    });
  };
  const categories = categoriesQuery.data ?? [];

  return <div className="types-page">
    <PageHeader eyebrow="ORGANIZACIÓN DEL INVENTARIO" title="Tipos de producto" subtitle="Clasifica los productos para mantener cada lista en orden." action={<button className="primary-button" onClick={openCreate} data-testid="button-create-product-type"><Plus size={17} /> Nuevo tipo</button>} />
    {feedback && <div className={`notice-banner ${feedback.type}`} role="status" data-testid="status-product-type-feedback"><span className="notice-icon">{feedback.type === "success" ? <Check size={17} /> : <AlertCircle size={17} />}</span><span>{feedback.message}</span><button onClick={() => setFeedback(null)} aria-label="Cerrar mensaje" data-testid="button-dismiss-product-type-feedback"><X size={16} /></button></div>}
    <section className="users-card">
      <div className="list-heading"><div><h2>Tipos registrados</h2><p>Gestiona nombres y descripción de categorías.</p></div><span className="count-pill" data-testid="text-product-type-count">{categoriesQuery.isLoading ? "Cargando" : `${categories.length} ${categories.length === 1 ? "tipo" : "tipos"}`}</span></div>
      {categoriesQuery.isLoading ? <LoadingRows count={4} /> : categoriesQuery.isError ? <div className="state-panel error-state" role="alert" data-testid="state-product-types-error"><div className="state-icon"><AlertCircle size={22} /></div><h3>No fue posible cargar los tipos</h3><p>{apiMessage(categoriesQuery.error)}</p><button className="secondary-button" onClick={() => categoriesQuery.refetch()} data-testid="button-retry-product-types">Reintentar</button></div> : categories.length === 0 ? <div className="state-panel empty-state" data-testid="state-product-types-empty"><div className="state-icon"><Tags size={22} /></div><h3>Aún no hay tipos de producto</h3><p>Crea una categoría para organizar los productos del inventario.</p><button className="secondary-button" onClick={openCreate} data-testid="button-empty-create-product-type"><Plus size={16} /> Crear primer tipo</button></div> : <div className="type-grid" style={{ padding: 18 }}>
        {categories.map((category) => <article className="type-card" key={category.id} data-testid={`card-product-type-${category.id}`}>
          <div className="type-card-main"><div className="type-card-head"><h2 data-testid={`text-product-type-name-${category.id}`}>{category.name}</h2><span className="type-count" data-testid={`text-product-type-count-${category.id}`}>{category.productCount} {category.productCount === 1 ? "producto" : "productos"}</span></div><p><span className="count-pill">{category.id}</span> {category.description || "Sin descripción"}</p></div>
          <div className="type-card-actions"><button className="table-action" onClick={() => openEdit(category)} aria-label={`Editar ${category.name}`} title="Editar tipo" data-testid={`button-edit-product-type-${category.id}`}><Edit3 size={16} /></button><button className="table-action delete-action" onClick={() => deleteType(category)} disabled={category.productCount > 0 || remove.isPending} aria-label={`Eliminar ${category.name}`} title={category.productCount > 0 ? "Hay productos asociados" : "Eliminar tipo"} data-testid={`button-delete-product-type-${category.id}`}><Trash2 size={16} /></button></div>
        </article>)}
      </div>}
    </section>
    {modalOpen && <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) setModalOpen(false); }}>
      <section className="user-modal" role="dialog" aria-modal="true" aria-labelledby="type-modal-title">
        <header className="modal-heading"><div><div className="modal-kicker">{editing ? "ACTUALIZAR CLASIFICACIÓN" : "NUEVA CLASIFICACIÓN"}</div><h2 id="type-modal-title">{editing ? "Editar tipo" : "Nuevo tipo de producto"}</h2><p>Define un nombre claro para agrupar productos.</p></div><button className="icon-button modal-close" onClick={() => setModalOpen(false)} disabled={busy} aria-label="Cerrar" data-testid="button-close-product-type-modal"><X size={19} /></button></header>
        <form onSubmit={submit} noValidate>
          <div className="modal-body">
            <div className="form-field"><label htmlFor="type-name">Nombre <span>*</span></label><input id="type-name" {...form.register("name")} aria-invalid={!!form.formState.errors.name} data-testid="input-product-type-name" />{form.formState.errors.name && <small className="field-error">{form.formState.errors.name.message}</small>}</div>
            <div className="form-field"><label htmlFor="type-description">Descripción</label><textarea id="type-description" {...form.register("description")} data-testid="input-product-type-description" /></div>
            {(create.isError || update.isError) && <div className="form-api-error" role="alert" data-testid="status-save-product-type-error"><AlertCircle size={16} />{apiMessage(create.error || update.error)}</div>}
          </div>
          <footer className="modal-footer"><button type="button" className="secondary-button" onClick={() => setModalOpen(false)} disabled={busy} data-testid="button-cancel-product-type">Cancelar</button><button className="primary-button" type="submit" disabled={busy} data-testid="button-save-product-type">{busy ? <><span className="button-spinner" /> Guardando</> : <><Check size={16} /> Guardar tipo</>}</button></footer>
        </form>
      </section>
    </div>}
  </div>;
}
