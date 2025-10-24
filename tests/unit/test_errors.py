from farol_core.domain.errors import FarolError, WriteError


def test_farol_error_preserves_cause() -> None:
    original = ValueError("falha")
    error = FarolError("mensagem", cause=original)

    assert error.cause is original
    assert str(error) == "mensagem"


def test_write_error_is_subclass_of_farol_error() -> None:
    error = WriteError("erro ao escrever")

    assert isinstance(error, FarolError)
    assert error.cause is None
