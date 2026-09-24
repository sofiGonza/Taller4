"""
Modelos de base de datos (SQLAlchemy).
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(150), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    has_face_registered = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    face_samples = relationship(
        "FaceSample", back_populates="user", cascade="all, delete-orphan"
    )


class FaceSample(Base):
    """
    Registra cada foto de referencia usada para entrenar el modelo LBPH
    de un usuario (se guardan varias por robustez).
    """

    __tablename__ = "face_samples"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    image_path = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="face_samples")
