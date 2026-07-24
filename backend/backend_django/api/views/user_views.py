from rest_framework.views import APIView
from rest_framework.response import Response
from api.models import User
from api.serializers import UserOutSerializer, UserWriteSerializer
from api.permissions import IsAdmin


class UserListCreateView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response(UserOutSerializer(User.objects.all(), many=True).data)

    def post(self, request):
        ser = UserWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        user = ser.save()
        return Response(UserOutSerializer(user).data, status=201)


class UserDetailView(APIView):
    permission_classes = [IsAdmin]

    def get_object(self, user_id):
        return User.objects.filter(id=user_id).first()

    def patch(self, request, user_id):
        user = self.get_object(user_id)
        if not user:
            return Response({"detail": "No encontrado"}, status=404)
        ser = UserWriteSerializer(user, data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        ser.save()
        return Response(UserOutSerializer(user).data)

    def delete(self, request, user_id):
        user = self.get_object(user_id)
        if not user:
            return Response({"detail": "No encontrado"}, status=404)
        if user.id == request.user.id:
            return Response({"detail": "No puedes eliminar tu propio usuario"}, status=400)
        user.is_active = False
        user.save(update_fields=["is_active"])
        return Response(status=204)
