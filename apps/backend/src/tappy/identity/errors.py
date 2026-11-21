class IdentityError(Exception):
    pass


class PasswordPolicyError(IdentityError):
    pass


class InvalidEmailError(IdentityError):
    pass


class IdentityAlreadyExistsError(IdentityError):
    def __init__(self) -> None:
        super().__init__("An identity with this email already exists")


class IdentityNotFoundError(IdentityError):
    def __init__(self) -> None:
        super().__init__("Identity not found")


class InvalidResetLinkError(IdentityError):
    def __init__(self) -> None:
        super().__init__("This link is invalid or has expired")
