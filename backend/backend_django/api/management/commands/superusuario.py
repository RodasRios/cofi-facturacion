"""Crea o recupera el superusuario desde el servidor.

    python manage.py superusuario <usuario>            # promueve uno existente
    python manage.py superusuario <usuario> --password # y le pone contraseña nueva

Sirve si se pierde el acceso: la app no deja quitar el último superusuario,
pero esto funciona aunque no se pueda entrar.
"""
import getpass

from django.core.management.base import BaseCommand, CommandError

from api.models import User


class Command(BaseCommand):
    help = "Crea o promueve un superusuario (dueño del sistema)."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--password", action="store_true", help="Pedir una contraseña nueva")

    def handle(self, username, password, **opts):
        user = User.objects.filter(username__iexact=username).first()
        nuevo = user is None
        if nuevo:
            user = User(username=username.lower(), rol="comercial")
        if nuevo or password:
            clave = getpass.getpass("Contraseña nueva: ")
            if len(clave) < 8:
                raise CommandError("La contraseña debe tener al menos 8 caracteres.")
            if clave != getpass.getpass("Repítela: "):
                raise CommandError("Las contraseñas no coinciden.")
            user.set_password(clave)
            user.debe_cambiar_password = False
        user.is_superadmin = True
        user.is_active = True
        user.save()
        self.stdout.write(self.style.SUCCESS(
            f"{user.username} {'creado' if nuevo else 'actualizado'} como superusuario."
        ))
