import re
from django.db import migrations


def rem_a_electronico(apps, schema_editor):
    """REM-0003 → E-000003: los controles hechos en la app llevan E- para no
    confundirse con los números del talonario en papel."""
    Despacho = apps.get_model("api", "Despacho")
    for d in Despacho.objects.filter(numero__startswith="REM-"):
        m = re.fullmatch(r"REM-(\d+)", d.numero)
        if m:
            d.numero = f"E-{int(m.group(1)):06d}"
            d.save(update_fields=["numero"])


class Migration(migrations.Migration):
    dependencies = [("api", "0016_formato_despacho")]
    operations = [migrations.RunPython(rem_a_electronico, migrations.RunPython.noop)]
