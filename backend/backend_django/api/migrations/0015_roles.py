from django.db import migrations, models

# Copia congelada de api.permissions al momento de esta migración: si el
# catálogo cambia después, esta conversión no debe cambiar con él.
PUESTOS = {
    "comercial": {"tablero", "clientes", "solicitudes", "cotizaciones", "pagos", "ordenes"},
    "financiera": {"tablero", "pagos", "aprobar_pagos"},
    "logistica": {"tablero", "ordenes", "despachos"},
    "aprobador": {"tablero", "aprobar_cotizaciones"},
    "despacho": {"despachos"},
    "disponibilidad": {"disponibilidad"},
}
EXCLUSIVOS = {"aprobar_pagos"}


def roles_desde_permisos(apps, schema_editor):
    """Cada usuario recibe los puestos que ya cubrían sus permisos; lo que
    sobre queda como permiso adicional. Nadie gana ni pierde acceso."""
    User = apps.get_model("api", "User")
    for u in User.objects.all():
        propios = set(u.permisos or [])
        if u.is_admin or u.is_superadmin:
            u.roles = ["admin"]
            u.permisos = sorted(propios & EXCLUSIVOS)
        else:
            roles, cubiertos = [], set()
            # Los más grandes primero: un puesto contenido en otro no se agrega.
            for rol, perms in sorted(PUESTOS.items(), key=lambda x: -len(x[1])):
                if perms <= propios and not perms <= cubiertos:
                    roles.append(rol)
                    cubiertos |= perms
            u.roles = roles
            u.permisos = sorted(propios - cubiertos)
        u.save(update_fields=["roles", "permisos"])


class Migration(migrations.Migration):
    dependencies = [("api", "0014_nombre_tarifa_detal")]

    operations = [
        migrations.AddField(model_name="user", name="roles", field=models.JSONField(blank=True, default=list)),
        migrations.RunPython(roles_desde_permisos, migrations.RunPython.noop),
    ]
