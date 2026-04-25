import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.model import (
    InputAlgorithm, OutputAlgorithm, RelocationAlgorithm, 
    Box, Silo, Position, Shuttle, Pallet, MAX_ACTIVE_PALLETS,
    NUM_AISLES, NUM_SIDES, MAX_X, MAX_Y, MAX_Z
)
from typing import Optional

class BaselineInputAlgorithm(InputAlgorithm):
    """
    A dumb input algorithm.
    It simply iterates through the grid and finds the first available spot.
    Since 'Silo' enforces that Z=2 can only be placed if Z=1 is full, 
    we always check Z=1 first, and then Z=2.
    """
    def assign_position(self, box: Box, silo: Silo) -> Position:
        for a in range(1, NUM_AISLES + 1):
            for s in range(1, NUM_SIDES + 1):
                for y in range(1, MAX_Y + 1):
                    for x in range(1, MAX_X + 1):
                        pos_z1 = Position(a, s, x, y, 1)
                        pos_z2 = Position(a, s, x, y, 2)
                        
                        # Channel completely empty: place at rear (Z=2) first
                        if silo.is_empty(pos_z1) and silo.is_empty(pos_z2):
                            return pos_z2
                        
                        # Rear occupied, front empty: place at front (Z=1)
                        if not silo.is_empty(pos_z2) and silo.is_empty(pos_z1):
                            return pos_z1
                            
        raise RuntimeError("Silo is completely full!")


class BaselineOutputAlgorithm(OutputAlgorithm):
    """
    A dumb output algorithm.
    - select_active_pallets: just picks the first N open pallets.
    - next_retrieval: simply returns the first physical box it can find for any active pallet.
    """
    def select_active_pallets(self, open_pallets: dict[str, Pallet]) -> list[Pallet]:
        # For the baseline, we strongly prefer full pallets. We don't fallback to partial pallets,
        # otherwise they get marked RESERVED and can't accept further incoming boxes in SCC.
        full_pallets = [p for p in open_pallets.values() if p.is_full]
        return full_pallets[:MAX_ACTIVE_PALLETS]

    def next_retrieval(
        self,
        active_pallets: list[Pallet],
        silo: Silo,
        shuttles: list[Shuttle],
    ) -> Optional[tuple[Box, Position]]:
        
        # Look for any box demanded by active pallets
        # To avoid searching everything randomly, we iterate active pallets, then their boxes
        for pallet in active_pallets:
            for box in pallet.boxes:
                pos = silo.find_box(box)
                if pos:
                    return (box, pos)
        
        return None


class BaselineRelocationAlgorithm(RelocationAlgorithm):
    """
    When Z=2 is requested but Z=1 is present, Z=1 must be relocated.
    This baseline just pushes it to the nearest empty slot on the SAME Y-level (to keep time low).
    """
    def relocation_target(self, blocking_box: Box, silo: Silo) -> Position:
        # The blocking box was at some Z=1 slot. We'll search for nearest empty slot.
        # But we don't know exactly its original position from the signature.
        # We can just search globally for an empty spot.
        for a in range(1, NUM_AISLES + 1):
            for s in range(1, NUM_SIDES + 1):
                for y in range(1, MAX_Y + 1):
                    for x in range(1, MAX_X + 1):
                        pos_z1 = Position(a, s, x, y, 1)
                        pos_z2 = Position(a, s, x, y, 2)
                        
                        if silo.is_empty(pos_z1) and silo.is_empty(pos_z2):
                            return pos_z2
                            
                        # Or if Z=2 is full, we can use Z=1.
                        if not silo.is_empty(pos_z2) and silo.is_empty(pos_z1):
                            return pos_z1
                                
        raise RuntimeError("No space available for reshuffling!")
