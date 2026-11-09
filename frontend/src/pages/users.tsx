import { type FormEvent, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getGetMeQueryKey, getListUsersQueryKey, useCreateUser, useDeleteUser, useListUsers, useUpdateUser } from "@/api-client";
import type { CreateUserRequest, UpdateUserRequest, User } from "@/api-client";
import { AlertCircle, Check, CircleUserRound, Edit3, KeyRound, Plus, ShieldCheck, Trash2, UserRound, UsersRound, X } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { LoadingRows, PageHeader } from "@/components/app-shell";

type FormFields = { id: string; cedula: string; username: string; name: string; password: string; role: "admin" | "empleado"; isActive: boolean };

const CEDULA_RE = /^[0-9]{5,20}$/;

function apiMessage(error: unknown) {
  const value = error as { message?: string; response?: { data?: { error?: string; detail?: string } } };
  const message = value?.response?.data?.error || value?.response?.data?.detail || value?.message || "";
  if (/duplicate|already exists|username.*exists|user.*exists|ya existe|existe un usuario/i.test(message)) return "Esa cédula o nombre de usuario ya está en uso. Revisa los datos.";
  if (/permission|forbidden|not allowed/i.test(message)) return "No tienes permisos para realizar esta acción.";
  return message || "No se pudo completar la solicitud. Intenta de nuevo.";
}

