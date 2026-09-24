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
from api.models import User  # noqa: E402




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

    # Plantas, materiales y precios reales. Actualiza los valores si ya existen.
    call_command("cargar_precios")


if __name__ == "__main__":
    run()
