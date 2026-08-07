"""Customer field validators (NP-041)."""

from __future__ import annotations

from django.core.exceptions import ValidationError


def validate_turkish_tax_number(value: str) -> None:
    """
    Vergi numarası girilmişse format kontrolü.
    10 haneli VKN veya 11 haneli TCKN kabul edilir.
    """
    raw = (value or "").strip()
    if not raw:
        return

    if not raw.isdigit():
        raise ValidationError("Vergi numarası yalnızca rakamlardan oluşmalıdır.")

    if len(raw) == 10:
        if not _is_valid_vkn(raw):
            raise ValidationError("Geçersiz vergi kimlik numarası (VKN).")
        return

    if len(raw) == 11:
        if not _is_valid_tckn(raw):
            raise ValidationError("Geçersiz T.C. kimlik numarası.")
        return

    raise ValidationError("Vergi numarası 10 (VKN) veya 11 (TCKN) haneli olmalıdır.")


def _is_valid_vkn(vkn: str) -> bool:
    digits = [int(c) for c in vkn]
    total = 0
    for i in range(9):
        tmp = (digits[i] + (9 - i)) % 10
        powered = (tmp * (2 ** (9 - i))) % 9
        if tmp != 0 and powered == 0:
            powered = 9
        total += powered
    check = (10 - (total % 10)) % 10
    return check == digits[9]


def _is_valid_tckn(tckn: str) -> bool:
    if tckn[0] == "0":
        return False
    digits = [int(c) for c in tckn]
    odd_sum = digits[0] + digits[2] + digits[4] + digits[6] + digits[8]
    even_sum = digits[1] + digits[3] + digits[5] + digits[7]
    if ((odd_sum * 7) - even_sum) % 10 != digits[9]:
        return False
    return sum(digits[:10]) % 10 == digits[10]
