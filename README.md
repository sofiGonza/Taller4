# Sistema de Login Biométrico — Django + FastAPI

Proyecto compuesto por dos aplicaciones independientes que se comunican por HTTP:

- **`backend/`** — API en **FastAPI** que expone autenticación por JWT y reconocimiento
  facial (detección con Haar Cascade + reconocimiento con LBPH, ambos de OpenCV).
  Documentación interactiva automática en `/docs` (Swagger).
- **`frontend/`** — Sitio **Django** con vistas, plantillas HTML5 y JavaScript que
  captura video de la cámara del usuario (`getUserMedia`), lo envía al backend y
  muestra el resultado.

```
fastapi_taller4/
├── backend/     # API FastAPI (Python, Pydantic, OpenCV, JWT)
└── frontend/    # Sitio Django (vistas, plantillas, JS de cámara)
```

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
   por defecto 80), se considera una coincidencia.

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
  botones **"Registrar mi rostro"** y **"Reconocer rostro"`.

> Importante: levanta primero el backend (puerto 8001) y luego el frontend
> (puerto 8000); el registro y el login de Django llaman al backend para
> crear el usuario también en la API y obtener su JWT.

## 3. Autenticación

- **Django** usa su sistema de sesiones estándar (`django.contrib.auth`) para
  proteger las vistas del sitio (`@login_required`).
- **FastAPI** usa JWT (`python-jose` + `passlib`/bcrypt) para proteger sus
  propios endpoints. Al iniciar sesión en Django, este también hace login
  contra FastAPI y guarda el `access_token` en `request.session`, que luego
  se envía como `Authorization: Bearer` al llamar `/face/register`.

Ambos sistemas están desacoplados a propósito: la API puede consumirse desde
cualquier otro cliente (una app móvil, Swagger, etc.) sin depender de Django.

## 4. Despliegue en Vercel

Cada aplicación se despliega como un **proyecto de Vercel independiente**
(dos proyectos, dos dominios), cada uno con su propio `vercel.json`:

### Backend
```bash
cd backend
vercel --prod
```
Configura en el dashboard de Vercel las variables de entorno de `.env.example`
(`SECRET_KEY`, `DATABASE_URL`, etc.).

**Limitaciones a tener en cuenta:**
- El filesystem de una función serverless es de solo lectura salvo `/tmp`, y
  cada invocación puede correr en una instancia distinta. Esto significa que
  las fotos de referencia y el modelo LBPH entrenado (carpetas `data/` y
  `models_store/`) **no persisten de forma confiable entre invocaciones** en
  producción. Para un despliegue real conviene:
  - mover la base de datos a un servicio externo (Postgres, Turso, etc.) vía `DATABASE_URL`, y
  - subir las muestras de rostro y el modelo entrenado a un storage externo
    (S3, Vercel Blob, etc.) en lugar del filesystem local.
  - Alternativamente, desplegar el backend en un servicio con filesystem
    persistente (Render, Railway, un VPS) y dejar solo el frontend en Vercel.
- El paquete `opencv-contrib-python-headless` es voluminoso; si el tamaño del
  build supera el límite de Vercel, considera separar el backend a otro
  proveedor.

### Frontend
```bash
cd frontend
python manage.py collectstatic --noinput   # genera staticfiles/ (servido por whitenoise)
vercel --prod
```
Configura `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS` y,
sobre todo, `FASTAPI_BASE_URL` apuntando a la URL pública del backend ya
desplegado.

## 5. Pruebas realizadas

Antes de entregar este esqueleto se verificó, de punta a punta, con un
servidor FastAPI real y el test client de Django:

- Registro e inicio de sesión (Django + FastAPI sincronizados, JWT emitido).
- Registro de una foto de referencia con detección de rostro real (OpenCV).
- Reconocimiento facial exitoso contra el usuario registrado.
- Manejo de errores: imagen sin rostro (`422`), sin coincidencia registrada,
  backend no disponible.

## Próximos pasos sugeridos

- Agregar límite de intentos / rate limiting al login y al reconocimiento.
- Servir los archivos de datos biométricos desde un storage externo antes de
  desplegar a producción.
- Agregar tests automatizados (`pytest` para el backend, `pytest-django` o
  `unittest` para el frontend).
- Mostrar en la interfaz un recuadro sobre el rostro detectado (dibujando el
  bounding box que ya calcula `face_service.extract_face`).
