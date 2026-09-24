"""
Entrypoint para Vercel Serverless Functions (runtime Python, WSGI).

Vercel expone la variable `app`, que debe ser un callable WSGI. Django ya
provee uno en config.wsgi.application; aquí solo ajustamos sys.path y las
variables de entorno necesarias antes de importar el proyecto.
"""
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.wsgi import application as app  # noqa: E402
