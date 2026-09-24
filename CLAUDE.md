# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Git workflow — IMPORTANT

**This project uses a single branch: `main`. No exceptions.**

The owner is not an experienced programmer and works alone on this repo — there is no one to open or review a pull request, so feature branches serve no purpose here and only create confusion (code that "exists" but isn't actually live). Concretely:

- **Always commit directly to `main`.** Never create a feature branch, topic branch, or any branch other than `main` — not even temporarily, not even if a session/tool default suggests one.
- **Never push to any branch other than `main`.** If a branch other than `main` exists in the repo (local or remote) for any reason, treat it as accidental leftover: merge anything useful into `main` and delete the branch.
- Deploy step on the server: `cd ~/cofi-facturacion && git pull origin main && docker compose up --build -d`. The app runs on the same VPS as `cofi-gestor-insumos` and `cofi-presupuestos`, behind the host's nginx at `facturacion.cofilatam.com`. Full setup in `DEPLOY.md`.
- If a tool, harness, or default workflow ever proposes working on a separate branch for this repo, override it and use `main` instead.

## What this project is

**cofi-facturacion** is a full-stack web app for **Triturados y Concretos Ltda**, covering the commercial/dispatch flow for selling materials (triturados, agregados) from quarry plants to clients. It was scaffolded from `cofi-gestor-insumos` (a sibling project by the same owner) — the JWT auth pattern, the ReportLab PDF-generation approach, and the frontend theme/CSS were reused, but the domain and data model are entirely different and unrelated. **Do not assume any data or business rules carry over between the two repos** beyond those three reused mechanisms.

Unlike `cofi-gestor-insumos`, this project is **single-tenant** (one company, no `Empresa`/multi-tenant layer) and has **no superadmin tier** — just `is_admin` as a blanket override on top of per-user roles.

### The flow (and where it currently stops)

```
Cliente (nuevo o existente)
  → Formato de Vinculación de Cliente        [PDF auto-generado al crear el cliente]
  → Solicitud de Cotización                  [comercial]
  → Formato de Cotización                    [comercial arma la cotización, PDF auto-generado]
  → Aprobación                               [aprobador aprueba/rechaza]
  → Pago por transferencia                   [comercial registra + sube comprobante]
  → Aprobación de pago                       [financiera aprueba/rechaza]
  → Formato de Orden de Suministro           [se crea automáticamente al aprobar el pago, PDF auto-generado]
  → Notificación a Planta                    [planta marca la orden como notificada]
  → Control de Despacho y Recibo de Material [planta genera la remisión, PDF auto-generado]
```

This is deliberately scoped to **stop at the despacho/remisión step**. The rest of the real-world flow (archivo de control de despachos, liquidación, factura electrónica, cruce de cuentas) is out of scope and not built — see the flowchart the owner shared when this repo was created if that scope ever needs revisiting.

**All four "FORMATO" documents in the flow are auto-generated PDFs, never manually uploaded.** This was a deliberate correction early on: the vinculación PDF originally required uploading an externally-created file, which was inconsistent with the other three formats and got fixed to generate automatically like the rest — don't reintroduce an upload-based flow for any new formato without discussing it first.

### Links de vinculación (`ClienteToken`)

El `Formato de Vinculación` puede llenarlo el propio cliente en vez del comercial.
El comercial genera un token en Clientes → "Link para cliente", copia el link
(`/vincular/<token>`) y se lo manda. El cliente lo abre **sin tener usuario** —
el token es la credencial — llena los mismos campos que `ClienteSerializer`
expone en "Nuevo cliente", y al enviarlo se crea el `Cliente` con su
`numero_vinculacion` y su PDF, igual que por la vía interna.

- **Un solo uso y 3 días de vigencia** (`VINCULACION_TOKEN_DIAS` en `models.py`).
  `ClienteToken.estado` deriva de `usado_at`/`revocado`/`expira_at`; no se guarda.
- El `POST` público toma el token con `select_for_update()` dentro de una
  transacción: sin eso, dos envíos simultáneos del mismo link crearían dos clientes.
- `VinculacionPublicaView` lleva `authentication_classes = []` y un
  `AnonRateThrottle` con scope `vinculacion_publica` (`DEFAULT_THROTTLE_RATES`
  en settings), porque es el único endpoint sin login de la app.
- En el frontend, `api/clienteTokens.ts` usa una instancia de axios **aparte**
  para lo público: el `client` compartido manda el `Authorization` guardado y
  redirige a `/login` ante un 401, y nada de eso aplica a un visitante sin cuenta.
- La ruta `/vincular/:token` va fuera del `Shell` en `App.tsx` (sin `ProtectedRoute`).
- `api/tests.py` cubre el flujo completo, el un-solo-uso, vencido/revocado y el
  gate de rol.

### Reintentos: las dos flechas de "No" del flujo

`Cotizacion.solicitud` y `Pago.cotizacion` son **FK, no 1:1**, y eso es
deliberado. Cuando eran 1:1, un rechazo dejaba el caso muerto: una solicitud con
cotización rechazada no admitía otra cotización, y una cotización con pago
rechazado no admitía otro comprobante. El diagrama del negocio dice lo
contrario — ambos "No" pasan por `SEGUIMIENTO CLIENTE` y **vuelven** al paso
anterior.

- Solo puede haber **una viva a la vez**: `SolicitudCotizacion.cotizacion_vigente`
  y `Cotizacion.pago_vigente` ignoran las rechazadas y son lo que las vistas
  consultan antes de permitir crear otra. No hay constraint en la base que lo
  imponga; la regla vive en las vistas.
- Rechazar una cotización deja la solicitud en `estado="en_seguimiento"`; crear
  una nueva la devuelve a `"cotizada"`.
- Los serializers exponen `tiene_cotizacion` / `tiene_pago` derivados de esos
  `*_vigente`, y el frontend filtra por ellos (**no** por "tiene alguna fila
  relacionada", que es lo que bloqueaba el reintento).
- Cada rechazo, aprobación y nueva cotización escribe un `Seguimiento`
  automático; las notas manuales las agrega el comercial desde el tablero.

### Dos tarifas e IVA

La lista de precios real de la empresa maneja **dos tarifas por material y
planta**: venta especial (clientes con convenio) y venta detal. Por eso
`MaterialPlanta` tiene `precio_especial` y `precio_detal`, ambos **sin IVA**.

- `precio_detal` puede ser `null` — no todas las plantas manejan esa tarifa.
  `MaterialPlanta.precio(tipo_precio)` cae a la especial cuando falta, así que
  **nunca leas los campos directamente** para cotizar.
- `Cliente.tipo_precio` define qué tarifa se le aplica; la cotización copia esa
  decisión en `Cotizacion.tipo_precio` al crearse (se puede forzar otra mandando
  `tipo_precio` en el POST).
- El IVA (19%, `IVA_PORCENTAJE`) lo calcula la cotización, no se guarda en los
  precios. `Cotizacion.subtotal` es sin IVA, `iva` el impuesto y `total` la
  suma — **`total` cambió de significado**: antes era la suma de las líneas,
  ahora incluye IVA (es lo que se le cobra al cliente y lo que propone el pago).
- `Cotizacion.iva_porcentaje` guarda una copia de la tarifa vigente, para que
  subir el IVA mañana no altere documentos ya emitidos.

### Catálogo real de precios

`api/management/commands/cargar_precios.py` tiene las 6 plantas, 27 materiales
y 41 precios reales (lista del 15/04/2026). Es la **única fuente**: `seed.py`
solo lo invoca, así que no dupliques catálogos.

```bash
python manage.py cargar_precios                    # crea o actualiza precios
python manage.py cargar_precios --desactivar-otros # apaga lo que no esté en la lista
```

`GET /plantas/` devuelve **solo las activas**; el panel de administración pide
`?todas=1` para verlas todas y poder reactivar una. Los selectores de cotización
y despacho usan el valor por defecto, así que una planta dada de baja deja de
ofrecerse. Lo mismo hace `GET /materiales/` con `activo`.

Es idempotente — cuando cambien los precios, se editan las tablas de ese
archivo y se vuelve a correr. Un detalle del PDF original: el MDC-25 aparece
con unidad "M4", que se cargó como m3 por ser un error de digitación evidente.

### Reparto por planta (multi-planta)

La planta está en el **ítem**, no en la cotización. `CotizacionItem.planta`
permite que un mismo material aparezca en varias líneas con plantas distintas
(60 m³ de una, 40 de otra), y el `precio_unitario` de cada línea sale del
`MaterialPlanta` de **su** planta — repartir entre plantas con precios
distintos cobra lo correcto en cada una.

- `Cotizacion.planta` sigue existiendo pero es solo la **planta por defecto**
  (la preseleccionada al armar). Nunca la uses como "la planta" de la
  cotización: usa `Cotizacion.plantas` o `CotizacionItem.planta_efectiva`,
  que cae a la de la cotización para las líneas anteriores a este cambio.
- Al aprobar el pago se emite **una `OrdenSuministro` por planta**, cada una
  con solo sus ítems, su `numero` y su PDF — porque cada planta despacha por
  su cuenta. `unique_together (cotizacion, planta)` impide duplicarlas.
- El porcentaje del reparto **no se guarda**: se calcula desde las cantidades
  (`frontend/src/lib/cotizacion.ts`). Guardarlo sería un dato que puede quedar
  en contra de las cantidades.
- El frontend exige que el reparto de cada material sume exactamente lo pedido
  antes de dejar generar la cotización.

### Armado de la cotización (`components/NuevaCotizacion.tsx`)

- **Precio por línea** (`CotizacionItem.origen_precio`): `especial` o `detal`
  toma la tarifa de SU planta — el servidor la pone e **ignora el precio que
  mande el navegador** — y `manual` usa el `precio_unitario` enviado. El
  aprobador ve el distintivo "precio manual" en la lista.
- **Una planta sin precio para el material no se puede elegir**: el formulario
  no la ofrece y `_validar_lineas()` responde 400. Antes caía a $0 en silencio y
  salían cotizaciones sin valores. Todo se valida antes de crear nada.
- **Cargos y descuentos** (`CotizacionAjuste`): monto fijo o porcentaje; el
  porcentaje es sobre el subtotal de materiales (no sobre otros ajustes, así el
  orden no importa). `aplica_iva` por ajuste: un flete puede ir sin IVA.
  `Cotizacion.subtotal` = materiales + ajustes; `iva` = solo sobre lo gravado.
  `lib/cotizacion.ts::calcularTotales` replica ese cálculo para la vista previa
  — si cambia en el modelo, cambia allá también.
- **Notas aclaratorias**: catálogo en `services/notas_cotizacion.py` (clave,
  título, texto). `Cotizacion.notas_aclaratorias` guarda las claves elegidas
  (`None` = todas, que es como quedan las cotizaciones anteriores). `notas`
  guarda las notas extra, una viñeta por línea.

### Link de pedidos (`SolicitudToken`)

El cliente arma sus propias solicitudes de cotización desde `/pedir/<token>`,
sin usuario. A diferencia del link de vinculación, este es **permanente y
multiuso**: es la puerta de ese cliente, se genera una vez desde el ícono del
carrito en Clientes y él la conserva. `POST /solicitud-tokens/` devuelve el
link vivo que ya tenga el cliente (200) en vez de crear otro (201), para no
acumular links equivalentes.

El catálogo público va **sin precios** — el cliente pide materiales y
cantidades; la cotización, con planta y precio, la arma la empresa después.
Las solicitudes creadas así se atribuyen a quien generó el link, para que
tengan dueño en el sistema.

### Tablero de seguimiento

`api/views/tablero_views.py` calcula en qué etapa va cada solicitud **sin
guardar nada**: `_etapa_de()` la deduce del estado de los documentos colgados de
la solicitud. Con varias órdenes (una por planta), la solicitud avanza al ritmo
de la más atrasada: sigue "por notificar" mientras quede una planta sin avisar. No hay campo `etapa` que pueda quedar desincronizado. Si se agrega
un paso al flujo, se agrega ahí y en el diccionario `ETAPAS` (que también dice
qué rol tiene la pelota en cada etapa).

### Roles, administradores y superusuario

`User.rol` (plain `CharField`, not `AbstractUser`) is one of `comercial | aprobador | financiera | planta`, gating the corresponding step above via the permission classes in `api/permissions.py` (`IsComercial`, `IsAprobador`, `IsFinanciera`, `IsPlanta`). `User.is_admin` is a blanket override — `_has_rol()` in `permissions.py` lets an admin through regardless of `rol`. No TOTP/2FA and no multi-tenant layer (both exist in `cofi-gestor-insumos` but were deliberately left out).

**Superusuario (`User.is_superadmin`)** — la cuenta del dueño. `User.save()` lo
fuerza a ser también `is_admin`. Reglas en `api/views/user_views.py`:
- Un admin crea y edita usuarios normales; **solo el superusuario** crea, edita,
  da o quita permisos de admin/superusuario y toca cuentas de administradores.
- Nadie se quita su propio acceso, y siempre queda al menos un superusuario activo.
- **Eliminar** solo borra si el usuario no tiene documentos (`User.tiene_documentos()`);
  si los tiene, responde 409 y se desactiva en su lugar — así las cotizaciones
  conservan a su firmante.
- La migración 0011 convirtió en superusuario al usuario `admin` existente.
  Si se pierde el acceso: `python manage.py superusuario <usuario> --password`.

**Contraseñas temporales**: al crear un usuario o restablecer su contraseña desde
Configuración → Usuarios, la clave la genera el navegador, se muestra una sola vez
para copiarla, y queda `debe_cambiar_password=True`. `ProtectedRoute` manda a esa
persona a `/primer-ingreso` hasta que la cambie (`POST auth/cambiar-password`, que
en ese caso no pide la actual). El login no distingue mayúsculas en el usuario.

**Configuración** (`pages/ConfiguracionPage.tsx`, `/configuracion`, ícono de engranaje
con el nombre en la cabecera; idea traída de `cofi-gestor-insumos`):
Mi cuenta (nombre, cédula, cargo, teléfono, correo + contraseña, `PATCH auth/perfil`),
Mi firma (con recorte, `components/ui/ImageCropper.tsx`, y vista previa de cómo sale
en la cotización) y Usuarios (admin/superusuario). La cédula sale bajo el nombre del
firmante en la cotización FR-GC-08. `/admin` quedó solo para plantas y precios.

**Resumen del tablero** (`GET tablero/resumen/`, `components/ResumenTablero.tsx`):
ventas del mes (= pagos aprobados), cotizado, % de aprobación, pendientes, despachado,
6 meses de ventas vs. cotizado y tops por planta/cliente/material. Se calcula al
vuelo, igual que las etapas; no hay tablas de agregados.

## Commands

### Backend (Django)
```bash
cd backend/backend_django
python -m venv venv && source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .env.example .env           # DEBUG defaults to True here; set SECRET_KEY for anything beyond local use
python manage.py migrate
python seed.py                 # creates superusuario 'admin' (password 'admin123' or $ADMIN_PASSWORD) + the real catalog

python manage.py runserver 8000
```

> Same gotcha as `cofi-gestor-insumos`: `User` is a plain `models.Model`, not `AbstractUser`, so `python manage.py createsuperuser` creates a row nothing in this app ever reads. Create/promote users via `seed.py` or `python manage.py shell`:
> ```python
> from api.models import User
> u = User(username="alguien", rol="aprobador", is_admin=True)
> u.set_password("...")
> u.save()
> ```

### Frontend
```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api to localhost:8000
npm run build      # tsc -b && vite build
npm run lint
```

### Docker Compose (the normal way to run this locally)
```bash
docker compose up --build
```
Frontend on `http://localhost:8081`, backend on `http://localhost:8001`, Postgres on `5433`. **These ports (and the `facturacion_*` container/volume names) are deliberately different from `cofi-gestor-insumos`'s (`8080`/`8000`/`5432`, `cofi_*`)** so both projects can run side by side on the same machine without collisions — keep that offset if either compose file changes.

### Database migrations
```bash
cd backend/backend_django
python manage.py makemigrations api
python manage.py migrate
```
**Always add a new migration file — never delete and regenerate `0001_initial.py` once it may have been applied anywhere.** This already caused a real outage once: a model change (adding `numero_vinculacion`/`pdf_path` to `Cliente`) was implemented by deleting and re-running `makemigrations` to produce a fresh `0001_initial.py`. Anyone whose Postgres volume had already run the old `0001_initial` had that migration recorded as applied in `django_migrations`, so `migrate` silently skipped it and the actual columns never got added — `UndefinedColumn` errors in production use. The only clean fix at that point was `docker compose down -v` to wipe the volume and start over, which is destructive and only OK because there was no real data yet. Once this app has real data, a schema change **must** ship as an additive `000N_*.py` migration.

## Architecture

### Backend — `backend/backend_django/`

Same DRF layout as `cofi-gestor-insumos`, Django project package is `facturacion` (not `cofi`):
- `api/models.py` — Django ORM models
- `api/serializers.py` — DRF serializers
- `api/views/` — one file per resource group (`auth_views`, `user_views`, `planta_views`, `material_views`, `cliente_views`, `solicitud_views`, `cotizacion_views`, `pago_views`, `orden_suministro_views`, `despacho_views`), all mounted under `/api/v1/` via `api/urls.py`
- `services/pdf_service.py` — all PDF generation (ReportLab, no system deps)
- `api/auth_backend.py` — `FacturacionJWTAuthentication` (custom `get_user`, same pattern as `CofiJWTAuthentication`)
- `api/permissions.py` — role-gate permission classes described above
- `seed.py` — idempotent; safe to re-run

### Data model and relationships

```
Planta
  └── MaterialPlanta (precio_especial + precio_detal por planta, ambos SIN IVA) → Material

Cliente
  ├── ClienteToken     (link de vinculación: un solo uso, 3 días)
  ├── SolicitudToken   (link de pedidos: permanente, multiuso, revocable)
  └── SolicitudCotizacion
        ├── SolicitudCotizacionItem → Material
        ├── Seguimiento  (bitácora de la solicitud: rechazos, aprobaciones y notas del comercial)
        └── Cotizacion  (FK, NO 1:1 — planta elegida aquí, fija de qué MaterialPlanta se toma el precio)
              ├── CotizacionItem → Material + Planta  (precio_unitario es una FOTO tomada del MaterialPlanta de ESA planta al crear la cotización — no vuelve a mirar el precio actual)
              ├── Pago  (FK, NO 1:1)
              └── OrdenSuministro  (FK, NO 1:1 — UNA POR PLANTA; se crean automáticamente al aprobar el Pago, no hay endpoint de creación manual)
                    └── Despacho  (FK a OrdenSuministro, no 1:1 — una orden puede tener varios despachos parciales)
                          └── DespachoItem → Material
```

Every document-producing model has a sequential `numero` (`SC-0001`, `COT-0001`, `OS-0001`, `REM-0001`, and `Cliente.numero_vinculacion` as `VIN-0001`), generated by a small `_numero_xxx()` helper at the top of the relevant `views/*.py` file that just counts existing rows — not a Postgres sequence, so don't create/delete rows outside the API in ways that could produce duplicate numbers.

### PDF generation (`services/pdf_service.py`)

**Formatos oficiales de la empresa** (calcados de los que Triturados y Concretos
ya usaba en papel/Excel, tamaño carta, logo en `services/assets/logo_tyc.png`):

- `generate_cotizacion(path, datos)` — **FR-GC-08 Versión 01**. Cuadro con logo
  en cada página, "Señores:", tabla con una sección por planta ("SUMINISTRO DE
  PLANTA X 2026"), notas aclaratorias, ubicación de cada planta (`Planta.ubicacion`),
  observaciones, firma del **comercial que armó la cotización** (no del
  aprobador) y cuadro Realizó/Revisó/Aprobó. El texto legal está en constantes
  `_COT_*` — si cambia el formato en papel, se cambia ahí.
- `generate_orden_suministro(path, datos)` — tabla etiqueta/valor con obra,
  fecha de suministro, transporte y placas, y "Autorizó" = el comercial.
- `generate_control_despachos(datos) -> bytes` — el consolidado por cliente
  ("Archivo data – control despachos" del flujo). **No se guarda**: se arma al
  vuelo en `GET /control-despachos/pdf/?cliente=&desde=&hasta=&obra=`.

Las tres usan `_on_page_formato()` (o un pie propio) vía `_build_doc(..., on_page=)`.
Los PDF de cotización y orden **se regeneran cada vez que se abren**, para que
los documentos viejos salgan con el formato nuevo y la orden refleje las placas
recién cargadas; los valores no cambian porque los precios de cada línea son
una foto tomada al crear la cotización.

Numeración de cotizaciones: `NNN-AAAA` por año, impresa como "COT: 160-2.026".
`COTIZACION_CONSECUTIVO_INICIAL` (env) es el último número emitido fuera del
sistema, para continuar la numeración real sin saltos.

Datos que alimentan los formatos y se capturan en la app: `SolicitudCotizacion.obra`,
`OrdenSuministro.fecha_suministro/placas_empresa/placas_cliente` (se editan
después de emitida, `PATCH /ordenes-suministro/<id>/`, comercial o planta),
`Despacho.consecutivo` (tiquete de báscula de la planta, distinto del REM
interno) y `User.cargo/telefono` (salen bajo la firma; se editan en Admin →
Usuarios). La firma la sube cada usuario desde Cotizaciones o Admin.

**Formatos genéricos** (vinculación y remisión, aún con el estilo anterior):

`generate_vinculacion` and `generate_despacho` share:
- `_on_page(canvas, doc)` — brand color bar at the top and a footer (page number + "documento generado automáticamente") on every page, wired via `doc.build(elements, onFirstPage=_on_page, onLaterPages=_on_page)` (always go through the `_build_doc()` wrapper, don't call `doc.build()` directly, or the page decoration silently disappears).
- `_build_header(titulo, numero, fecha)` — empresa name + document title + numero/fecha.
- `_items_table(items, mostrar_precio=True)` — `mostrar_precio=False` drops the Precio/Subtotal columns entirely (used for `orden_suministro` and `despacho`, which are internal delivery documents, not billing documents — showing price columns full of `-` there was flagged as unprofessional-looking and removed).
- `_build_firma_section(firma_path, label)` — embeds a *saved* signature image when one exists (for the approving user's `firma_path`); returns `[]` (no placeholder) when there isn't one.
- `_build_firmas_en_blanco(izq, der)` — two blank handwritten-signature lines side by side, for documents meant to be printed and physically signed (`despacho`, `vinculacion`).

Each PDF is generated server-side at the point the corresponding object is created/approved (see `_generar_pdf()` in each `views/*.py` file) and stored on disk under `GENERATED_PDF_DIR`, with the path saved to that model's `pdf_path` field. The frontend never uploads a formato — it only ever downloads/previews one that the backend already produced.

### Frontend — `frontend/src/`

Reused near-verbatim from `cofi-gestor-insumos` (same visual language on purpose):
- `index.css` — same CSS variable theme (`--bg-surface`, `--text-primary`, etc.), same dark mode via `.dark` class on `<html>` (Tailwind's `dark:` prefix does **not** work here either — use `.dark .classname` in CSS).
- `components/ui/Icon.tsx` + the Material Symbols font — same icon system.
- `components/ui/NeuralBackground.tsx` — same animated canvas background on the login page and app shell.
- `components/ui/PdfViewerModal.tsx` — ported later, after the first "Descargar PDF" pass; every "Ver PDF" button across the app opens this modal (loads the PDF as an authenticated blob, shows it in an iframe, has its own Descargar button inside) instead of triggering a direct file download. Prefer this pattern for any new document-viewing UI rather than reintroducing `downloadAuthed`-style direct downloads.
- `contexts/AuthContext.tsx` / `contexts/ThemeContext.tsx` — same shape, but simplified: no TOTP step, no `empresa_id` redirect logic (this app has no multi-tenant concept).
- `components/layout/AppShell.tsx` — simplified nav (no `obraId`-scoped routes, no superadmin panel); nav items are shown to everyone regardless of role, with role-specific actions (approve/reject, notify, etc.) gated inline per-button using `user.rol`/`user.is_admin` from `useAuth()`.
- Data fetching: TanStack Query v5, same as the sibling project. No react-hook-form/zod here (forms are plain `useState`) and no react-dropzone — this app's forms are intentionally simpler ("una pequeña página" was the original ask), so don't reach for those libraries without a reason.

## Key environment variables

Only one `.env`, at `backend/backend_django/.env` (no root-level `.env` yet — there's no separate Docker-prod config split like `cofi-gestor-insumos` has, since this project has no production deployment yet).

| Variable | Default | Notes |
|---|---|---|
| `SECRET_KEY` | `dev-secret-key-change-in-production` | Generate a real one with `openssl rand -hex 32` before this ever leaves localhost |
| `DEBUG` | `True` | Set to `False` deliberately when deploying anywhere real |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | `facturacion` / `facturacion_user` / `facturacion_pass` / `localhost` / `5432` | Postgres only, no SQLite |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | No refresh-token/logout endpoint, same as the sibling project |
| `UPLOAD_DIR` | `media/uploads` | Currently only used for `auth/firma` (signature images); every other formato is generated, not uploaded |
| `GENERATED_PDF_DIR` | `media/generated_pdfs` | All four auto-generated formatos land here |
