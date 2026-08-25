from dataclasses import dataclass, field


@dataclass
class OperationResult:
    """Resultado estándar de cualquier operación sobre una malla."""

    pieces: list
    names: list[str]
    operation: str
    splits: list = field(default_factory=list)
    supports_meta: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
