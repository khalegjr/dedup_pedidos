from dataclasses import dataclass, field
from enum import Enum


class ConflictType(Enum):
    NONE = "Sem Conflitos" # Critério claro atingido
    MANUAL_MERGE_REQUIRED = "Intervenção Manual Necessária" # Impasse (ex: múltiplos pedidos com item_relacionado)

@dataclass
class ItemDetail:
    id: int
    pedido_id: int
    quantidade: float
    preco_unitario: float
    preco_total: float
    quantidade_entrada: float | None

@dataclass
class DependentRecord:
    table_name: str
    record_id: int
    fk_column: str
    details: str

@dataclass
class PedidoDiagnostic:
    id: int
    numero_pedido: str
    filial: str
    item_pedido_count: int
    has_item_relacionado: bool
    has_item_relacionado_servico: bool
    total_dependencias: int
    dependencias: list[DependentRecord] = field(default_factory=list)
    items: list[ItemDetail] = field(default_factory=list)

@dataclass
class DuplicateGroup:
    db_name: str
    numero_pedido: str
    filial: str
    pedidos: list[PedidoDiagnostic] = field(default_factory=list)
    conflict_type: ConflictType = ConflictType.NONE
    canonical_id: int | None = None
    reason: str = ""
