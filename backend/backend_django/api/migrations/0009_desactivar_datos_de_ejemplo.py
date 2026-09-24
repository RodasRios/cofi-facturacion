"""Desactiva las plantas y materiales de ejemplo del seed original.

Antes de cargar la lista real de precios, seed.py creaba cuatro plantas y seis
materiales inventados. Quedaron en las bases que ya habían arrancado y seguían
apareciendo al cotizar. Se desactivan (no se borran: alguna cotización de
prueba puede apuntarlos) y se hace por nombre exacto, para no tocar nunca una
planta o material real que alguien cree después desde el panel.
"""
from django.db import migrations

PLANTAS_EJEMPLO = [
    "Planta El Roble", "Planta Cantera Azul", "Planta Los Guayabos", "Planta Cerro Verde",
]
MATERIALES_EJEMPLO = [
    "Triturado 3/4", "Triturado 1/2", "Base granular", "Arena de peña", "Recebo", "Gravilla",
]


def desactivar(apps, schema_editor):
    apps.get_model("api", "Planta").objects.filter(nombre__in=PLANTAS_EJEMPLO).update(activa=False)
    apps.get_model("api", "Material").objects.filter(nombre__in=MATERIALES_EJEMPLO).update(activo=False)


def reactivar(apps, schema_editor):
    apps.get_model("api", "Planta").objects.filter(nombre__in=PLANTAS_EJEMPLO).update(activa=True)
    apps.get_model("api", "Material").objects.filter(nombre__in=MATERIALES_EJEMPLO).update(activo=True)


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0008_campos_formatos_reales"),
    ]

    operations = [
        migrations.RunPython(desactivar, reactivar),
    ]
