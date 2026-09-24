"""
Vistas de autenticación: registro, login y logout.

Django maneja la sesión del sitio (login por username/password clásico).
Al iniciar sesión, además se obtiene un JWT del backend FastAPI y se
guarda en la sesión de Django (`request.session['fastapi_token']`) para
poder llamar a los endpoints protegidos de reconocimiento facial desde
las vistas de la app `capture`.
"""
from django.contrib import messages
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.shortcuts import redirect, render

from .forms import LoginForm, RegisterForm
from .services import FastAPIError, login_user, register_user


def register_view(request):
    if request.user.is_authenticated:
        return redirect("capture:capture")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            email = form.cleaned_data.get("email", "")
            password = form.cleaned_data["password1"]

            try:
                register_user(username, email, password)
            except FastAPIError as exc:
                messages.error(request, f"No se pudo crear la cuenta: {exc}")
                return render(request, "accounts/register.html", {"form": form})

            user = form.save()
            messages.success(request, "Cuenta creada correctamente. Ahora inicia sesión.")
            return redirect("accounts:login")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("capture:capture")

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()

            try:
                token = login_user(user.username, form.cleaned_data["password"])
                request.session["fastapi_token"] = token
            except FastAPIError as exc:
                messages.warning(
                    request,
                    f"Sesión iniciada, pero el reconocimiento facial no está disponible: {exc}",
                )

            django_login(request, user)
            return redirect("capture:capture")
    else:
        form = LoginForm()

    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
    request.session.pop("fastapi_token", None)
    django_logout(request)
    messages.info(request, "Sesión cerrada correctamente.")
    return redirect("accounts:login")
