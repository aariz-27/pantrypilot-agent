from app.domain.errors import InvalidInputError, PantryPilotError


def test_invalid_input_error_envelope_shape():
    error = InvalidInputError("Add at least one valid pantry ingredient.")
    envelope = error.to_error_envelope(request_id="req_123")
    assert envelope == {
        "request_id": "req_123",
        "error": {
            "code": "INVALID_INPUT",
            "message": "Add at least one valid pantry ingredient.",
            "retryable": False,
        },
    }


def test_base_error_defaults():
    error = PantryPilotError("something went wrong")
    assert error.code == "INTERNAL_ERROR"
    assert error.retryable is False


def test_error_is_a_real_exception():
    try:
        raise InvalidInputError("bad input")
    except PantryPilotError as exc:
        assert exc.message == "bad input"
    else:
        raise AssertionError("expected PantryPilotError to be raised")