export default function Users() {
  const { user: currentUser } = useAuth();
  const client = useQueryClient();
  const usersQuery = useListUsers({ request: { credentials: "include" } });
  const create = useCreateUser({ request: { credentials: "include" } });
  const update = useUpdateUser({ request: { credentials: "include" } });
  const remove = useDeleteUser({ request: { credentials: "include" } });
  const [isOpen, setIsOpen] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [fields, setFields] = useState<FormFields>({ id: "", username: "", name: "", password: "", role: "empleado", isActive: true });
  const [errors, setErrors] = useState<Partial<Record<keyof FormFields, string>>>({});
  const [notice, setNotice] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const busy = create.isPending || update.isPending;

  const refresh = () => {
    void client.invalidateQueries({ queryKey: getListUsersQueryKey() });
    void client.invalidateQueries({ queryKey: getGetMeQueryKey() });
  };
  const openCreate = () => {
    create.reset(); update.reset(); setNotice(null); setEditing(null);
    setErrors({});
    setFields({ id: "", cedula: "", username: "", name: "", password: "", role: "empleado", isActive: true });
    setIsOpen(true);
  };
  const openEdit = (record: User) => {
    create.reset(); update.reset(); setNotice(null); setEditing(record); setErrors({});
    setFields({ id: record.id, cedula: record.cedula, username: record.username, name: record.name, password: "", role: record.role, isActive: record.isActive });
    setIsOpen(true);
  };
  const closeModal = () => { if (!busy) setIsOpen(false); };
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors: Partial<Record<keyof FormFields, string>> = {};
    const cedula = fields.cedula.trim().toUpperCase();
    if (!cedula) nextErrors.cedula = "La cédula es obligatoria.";
    else if (!CEDULA_RE.test(cedula)) nextErrors.cedula = "La cédula debe contener solo números (entre 5 y 20 dígitos).";
    if (!fields.name.trim()) nextErrors.name = "Escribe el nombre de la persona.";
    if (!fields.username.trim()) nextErrors.username = "El usuario es obligatorio.";
    else if (!editing && fields.username.trim().length < 3) nextErrors.username = "Usa al menos 3 caracteres.";
    if (!editing && !fields.password.trim()) nextErrors.password = "La contraseña es obligatoria al crear un usuario.";
    if (fields.role !== "admin" && fields.role !== "empleado") nextErrors.role = "Selecciona un rol válido.";
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;

    if (editing) {
      const payload: UpdateUserRequest = { id: cedula, name: fields.name.trim(), role: fields.role, isActive: fields.isActive };
      if (fields.password.trim()) payload.password = fields.password;
      update.mutate({ id: editing.id, data: payload }, {
        onSuccess: () => { refresh(); setIsOpen(false); setNotice({ type: "success", text: `Se actualizaron los datos de ${fields.name.trim()}.` }); },
        onError: (error) => setNotice({ type: "error", text: apiMessage(error) }),
      });
    } else {
      const payload: CreateUserRequest = { id: cedula, username: fields.username.trim(), name: fields.name.trim(), password: fields.password, role: fields.role };
      create.mutate({ data: payload }, {
        onSuccess: () => { refresh(); setIsOpen(false); setNotice({ type: "success", text: `La cuenta de ${fields.name.trim()} ya está creada.` }); },
        onError: (error) => setNotice({ type: "error", text: apiMessage(error) }),
      });
    }
  };
  const deleteUser = (record: User) => {
    if (record.id === currentUser?.id) {
      setNotice({ type: "error", text: "No puedes eliminar la cuenta con la que tienes esta sesión abierta." });
      return;
    }
    if (!window.confirm(`¿Eliminar la cuenta de ${record.name}? Esta acción no se puede deshacer.`)) return;
    setNotice(null);
    remove.mutate({ id: record.id }, {
      onSuccess: () => { refresh(); setNotice({ type: "success", text: `Se eliminó la cuenta de ${record.name}.` }); },
      onError: (error) => setNotice({ type: "error", text: apiMessage(error) }),
    });
  };
  const setField = <K extends keyof FormFields>(field: K, value: FormFields[K]) => {
    setFields((previous) => ({ ...previous, [field]: value }));
    if (errors[field]) setErrors((previous) => ({ ...previous, [field]: undefined }));
  };
  const users = usersQuery.data ?? [];
  const admins = users.filter((entry) => entry.role === "admin").length;
  const active = users.filter((entry) => entry.isActive).length;

  return <div className="users-page">
    <PageHeader eyebrow="EQUIPO Y ACCESOS" title="Usuarios" subtitle="Administra quién puede entrar y qué rol tiene en el sistema." action={<button className="primary-button" onClick={openCreate} data-testid="button-create-user"><Plus size={17} /> Nuevo usuario</button>} />
    {notice && <div className={`notice-banner ${notice.type}`} role="status" data-testid="status-user-feedback"><span className="notice-icon">{notice.type === "success" ? <Check size={17} /> : <AlertCircle size={17} />}</span><span>{notice.text}</span><button onClick={() => setNotice(null)} aria-label="Cerrar mensaje" data-testid="button-dismiss-feedback"><X size={16} /></button></div>}
    <section className="user-metrics" aria-label="Resumen de usuarios">
      <div className="metric-block"><div className="metric-symbol teal"><CircleUserRound size={18} /></div><div><span>CUENTAS REGISTRADAS</span><strong data-testid="text-user-count">{usersQuery.isLoading ? "—" : users.length.toString().padStart(2, "0")}</strong></div></div>
      <div className="metric-block"><div className="metric-symbol amber"><ShieldCheck size={18} /></div><div><span>ADMINISTRADORES</span><strong data-testid="text-admin-count">{usersQuery.isLoading ? "—" : admins.toString().padStart(2, "0")}</strong></div></div>
      <div className="metric-block"><div className="metric-symbol blue"><UserRound size={18} /></div><div><span>CUENTAS ACTIVAS</span><strong data-testid="text-active-count">{usersQuery.isLoading ? "—" : active.toString().padStart(2, "0")}</strong></div></div>
      <div className="metric-aside"><KeyRound size={15} /><span>El rol define el acceso disponible.</span></div>
    </section>
    <section className="users-card">
      <div className="list-heading"><div><h2>Personas con acceso</h2><p>Gestiona sus datos, estado y rol.</p></div><span className="count-pill">{usersQuery.isLoading ? "Cargando" : `${users.length} ${users.length === 1 ? "cuenta" : "cuentas"}`}</span></div>
      {usersQuery.isLoading ? <LoadingRows count={4} /> : usersQuery.isError ? <div className="state-panel error-state"><div className="state-icon"><AlertCircle size={22} /></div><h3>No fue posible cargar las cuentas</h3><p>{apiMessage(usersQuery.error)}</p><button className="secondary-button" onClick={() => usersQuery.refetch()} data-testid="button-retry-users">Reintentar</button></div> : users.length === 0 ? <div className="state-panel empty-state"><div className="state-icon"><UsersRoundIcon /></div><h3>Aún no hay usuarios registrados</h3><p>Crea la primera cuenta para dar acceso a tu equipo.</p><button className="secondary-button" onClick={openCreate} data-testid="button-empty-create"><Plus size={16} /> Crear primer usuario</button></div> : <>
        <div className="user-table-wrap">
          <table className="user-table">
            <thead><tr><th>PERSONA</th><th>ID TÉCNICO</th><th>CÉDULA</th><th>USUARIO</th><th>ROL</th><th>ESTADO</th><th className="actions-head">ACCIONES</th></tr></thead>
            <tbody>{users.map((record) => <tr key={record.id} data-testid={`row-user-${record.id}`}>
              <td><div className="person-cell"><span className={`person-avatar ${record.role === "admin" ? "admin-avatar" : ""}`}>{record.name.slice(0, 1).toUpperCase()}</span><span><strong>{record.name}</strong>{record.id === currentUser?.id && <small>Tu cuenta</small>}</span></div></td>
              <td><span className="username-cell" style={{ fontSize: '11px', opacity: 0.7 }}>{record.id}</span></td>
              <td><span className="username-cell">{record.cedula}</span></td>
              <td><span className="username-cell">@{record.username}</span></td>
              <td><span className={`role-chip ${record.role}`}><span className="role-dot" />{record.role === "admin" ? "Administrador" : "Empleado"}</span></td>
              <td><span className={`status-chip ${record.isActive ? "enabled" : "disabled"}`}><span />{record.isActive ? "Activo" : "Inactivo"}</span></td>
              <td><div className="row-actions"><button className="table-action" onClick={() => openEdit(record)} aria-label={`Editar ${record.name}`} title="Editar usuario" data-testid={`button-edit-user-${record.id}`}><Edit3 size={16} /></button><button className="table-action delete-action" onClick={() => deleteUser(record)} disabled={record.id === currentUser?.id || remove.isPending} aria-label={`Eliminar ${record.name}`} title={record.id === currentUser?.id ? "No puedes eliminar tu propia cuenta" : "Eliminar usuario"} data-testid={`button-delete-user-${record.id}`}><Trash2 size={16} /></button></div></td>
            </tr>)}</tbody>
          </table>
        </div>
        <div className="table-footer"><span><span className="footer-dot" /> Los permisos dependen exclusivamente del rol asignado.</span><span>{users.length} registros</span></div>
      </>}
    </section>
    {isOpen && <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) closeModal(); }}>
      <section className="user-modal" role="dialog" aria-modal="true" aria-labelledby="user-modal-title">
        <header className="modal-heading"><div><div className="modal-kicker">{editing ? "ACTUALIZAR CUENTA" : "NUEVO ACCESO"}</div><h2 id="user-modal-title">{editing ? "Editar usuario" : "Crear usuario"}</h2><p>{editing ? "Ajusta los datos y el acceso de esta persona." : "Registra a una persona del equipo."}</p></div><button type="button" className="icon-button modal-close" onClick={closeModal} aria-label="Cerrar" data-testid="button-close-user-modal"><X size={19} /></button></header>
        <form onSubmit={submit} noValidate>
          <div className="modal-body">
            <div className="form-field"><label htmlFor="user-id">Cédula <span>*</span></label><input id="user-id" value={fields.cedula} onChange={(event) => setField("cedula", event.target.value)} placeholder="Ej. 1234567890" autoComplete="off" aria-invalid={!!errors.cedula} data-testid="input-user-id" />{errors.cedula && <small className="field-error">{errors.cedula}</small>}<small className="field-hint">{editing ? "Puedes actualizar la cédula si hubo un error al registrarla." : "Ingresa la cédula numérica del empleado."}</small></div>
            <div className="form-field"><label htmlFor="user-name">Nombre completo <span>*</span></label><input id="user-name" value={fields.name} onChange={(event) => setField("name", event.target.value)} placeholder="Ej. Camila Rodríguez" aria-invalid={!!errors.name} data-testid="input-user-name" />{errors.name && <small className="field-error">{errors.name}</small>}</div>
            <div className="form-field"><label htmlFor="user-username">Usuario de acceso <span>*</span></label><div className="username-input"><span>@</span><input id="user-username" value={fields.username} onChange={(event) => setField("username", event.target.value)} placeholder="camila.rodriguez" readOnly={!!editing} aria-invalid={!!errors.username} data-testid="input-user-username" /></div>{errors.username && <small className="field-error">{errors.username}</small>}{editing && <small className="field-hint">El usuario de acceso no se puede modificar.</small>}</div>
            <div className="form-field"><label htmlFor="user-password">Contraseña {editing ? <span className="optional-label">OPCIONAL</span> : <span>*</span>}</label><input id="user-password" type="password" autoComplete="new-password" value={fields.password} onChange={(event) => setField("password", event.target.value)} placeholder={editing ? "Dejar en blanco para conservarla" : "Define una contraseña"} aria-invalid={!!errors.password} data-testid="input-user-password" />{errors.password && <small className="field-error">{errors.password}</small>}{editing && <small className="field-hint">Nunca mostramos la contraseña actual.</small>}</div>
            <div className="form-field"><label htmlFor="user-role">Rol de acceso <span>*</span></label><select id="user-role" value={fields.role} onChange={(event) => setField("role", event.target.value as FormFields["role"])} data-testid="select-user-role"><option value="empleado">Empleado · acceso operativo</option><option value="admin">Administrador · gestión de usuarios</option></select><small className="field-hint">El sistema solo contempla los roles administrador y empleado.</small></div>
            {editing && <label className="active-switch" htmlFor="user-active"><span className="switch-visual"><input id="user-active" type="checkbox" checked={fields.isActive} onChange={(event) => setField("isActive", event.target.checked)} data-testid="checkbox-user-active" /><span /></span><span><strong>Cuenta activa</strong><small>Las cuentas inactivas no pueden iniciar sesión.</small></span></label>}
            {(create.isError || update.isError) && <div className="form-api-error" role="alert"><AlertCircle size={16} />{apiMessage(create.error || update.error)}</div>}
          </div>
          <footer className="modal-footer"><button type="button" className="secondary-button" onClick={closeModal} disabled={busy} data-testid="button-cancel-user">Cancelar</button><button className="primary-button" type="submit" disabled={busy} data-testid="button-save-user">{busy ? <><span className="button-spinner" /> Guardando</> : <>{editing ? "Guardar cambios" : "Crear usuario"}<Plus size={16} /></>}</button></footer>
        </form>
      </section>
    </div>}
  </div>;
}

function UsersRoundIcon() {
  return <UserRound size={22} />;
}
