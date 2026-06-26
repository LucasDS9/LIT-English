"""
Rotas de autenticação: registro de usuário e login.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.models import User, UserRole
from app.schemas import Token, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Cria um novo usuário.
    - Se for professor: aprovado automaticamente.
    - Se for aluno: fica pendente até o professor aprovar manualmente.
    """
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Este e-mail já está cadastrado.")

    new_user = User(
        name=user_in.name,
        email=user_in.email,
        whatsapp=user_in.whatsapp,
        hashed_password=hash_password(user_in.password),
        role=user_in.role,
        is_approved=(user_in.role == UserRole.professor),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Login compatível com o padrão OAuth2 do FastAPI (usa 'username' como e-mail).
    Retorna um token JWT.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos.",
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    return Token(access_token=access_token)


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    """Retorna os dados do usuário logado (útil pro frontend saber quem está logado)."""
    return current_user
