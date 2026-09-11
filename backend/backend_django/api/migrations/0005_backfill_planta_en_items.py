"""Rellena CotizacionItem.planta en las líneas anteriores al reparto por planta.

Antes de esto la planta vivía solo en la cotización, así que toda línea vieja
sale de esa misma planta. `planta_efectiva` ya hace ese fallback en memoria,
pero dejar el dato escrito permite filtrar y agrupar por planta en consultas.
"""
from django.db import migrations


def rellenar_items(apps, schema_editor):
    CotizacionItem = apps.get_model("api", "CotizacionItem")
    for item in CotizacionItem.objects.filter(planta__isnull=True).select_related("cotizacion"):
        item.planta_id = item.cotizacion.planta_id
        item.save(update_fields=["planta"])


def revertir(apps, schema_editor):
    """Nada que deshacer: la columna se va con la migración anterior."""


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0004_cotizacionitem_planta_alter_cotizacion_planta_and_more"),
    ]

    operations = [
        migrations.RunPython(rellenar_items, revertir),
    ]
