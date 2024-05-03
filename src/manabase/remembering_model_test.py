import pytest

from .remembering_model import KeyCollision, RememberingModel


def test_remembering_model_collision() -> None:
    model = RememberingModel()
    model.new_int_var(0, 1, ("test",))
    model.new_int_var(0, 1, ("test", "other"))
    with pytest.raises(KeyCollision):
        model.new_int_var(0, 2, ("test",))
