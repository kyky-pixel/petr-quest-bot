import math

# Variant B: стоимость следующего уровня растёт на 18%
def next_xp_for_level(L: int) -> int:
    if L < 1:
        L = 1
    return int(round(120 * (1.18 ** (L - 1))))

def total_xp_for_level(L: int) -> int:
    # суммарный XP, требуемый для достижения уровня L (уровень 1 = 0)
    total = 0
    for l in range(1, L):
        total += next_xp_for_level(l)
    return total

def progress_at(total_xp: int, level: int) -> tuple[int, int, int, float]:
    """
    Возвращает:
      base   — XP порог текущего уровня (накопленный для level)
      need   — XP, требуемый для перехода на следующий уровень
      have   — XP, набранный внутри текущего уровня (total_xp - base)
      pct    — прогресс внутри уровня (0..100)
    """
    base = total_xp_for_level(level)
    need = next_xp_for_level(level)
    have = max(0, total_xp - base)
    pct = 0.0 if need <= 0 else min(100.0, have * 100.0 / need)
    return base, need, have, pct
