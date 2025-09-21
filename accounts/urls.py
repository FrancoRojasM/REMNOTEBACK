from django.urls import path
from .views import RegisterView, LoginView, MeView, RefreshView,ChangePasswordView,PasswordResetRequestView,PasswordResetConfirmView

urlpatterns = [
    path("register", RegisterView.as_view(), name="register"),
    path("login", LoginView.as_view(), name="login"),
    path("refresh", RefreshView.as_view(), name="token_refresh"),
    path("me", MeView.as_view(), name="me"),
    
    path("change-password",      ChangePasswordView.as_view(), name="change_password"),
    path("password/reset",       PasswordResetRequestView.as_view(), name="password_reset"),
    path("password/reset/confirm", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
]
