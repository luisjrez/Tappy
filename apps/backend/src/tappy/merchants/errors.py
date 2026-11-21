class MerchantError(Exception):
    pass


class MerchantNotFoundError(MerchantError):
    def __init__(self) -> None:
        super().__init__("Merchant not found")


class OperatorNotAssignableError(MerchantError):
    def __init__(self) -> None:
        super().__init__("Only active operators can be assigned to a merchant")


class InvalidMerchantNameError(MerchantError):
    def __init__(self, max_length: int) -> None:
        super().__init__(f"Merchant name must have between 1 and {max_length} characters")
