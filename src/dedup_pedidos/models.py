from dataclasses import dataclass, field
from enum import Enum


class ConflictType(Enum):
    AUTO_RESOLVABLE = "AUTO_RESOLVABLE"          # Critério claro atingido
    MANUAL_MERGE_REQUIRED = "MANUAL_MERGE_REQUIRED" # Impasse (ex: múltiplos pedidos com item_relacionado)


@dataclass
class DependentRecord:
    table_name: str
    record_id: str
    foreign_key_column: str
    details: str


@dataclass
class PedidoDiagnostic:
    id: str
    numero_pedido: str
    filial: str
    item_pedido_count: int
    has_item_relacionado: bool
    has_item_relacionado_servico: bool
    total_dependencias: int
    dependencias: list[DependentRecord] = field(default_factory=list)


@dataclass
class DuplicateGroup:
    db_name: str
    numero_pedido: str
    filial: str
    pedidos: list[PedidoDiagnostic]
    canonical_id: str | None = None
    conflict_type: ConflictType = ConflictType.AUTO_RESOLVABLE
    reason: str = ""
