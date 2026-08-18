"""Utilidades relacionadas à língua-alvo do aluno."""

from app.models import AccessType, User


def student_language(student: User) -> str:
    """Retorna a língua-alvo usada pelos conteúdos do aluno.

    O curso padrão usa inglês. Contas de Acesso Especial usam a língua
    escolhida no cadastro.
    """
    if student.access_type == AccessType.especial and student.target_language:
        return student.target_language.strip().lower()
    return "ingles"


def student_source_language(student: User) -> str:
    """Retorna a língua de origem/nativa usada no par dos conteúdos."""
    if student.native_language:
        return student.native_language.strip().lower()
    return "pt"
