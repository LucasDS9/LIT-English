"""
Algoritmo SM-2 (SuperMemo 2) de repetição espaçada.

O aluno avalia cada card com uma "qualidade" de 0 a 5:
  0-2 = errou / muito difícil  -> reseta a repetição, revisa de novo logo
  3   = difícil, mas lembrou
  4   = bom, lembrou normalmente
  5   = fácil, lembrou na hora

Mapeamos isso para botões simples no frontend: Errei (0) / Difícil (3) / Bom (4) / Fácil (5)
"""
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class SM2Result:
    repetitions: int
    interval_days: int
    ease_factor: float
    next_review: datetime


def calculate_sm2(
    quality: int,
    repetitions: int,
    interval_days: int,
    ease_factor: float,
) -> SM2Result:
    """
    Recebe o estado atual do card + a qualidade da resposta (0-5)
    e retorna o novo estado (repetições, intervalo em dias, fator de facilidade, próxima data).
    """
    quality = max(0, min(5, quality))  # garante que fica entre 0 e 5

    if quality < 3:
        # Errou: reseta repetições e revisa de novo rapidamente
        repetitions = 0
        interval_days = 1
    else:
        if repetitions == 0:
            interval_days = 1
        elif repetitions == 1:
            interval_days = 6
        else:
            interval_days = round(interval_days * ease_factor)
        repetitions += 1

    # Atualiza o fator de facilidade (fórmula original do SM-2)
    ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease_factor = max(1.3, ease_factor)  # nunca deixa ficar abaixo de 1.3

    next_review = datetime.utcnow() + timedelta(days=interval_days)

    return SM2Result(
        repetitions=repetitions,
        interval_days=interval_days,
        ease_factor=round(ease_factor, 2),
        next_review=next_review,
    )
