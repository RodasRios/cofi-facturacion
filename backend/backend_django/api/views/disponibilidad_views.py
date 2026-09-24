"""Disponibilidad de material por planta.

La actualiza la gente de planta (permiso "disponibilidad"), limitada a sus
plantas asignadas si las tiene. Se muestra al cotizar, para no ofrecer lo que
no hay. Leerla, cualquiera con sesión.
"""
from decimal import Decimal, InvalidOperation

from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response

from api.models import Planta, MaterialPlanta, DISPONIBILIDAD_CHOICES
from api.serializers import PlantaSerializer, MaterialPlantaSerializer
from api.permissions import Requiere, plantas_de

ESTADOS = {c for c, _ in DISPONIBILIDAD_CHOICES}


def _puede_planta(user, planta_id):
    limitadas = plantas_de(user)
    return limitadas is None or planta_id in limitadas


class DisponibilidadView(APIView):
    """Una entrada por planta activa con sus materiales. `?mias=1` = solo las del usuario."""
    permission_classes = [Requiere((), ("disponibilidad",))]

    def get(self, request):
        plantas = Planta.objects.filter(activa=True).order_by("nombre")
        limitadas = plantas_de(request.user)
        if request.query_params.get("mias") and limitadas is not None:
            plantas = plantas.filter(id__in=limitadas)
        filas = (
            MaterialPlanta.objects.filter(planta__in=plantas, material__activo=True)
            .select_related("material", "planta", "disponibilidad_actualizada_por")
            .order_by("material__nombre")
        )
        por_planta = {}
        for mp in filas:
            por_planta.setdefault(mp.planta_id, []).append(mp)
        return Response([
            {
                **PlantaSerializer(p).data,
                "editable": _puede_planta(request.user, p.id),
                "materiales": MaterialPlantaSerializer(por_planta.get(p.id, []), many=True).data,
            }
            for p in plantas
        ])


class DisponibilidadMaterialView(APIView):
    permission_classes = [Requiere(("disponibilidad",))]

    def patch(self, request, mp_id):
        mp = MaterialPlanta.objects.select_related("planta", "material").filter(id=mp_id).first()
        if not mp:
            return Response({"detail": "No encontrado"}, status=404)
        if not _puede_planta(request.user, mp.planta_id):
            return Response({"detail": f"No tienes asignada {mp.planta.nombre}."}, status=403)
        d = request.data
        if "disponibilidad" in d:
            if d["disponibilidad"] not in ESTADOS:
                return Response({"detail": "Estado no válido"}, status=400)
            mp.disponibilidad = d["disponibilidad"]
        if "cantidad_disponible" in d:
            v = d["cantidad_disponible"]
            if v in (None, ""):
                mp.cantidad_disponible = None
            else:
                try:
                    mp.cantidad_disponible = Decimal(str(v))
                except InvalidOperation:
                    return Response({"detail": "La cantidad no es un número"}, status=400)
                if mp.cantidad_disponible < 0:
                    return Response({"detail": "La cantidad no puede ser negativa"}, status=400)
        if "disponibilidad_nota" in d:
            mp.disponibilidad_nota = (d["disponibilidad_nota"] or "").strip() or None
        mp.disponibilidad_actualizada_at = timezone.now()
        mp.disponibilidad_actualizada_por = request.user
        mp.save()
        return Response(MaterialPlantaSerializer(mp).data)


class DisponibilidadPlantaView(APIView):
    """Aviso general de la planta ("sin despacho el sábado")."""
    permission_classes = [Requiere(("disponibilidad",))]

    def patch(self, request, planta_id):
        planta = Planta.objects.filter(id=planta_id).first()
        if not planta:
            return Response({"detail": "No encontrada"}, status=404)
        if not _puede_planta(request.user, planta.id):
            return Response({"detail": f"No tienes asignada {planta.nombre}."}, status=403)
        planta.nota_disponibilidad = (request.data.get("nota_disponibilidad") or "").strip() or None
        planta.nota_actualizada_at = timezone.now()
        planta.save(update_fields=["nota_disponibilidad", "nota_actualizada_at"])
        return Response(PlantaSerializer(planta).data)
