from app.services.password import hash_password, verify_password


def test_password_hash_is_not_plaintext() -> None:
    password = "CommonDepth-Test-Password-2026!"

    password_hash = hash_password(password)

    assert password_hash != password


def test_password_hash_uses_unique_salts() -> None:
    password = "CommonDepth-Test-Password-2026!"

    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash != second_hash


def test_correct_password_verifies() -> None:
    password = "CommonDepth-Test-Password-2026!"
    password_hash = hash_password(password)

    assert verify_password(password, password_hash) is True


def test_wrong_password_does_not_verify() -> None:
    password_hash = hash_password("CommonDepth-Test-Password-2026!")

    assert verify_password("Wrong-Password", password_hash) is False


def test_malformed_hash_does_not_verify() -> None:
    assert verify_password("CommonDepth-Test-Password-2026!", "not-a-valid-argon2-hash") is False
