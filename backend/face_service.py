"""
Servicio de reconocimiento facial.

Implementación con OpenCV (detección Haar Cascade + reconocedor LBPH):
  - No requiere compilar dlib (a diferencia de la librería `face_recognition`),
    lo que la hace mucho más portable para instalar en distintos entornos,
    incluyendo funciones serverless.
  - Sigue siendo reconocimiento facial real (no un mock): cada usuario
    entrena el modelo con sus propias fotos de referencia y luego se predice
    contra ese modelo entrenado.

Nota sobre rutas con tildes/ñ en Windows:
    El código nativo (C++) de OpenCV para abrir archivos en Windows falla
    silenciosamente cuando la ruta contiene caracteres acentuados (por
    ejemplo, una carpeta de usuario como "C:\\Users\\José\\..."): no lanza
    una excepción, simplemente no lee/escribe nada. Para evitarlo, este
    módulo nunca deja que OpenCV abra un archivo directamente en una ruta
    que pueda tener esos caracteres:
      - Las fotos de muestra se codifican/decodifican en memoria
        (`cv2.imencode`/`cv2.imdecode`) y el archivo en disco lo escribe y
        lee Python puro (`Path.write_bytes`/`read_bytes`), que sí soporta
        rutas Unicode en Windows sin problema.
      - El modelo LBPH entrenado (`recognizer.write`/`.read`) solo acepta
        una ruta de archivo, así que se usa una carpeta temporal sin
        caracteres especiales como intermediaria: OpenCV lee/escribe ahí,
        y Python mueve los bytes entre esa carpeta temporal y la ubicación
        real del proyecto.

Flujo:
  1. `register_face(user_id, image_bytes)` guarda la foto recortada del
     rostro del usuario y reentrena el modelo global LBPH con todas las
     muestras existentes.
  2. `recognize_face(image_bytes)` detecta el rostro en la imagen recibida
     y lo compara contra el modelo entrenado, devolviendo el usuario más
     parecido (o "sin coincidencia" si la confianza no supera el umbral).
"""
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from config import FACE_SIZE, FACES_DIR, LABELS_PATH, LBPH_CONFIDENCE_THRESHOLD, MODEL_PATH


def _load_face_cascade() -> cv2.CascadeClassifier:
    """Carga el Haar Cascade leyendo el XML con Python y entregándoselo a
    OpenCV ya en memoria (ver nota del módulo sobre rutas con tildes)."""
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

    try:
        xml_data = Path(cascade_path).read_text(encoding="utf-8")
        fs = cv2.FileStorage(xml_data, cv2.FILE_STORAGE_READ | cv2.FILE_STORAGE_MEMORY)
        cascade = cv2.CascadeClassifier()
        cascade.read(fs.getFirstTopLevelNode())
    except Exception:
        cascade = cv2.CascadeClassifier()

    if cascade.empty():
        # Último intento: la forma "normal" de cargarlo directamente por
        # ruta (funciona en Linux/Mac y en Windows sin caracteres especiales).
        cascade = cv2.CascadeClassifier(cascade_path)

    if cascade.empty():
        raise RuntimeError(
            "No se pudo cargar el Haar Cascade de detección facial desde "
            f"'{cascade_path}' (ni por ruta directa ni cargándolo en memoria). "
            "Verifica la versión instalada de OpenCV (cv2.__version__) y su "
            "compatibilidad con cv2.data.haarcascades."
        )
    return cascade


_face_cascade = _load_face_cascade()


class NoFaceDetectedError(Exception):
    """No se detectó ningún rostro en la imagen enviada."""


def _ensure_dirs() -> None:
    FACES_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)


def _ascii_safe_tempdir() -> Path:
    """
    Busca una carpeta temporal cuya ruta completa no tenga caracteres fuera
    de ASCII, para que OpenCV pueda leer/escribir ahí sin problema. Se
    prueba primero C:\\Windows\\Temp (típicamente sin tildes en cualquier
    perfil de usuario) y se cae de vuelta al temp del sistema si hace falta.
    """
    candidates = []
    if os.name == "nt":
        windir = os.environ.get("SystemRoot", r"C:\Windows")
        candidates.append(Path(windir) / "Temp")
    candidates.append(Path(tempfile.gettempdir()))

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            str(candidate).encode("ascii")
            probe = candidate / f".probe_{uuid.uuid4().hex}"
            probe.write_bytes(b"x")
            probe.unlink()
            return candidate
        except Exception:
            continue

    # Último recurso: puede que siga fallando en Windows con tildes, pero
    # es mejor que no tener ninguna carpeta.
    return Path(tempfile.gettempdir())


