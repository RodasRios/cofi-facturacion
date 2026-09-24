from django.db import migrations, models


def promover_superusuario(apps, schema_editor):
    """El dueño ya entra como 'admin': ese usuario pasa a ser el superusuario."""
    User = apps.get_model("api", "User")
    if User.objects.filter(is_superadmin=True).exists():
        return
    u = (User.objects.filter(username="admin", is_active=True).first()
         or User.objects.filter(is_admin=True, is_active=True).order_by("id").first())
    if u:
        u.is_superadmin = True
        u.is_admin = True
        u.save(update_fields=["is_superadmin", "is_admin"])


class Migration(migrations.Migration):
    dependencies = [("api", "0010_ajustes_notas_y_origen_precio")]

    operations = [
        migrations.AddField("user", "is_superadmin", models.BooleanField(default=False)),
        migrations.AddField("user", "debe_cambiar_password", models.BooleanField(default=False)),
        migrations.AddField("user", "cedula", models.CharField(max_length=30, blank=True, null=True)),
        migrations.AddField("user", "last_login", models.DateTimeField(null=True, blank=True)),
        migrations.RunPython(promover_superusuario, migrations.RunPython.noop),
    ]
