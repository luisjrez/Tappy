class SaleError(Exception):
    pass


class SaleNotFoundError(SaleError):
    def __init__(self) -> None:
        super().__init__("Sale not found")


class InvalidAmountError(SaleError):
    def __init__(self, maximum: int) -> None:
        super().__init__(f"Amount must be a whole number of centavos between 1 and {maximum}")


class InvalidConceptError(SaleError):
    def __init__(self, max_length: int) -> None:
        super().__init__(f"Concept must have at most {max_length} characters")


class SaleNotOpenError(SaleError):
    def __init__(self) -> None:
        super().__init__("The sale is not open")


class ActiveAttemptError(SaleError):
    def __init__(self) -> None:
        super().__init__("The sale already has an active payment attempt")


class ReceiverChangedError(SaleError):
    def __init__(self) -> None:
        super().__init__(
            "The receiving account changed after the sale was created; create a new sale"
        )


class AttemptNotFoundError(SaleError):
    def __init__(self) -> None:
        super().__init__("Attempt not found")


class UnverifiedAttemptError(SaleError):
    def __init__(self) -> None:
        super().__init__("The previous attempt expired; verify it before creating another")


class NoReceptionError(SaleError):
    def __init__(self) -> None:
        super().__init__("The sale has no confirmed reception")


class ExceptionNotFoundError(SaleError):
    def __init__(self) -> None:
        super().__init__("Incident not found")


class InvalidNoteError(SaleError):
    def __init__(self, max_length: int) -> None:
        super().__init__(f"A note needs between 1 and {max_length} characters")


class NothingToReconcileError(SaleError):
    def __init__(self) -> None:
        super().__init__("The incident has no QR attempt to reconcile")


class AttemptAlreadyPaidError(SaleError):
    def __init__(self) -> None:
        super().__init__("The incident's attempt is already paid")
