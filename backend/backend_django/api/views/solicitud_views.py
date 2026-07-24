from rest_framework.views import APIView
from rest_framework.response import Response
from api.models import SolicitudCotizacion, SolicitudCotizacionItem, Cliente, Material
from api.serializers import SolicitudCotizacionSerializer


def _numero_solicitud():
    count = SolicitudCotizacion.objects.count()
    return f"SC-{count + 1:04d}"


class SolicitudCotizacionListCreateView(APIView):
    def get(self, request):
        solicitudes = SolicitudCotizacion.objects.select_related("cliente", "creado_por").prefetch_related("items")
        estado = request.query_params.get("estado")
        if estado:
            solicitudes = solicitudes.filter(estado=estado)
        return Response(SolicitudCotizacionSerializer(solicitudes, many=True).data)

    def post(self, request):
        d = request.data
        cliente_id = d.get("cliente")
        items = d.get("items") or []
        if not cliente_id:
            return Response({"detail": "cliente es requerido"}, status=400)
        if not items:
            return Response({"detail": "La solicitud debe tener al menos un material"}, status=400)
        cliente = Cliente.objects.filter(id=cliente_id).first()
        if not cliente:
            return Response({"detail": "Cliente no encontrado"}, status=404)

        solicitud = SolicitudCotizacion.objects.create(
            numero=_numero_solicitud(),
            cliente=cliente,
            notas=d.get("notas"),
            creado_por=request.user,
        )
        for it in items:
            material = Material.objects.filter(id=it.get("material")).first()
            if not material:
                continue
            SolicitudCotizacionItem.objects.create(
                solicitud=solicitud, material=material, cantidad=it.get("cantidad") or 0,
            )
        return Response(SolicitudCotizacionSerializer(solicitud).data, status=201)


class SolicitudCotizacionDetailView(APIView):
    def get_object(self, solicitud_id):
        return SolicitudCotizacion.objects.filter(id=solicitud_id).first()

    def get(self, request, solicitud_id):
        solicitud = self.get_object(solicitud_id)
        if not solicitud:
            return Response({"detail": "No encontrada"}, status=404)
        return Response(SolicitudCotizacionSerializer(solicitud).data)

    def delete(self, request, solicitud_id):
        solicitud = self.get_object(solicitud_id)
        if not solicitud:
            return Response({"detail": "No encontrada"}, status=404)
        if hasattr(solicitud, "cotizacion"):
            return Response({"detail": "No se puede eliminar: ya tiene una cotización"}, status=400)
        solicitud.delete()
        return Response(status=204)
