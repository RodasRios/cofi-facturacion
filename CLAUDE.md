# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Git workflow — IMPORTANT

**This project uses a single branch: `main`. No exceptions.**

The owner is not an experienced programmer and works alone on this repo — there is no one to open or review a pull request, so feature branches serve no purpose here and only create confusion (code that "exists" but isn't actually live). Concretely:

- **Always commit directly to `main`.** Never create a feature branch, topic branch, or any branch other than `main` — not even temporarily, not even if a session/tool default suggests one.
- **Never push to any branch other than `main`.** If a branch other than `main` exists in the repo (local or remote) for any reason, treat it as accidental leftover: merge anything useful into `main` and delete the branch.
- This repo is currently run **locally only** via `docker compose up --build` (see below) — there is no production server yet. When one exists, update this section with the actual deploy command, mirroring how `cofi-gestor-insumos` documents its own `git pull origin master && docker compose up --build` deploy step.
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

### Roles

`User.rol` (plain `CharField`, not `AbstractUser`) is one of `comercial | aprobador | financiera | planta`, gating the corresponding step above via the permission classes in `api/permissions.py` (`IsComercial`, `IsAprobador`, `IsFinanciera`, `IsPlanta`). `User.is_admin` is a blanket override — `_has_rol()` in `permissions.py` lets an admin through regardless of `rol`. There is no `is_superadmin` and no TOTP/2FA in this project (both exist in `cofi-gestor-insumos` but were deliberately left out here to keep scope small).

## Commands

### Backend (Django)
```bash
cd backend/backend_django
python -m venv venv && source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .env.example .env           # DEBUG defaults to True here; set SECRET_KEY for anything beyond local use
python manage.py migrate
python seed.py                 # creates 'admin' (password 'admin123'), 4 plantas, 6 materiales with example prices

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
  └── MaterialPlanta (precio_unitario por planta) → Material

Cliente
  └── SolicitudCotizacion
        ├── SolicitudCotizacionItem → Material
        └── Cotizacion  (1:1, planta elegida aquí — fija de qué MaterialPlanta se toma el precio)
              ├── CotizacionItem → Material  (precio_unitario es una FOTO tomada de MaterialPlanta al crear la cotización — no vuelve a mirar el precio actual)
              ├── Pago  (1:1)
              └── OrdenSuministro  (1:1 con Cotizacion; se crea automáticamente al aprobar el Pago — no hay endpoint de creación manual)
                    └── Despacho  (FK a OrdenSuministro, no 1:1 — una orden puede tener varios despachos parciales)
                          └── DespachoItem → Material
```

Every document-producing model has a sequential `numero` (`SC-0001`, `COT-0001`, `OS-0001`, `REM-0001`, and `Cliente.numero_vinculacion` as `VIN-0001`), generated by a small `_numero_xxx()` helper at the top of the relevant `views/*.py` file that just counts existing rows — not a Postgres sequence, so don't create/delete rows outside the API in ways that could produce duplicate numbers.

### PDF generation (`services/pdf_service.py`)

Four generators, one per formato: `generate_vinculacion`, `generate_cotizacion`, `generate_orden_suministro`, `generate_despacho`. All share:
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
