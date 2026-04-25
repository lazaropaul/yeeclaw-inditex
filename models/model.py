"""
HackUPC 2026 – Yeeclaw
This module defines the data model and abstract interfaces.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


# ---------------------------------------------------------------------------
# Constants (from the problem statement)
# ---------------------------------------------------------------------------

NUM_AISLES = 4          # Aisles 1..4
NUM_SIDES = 2           # Side 1 (Left) and Side 2 (Right)
MAX_X = 60              # X positions 1..60 (distance from head)
MAX_Y = 8               # Y levels 1..8 (height)
MAX_Z = 2               # Z depths 1..2
HEAD_X = 0              # Shuttle home position

SHUTTLE_HANDLING_TIME = 10   # seconds, fixed per pick or drop
PALLET_SIZE = 12             # boxes per pallet
NUM_ROBOTS = 8               # palletizing robots
PALLETS_PER_ROBOT = 1        # pallets each robot handles simultaneously
MAX_ACTIVE_PALLETS = NUM_ROBOTS * PALLETS_PER_ROBOT   # = 8


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Position:
    """
    An 11-character location string in the silo: AISLE_SIDE_XXX_YY_Z
    Example: "01_02_003_04_01"
    """
    aisle: int   # 1..NUM_AISLES
    side:  int   # 1..NUM_SIDES
    x:     int   # 1..MAX_X
    y:     int   # 1..MAX_Y
    z:     int   # 1..MAX_Z

    def __post_init__(self):
        assert 1 <= self.aisle <= NUM_AISLES, f"Invalid aisle: {self.aisle}"
        assert 1 <= self.side  <= NUM_SIDES,  f"Invalid side: {self.side}"
        assert 1 <= self.x     <= MAX_X,      f"Invalid x: {self.x}"
        assert 1 <= self.y     <= MAX_Y,      f"Invalid y: {self.y}"
        assert 1 <= self.z     <= MAX_Z,      f"Invalid z: {self.z}"

    def __str__(self) -> str:
        return f"{self.aisle:02d}_{self.side:02d}_{self.x:03d}_{self.y:02d}_{self.z:02d}"

    @staticmethod
    def from_str(s: str) -> "Position":
        parts = s.split("_")
        return Position(int(parts[0]), int(parts[1]), int(parts[2]),
                        int(parts[3]), int(parts[4]))


# ---------------------------------------------------------------------------
# Box
# ---------------------------------------------------------------------------

@dataclass
class Box:
    """
    Represents a single box with its 20-digit identity code.

    Code layout (example: 30100280122093090329):
        source      : digits 0-6   → "3010028"
        destination : digits 7-14  → "01220930"
        bulk_number : digits 15-19 → "90329"
    """
    code: str  # 20-digit string

    def __post_init__(self):
        assert len(self.code) == 20 and self.code.isdigit(), \
            f"Box code must be exactly 20 digits: {self.code}"

    @property
    def source(self) -> str:
        return self.code[0:7]

    @property
    def destination(self) -> str:
        return self.code[7:15]

    @property
    def bulk_number(self) -> str:
        return self.code[15:20]

    def __repr__(self) -> str:
        return f"Box({self.code})"


# ---------------------------------------------------------------------------
# Shuttle
# ---------------------------------------------------------------------------

class ShuttleStatus(Enum):
    IDLE    = "idle"
    MOVING  = "moving"
    PICKING = "picking"
    PLACING = "placing"


@dataclass
class Shuttle:
    """
    One shuttle per (aisle, side, y-level) pair.
    Moves along X. Starts at HEAD_X (x=0) at t=0.
    """
    aisle:  int
    side:   int
    y:      int   # height level this shuttle belongs to

    current_x: int = HEAD_X
    current_time: float = 0.0          # earliest time this shuttle is free
    status: ShuttleStatus = ShuttleStatus.IDLE
    carrying: Optional[Box] = None

    def travel_time(self, from_x: int, to_x: int) -> float:
        """Time to move between two X positions (handling time included)."""
        return SHUTTLE_HANDLING_TIME + abs(to_x - from_x)

    def time_to_head(self) -> float:
        """Time to return to head from current position."""
        return self.travel_time(self.current_x, HEAD_X)

    def __repr__(self) -> str:
        return (f"Shuttle(aisle={self.aisle}, side={self.side}, y={self.y}, "
                f"x={self.current_x}, free_at={self.current_time:.1f}s)")


# ---------------------------------------------------------------------------
# Pallet
# ---------------------------------------------------------------------------

class PalletStatus(Enum):
    OPEN      = "open"       # collecting boxes, not yet assigned to a robot
    RESERVED  = "reserved"   # assigned to a robot, all boxes being retrieved
    COMPLETE  = "complete"   # all 12 boxes palletized and shipped


@dataclass
class Pallet:
    """A group of PALLET_SIZE boxes sharing the same destination."""
    destination: str
    status: PalletStatus = PalletStatus.OPEN
    boxes: list[Box] = field(default_factory=list)

    @property
    def is_full(self) -> bool:
        return len(self.boxes) >= PALLET_SIZE

    @property
    def missing(self) -> int:
        return PALLET_SIZE - len(self.boxes)

    def add_box(self, box: Box) -> None:
        assert not self.is_full, "Pallet already full"
        self.boxes.append(box)

    def __repr__(self) -> str:
        return (f"Pallet(dest={self.destination}, "
                f"boxes={len(self.boxes)}/{PALLET_SIZE}, status={self.status.value})")


# ---------------------------------------------------------------------------
# Silo state
# ---------------------------------------------------------------------------

class Silo:
    """
    Represents the physical 3-D grid and its contents.

    The grid is addressed as: grid[aisle][side][x][y][z]
    All indices are 1-based (as in the problem), adjusted internally.
    """

    def __init__(self):
        # 5-D grid: [aisle][side][x][y][z] → Optional[Box]
        self._grid: list = [
            [
                [
                    [
                        [None] * MAX_Z
                        for _ in range(MAX_Y)
                    ]
                    for _ in range(MAX_X)
                ]
                for _ in range(NUM_SIDES)
            ]
            for _ in range(NUM_AISLES)
        ]
        self._cache: dict[str, Position] = {} # code -> Position

    def _idx(self, pos: Position):
        return (pos.aisle - 1, pos.side - 1, pos.x - 1, pos.y - 1, pos.z - 1)

    def get(self, pos: Position) -> Optional[Box]:
        a, s, x, y, z = self._idx(pos)
        return self._grid[a][s][x][y][z]

    def is_empty(self, pos: Position) -> bool:
        return self.get(pos) is None

    def place(self, pos: Position, box: Box) -> None:
        """Place a box. Enforces z-depth stacking rule (z=1 must be empty to reach z=2)."""
        if pos.z == 2:
            front = Position(pos.aisle, pos.side, pos.x, pos.y, 1)
            assert self.is_empty(front), \
                f"Cannot place at z=2 when z=1 is occupied at {pos}. Blocking!"
        a, s, x, y, z = self._idx(pos)
        assert self._grid[a][s][x][y][z] is None, f"Position {pos} already occupied"
        self._grid[a][s][x][y][z] = box
        self._cache[box.code] = pos

    def remove(self, pos: Position) -> Box:
        """Remove and return a box. Enforces z-depth retrieval rule."""
        if pos.z == 2:
            front = Position(pos.aisle, pos.side, pos.x, pos.y, 1)
            assert self.is_empty(front), \
                f"Cannot retrieve z=2 while z=1 is occupied at {pos}; relocate first"
        a, s, x, y, z = self._idx(pos)
        box = self._grid[a][s][x][y][z]
        assert box is not None, f"No box at {pos}"
        self._grid[a][s][x][y][z] = None
        if box.code in self._cache:
            del self._cache[box.code]
        return box

    def find_box(self, box: Box) -> Optional[Position]:
        """O(1) cache lookup."""
        return self._cache.get(box.code)

    def capacity(self) -> int:
        return NUM_AISLES * NUM_SIDES * MAX_X * MAX_Y * MAX_Z

    def occupancy(self) -> int:
        count = 0
        for a in range(NUM_AISLES):
            for s in range(NUM_SIDES):
                for x in range(MAX_X):
                    for y in range(MAX_Y):
                        for z in range(MAX_Z):
                            if self._grid[a][s][x][y][z] is not None:
                                count += 1
        return count


# ---------------------------------------------------------------------------
# Abstract algorithm interfaces
# ---------------------------------------------------------------------------

class InputAlgorithm(ABC):
    """
    Decides WHERE to store an incoming box.
    Implement this to define your storage strategy.
    """

    @abstractmethod
    def assign_position(self, box: Box, silo: Silo) -> Position:
        """
        Given an arriving box and the current silo state,
        return the position where the box should be stored.
        """
        ...


class OutputAlgorithm(ABC):
    """
    Decides WHICH box to retrieve next and how to schedule shuttles.
    Implement this to define your retrieval/pallet-building strategy.
    """

    @abstractmethod
    def next_retrieval(
        self,
        active_pallets: list[Pallet],
        silo: Silo,
        shuttles: list[Shuttle],
    ) -> Optional[tuple[Box, Position]]:
        """
        Select the next (box, position) pair to retrieve.
        May return None if no retrieval should happen right now.

        active_pallets: pallets currently reserved (up to MAX_ACTIVE_PALLETS).
        silo:           current silo state.
        shuttles:       all shuttles (use to pick the least-busy one).
        """
        ...

    @abstractmethod
    def select_active_pallets(
        self,
        open_pallets: dict[str, Pallet],
    ) -> list[Pallet]:
        """
        Given all open pallets, choose up to MAX_ACTIVE_PALLETS to promote
        to RESERVED status for the two palletizing robots.
        """
        ...


class RelocationAlgorithm(ABC):
    """
    Decides where to move a blocking z=1 box when the z=2 box is needed.
    """

    @abstractmethod
    def relocation_target(self, blocking_box: Box, silo: Silo) -> Position:
        """
        Return a free position to temporarily store `blocking_box`
        so the box behind it can be retrieved.
        """
        ...


# ---------------------------------------------------------------------------
# Abstract Simulator
# ---------------------------------------------------------------------------

class Simulator(ABC):
    """
    Drives the full simulation loop.
    Wire up your concrete algorithm implementations here.
    """

    def __init__(
        self,
        input_algo: InputAlgorithm,
        output_algo: OutputAlgorithm,
        relocation_algo: RelocationAlgorithm,
    ):
        self.silo = Silo()
        self.shuttles: list[Shuttle] = [
            Shuttle(aisle=a, side=0, y=y)  # side=0 indicates it serves both sides in the aisle
            for a in range(1, NUM_AISLES + 1)
            for y in range(1, MAX_Y + 1)
        ]
        self.pallets: dict[str, Pallet] = {}   # destination → Pallet
        self.active_pallets: list[Pallet] = []
        self.completed_pallets: list[Pallet] = []

        self.input_algo = input_algo
        self.output_algo = output_algo
        self.relocation_algo = relocation_algo

        self.current_time: float = 0.0
        self.boxes_received: int = 0

    @abstractmethod
    def run(self, incoming_boxes: list[Box]) -> None:
        """
        Execute the full simulation for the given sequence of incoming boxes.
        Update self.current_time, self.silo, self.pallets, etc.
        """
        ...

    # ------------------------------------------------------------------
    # Metrics (call after run())
    # ------------------------------------------------------------------

    def full_pallet_percentage(self) -> float:
        """% of completed pallets that shipped all 12 boxes."""
        if not self.completed_pallets:
            return 0.0
        full = sum(1 for p in self.completed_pallets if len(p.boxes) == PALLET_SIZE)
        return full / len(self.completed_pallets) * 100

    def average_time_per_pallet(self) -> float:
        """Throughput proxy: total simulation time / completed pallets."""
        if not self.completed_pallets:
            return float("inf")
        return self.current_time / len(self.completed_pallets)

    def report(self) -> dict:
        return {
            "total_time_s":          self.current_time,
            "boxes_received":        self.boxes_received,
            "pallets_completed":     len(self.completed_pallets),
            "full_pallet_pct":       self.full_pallet_percentage(),
            "avg_time_per_pallet_s": self.average_time_per_pallet(),
            "silo_occupancy":        self.silo.occupancy(),
            "silo_capacity":         self.silo.capacity(),
        }