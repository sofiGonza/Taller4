# Sistema de Login Biométrico — Django + FastAPI

Proyecto compuesto por dos aplicaciones independientes que se comunican por HTTP:

- **`backend/`** — API en **FastAPI** que expone autenticación por JWT y reconocimiento
  facial (detección con Haar Cascade + reconocimiento con LBPH, ambos de OpenCV).
  Documentación interactiva automática en `/docs` (Swagger).
- **`frontend/`** — Sitio **Django** con vistas, plantillas HTML5 y JavaScript que
  captura video de la cámara del usuario (`getUserMedia`), lo envía al backend y
  muestra el resultado.

## Estructura del proyecto

```
fastapi_taller4/
├── render.yaml                      # Blueprint de Render (raíz del repo)
├── README.md
├── backend/                         # API FastAPI (Python, Pydantic, OpenCV, JWT)
│   ├── Dockerfile                   # Imagen python:3.12-slim + libs de OpenCV
│   ├── requirements.txt
│   ├── main.py                      # App FastAPI, CORS y healthcheck (/)
│   ├── config.py                    # Configuración central (variables de entorno)
│   ├── database.py                  # Motor y sesión de SQLAlchemy
│   ├── models_db.py                 # Modelos de la base de datos
│   ├── schemas.py                   # Schemas Pydantic
│   ├── deps.py                      # Dependencias (usuario autenticado por JWT)
│   ├── security.py                  # Hash y verificación de contraseñas
│   ├── face_service.py              # Detección Haar Cascade + reconocimiento LBPH
│   ├── routers/
│   │   ├── auth.py                  # POST /auth/register · /auth/login · GET /auth/me
│   │   └── face.py                  # POST /face/register · /face/recognize
│   ├── data/faces/                  # Fotos de referencia (efímeras en Render free)
│   ├── models_store/                # Modelo LBPH entrenado (efímero)
│   ├── api/index.py                 # Entrypoint legacy para Vercel (no usado con Docker)
│   ├── runtime.txt                  # Fija Python 3.12
│   └── .env.example
└── frontend/                        # Sitio Django (vistas, plantillas, JS de cámara)
    ├── manage.py
    ├── requirements.txt
    ├── vercel.json                  # Despliegue en Vercel (WSGI + collectstatic)
    ├── api/index.py                 # Entrypoint WSGI para Vercel
    ├── config/
    │   ├── settings.py              # Configuración Django (Postgres vía DATABASE_URL)
    │   ├── urls.py
    │   ├── asgi.py
    │   └── wsgi.py
    ├── accounts/                    # Registro y login (Django + sincronización FastAPI)
    │   ├── views.py · services.py · forms.py · urls.py
    │   └── templates/accounts/
    ├── capture/                     # Captura de cámara y verificación facial
    │   ├── views.py · services.py · urls.py
    │   ├── static/capture/js/camera.js
    │   └── templates/capture/
    ├── templates/base.html
    ├── static/css/main.css
    ├── staticfiles/                 # Estáticos recolectados (whitenoise, versionados)
    └── .env.example
```

## Enlaces del proyecto (producción)

| Aplicación | URL |
|---|---|
| **Frontend** (Sitio Django · Vercel) | https://taller4-jtnw.vercel.app/ |
| **Backend** (API FastAPI · Render) | https://taller4-api.onrender.com |
| Swagger del backend (`/docs`) | https://taller4-api.onrender.com/docs |

## Cómo funciona el reconocimiento facial

Se usa OpenCV en vez de librerías basadas en `dlib` (como `face_recognition`)
porque estas últimas requieren compilar dependencias pesadas que suelen fallar
al desplegar en entornos serverless como Vercel. El enfoque usado es real
reconocimiento facial, no una simulación:

1. **Detección**: Haar Cascade (`haarcascade_frontalface_default.xml`, incluido con OpenCV)
   localiza el rostro dentro de la imagen capturada.
2. **Entrenamiento**: cada vez que un usuario registra una foto de referencia
   (`POST /face/register`), se guarda el recorte de su rostro y se reentrena un
   modelo **LBPH** (`cv2.face.LBPHFaceRecognizer_create`) con todas las muestras
   de todos los usuarios.
3. **Reconocimiento**: al capturar una nueva foto (`POST /face/recognize`), se
   detecta el rostro y se compara contra el modelo entrenado. Si la distancia
   (confianza) es menor al umbral configurado (`LBPH_CONFIDENCE_THRESHOLD`,
   por defecto 60), se considera una coincidencia.

Se recomienda registrar 3-5 fotos por usuario (distintos ángulos/gestos) para
mejorar la precisión.

## 1. Backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # ajusta SECRET_KEY, etc.
uvicorn main:app --reload --port 8001
```

- Swagger interactivo: http://127.0.0.1:8001/docs
- Endpoints principales:
  - `POST /auth/register` — crea un usuario (`username`, `email`, `password`)
  - `POST /auth/login` — devuelve un JWT (`access_token`)
  - `GET  /auth/me` — datos del usuario autenticado (requiere `Authorization: Bearer <token>`)
  - `POST /face/register` — guarda una foto de referencia del usuario autenticado
  - `POST /face/recognize` — compara una foto contra los rostros registrados (público)

## 2. Frontend (Django)

```bash
cd frontend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # ajusta FASTAPI_BASE_URL si es necesario
python manage.py migrate
python manage.py runserver 8000
```

- Sitio: http://127.0.0.1:8000
- Flujo: `Registrarse` → `Iniciar sesión` → página de captura de cámara con
  botones **"Registrar mi rostro"** y **"Reconocer rostro"**.

## 3. Autenticación

- **Django** usa su sistema de sesiones estándar (`django.contrib.auth`) para
  proteger las vistas del sitio (`@login_required`).
- **FastAPI** usa JWT (`python-jose` + `passlib`/bcrypt) para proteger sus
  propios endpoints. Al iniciar sesión en Django, este también hace login
  contra FastAPI y guarda el `access_token` en `request.session`, que luego
  se envía como `Authorization: Bearer` al llamar `/face/register`.

Ambos sistemas están desacoplados a propósito: la API puede consumirse desde
cualquier otro cliente (una app móvil, Swagger, etc.) sin depender de Django.

## 4. Despliegue

El proyecto está desplegado en producción:

| Aplicación | URL | Plataforma |
|---|---|---|
| **Frontend** (Django) | https://taller4-jtnw.vercel.app/ | Vercel |
| **Backend** (API FastAPI) | https://taller4-api.onrender.com | Render |
| Swagger del backend (`/docs`) | https://taller4-api.onrender.com/docs | Render |

- El **backend** corre en Render con Docker (`python:3.12-slim`, libs de OpenCV
  instaladas en la imagen; config en `render.yaml` + `backend/Dockerfile`).
- El **frontend** corre en Vercel (WSGI vía `frontend/api/index.py` + whitenoise
  para los estáticos) y usa un **Postgres externo** (Neon) para persistir
  usuarios y sesiones de Django.
- Nota (plan gratuito): Render duerme la instancia tras ~15 min sin tráfico
  (primer request lento) y su disco es efímero: fotos de rostro y modelo LBPH
  se pierden si la instancia se recicla. Aceptable para demo.

## 5. Pruebas realizadas

Registro e inicio de sesión (Django + FastAPI sincronizados, JWT emitido),
registro de una foto de referencia con detección de rostro real (OpenCV),
reconocimiento facial exitoso, y manejo de errores (imagen sin rostro, sin
coincidencia registrada, backend no disponible).
