from rest_framework.views import APIView
from rest_framework.response import Response
from api.models import Planta
from api.serializers import PlantaSerializer
from api.permissions import Requiere

# Leer el catálogo, cualquiera con sesión (se usa al cotizar, despachar…); cambiarlo, "precios".
CATALOGO = Requiere((), ("precios",))


class PlantaListCreateView(APIView):
    permission_classes = [CATALOGO]

    def get(self, request):
        # Por defecto solo las activas: los selectores de cotización y despacho
        # no deben ofrecer plantas dadas de baja. El panel de administración
        # pide ?todas=1 para poder verlas y reactivarlas.
        plantas = Planta.objects.all()
        if request.query_params.get("todas") not in ("1", "true", "True"):
            plantas = plantas.filter(activa=True)
        return Response(PlantaSerializer(plantas, many=True).data)

    def post(self, request):
        ser = PlantaSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        ser.save()
        return Response(ser.data, status=201)


class PlantaDetailView(APIView):
    permission_classes = [CATALOGO]

    def get_object(self, planta_id):
        return Planta.objects.filter(id=planta_id).first()

    def get(self, request, planta_id):
        planta = self.get_object(planta_id)
        if not planta:
            return Response({"detail": "No encontrada"}, status=404)
        return Response(PlantaSerializer(planta).data)

    def patch(self, request, planta_id):
        planta = self.get_object(planta_id)
        if not planta:
            return Response({"detail": "No encontrada"}, status=404)
        ser = PlantaSerializer(planta, data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        ser.save()
        return Response(ser.data)

    def delete(self, request, planta_id):
        planta = self.get_object(planta_id)
        if not planta:
            return Response({"detail": "No encontrada"}, status=404)
        planta.delete()
        return Response(status=204)
