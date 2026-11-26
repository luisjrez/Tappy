from tappy.sales.errors import InvalidAmountError


def validated_amount(amount_cents: int, maximum: int) -> int:
    if not 1 <= amount_cents <= maximum:
        raise InvalidAmountError(maximum)
    return amount_cents
