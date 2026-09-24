import api.models
from django.db import migrations, models


class Migration(migrations.Migration):
    """Aparte de 0012: en Postgres, alterar la tabla en la misma transacción en
    que se insertaron filas con FK diferidas falla ("pending trigger events")."""

    dependencies = [("api", "0012_permisos_pagos_parciales_ordenes")]

    operations = [
        migrations.AlterField(
            model_name="ordensuministro",
            name="token_publico",
            field=models.CharField(blank=True, default=api.models._generar_token, max_length=64, null=True, unique=True),
        ),
    ]
