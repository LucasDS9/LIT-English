"""
Rotas administrativas, acessíveis apenas pelo professor:
- listar alunos
- aprovar acesso de um aluno
- revogar/bloquear acesso de um aluno
- excluir aluno
"""
import base64
import hashlib
import secrets
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_professor, SECRET_KEY
from app.database import get_db
from app.models import (
    AccessType,
    CardProgress,
    ExerciseAssignment,
    ExerciseBatchStudent,
    ExerciseProgress,
    ExerciseSubmission,
    FlashcardAssignment,
    LitPointLog,
    QAAnswerLog,
    ReadingTimeLog,
    ReviewLog,
    TextAssignment,
    User,
    UserRole,
    RegistrationCode,
)
from app.routers.dashboard import build_dashboard_metrics
from app.language import student_language
from app.schemas import StudentDetailsOut, UserOut

router = APIRouter(prefix="/admin", tags=["Admin (Professor)"])


def _get_student_or_404(student_id: int, db: Session) -> User:
    student = (
        db.query(User)
        .filter(User.id == student_id, User.role == UserRole.aluno)
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Aluno não encontrado.")
    return student


@router.get("/students", response_model=list[UserOut])
def list_students(
    access_type: str | None = None,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """
    Lista todos os alunos cadastrados (aprovados e pendentes).

    `access_type` (opcional: "padrao" ou "especial") filtra pra só um dos
    dois grupos — usado nas telas de envio de conteúdo (Flashcards, Read and
    Listen) pra não misturar aluno de "Acesso Especial" (ex.: italiano) com
    quem faz o curso normal (inglês), já que o conteúdo desses módulos ainda
    não é separado por língua.
    """
    query = db.query(User).filter(User.role == UserRole.aluno)
    if access_type:
        try:
            query = query.filter(User.access_type == AccessType(access_type))
        except ValueError:
            pass
    return query.order_by(User.created_at.desc()).all()


@router.get("/students/{student_id}/details", response_model=StudentDetailsOut)
def get_student_details(
    student_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Detalhes de um aluno: quantidade de exercícios respondidos, tempo de
    texto e demais métricas (mesmas exibidas na tela inicial do aluno)."""
    student = _get_student_or_404(student_id, db)
    metrics = build_dashboard_metrics(db, student_id)
    return StudentDetailsOut(student=student, metrics=metrics)


@router.patch("/students/{student_id}/approve", response_model=UserOut)
def approve_student(
    student_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Aprova o acesso de um aluno.

    A aprovação apenas libera o acesso do aluno. A língua escolhida no
    cadastro continua disponível para os módulos que já suportam múltiplos
    idiomas.
    """
    student = _get_student_or_404(student_id, db)
    student.is_approved = True

    db.commit()
    db.refresh(student)
    return student


@router.patch("/students/{student_id}/revoke", response_model=UserOut)
def revoke_student(
    student_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Revoga/bloqueia o acesso de um aluno (ex: aluno parou as aulas)."""
    student = _get_student_or_404(student_id, db)
    student.is_approved = False
    db.commit()
    db.refresh(student)
    return student


@router.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Remove permanentemente um aluno e todos os dados associados."""
    student = _get_student_or_404(student_id, db)

    db.query(ExerciseSubmission).filter(ExerciseSubmission.student_id == student_id).delete()
    db.query(ExerciseAssignment).filter(ExerciseAssignment.student_id == student_id).delete()
    db.query(ExerciseProgress).filter(ExerciseProgress.student_id == student_id).delete()
    db.query(ExerciseBatchStudent).filter(ExerciseBatchStudent.student_id == student_id).delete()
    db.query(ReviewLog).filter(ReviewLog.student_id == student_id).delete()
    db.query(CardProgress).filter(CardProgress.student_id == student_id).delete()
    db.query(FlashcardAssignment).filter(FlashcardAssignment.student_id == student_id).delete()
    db.query(TextAssignment).filter(TextAssignment.student_id == student_id).delete()
    db.query(QAAnswerLog).filter(QAAnswerLog.student_id == student_id).delete()
    db.query(LitPointLog).filter(LitPointLog.student_id == student_id).delete()
    db.query(ReadingTimeLog).filter(ReadingTimeLog.student_id == student_id).delete()

    db.delete(student)
    db.commit()
    return None


_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_CODE_CIPHER = Fernet(base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode("utf-8")).digest()))

def _code_digest(code: str) -> str:
    return hashlib.sha256(code.upper().encode("utf-8")).hexdigest()

def _encrypt_code(code: str) -> str:
    return _CODE_CIPHER.encrypt(code.encode("utf-8")).decode("ascii")

def _decrypt_code(value: str | None) -> str | None:
    if not value:
        return None  # códigos criados antes desta atualização não podem ser revelados
    try:
        return _CODE_CIPHER.decrypt(value.encode("ascii")).decode("utf-8")
    except Exception:
        return None

@router.post("/registration-codes")
def create_registration_code(
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Gera código aleatório de cinco caracteres, válido por sete dias; mantém no máximo cinco ativos."""
    now = datetime.utcnow()
    # Limpa códigos já consumidos ou expirados antes de abrir espaço.
    db.query(RegistrationCode).filter(
        (RegistrationCode.used_at.is_not(None)) | (RegistrationCode.expires_at <= now)
    ).delete(synchronize_session=False)
    active = db.query(RegistrationCode).filter(
        RegistrationCode.used_at.is_(None), RegistrationCode.expires_at > now
    ).order_by(RegistrationCode.created_at.asc()).all()
    # A lista mantém somente os cinco códigos mais recentes disponíveis.
    while len(active) >= 5:
        db.delete(active.pop(0))
    for _ in range(10):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(5))
        digest = _code_digest(code)
        if not db.query(RegistrationCode).filter(RegistrationCode.code_hash == digest).first():
            item = RegistrationCode(
                code_hash=digest,
                code_encrypted=_encrypt_code(code),
                expires_at=now + timedelta(days=7),
            )
            db.add(item)
            db.commit()
            return {"code": code, "expires_at": item.expires_at.isoformat()}
    db.rollback()
    raise HTTPException(status_code=500, detail="Não foi possível gerar um código. Tente novamente.")

@router.get("/registration-codes")
def list_registration_codes(
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    now = datetime.utcnow()
    # Remove usados/expirados e entrega no máximo cinco disponíveis.
    db.query(RegistrationCode).filter(
        (RegistrationCode.used_at.is_not(None)) | (RegistrationCode.expires_at <= now)
    ).delete(synchronize_session=False)
    db.commit()
    active = db.query(RegistrationCode).filter(
        RegistrationCode.used_at.is_(None), RegistrationCode.expires_at > now
    ).order_by(RegistrationCode.created_at.desc()).all()
    # Também corrige eventuais listas antigas com mais de cinco códigos.
    for old_item in active[5:]:
        db.delete(old_item)
    if len(active) > 5:
        db.commit()
    rows = active[:5]
    return [{"id": r.id, "code": _decrypt_code(r.code_encrypted),
             "created_at": r.created_at.isoformat(), "expires_at": r.expires_at.isoformat(),
             "used": False, "expired": False} for r in rows]
