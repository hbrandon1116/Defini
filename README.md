# Defini — Miniproyecto de Inventario (Sprint 2)

Proyecto fuente separado por capas: `frontend/` contiene React + TypeScript y `backend/` contiene Django + SQLite. No incluye archivos `.bat` ni `.sh`; los servicios se ejecutan con comandos desde terminal.

## Estructura

```text
miniproyecto-defini-sprint-2/
├── frontend/
│   ├── public/             # Logo, imágenes e iconos
│   ├── src/
│   │   ├── api-client/     # Cliente HTTP tipado
│   │   ├── components/     # Componentes de interfaz
│   │   ├── hooks/          # Sesión y estado compartido
│   │   └── pages/          # Inicio de sesión, usuarios e inventario
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
└── backend/
    ├── api/                # Modelos, vistas y rutas REST
    ├── inventario/         # Configuración Django y SQLite
    ├── requirements.txt
    └── run.py
```

El ZIP incluye `backend/data/inventario.sqlite3` con una copia de los datos de prueba actuales del proyecto principal: 2 usuarios, 3 tipos y 16 productos. Se conservaron los hashes de contraseña, no las contraseñas en texto; por eso las cuentas actuales y la contraseña del administrador siguen funcionando.

## Identificadores

Los registros no usan ids numéricos autoincrementales. Cada uno tiene un código legible:

- **Usuarios**: la cédula de la persona (ej. `V-12345678`). Se escribe al crear la cuenta y se puede corregir al editarla.
- **Tipos de producto**: `CAT-001`, `CAT-002`...
- **Productos**: `PRO-0001`, `PRO-0002`...
- **Movimientos**: `MOV-000001`, `MOV-000002`...
- **Ventas**: `VEN-000001`, `VEN-000002`...
- **Detalles de venta**: `DET-000001`, `DET-000002`...

Al abrir una base anterior con ids numéricos, `backend/run.py` la convierte automáticamente y guarda una copia de seguridad `inventario.sqlite3.bak-AAAAmmdd-HHMMSS` en `backend/data/`.

## Requisitos

- Python 3.11 o superior.
- Node.js 20.19 o superior (o 22.12 o superior) y npm.
- Internet la primera vez para instalar las dependencias.

## Inicio rápido en Windows (recomendado)

Haz doble clic en **`Iniciar-Defini.bat`**. El iniciador verifica Python y Node.js, crea el entorno virtual si falta, instala o repara las dependencias, revisa la base de datos, comprueba los puertos y muestra las direcciones de acceso. Después arranca backend y frontend en modo LAN y deja la salida de ambos en tiempo real en esa misma ventana.

Archivos incluidos:

- `Iniciar-Defini.bat`: arranca todo con un doble clic en una sola ventana.
- `Actualizar-Defini.bat`: actualiza dependencias compatibles de Python y npm.
- `Detener-Defini.bat`: detiene backend y frontend desde otra ventana.

Para detener todo usa **Ctrl+C** en la ventana del iniciador o ejecuta `Detener-Defini.bat`. Si otro dispositivo no conecta por LAN, permite Python y Node en el firewall para redes privadas.

## Ejecutar en modo desarrollo

Abre dos terminales en la carpeta descomprimida.

### Terminal 1: backend

```bash
cd backend
python -m venv .venv
```

Activa el entorno virtual:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS o Linux
source .venv/bin/activate
```

Instala y ejecuta:

```bash
python -m pip install -r requirements.txt
python run.py
```

El administrador y las demás cuentas de prueba ya vienen en la base incluida. Usa el mismo usuario y contraseña del proyecto principal. Si eliminas el archivo SQLite, el backend creará una base nueva y mostrará una contraseña temporal para un administrador nuevo.

### Terminal 2: frontend

```bash
cd frontend
npm install
npm run dev
```

En el mismo computador abre <http://localhost:5173>. Vite reenvía las llamadas `/api` al backend en el puerto 8080.

## Acceso desde la LAN

Conecta ambos servicios y los dispositivos cliente a la misma red local. En los otros dispositivos abre `http://IP-DEL-COMPUTADOR:5173`, usando la IPv4 del equipo que ejecuta los servicios. Si hace falta, permite Node y Python en el firewall para redes privadas; no desactives el firewall completo. No configures reenvío de puertos del router ni publiques la aplicación en Internet.

## Compilar la interfaz

Desde `frontend/`:

```bash
npm run build
```

La salida queda en `frontend/dist/`. El backend la sirve en `/` si existe; para trabajar en desarrollo usa el servidor Vite descrito arriba.

## Funciones del Sprint 2

- Validar los campos obligatorios.
- Crear, listar, actualizar y eliminar usuarios.
- Asignar roles de administrador y empleado y validar sus accesos.
- Cerrar sesión.
- Crear, listar, actualizar y eliminar tipos de producto.
- Registrar y listar productos del inventario.
- Buscar productos y filtrar por tipo.

La base local conserva sus datos al detener y volver a ejecutar el backend. Si vas a usar información real, no compartas la carpeta `backend/data/`, porque contiene las cuentas y los datos guardados.
