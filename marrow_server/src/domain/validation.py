from abc import ABC, abstractmethod


class Validator(ABC):
    """Single-rule domain validator. Raises ValidationError on failure."""

    @abstractmethod
    def validate(self) -> None: ...


class ValidationPipeline:
    """Composes and fires validators. Short-circuits on first failure."""

    def __init__(self, validators: list[Validator]) -> None:
        self._validators = validators

    def run(self) -> None:
        for v in self._validators:
            v.validate()
