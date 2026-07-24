from pathlib import Path
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from api.models import Cliente
from api.serializers import ClienteSerializer


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
        ser.save(creado_por=request.user)
        return Response(ser.data, status=201)


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


class ClienteVinculacionView(APIView):
    """Sube el formato de vinculación firmado por un cliente nuevo y lo marca como vinculado."""
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, cliente_id):
        cliente = Cliente.objects.filter(id=cliente_id).first()
        if not cliente:
            return Response({"detail": "No encontrado"}, status=404)
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "No se envió archivo"}, status=400)
        ext = Path(file.name).suffix.lower()
        if ext not in [".pdf", ".png", ".jpg", ".jpeg"]:
            return Response({"detail": "Solo PDF, PNG o JPG"}, status=400)

        dest_dir = settings.UPLOAD_DIR / "vinculacion"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"vinculacion_cliente_{cliente.id}{ext}"
        with dest.open("wb") as f:
            for chunk in file.chunks():
                f.write(chunk)

        cliente.documento_vinculacion_path = str(dest)
        cliente.vinculado = True
        cliente.save(update_fields=["documento_vinculacion_path", "vinculado"])
        return Response(ClienteSerializer(cliente).data)
