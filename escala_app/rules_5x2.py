
from typing import List, Tuple

# T = Trabalho, F = Folga
def validate_5x2(cycle: List[str]) -> Tuple[bool, str]:
    if len(cycle) != 7:
        return False, "Ciclo deve ter 7 dias."

    for d in cycle:
        if d not in ("T", "F"):
            return False, "Use apenas 'T' ou 'F'."

    work_days = cycle.count("T")
    off_days = cycle.count("F")

    if work_days > 5:
        return False, "Inválido: mais de 5 dias de trabalho."
    if off_days < 2:
        return False, "Inválido: menos de 2 folgas."

    streak = 0
    for d in cycle:
        if d == "T":
            streak += 1
            if streak > 5:
                return False, "Inválido: mais de 5 dias seguidos."
        else:
            streak = 0

    return True, "OK"
