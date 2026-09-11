"""Carga el catálogo real de plantas, materiales y precios.

Los datos salen de la lista de precios de Triturados y Concretos Ltda
(actualización del 15/04/2026). Los precios se guardan **sin IVA**; el 19% lo
calcula la cotización.

Es idempotente: se puede volver a correr cuando cambien los precios y solo
actualiza los valores. Con --desactivar-otros, además apaga las plantas y
materiales que no estén en esta lista (útil para limpiar los de ejemplo).

    python manage.py cargar_precios
    python manage.py cargar_precios --desactivar-otros
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import Material, MaterialPlanta, Planta

M3, CANECA, GALON = "m3", "caneca", "galón"

# nombre -> (tipo, unidad)
MATERIALES = {
    "Base granular tipo INVIAS": ("agregado", M3),
    "Base granular tipo INVIAS Clase A": ("agregado", M3),
    "Base granular tipo INVIAS Clase B": ("agregado", M3),
    "Sub base granular tipo INVIAS": ("agregado", M3),
    "Sub base granular tipo INVIAS Clase A": ("agregado", M3),
    "Piedra filtro": ("agregado", M3),
    "Piedra mezclada": ("agregado", M3),
    'Triturado de 3/4"': ("triturado", M3),
    'Triturado de 1"': ("triturado", M3),
    "Triturado 3/4 para concretos": ("triturado", M3),
    "Triturado 1/2 para concretos": ("triturado", M3),
    "Crudo de río": ("agregado", M3),
    "Crudo delgado (gravilla)": ("agregado", M3),
    "Arenón / arena de trituración": ("triturado", M3),
    "Arena de trituración (por cono)": ("triturado", M3),
    "Arena natural": ("agregado", M3),
    "Arena gruesa": ("agregado", M3),
    "Gravilla 3/4": ("agregado", M3),
    'Gravilla (canto rodado) 3/4"': ("agregado", M3),
    "Gravilla número 4": ("agregado", M3),
    "Número 4 (clasificado, sin fracturar)": ("agregado", M3),
    "MDC-19 con asfalto normalizado 60/70": ("otro", M3),
    "MDC-25 con asfalto normalizado 60/71": ("otro", M3),
    "MDC-10 con asfalto normalizado 60/70": ("otro", M3),
    "Emulsión (no incluye recipiente)": ("otro", CANECA),
    "Emulsión (incluye recipiente)": ("otro", CANECA),
    "Emulsión": ("otro", GALON),
}

# planta -> (vigencia, [(material, precio especial, precio detal)])
# El precio detal en None significa que esa planta no maneja esa tarifa; al
# cotizar a un cliente de detal se usa entonces el precio especial.
PLANTAS = {
    "Planta Río Frío": (
        "Vigente desde el 15 de enero de 2026 · Fuente DCG Constructora",
        [
            ("Base granular tipo INVIAS", 65000, 65000),
            ("Sub base granular tipo INVIAS", 50000, 50000),
            ("Piedra filtro", 50000, 50000),
            ('Triturado de 3/4"', 66000, 66000),
            ('Triturado de 1"', 66000, 66000),
            ("Crudo de río", 40000, 40000),
            ("Arenón / arena de trituración", 66000, 66000),
        ],
    ),
    "Planta Catarina": (
        "Vigente desde el 15 de enero de 2026",
        [
            ("Base granular tipo INVIAS", 43000, None),
            ("Sub base granular tipo INVIAS", 39000, None),
        ],
    ),
    "Planta Portobelo": (
        "Vigente desde el 22 de julio de 2026",
        [
            ("Base granular tipo INVIAS Clase A", 65000, 68000),
            ("Base granular tipo INVIAS Clase B", 54000, 61000),
            ("Sub base granular tipo INVIAS Clase A", 41000, 44000),
            ("Arena natural", 48000, 58000),
            ("Triturado 3/4 para concretos", 55000, 60000),
            ("Triturado 1/2 para concretos", 55000, 60000),
            ("Piedra filtro", 44000, 54000),
            ("Piedra mezclada", 44000, 54000),
            ("Número 4 (clasificado, sin fracturar)", 36000, 36000),
            ('Gravilla (canto rodado) 3/4"', 39500, 40000),
            ("Crudo de río", 35000, 42000),
            ("Arena de trituración (por cono)", 55000, 60000),
            ("MDC-19 con asfalto normalizado 60/70", 640000, 640000),
            ("MDC-25 con asfalto normalizado 60/71", 635000, 635000),
            ("MDC-10 con asfalto normalizado 60/70", 670000, 670000),
            ("Emulsión (no incluye recipiente)", 890000, 890000),
            ("Emulsión (incluye recipiente)", 945000, 945000),
            ("Emulsión", 16182, 16182),
        ],
    ),
    "Planta Corinto": (
        "Vigente desde el 15 de enero de 2026",
        [
            ("Sub base granular tipo INVIAS", 41000, 44000),
            ("Piedra mezclada", 44000, 54000),
            ("Crudo de río", 35000, 42000),
        ],
    ),
    "Planta Zabaleta": (
        "Vigente desde el 15 de abril de 2026",
        [
            ("Gravilla 3/4", 29500, 35000),
            ("Arena gruesa", 38000, 52500),
            ("Gravilla número 4", 26000, 26000),
            ("Piedra mezclada", 35000, 45000),
            ("Piedra filtro", 35000, 45000),
        ],
    ),
    "Planta La Vieja": (
        "Lista 2026",
        [
            ("Arena natural", 48000, None),
            ("Base granular tipo INVIAS", 50000, None),
            ("Sub base granular tipo INVIAS", 42000, None),
            ("Crudo de río", 35000, None),
            ("Crudo delgado (gravilla)", 40000, None),
            ("Piedra filtro", 64000, None),
        ],
    ),
}


class Command(BaseCommand):
    help = "Carga plantas, materiales y precios reales (sin IVA). Idempotente."

    def add_arguments(self, parser):
        parser.add_argument(
            "--desactivar-otros",
            action="store_true",
            help="Desactiva plantas y materiales que no estén en esta lista (no los borra).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        materiales = {}
        for nombre, (tipo, unidad) in MATERIALES.items():
            material, creado = Material.objects.get_or_create(
                nombre=nombre, defaults={"tipo": tipo, "unidad_medida": unidad},
            )
            if not creado:
                material.tipo, material.unidad_medida, material.activo = tipo, unidad, True
                material.save(update_fields=["tipo", "unidad_medida", "activo"])
            materiales[nombre] = material

        precios = 0
        for nombre_planta, (ubicacion, lista) in PLANTAS.items():
            planta, _ = Planta.objects.get_or_create(
                nombre=nombre_planta, defaults={"ubicacion": ubicacion},
            )
            planta.ubicacion, planta.activa = ubicacion, True
            planta.save(update_fields=["ubicacion", "activa"])

            for nombre_material, especial, detal in lista:
                MaterialPlanta.objects.update_or_create(
                    material=materiales[nombre_material], planta=planta,
                    defaults={
                        "precio_especial": Decimal(str(especial)),
                        "precio_detal": Decimal(str(detal)) if detal is not None else None,
                    },
                )
                precios += 1

        self.stdout.write(self.style.SUCCESS(
            f"{len(PLANTAS)} plantas, {len(MATERIALES)} materiales y {precios} precios cargados."
        ))

        if options["desactivar_otros"]:
            plantas_off = Planta.objects.exclude(nombre__in=PLANTAS).update(activa=False)
            materiales_off = Material.objects.exclude(nombre__in=MATERIALES).update(activo=False)
            self.stdout.write(self.style.WARNING(
                f"Desactivados: {plantas_off} plantas y {materiales_off} materiales fuera de la lista."
            ))
