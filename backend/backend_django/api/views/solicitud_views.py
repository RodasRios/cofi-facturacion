from rest_framework.views import APIView
from rest_framework.response import Response
from api.permissions import Requiere
from api.numeracion import siguiente
from django.db import transaction
from api.models import SolicitudCotizacion, SolicitudCotizacionItem, Cliente, Material, Seguimiento
from api.serializers import SolicitudCotizacionSerializer


def _numero_solicitud():
    return siguiente(SolicitudCotizacion, "SC-")


class SolicitudCotizacionListCreateView(APIView):
    permission_classes = [Requiere(("solicitudes", "cotizaciones", "tablero"), ("solicitudes",))]
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
            obra=(d.get("obra") or "").strip() or None,
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
    permission_classes = [Requiere(("solicitudes", "cotizaciones", "tablero"), ("solicitudes",))]
    def get_object(self, solicitud_id):
        return SolicitudCotizacion.objects.filter(id=solicitud_id).first()

    def get(self, request, solicitud_id):
        solicitud = self.get_object(solicitud_id)
        if not solicitud:
            return Response({"detail": "No encontrada"}, status=404)
        return Response(SolicitudCotizacionSerializer(solicitud).data)

    def patch(self, request, solicitud_id):
        """Corregir cliente, obra, notas o materiales mientras nadie la haya cotizado
        (o sus cotizaciones estén rechazadas)."""
        solicitud = self.get_object(solicitud_id)
        if not solicitud:
            return Response({"detail": "No encontrada"}, status=404)
        vigente = solicitud.cotizacion_vigente
        if vigente:
            return Response({
                "detail": f"Ya tiene la cotización {vigente.numero}. Edita o elimina la cotización primero.",
            }, status=400)
        d = request.data
        if "cliente" in d:
            cliente = Cliente.objects.filter(id=d.get("cliente")).first()
            if not cliente:
                return Response({"detail": "Cliente no encontrado"}, status=404)
            solicitud.cliente = cliente
        if "obra" in d:
            solicitud.obra = (d.get("obra") or "").strip() or None
        if "notas" in d:
            solicitud.notas = (d.get("notas") or "").strip() or None
        items = None
        if "items" in d:
            items = [it for it in (d.get("items") or []) if it.get("material") and float(it.get("cantidad") or 0) > 0]
            if not items:
                return Response({"detail": "La solicitud debe tener al menos un material"}, status=400)
        with transaction.atomic():
            solicitud.save()
            if items is not None:
                solicitud.items.all().delete()
                for it in items:
                    material = Material.objects.filter(id=it["material"]).first()
                    if material:
                        SolicitudCotizacionItem.objects.create(solicitud=solicitud, material=material, cantidad=it["cantidad"])
        Seguimiento.objects.create(solicitud=solicitud, tipo="nota", usuario=request.user,
                                   texto=f"Solicitud {solicitud.numero} editada.")
        solicitud.refresh_from_db()
        return Response(SolicitudCotizacionSerializer(solicitud).data)

    def delete(self, request, solicitud_id):
        """Solo sin cotización viva: con una rechazada, se borra junto con ella."""
        solicitud = self.get_object(solicitud_id)
        if not solicitud:
            return Response({"detail": "No encontrada"}, status=404)
        vigente = solicitud.cotizacion_vigente
        if vigente:
            return Response({
                "detail": f"No se puede eliminar: tiene la cotización {vigente.numero}. Elimínala primero.",
            }, status=400)
        solicitud.delete()
        return Response(status=204)
