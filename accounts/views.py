from django.contrib.auth.models import User
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.conf import settings
from django.contrib.auth import authenticate
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.utils import extend_schema, OpenApiExample
from .serializers import RegisterSerializer, UserSerializer
from .serializers import ChangePasswordSerializer
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from rest_framework import permissions, status
from .serializers import PasswordResetRequestSerializer, PasswordResetConfirmSerializer, ChangePasswordSerializer

token_generator = PasswordResetTokenGenerator()


class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    @extend_schema(tags=["Auth"], request=RegisterSerializer, responses={201: UserSerializer})
    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()  # 👉 usa el create del serializer
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Auth"],
        examples=[OpenApiExample("Ejemplo login", value={"email": "jane@acme.com", "password": "Demo12345!"}, request_only=True)],
    )
    def post(self, request):
        email = (request.data.get("email") or "").lower().strip()
        password = request.data.get("password") or ""
        user = None
        if email:
            try:
                u = User.objects.get(email__iexact=email)
                user = authenticate(username=u.username, password=password)
            except User.DoesNotExist:
                user = None
        if not user:
            return Response({"detail": "Credenciales inválidas."}, status=400)

        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data
        })

class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    def get_object(self):
        return self.request.user

class RefreshView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    @extend_schema(tags=["Auth"], request=ChangePasswordSerializer, responses={204: None, 403: None})
    def post(self, request):
        ser = ChangePasswordSerializer(data=request.data); ser.is_valid(raise_exception=True)
        if not request.user.check_password(ser.validated_data["current_password"]):
            return Response({"detail": "La contraseña actual no es correcta."}, status=403)
        request.user.set_password(ser.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return Response(status=204)

class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    @extend_schema(tags=["Auth"], request=PasswordResetRequestSerializer, responses={200: None})
    def post(self, request):
        ser = PasswordResetRequestSerializer(data=request.data); ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # No revelar existencia del email
            return Response(status=200)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = token_generator.make_token(user)
        reset_url = f'{getattr(settings, "FRONTEND_URL", "http://localhost:3000")}/reset-password?uid={uid}&token={token}'

        send_mail(
            subject="Restablecer tu contraseña",
            message=f"Para restablecer tu contraseña, abre: {reset_url}",
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@remnote.local"),
            recipient_list=[email],
            fail_silently=True,
        )

        # Conveniencia en DEV: devolver el link para probar rápido
        if settings.DEBUG:
            return Response({"reset_url": reset_url}, status=200)
        return Response(status=200)

class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    @extend_schema(tags=["Auth"], request=PasswordResetConfirmSerializer, responses={204: None, 400: None})
    def post(self, request):
        ser = PasswordResetConfirmSerializer(data=request.data); ser.is_valid(raise_exception=True)
        try:
            uid = urlsafe_base64_decode(ser.validated_data["uid"]).decode("utf-8")
            user = User.objects.get(pk=uid)
        except Exception:
            return Response({"detail":"Link inválido"}, status=400)
        token = ser.validated_data["token"]
        if not token_generator.check_token(user, token):
            return Response({"detail":"Token inválido o expirado"}, status=400)
        user.set_password(ser.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response(status=204)