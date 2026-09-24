"""
Endpoints de reconocimiento facial.
"""
import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import deps
import face_service
import models_db
import schemas
from config import MIN_FACE_SAMPLES
from database import get_db

router = APIRouter(prefix="/face", tags=["face"])


def _decode_data_url(image_base64: str) -> bytes:
    """Acepta tanto un Data URL completo ("data:image/jpeg;base64,...") como
    un string base64 "pelado"."""
    if "," in image_base64 and image_base64.strip().lower().startswith("data:"):
        image_base64 = image_base64.split(",", 1)[1]
    try:
        return base64.b64decode(image_base64)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Base64 inválido") from exc


@router.post("/register", response_model=schemas.FaceRegisterResponse)
def register_face(
    payload: schemas.ImagePayload,
    db: Session = Depends(get_db),
    current_user: models_db.User = Depends(deps.get_current_user),
):
    """
    Registra una foto de referencia del rostro del usuario autenticado.

    Se piden varias fotos (MIN_FACE_SAMPLES, por defecto 3) en ángulos o
    gestos distintos antes de dar por completado el registro: con una sola
    foto, LBPH tiene muy poca información para distinguir ese rostro de
    otro cualquiera, lo que produce falsos positivos al verificar.

    Por seguridad, una vez que se junta ese mínimo de fotos la cuenta no
    puede volver a registrar su rostro (evita que alguien con una sesión
    ya iniciada reemplace el rostro registrado por el suyo).
    """
    if current_user.has_face_registered:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya tienes un rostro registrado en el sistema. Por seguridad, no es posible volver a registrarlo.",
        )

    image_bytes = _decode_data_url(payload.image_base64)

    try:
        total_samples = face_service.register_face(
            user_id=current_user.id, username=current_user.username, image_bytes=image_bytes
        )
    except face_service.NoFaceDetectedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.add(models_db.FaceSample(user_id=current_user.id, image_path=f"user_{current_user.id}"))

    enrollment_complete = total_samples >= MIN_FACE_SAMPLES
    if enrollment_complete:
        current_user.has_face_registered = True
    db.commit()

    if enrollment_complete:
        detail = "Registro de rostro completado correctamente."
    else:
        faltan = MIN_FACE_SAMPLES - total_samples
        detail = f"Muestra {total_samples}/{MIN_FACE_SAMPLES} guardada. Toma {faltan} foto(s) más, en un ángulo o gesto distinto."

    return schemas.FaceRegisterResponse(
        detail=detail,
        total_samples=total_samples,
        required_samples=MIN_FACE_SAMPLES,
        enrollment_complete=enrollment_complete,
    )


@router.post("/recognize", response_model=schemas.RecognitionResult)
def recognize_face(payload: schemas.ImagePayload, db: Session = Depends(get_db)):
    """
    Recibe una foto capturada por la cámara y la compara contra los
    rostros registrados. No requiere autenticación: es el endpoint que
    usaría, por ejemplo, un flujo de "login con tu cara".
    """
    image_bytes = _decode_data_url(payload.image_base64)

    try:
        user_id, confidence = face_service.recognize_face(image_bytes)
    except face_service.NoFaceDetectedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if user_id is None:
        return schemas.RecognitionResult(
            matched=False,
            confidence=confidence,
            message="No se encontró ninguna coincidencia registrada",
        )

    user = db.query(models_db.User).filter(models_db.User.id == int(user_id)).first()
    if user is None:
        return schemas.RecognitionResult(
            matched=False, confidence=confidence, message="Usuario asociado ya no existe"
        )

    return schemas.RecognitionResult(
        matched=True,
        username=user.username,
        confidence=confidence,
        message=f"Bienvenido/a, {user.username}",
    )
