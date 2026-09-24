from rest_framework.views import APIView
from rest_framework.response import Response
from api.models import Material, MaterialPlanta, Planta
from api.serializers import MaterialSerializer
from api.permissions import IsAdmin


class MaterialListCreateView(APIView):
    def get(self, request):
        materiales = Material.objects.filter(activo=True).prefetch_related("precios_planta")
        return Response(MaterialSerializer(materiales, many=True).data)

    def post(self, request):
        if not request.user.is_admin:
            return Response({"detail": "Solo un administrador puede crear materiales"}, status=403)
        ser = MaterialSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        ser.save()
        return Response(ser.data, status=201)


class MaterialDetailView(APIView):
    def get_permissions(self):
        if self.request.method in ("PATCH", "DELETE"):
            return [IsAdmin()]
        return super().get_permissions()

    def get_object(self, material_id):
        return Material.objects.filter(id=material_id).first()

    def get(self, request, material_id):
        material = self.get_object(material_id)
        if not material:
            return Response({"detail": "No encontrado"}, status=404)
        return Response(MaterialSerializer(material).data)

    def patch(self, request, material_id):
        material = self.get_object(material_id)
        if not material:
            return Response({"detail": "No encontrado"}, status=404)
        ser = MaterialSerializer(material, data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        ser.save()
        return Response(ser.data)

    def delete(self, request, material_id):
        material = self.get_object(material_id)
        if not material:
            return Response({"detail": "No encontrado"}, status=404)
        material.activo = False
        material.save(update_fields=["activo"])
        return Response(status=204)


class MaterialPrecioView(APIView):
    """Crea o actualiza el precio de un material en una planta (upsert)."""
    permission_classes = [IsAdmin]

    def post(self, request, material_id):
        material = Material.objects.filter(id=material_id).first()
        if not material:
            return Response({"detail": "Material no encontrado"}, status=404)
        planta_id = request.data.get("planta")
        if not planta_id:
            return Response({"detail": "planta es requerida"}, status=400)
        planta = Planta.objects.filter(id=planta_id).first()
        if not planta:
            return Response({"detail": "Planta no encontrada"}, status=404)

        # Solo se tocan las tarifas que vengan en la petición, para poder
        # editar una sin borrar la otra.
        defaults = {}
        if request.data.get("precio_especial") is not None:
            defaults["precio_especial"] = request.data["precio_especial"]
        if "precio_detal" in request.data:
            defaults["precio_detal"] = request.data["precio_detal"] or None
        if not defaults:
            return Response({"detail": "Envía precio_especial y/o precio_detal"}, status=400)

        existente = MaterialPlanta.objects.filter(material=material, planta=planta).first()
        if existente is None and "precio_especial" not in defaults:
            return Response({"detail": "El precio especial es obligatorio la primera vez"}, status=400)

        mp, _ = MaterialPlanta.objects.update_or_create(
            material=material, planta=planta, defaults=defaults,
        )
        return Response(MaterialSerializer(material).data, status=201)

    def delete(self, request, material_id):
        """Quita un material de una planta (esa planta deja de venderlo)."""
        planta_id = request.query_params.get("planta")
        borrados, _ = MaterialPlanta.objects.filter(material_id=material_id, planta_id=planta_id).delete()
        if not borrados:
            return Response({"detail": "Esa planta no tenía precio para este material"}, status=404)
        material = Material.objects.filter(id=material_id).first()
        return Response(MaterialSerializer(material).data)
