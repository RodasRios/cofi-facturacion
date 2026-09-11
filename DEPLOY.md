# Despliegue en el servidor

La app corre en el mismo VPS que `cofi-gestor-insumos` y `cofi-presupuestos`.
Los puertos (`8081`/`8001`/`5433`) y los nombres `facturacion_*` están elegidos
para no chocar con los de esos proyectos. El nginx **del host** (no el del
contenedor) es el que recibe el tráfico de internet en los puertos 80/443 y lo
reenvía al contenedor del frontend, que a su vez hace de proxy a `/api`.

```
internet → nginx del host (443, TLS de Let's Encrypt)
             → 127.0.0.1:8081  facturacion_frontend (nginx + React build)
                 → backend:8000  facturacion_backend (gunicorn + Django)
                     → postgres:5432  facturacion_postgres
```

## 1. DNS

Crear un registro **A** para `facturacion.cofilatam.com` apuntando a la IP del
servidor. Esperar a que resuelva:

```bash
dig +short facturacion.cofilatam.com
```

## 2. Clonar y configurar

```bash
cd ~
git clone <url-del-repo> cofi-facturacion
cd cofi-facturacion

cp .env.example .env
openssl rand -hex 32      # → pegar en SECRET_KEY
openssl rand -hex 24      # → pegar en DB_PASSWORD
openssl rand -hex 12      # → pegar en ADMIN_PASSWORD
nano .env
```

## 3. Levantar los contenedores

```bash
docker compose up --build -d
docker compose logs -f backend     # verificar que migró y arrancó gunicorn
curl -I http://127.0.0.1:8081      # debe responder 200
```

## 4. nginx del host

Crear `/etc/nginx/conf.d/facturacion.cofilatam.conf`:

```nginx
server {
    listen 80;
    server_name facturacion.cofilatam.com;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8081;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

## 5. Certificado TLS

```bash
sudo certbot --nginx -d facturacion.cofilatam.com
```

Certbot reescribe el bloque anterior para escuchar en 443 y redirigir el 80.
La renovación automática ya está configurada en este servidor (igual que para
`presupuestos.cofilatam.com`).

## 6. Después del primer arranque

1. Entrar a `https://facturacion.cofilatam.com` con `admin` y la contraseña de
   `ADMIN_PASSWORD`.
2. Borrar las plantas y materiales de ejemplo que creó el seed y cargar los reales.
3. Poner `RUN_SEED=false` en el `.env` y `docker compose up -d` para que no
   vuelva a insertarlos.

## Actualizar a una versión nueva

```bash
cd ~/cofi-facturacion
git pull origin main
docker compose up --build -d
```

Las migraciones se aplican solas al arrancar (`entrypoint.sh` corre `migrate`,
nunca `makemigrations` — esas se generan en local y se commitean).

## Cambiar `DB_PASSWORD` cuando ya hay datos

Postgres lee `POSTGRES_PASSWORD` **solo la primera vez**, cuando inicializa el
volumen. Después la ignora. Si se cambia `DB_PASSWORD` en el `.env` de un
proyecto que ya arrancó, el backend queda en `Restarting` con
`password authentication failed for user "facturacion_user"`.

Con el volumen vacío basta `docker compose down -v && docker compose up --build -d`,
pero eso **borra la base de datos**. Con datos reales, hay que cambiarla también
dentro de Postgres:

```bash
# 1. Cambiar la contraseña dentro de Postgres (con la clave NUEVA del .env)
docker exec -it facturacion_postgres psql -U facturacion_user -d facturacion \
    -c "ALTER USER facturacion_user WITH PASSWORD 'la-clave-nueva';"

# 2. Poner esa misma clave en el .env y reiniciar solo el backend
docker compose up -d --force-recreate backend
```

## Respaldo de la base de datos

```bash
docker exec facturacion_postgres pg_dump -U facturacion_user facturacion \
    | gzip > ~/facturacion-$(date +%F).sql.gz
```

Los PDFs generados y las firmas viven en el volumen `facturacion_media`:

```bash
docker run --rm -v facturacion_media:/media -v ~:/backup alpine \
    tar czf /backup/facturacion-media-$(date +%F).tar.gz -C /media .
```
