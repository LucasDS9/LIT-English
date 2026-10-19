"""
Rotas de autenticação: registro de usuário e login.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.models import AccessType, User, UserRole
from app.promo import has_valid_format, is_valid_promo_code, normalize_promo_code
from app.schemas import ALLOWED_PLANS, ALLOWED_TARGET_LANGUAGES, Token, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Cria um novo usuário. Há dois tipos de conta de aluno/usuário:

    - Aluno (access_type == padrao): exige código promocional de 5 caracteres
      e continua pendente até o professor aprovar manualmente (como sempre foi).
    - Usuário normal (access_type == especial, o antigo "Acesso Especial"):
      exige idade e língua-alvo (ALLOWED_TARGET_LANGUAGES), escolhe um plano
      (free/premium/pro; padrão free) e entra direto, sem aprovação do
      professor. O código promocional é opcional, mas se vier precisa ser
      válido. Língua nativa fica fixa em "pt".
    - Professor: aprovado automaticamente (sem código nem plano).

    Os códigos válidos são configurados em app/promo.py (variável PROMO_CODES).
    """
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Este e-mail já está cadastrado.")

    is_student = user_in.role == UserRole.aluno
    is_normal_user = is_student and user_in.access_type == AccessType.especial
    promo_code = normalize_promo_code(user_in.promo_code)
    plan = None

    if is_student and not is_normal_user:
        # Aluno: o código é obrigatório.
        if not promo_code:
            raise HTTPException(status_code=400, detail="Informe o código promocional.")
        if not is_valid_promo_code(promo_code):
            raise HTTPException(status_code=400, detail="Código promocional inválido.")

    if is_normal_user:
        if not user_in.target_language:
            raise HTTPException(
                status_code=400,
                detail="Informe a língua que deseja aprender.",
            )
        if user_in.target_language.strip().lower() not in ALLOWED_TARGET_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail="Essa língua ainda não está disponível na plataforma.",
            )
        if user_in.age is None:
            raise HTTPException(
                status_code=400,
                detail="Informe sua idade.",
            )
        plan = (user_in.plan or "free").strip().lower()
        if plan not in ALLOWED_PLANS:
            raise HTTPException(status_code=400, detail="Plano inválido.")
        # Código opcional: se preenchido, precisa estar correto.
        if promo_code and not (has_valid_format(promo_code) and is_valid_promo_code(promo_code)):
            raise HTTPException(status_code=400, detail="Código promocional inválido.")

    new_user = User(
        name=user_in.name,
        email=user_in.email,
        whatsapp=user_in.whatsapp,
        hashed_password=hash_password(user_in.password),
        role=user_in.role,
        # Professor e usuário normal entram direto; aluno aguarda aprovação.
        is_approved=(user_in.role == UserRole.professor or is_normal_user),
        access_type=user_in.access_type,
        # Língua nativa: por enquanto sempre português, sem opção de escolha.
        native_language="pt" if is_normal_user else None,
        target_language=user_in.target_language.strip().lower() if is_normal_user else None,
        age=user_in.age if is_normal_user else None,
        nationality=user_in.nationality or ("Brasileiro" if is_normal_user else None),
        plan=plan,
        promo_code=promo_code or None,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Login único, compatível com o padrão OAuth2 do FastAPI (usa 'username'
    como e-mail). Retorna um token JWT. Serve para qualquer tipo de conta:
    aluno, usuário normal (antigo Acesso Especial) e professor.
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
