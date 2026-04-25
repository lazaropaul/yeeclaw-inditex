"""
silo_state.py — Modelo del estado de un silo logístico automatizado.

Estructura:
  4 pasillos × 2 lados × 60 posiciones X × 8 niveles Y × 2 profundidades Z
  = 7 680 posiciones totales.

Diseñado para ser extendido con algoritmos de entrada, salida y scheduling.
"""

from __future__ import annotations

import itertools
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# SiloPosition
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class SiloPosition:
    """Coordenada única dentro del silo.

    aisle: 1-4
    side:  1 (izquierda) | 2 (derecha)
    x:     1-60  (distancia desde la cabeza)
    y:     1-8   (nivel de altura)
    z:     1-2   (1=delantera, 2=trasera)
    """

    aisle: int
    side: int
    x: int
    y: int
    z: int

    def __str__(self) -> str:
        """Formato AA_BB_CCC_DD_EE."""
        return (
            f"{self.aisle:02d}_{self.side:02d}_"
            f"{self.x:03d}_{self.y:02d}_{self.z:02d}"
        )

    def __repr__(self) -> str:
        return (
            f"SiloPosition(aisle={self.aisle}, side={self.side}, "
            f"x={self.x}, y={self.y}, z={self.z})"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Box
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(slots=True)
class Box:
    """Caja identificada por un código de 20 dígitos.

    Campos derivados del código:
      origin       — posiciones 0-6   (código de almacén de origen)
      destination  — posiciones 7-14  (código de destino)
      bulk_number  — posiciones 15-19 (número de bulto)
    """

    box_id: str           # 20 dígitos
    origin: str           # box_id[0:7]
    destination: str      # box_id[7:15]
    bulk_number: str      # box_id[15:20]
    position: Optional[SiloPosition] = None

    def __post_init__(self) -> None:
        if len(self.box_id) != 20 or not self.box_id.isdigit():
            raise ValueError(
                f"box_id debe tener exactamente 20 dígitos, recibido: {self.box_id!r}"
            )


# ──────────────────────────────────────────────────────────────────────────────
# Shuttle
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(slots=True)
class Shuttle:
    """Shuttle que opera en un (pasillo, nivel_Y).

    Hay 4 pasillos × 8 niveles = 32 shuttles.
    Tiempo de movimiento: t = 10 + |x_destino − x_actual| segundos.
    """

    aisle: int
    y_level: int
    current_x: float = 0.0
    pending_ops: deque = field(default_factory=deque)
    is_busy: bool = False

    def travel_time(self, target_x: float) -> float:
        """Tiempo en segundos para moverse a *target_x*."""
        return 10.0 + abs(target_x - self.current_x)


# ──────────────────────────────────────────────────────────────────────────────
# SiloState
# ──────────────────────────────────────────────────────────────────────────────

class SiloState:
    """Estado completo del silo.

    Attributes
    ----------
    grid : dict[SiloPosition, Box | None]
        Mapa de cada celda a la caja que contiene (o None).
    box_registry : dict[str, Box]
        Índice rápido box_id → Box.
    destination_index : defaultdict[str, list[SiloPosition]]
        Posiciones ocupadas agrupadas por destino.
    shuttles : dict[tuple[int, int], Shuttle]
        (aisle, y_level) → Shuttle.
    active_pallets : dict[str, list[str]]
        destination → lista de box_ids asignados al palé activo (máx 12 por palé, máx 8 palés).
    completed_pallets : list[dict]
        Palés ya completados.
    current_time : float
        Reloj de simulación (segundos).
    """

    MAX_ACTIVE_PALLETS = 8
    BOXES_PER_PALLET = 12

    # Rangos estructurales del silo
    AISLES = range(1, 5)       # 1-4
    SIDES = range(1, 3)        # 1-2
    X_RANGE = range(1, 61)     # 1-60
    Y_RANGE = range(1, 9)      # 1-8
    Z_RANGE = range(1, 3)      # 1-2

    def __init__(self) -> None:
        self.grid: dict[SiloPosition, Box | None] = {}
        self.box_registry: dict[str, Box] = {}
        self.destination_index: defaultdict[str, list[SiloPosition]] = defaultdict(list)
        self.shuttles: dict[tuple[int, int], Shuttle] = {}
        self.active_pallets: dict[str, list[str]] = {}
        self.completed_pallets: list[dict] = []
        self.current_time: float = 0.0

    # ── Consultas ─────────────────────────────────────────────────────────

    def is_position_free(self, pos: SiloPosition) -> bool:
        """Devuelve True si la posición está vacía."""
        return self.grid.get(pos) is None

    def is_retrievable(self, pos: SiloPosition) -> bool:
        """Devuelve True si la caja en *pos* puede ser retirada (regla Z).

        - La posición debe estar ocupada.
        - Si Z=1: siempre se puede retirar (está delante).
        - Si Z=2: solo se puede retirar si Z=1 está vacío.
        """
        if self.grid.get(pos) is None:
            return False

        if pos.z == 1:
            return True

        # Z=2: comprobar que Z=1 esté vacío
        front = SiloPosition(pos.aisle, pos.side, pos.x, pos.y, z=1)
        return self.grid.get(front) is None

    def can_place_at(self, pos: SiloPosition) -> bool:
        """Devuelve True si se puede colocar una caja en *pos* (regla Z).

        - La posición debe estar vacía.
        - Si Z=2: Z=1 debe estar ocupada.
        - Si Z=1: siempre se puede colocar (si está vacía).
        """
        if not self.is_position_free(pos):
            return False

        if pos.z == 2:
            front = SiloPosition(pos.aisle, pos.side, pos.x, pos.y, z=1)
            return not self.is_position_free(front)  # Z=1 debe estar ocupada

        return True

    # ── Mutaciones ────────────────────────────────────────────────────────

    def place_box(self, box: Box, pos: SiloPosition) -> None:
        """Coloca *box* en *pos*. Aplica la regla Z."""
        if not self.is_position_free(pos):
            raise ValueError(f"Posición {pos} ya está ocupada.")

        if not self.can_place_at(pos):
            raise ValueError(
                f"No se puede colocar en {pos}: violación de regla Z "
                f"(Z=2 requiere Z=1 ocupada)."
            )

        self.grid[pos] = box
        box.position = pos
        self.box_registry[box.box_id] = box
        self.destination_index[box.destination].append(pos)

    def remove_box(self, pos: SiloPosition) -> Box:
        """Retira la caja de *pos*. Aplica la regla Z. Devuelve la caja retirada."""
        box = self.grid.get(pos)
        if box is None:
            raise ValueError(f"No hay caja en {pos}.")

        if not self.is_retrievable(pos):
            raise ValueError(
                f"No se puede retirar la caja de {pos}: violación de regla Z "
                f"(Z=2 no se puede retirar si Z=1 está ocupada)."
            )

        self.grid[pos] = None
        box.position = None
        del self.box_registry[box.box_id]
        self.destination_index[box.destination].remove(pos)
        return box

    # ── Búsquedas ─────────────────────────────────────────────────────────

    def get_free_positions(self) -> list[SiloPosition]:
        """Devuelve todas las posiciones libres donde se puede colocar una caja (respetando regla Z)."""
        return [pos for pos in self.grid if self.can_place_at(pos)]

    def get_retrievable_boxes_for_destination(self, destination: str) -> list[Box]:
        """Devuelve las cajas de un destino que pueden ser retiradas ahora."""
        result: list[Box] = []
        for pos in self.destination_index.get(destination, []):
            if self.is_retrievable(pos):
                box = self.grid[pos]
                if box is not None:
                    result.append(box)
        return result

    # ── Estadísticas ──────────────────────────────────────────────────────

    def total_boxes(self) -> int:
        """Número de cajas actualmente almacenadas."""
        return len(self.box_registry)

    def occupancy_rate(self) -> float:
        """Ratio de ocupación (0.0 a 1.0)."""
        total_cells = len(self.grid)
        if total_cells == 0:
            return 0.0
        occupied = sum(1 for v in self.grid.values() if v is not None)
        return occupied / total_cells

    def __repr__(self) -> str:
        total = len(self.grid)
        occupied = self.total_boxes()
        return (
            f"SiloState(cells={total}, occupied={occupied}, "
            f"occupancy={self.occupancy_rate():.1%}, "
            f"shuttles={len(self.shuttles)}, t={self.current_time:.1f}s)"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Funciones de construcción
# ──────────────────────────────────────────────────────────────────────────────

def parse_box(box_code: str) -> Box:
    """Parsea un código de 20 dígitos y devuelve un Box.

    Esquema del código:
      [0:7]   → origin (código de almacén de origen)
      [7:15]  → destination (código de destino)
      [15:20] → bulk_number (número de bulto)
    """
    if len(box_code) != 20 or not box_code.isdigit():
        raise ValueError(
            f"El código de caja debe tener 20 dígitos, recibido: {box_code!r}"
        )
    return Box(
        box_id=box_code,
        origin=box_code[0:7],
        destination=box_code[7:15],
        bulk_number=box_code[15:20],
    )


def initialize_silo() -> SiloState:
    """Construye un SiloState vacío con todas las celdas y shuttles inicializados."""
    silo = SiloState()

    # Crear el grid completo: 4 × 2 × 60 × 8 × 2 = 7 680 posiciones
    for aisle, side, x, y, z in itertools.product(
        SiloState.AISLES,
        SiloState.SIDES,
        SiloState.X_RANGE,
        SiloState.Y_RANGE,
        SiloState.Z_RANGE,
    ):
        silo.grid[SiloPosition(aisle, side, x, y, z)] = None

    # Crear los 32 shuttles (1 por combinación pasillo × nivel_Y)
    for aisle, y_level in itertools.product(SiloState.AISLES, SiloState.Y_RANGE):
        silo.shuttles[(aisle, y_level)] = Shuttle(aisle=aisle, y_level=y_level)

    return silo


# ──────────────────────────────────────────────────────────────────────────────
# Test básico
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  SILO STATE — Test básico")
    print("=" * 60)

    # 1. Inicializar silo vacío
    silo = initialize_silo()
    print(f"\nSilo inicializado: {silo}")
    print(f"   Posiciones totales: {len(silo.grid)}")
    print(f"   Shuttles: {len(silo.shuttles)}")

    # 2. Parsear 3 cajas de ejemplo
    codes = [
        "30100280122093090329",
        "30100280122093190330",
        "30100281234567890001",
    ]
    boxes = [parse_box(c) for c in codes]

    print("\nCajas parseadas:")
    for b in boxes:
        print(
            f"   ID={b.box_id}  origin={b.origin}  "
            f"dest={b.destination}  bulk={b.bulk_number}"
        )

    # 3. Colocar la primera caja en una posición (aisle=1, side=1, x=1, y=1, z=1)
    pos1 = SiloPosition(aisle=1, side=1, x=1, y=1, z=1)
    silo.place_box(boxes[0], pos1)
    print(f"\nCaja {boxes[0].box_id} colocada en {pos1}")
    print(f"   Posición ocupada: {not silo.is_position_free(pos1)}")
    print(f"   Recuperable: {silo.is_retrievable(pos1)}")

    # 4. Intentar colocar en Z=2 (debería funcionar porque Z=1 está ocupada)
    pos2 = SiloPosition(aisle=1, side=1, x=1, y=1, z=2)
    silo.place_box(boxes[1], pos2)
    print(f"\nCaja {boxes[1].box_id} colocada en {pos2}")
    print(f"   Recuperable Z=2: {silo.is_retrievable(pos2)} (esperado: False)")
    print(f"   Recuperable Z=1: {silo.is_retrievable(pos1)} (esperado: True)")

    # 5. Verificar regla Z: no se puede retirar Z=2 si Z=1 está ocupada
    try:
        silo.remove_box(pos2)
        print("\nERROR: no debería poder retirar Z=2 con Z=1 ocupada")
    except ValueError as e:
        print(f"\nRegla Z correcta: {e}")

    # 6. Retirar Z=1, luego Z=2 debería ser recuperable
    removed = silo.remove_box(pos1)
    print(f"\nRetirada caja de Z=1: {removed.box_id}")
    print(f"   Recuperable Z=2 ahora: {silo.is_retrievable(pos2)} (esperado: True)")

    # 7. Probar shuttle
    shuttle = silo.shuttles[(1, 1)]
    print(f"\nShuttle (1,1): posición={shuttle.current_x}")
    print(f"   Tiempo a x=30: {shuttle.travel_time(30):.1f}s")
    print(f"   Tiempo a x=60: {shuttle.travel_time(60):.1f}s")

    # 8. Posiciones libres disponibles
    free = silo.get_free_positions()
    print(f"\nPosiciones libres (can_place_at): {len(free)}")

    # 9. Estado final
    print(f"\n{silo}")
    print("\n" + "=" * 60)
    print("  Test completado con éxito")
    print("=" * 60)
