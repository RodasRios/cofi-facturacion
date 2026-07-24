import logging
from pathlib import Path
from django.conf import settings
from django.http import FileResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from api.models import Cliente
from api.serializers import ClienteSerializer
from services.pdf_service import generate_vinculacion

logger = logging.getLogger(__name__)


def _numero_vinculacion():
    count = Cliente.objects.exclude(numero_vinculacion__isnull=True).count()
    return f"VIN-{count + 1:04d}"


def _generar_pdf(cliente):
    pdf_dir = settings.GENERATED_PDF_DIR
    pdf_path = pdf_dir / f"VIN_{cliente.id}_{cliente.numero_vinculacion.replace('-', '_')}.pdf"
    try:
        generate_vinculacion(
            pdf_path, cliente.numero_vinculacion, cliente.created_at.date(),
            {
                "nombre": cliente.nombre, "nit": cliente.nit,
                "telefono": cliente.telefono, "email": cliente.email, "direccion": cliente.direccion,
            },
        )
        cliente.pdf_path = str(pdf_path)
        cliente.save(update_fields=["pdf_path"])
    except Exception as e:
        logger.error("Error generando PDF de vinculación %s: %s", cliente.numero_vinculacion, e)


class ClienteListCreateView(APIView):
    def get(self, request):
        clientes = Cliente.objects.all()
        q = request.query_params.get("q")
        if q:
            clientes = clientes.filter(nombre__icontains=q)
        return Response(ClienteSerializer(clientes, many=True).data)

    def post(self, request):
        ser = ClienteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        cliente = ser.save(creado_por=request.user, numero_vinculacion=_numero_vinculacion())
        _generar_pdf(cliente)
        cliente.refresh_from_db()
        return Response(ClienteSerializer(cliente).data, status=201)


class ClienteDetailView(APIView):
    def get_object(self, cliente_id):
        return Cliente.objects.filter(id=cliente_id).first()

    def get(self, request, cliente_id):
        cliente = self.get_object(cliente_id)
        if not cliente:
            return Response({"detail": "No encontrado"}, status=404)
        return Response(ClienteSerializer(cliente).data)

    def patch(self, request, cliente_id):
        cliente = self.get_object(cliente_id)
        if not cliente:
            return Response({"detail": "No encontrado"}, status=404)
        ser = ClienteSerializer(cliente, data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        ser.save()
        return Response(ser.data)


class ClientePdfView(APIView):
    def get(self, request, cliente_id):
        cliente = Cliente.objects.filter(id=cliente_id).first()
        if not cliente or not cliente.pdf_path:
            return Response({"detail": "PDF no disponible"}, status=404)
        path = Path(cliente.pdf_path)
        if not path.exists():
            return Response({"detail": "Archivo no encontrado"}, status=404)
        return FileResponse(path.open("rb"), content_type="application/pdf", as_attachment=True, filename=f"{cliente.numero_vinculacion}.pdf")
