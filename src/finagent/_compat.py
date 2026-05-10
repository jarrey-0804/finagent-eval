"""Python version compatibility utilities."""
import enum


class StrEnum(str, enum.Enum):  # noqa: UP042
    """Python 3.10 compatible StrEnum (stdlib added in 3.11)."""
    def __str__(self) -> str:
        return self.value
