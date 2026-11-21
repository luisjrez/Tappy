class MerchantError(Exception):
    pass


class MerchantNotFoundError(MerchantError):
    def __init__(self) -> None:
        super().__init__("Merchant not found")


class OperatorNotAssignableError(MerchantError):
    def __init__(self) -> None:
        super().__init__("Only active operators can be assigned to a merchant")


class InvalidMerchantNameError(MerchantError):
    def __init__(self) -> None:
        super().__init__("Merchant name must not be blank")
