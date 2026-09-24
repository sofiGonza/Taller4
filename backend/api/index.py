"""
Entrypoint para Vercel Serverless Functions (runtime Python, ASGI).

Vercel detecta este archivo (api/index.py) y expone la variable `app`
como función serverless. Todas las rutas definidas en main.py quedan
disponibles bajo el dominio del deployment, p.ej.:
    https://tu-proyecto.vercel.app/docs
    https://tu-proyecto.vercel.app/auth/login
"""
import sys
from pathlib import Path

# Permite importar los módulos del backend (main, config, etc.) que están
# un nivel arriba de esta carpeta api/.
sys.path.append(str(Path(__file__).resolve().parent.parent))

from main import app  # noqa: E402  (import después de ajustar sys.path)

# Vercel busca una variable llamada `app` (o `handler`) en este módulo.
