"""Seed inicial: usuario admin + plantas + materiales de ejemplo.

Idempotente — se puede correr en cada arranque del contenedor sin duplicar datos.
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "facturacion.settings")
django.setup()

from api.models import User, Planta, Material, MaterialPlanta  # noqa: E402

PLANTAS = [
    {"nombre": "Planta El Roble", "ubicacion": "Vía La Ceja, km 4"},
    {"nombre": "Planta Cantera Azul", "ubicacion": "Vereda San Isidro"},
    {"nombre": "Planta Los Guayabos", "ubicacion": "Km 8 Vía al Retiro"},
    {"nombre": "Planta Cerro Verde", "ubicacion": "Corregimiento Santa Elena"},
]

MATERIALES = [
    {"nombre": "Triturado 3/4", "tipo": "triturado", "unidad_medida": "m3"},
    {"nombre": "Triturado 1/2", "tipo": "triturado", "unidad_medida": "m3"},
    {"nombre": "Base granular", "tipo": "triturado", "unidad_medida": "m3"},
    {"nombre": "Arena de peña", "tipo": "agregado", "unidad_medida": "m3"},
    {"nombre": "Recebo", "tipo": "agregado", "unidad_medida": "m3"},
    {"nombre": "Gravilla", "tipo": "agregado", "unidad_medida": "m3"},
]


def run():
    if not User.objects.filter(username="admin").exists():
        admin = User(username="admin", email="admin@cofi-facturacion.local", nombre="Administrador", rol="comercial", is_admin=True)
        admin.set_password("admin123")
        admin.save()
        print("Usuario admin creado (admin / admin123) — cambia la contraseña en producción.")

    plantas = {}
    for p in PLANTAS:
        planta, created = Planta.objects.get_or_create(nombre=p["nombre"], defaults={"ubicacion": p["ubicacion"]})
        plantas[planta.nombre] = planta
        if created:
            print(f"Planta creada: {planta.nombre}")

    materiales = []
    for m in MATERIALES:
        material, created = Material.objects.get_or_create(
            nombre=m["nombre"], defaults={"tipo": m["tipo"], "unidad_medida": m["unidad_medida"]},
        )
        materiales.append(material)
        if created:
            print(f"Material creado: {material.nombre}")

    base_precios = [42000, 45000, 38000, 55000, 30000, 48000]
    for planta in plantas.values():
        for material, base in zip(materiales, base_precios):
            MaterialPlanta.objects.get_or_create(
                material=material, planta=planta, defaults={"precio_unitario": base},
            )


if __name__ == "__main__":
    run()
