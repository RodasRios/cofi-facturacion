from rest_framework.views import APIView
from rest_framework.response import Response
from api.models import Planta
from api.serializers import PlantaSerializer
from api.permissions import IsAdmin


class PlantaListCreateView(APIView):
    def get(self, request):
        plantas = Planta.objects.all()
        return Response(PlantaSerializer(plantas, many=True).data)

    def post(self, request):
        if not request.user.is_admin:
            return Response({"detail": "Solo un administrador puede crear plantas"}, status=403)
        ser = PlantaSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        ser.save()
        return Response(ser.data, status=201)


class PlantaDetailView(APIView):
    def get_permissions(self):
        if self.request.method in ("PATCH", "DELETE"):
            return [IsAdmin()]
        return super().get_permissions()

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
