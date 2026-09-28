"""Seed inicial: usuario admin + catálogo real de plantas, materiales y precios.

Idempotente — se puede correr en cada arranque del contenedor sin duplicar datos.
El catálogo vive en ``api/management/commands/cargar_precios.py`` (lista de
precios real de la empresa); aquí solo se invoca, para tener una sola fuente.
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "facturacion.settings")
django.setup()

from django.core.management import call_command  # noqa: E402
from api.models import MaterialPlanta, User  # noqa: E402




def run():
    if not User.objects.filter(username="admin").exists():
        admin = User(username="admin", email="admin@cofi-facturacion.local", nombre="Administrador", rol="comercial", is_admin=True, is_superadmin=True)
        password = os.environ.get("ADMIN_PASSWORD", "admin123")
        admin.set_password(password)
        admin.save()
        if password == "admin123":
            print("Usuario admin creado (admin / admin123) — cambia la contraseña en producción.")
        else:
            print("Usuario admin creado con la contraseña de ADMIN_PASSWORD.")

    # Catálogo real, solo en el primer arranque. Antes corría en cada arranque
    # (RUN_SEED=true por defecto) y pisaba los precios y nombres editados en
    # Plantas y precios. Para recargar la lista a propósito:
    #   python manage.py cargar_precios
    if not MaterialPlanta.objects.exists():
        call_command("cargar_precios")


if __name__ == "__main__":
    run()
