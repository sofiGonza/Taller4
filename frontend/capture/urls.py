from django.urls import path

from . import views

app_name = "capture"

urlpatterns = [
    path("", views.capture_view, name="capture"),
    path("api/register-face/", views.register_face_view, name="register_face"),
    path("api/recognize-face/", views.recognize_face_view, name="recognize_face"),
]