def decode_image(image_bytes: bytes) -> np.ndarray:
    """Convierte bytes (jpg/png) en una imagen en escala de grises (numpy array)."""
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("No se pudo decodificar la imagen recibida")
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def extract_face(gray_image: np.ndarray) -> np.ndarray:
    """
    Detecta el rostro más grande de la imagen, lo recorta y lo normaliza
    al tamaño FACE_SIZE. Lanza NoFaceDetectedError si no encuentra ninguno.
    """
    faces = _face_cascade.detectMultiScale(
        gray_image, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
    )
    if len(faces) == 0:
        raise NoFaceDetectedError("No se detectó ningún rostro en la imagen")

    # Si hay varios rostros, usa el más grande (más cercano a la cámara).
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    face = gray_image[y : y + h, x : x + w]
    face = cv2.resize(face, FACE_SIZE)
    face = cv2.equalizeHist(face)  # normaliza el contraste/iluminación
    return face


def _save_face_image(path: Path, face: np.ndarray) -> None:
    """Guarda una imagen (array de OpenCV) en disco sin pasarle la ruta a
    OpenCV: se codifica en memoria y se escribe con Python puro."""
    ok, buf = cv2.imencode(".png", face)
    if not ok:
        raise ValueError("No se pudo codificar la imagen del rostro")
    path.write_bytes(buf.tobytes())


def _load_face_image(path: Path) -> Optional[np.ndarray]:
    """Lee una imagen guardada con `_save_face_image` (ver nota de arriba)."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    array = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(array, cv2.IMREAD_GRAYSCALE)


def _write_model(recognizer: "cv2.face_LBPHFaceRecognizer", path: Path) -> None:
    """Guarda el modelo LBPH entrenado en `path`, pasando por una carpeta
    temporal sin tildes porque `recognizer.write()` solo acepta una ruta
    (no se le puede dar el contenido ya en memoria)."""
    tmp_path = _ascii_safe_tempdir() / f"lbph_{uuid.uuid4().hex}.yml"
    try:
        recognizer.write(str(tmp_path))
        path.write_bytes(tmp_path.read_bytes())
    finally:
        tmp_path.unlink(missing_ok=True)


def _read_model(recognizer: "cv2.face_LBPHFaceRecognizer", path: Path) -> None:
    """Carga un modelo LBPH guardado con `_write_model` (ver nota de arriba)."""
    tmp_path = _ascii_safe_tempdir() / f"lbph_{uuid.uuid4().hex}.yml"
    try:
        tmp_path.write_bytes(path.read_bytes())
        recognizer.read(str(tmp_path))
    finally:
        tmp_path.unlink(missing_ok=True)


def _load_labels() -> dict:
    if LABELS_PATH.exists():
        return json.loads(LABELS_PATH.read_text())
    return {}


def _save_labels(labels: dict) -> None:
    LABELS_PATH.write_text(json.dumps(labels, indent=2))


def register_face(user_id: int, username: str, image_bytes: bytes) -> int:
    """
    Guarda una nueva muestra de rostro para el usuario y reentrena el
    modelo LBPH con todas las muestras disponibles.

    Devuelve el número total de muestras que tiene el usuario tras guardar.
    """
    _ensure_dirs()

    gray = decode_image(image_bytes)
    face = extract_face(gray)

    user_dir = FACES_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    existing = list(user_dir.glob("*.png"))
    sample_path = user_dir / f"{len(existing) + 1}.png"
    _save_face_image(sample_path, face)

    if not sample_path.exists() or sample_path.stat().st_size == 0:
        raise RuntimeError(
            f"La foto de referencia no se guardó en disco ('{sample_path}'). "
            "Revisa permisos de escritura en esa carpeta."
        )

    _retrain_model()
    return len(existing) + 1


def _retrain_model() -> None:
    """Reentrena el reconocedor LBPH con todas las muestras guardadas en disco."""
    recognizer = cv2.face.LBPHFaceRecognizer_create()

    images = []
    labels = []
    label_map: dict[str, int] = {}
    next_label = 0

    for user_dir in sorted(FACES_DIR.glob("*")):
        if not user_dir.is_dir():
            continue
        user_id = user_dir.name
        label_map[str(next_label)] = user_id
        for sample_path in user_dir.glob("*.png"):
            img = _load_face_image(sample_path)
            if img is None:
                continue
            images.append(img)
            labels.append(next_label)
        next_label += 1

    if not images:
        return

    recognizer.train(images, np.array(labels))
    _write_model(recognizer, MODEL_PATH)
    _save_labels(label_map)


def recognize_face(image_bytes: bytes) -> tuple[Optional[str], Optional[float]]:
    """
    Detecta el rostro en la imagen y lo compara contra el modelo entrenado.

    Devuelve (user_id, confidence) si hay coincidencia por debajo del
    umbral configurado, o (None, confidence) si no hay match / no hay
    modelo entrenado todavía.
    """
    if not MODEL_PATH.exists() or MODEL_PATH.stat().st_size == 0:
        return None, None

    gray = decode_image(image_bytes)
    face = extract_face(gray)

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    _read_model(recognizer, MODEL_PATH)
    label_map = _load_labels()

    label, confidence = recognizer.predict(face)
    if confidence > LBPH_CONFIDENCE_THRESHOLD:
        return None, confidence

    user_id = label_map.get(str(label))
    return user_id, confidence
