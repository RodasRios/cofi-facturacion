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
        precio = request.data.get("precio_unitario")
        if not planta_id or precio is None:
            return Response({"detail": "planta y precio_unitario son requeridos"}, status=400)
        planta = Planta.objects.filter(id=planta_id).first()
        if not planta:
            return Response({"detail": "Planta no encontrada"}, status=404)
        mp, _ = MaterialPlanta.objects.update_or_create(
            material=material, planta=planta, defaults={"precio_unitario": precio},
        )
        return Response(MaterialSerializer(material).data, status=201)
