"""
Endpoints de autenticación: registro de usuarios y login con JWT.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import deps
import models_db
import schemas
from database import get_db
from security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    # Se valida username Y email por separado para poder dar un mensaje claro
    # de cuál de los dos ya está en uso (en vez de dejar que la base de datos
    # rechace el INSERT con un error 500 genérico).
    conditions = [models_db.User.username == payload.username]
    if payload.email:
        conditions.append(models_db.User.email == payload.email)

    existing = db.query(models_db.User).filter(or_(*conditions)).first()
    if existing:
        if existing.username == payload.username:
            raise HTTPException(status_code=400, detail="El nombre de usuario ya existe")
        raise HTTPException(status_code=400, detail="Ese correo electrónico ya está registrado")

    user = models_db.User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Red de seguridad ante una condición de carrera (dos registros
        # simultáneos con el mismo username/email): evita el 500 crudo.
        db.rollback()
        raise HTTPException(
            status_code=400, detail="El nombre de usuario o el correo ya están registrados"
        )
    db.refresh(user)
    return user


@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Login estilo OAuth2 password flow (compatible con Swagger /docs
    y con formularios application/x-www-form-urlencoded desde Django).
    """
    user = db.query(models_db.User).filter(models_db.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.username})
    return schemas.Token(access_token=access_token)


@router.get("/me", response_model=schemas.UserOut)
def read_current_user(current_user: models_db.User = Depends(deps.get_current_user)):
    return current_user
