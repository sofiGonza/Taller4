"""
Esquemas Pydantic: validación de entrada/salida de la API.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, examples=["juan"])
    email: Optional[EmailStr] = Field(None, examples=["juan@example.com"])
    password: str = Field(..., min_length=6, examples=["superclave123"])


class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[EmailStr] = None
    has_face_registered: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


class ImagePayload(BaseModel):
    """
    Imagen capturada desde la cámara del navegador (getUserMedia + canvas),
    enviada como Data URL base64: "data:image/jpeg;base64,/9j/4AAQ...".
    """

    image_base64: str = Field(..., description="Imagen en base64 (con o sin encabezado data:URL)")

    @field_validator("image_base64")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or len(v) < 100:
            raise ValueError("La imagen enviada es demasiado pequeña o está vacía")
        return v


class FaceRegisterResponse(BaseModel):
    detail: str
    total_samples: int
    required_samples: int
    enrollment_complete: bool


class RecognitionResult(BaseModel):
    matched: bool
    username: Optional[str] = None
    confidence: Optional[float] = Field(
        None, description="Distancia LBPH: más bajo = más parecido"
    )
    message: str
