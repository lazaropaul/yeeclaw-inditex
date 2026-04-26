import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.model import (
    InputAlgorithm, OutputAlgorithm, RelocationAlgorithm, 
    Box, Silo, Position, Shuttle, Pallet, MAX_ACTIVE_PALLETS,
    NUM_AISLES, NUM_SIDES, MAX_X, MAX_Y, MAX_Z
)
from typing import Optional

class OptimizedInputAlgorithm(InputAlgorithm):
    """
    Implements Z-Homogeneity, ABC Classification, and ARM Clustering logic.
    """
    def _get_abc_range(self, destination: str):
        # Deterministic hashing to distribute uniformly classes A, B, C
        val = sum(ord(c) for c in destination) % 3
        if val == 0:
            return range(1, 16) # Class A (High Velocity)
        elif val == 1:
            return range(16, 41) # Class B (Medium Velocity)
        else:
            return range(41, MAX_X + 1) # Class C (Low Velocity)

    def assign_position(self, box: Box, silo: Silo) -> Position:
        x_range = list(self._get_abc_range(box.destination))
        
        # Rule 1: Z-Coordinate Homogeneity
        # Find a channel where Z=2 matches the exact destination, and Z=1 is empty.
        for x in x_range:
            for a in range(1, NUM_AISLES + 1):
                for s in range(1, NUM_SIDES + 1):
                    for y in range(1, MAX_Y + 1):
                        pos_z1 = Position(a, s, x, y, 1)
                        pos_z2 = Position(a, s, x, y, 2)
                        
                        # If Z=2 is occupied and Z=1 is empty, check if it matches destination
                        if not silo.is_empty(pos_z2) and silo.is_empty(pos_z1):
                            existing = silo.get(pos_z2)
                            if existing.destination == box.destination:
                                return pos_z1
                                    
        # Rule 2: ARM Clustering
        # We find a completely empty channel within our ABC classification zone.
        # This acts as creating a new homogenous channel cluster.
        for x in x_range:
            for a in range(1, NUM_AISLES + 1):
                for s in range(1, NUM_SIDES + 1):
                    for y in range(1, MAX_Y + 1):
                        pos_z1 = Position(a, s, x, y, 1)
                        pos_z2 = Position(a, s, x, y, 2)
                        if silo.is_empty(pos_z1) and silo.is_empty(pos_z2):
                            return pos_z2
                            
        # Rule 3 (Emergency Fallback): Breathing Topology
        for x in range(1, MAX_X + 1):
            for a in range(1, NUM_AISLES + 1):
                for s in range(1, NUM_SIDES + 1):
                    for y in range(1, MAX_Y + 1):
                        pos_z1 = Position(a, s, x, y, 1)
                        pos_z2 = Position(a, s, x, y, 2)
                        if silo.is_empty(pos_z1) and silo.is_empty(pos_z2):
                            return pos_z2
                        
                        if not silo.is_empty(pos_z2) and silo.is_empty(pos_z1):
                            return pos_z1

        raise RuntimeError("Silo is completely full!")


class OptimizedOutputAlgorithm(OutputAlgorithm):
    """
    Implements nearest-neighbor routing while protecting against forced reshuffles.
    Because our Input Algorithm creates homogeneous Z-cells, we can easily pull Z=1 first, then Z=2!
    """
    def select_active_pallets(self, open_pallets: dict[str, Pallet]) -> list[Pallet]:
        # Prioritize full pallets
        full_pallets = [p for p in open_pallets.values() if p.is_full]
        return full_pallets[:MAX_ACTIVE_PALLETS]

    def next_retrieval(
        self,
        active_pallets: list[Pallet],
        silo: Silo,
        shuttles: list[Shuttle],
    ) -> Optional[tuple[Box, Position]]:
        
        needed_boxes = []
        for pallet in active_pallets:
            for box in pallet.boxes:
                pos = silo.find_box(box)
                if pos:
                    needed_boxes.append((box, pos))
                    
        if not needed_boxes:
            return None
            
        def get_shuttle(pos):
            for s in shuttles:
                if s.aisle == pos.aisle and s.y == pos.y:
                    return s
            return None

        # CRITICAL OPTIMIZATION: Always prioritize retrieving Z=1 boxes over Z=2 boxes.
        z1_boxes = [pair for pair in needed_boxes if pair[1].z == 1]
        
        if z1_boxes:
            # TSP Nearest Neighbor + Load Balancing: 
            # 1. Prioritize whichever shuttle finishes first (lowest current_time)
            # 2. Break ties by closest geographic X coordinate to maximize DCC.
            z1_boxes.sort(key=lambda pair: (
                get_shuttle(pair[1]).current_time,
                abs(get_shuttle(pair[1]).current_x - pair[1].x)
            ))
            return z1_boxes[0]
            
        z2_boxes = [pair for pair in needed_boxes if pair[1].z == 2]
        if z2_boxes:
            z2_boxes.sort(key=lambda pair: (
                get_shuttle(pair[1]).current_time,
                abs(get_shuttle(pair[1]).current_x - pair[1].x)
            ))
            return z2_boxes[0]
                
        return None


class OptimizedRelocationAlgorithm(RelocationAlgorithm):
    """
    Should barely ever be called due to the optimized homogeneity constraints,
    but implemented safely for fallback breathing topology scenarios.
    """
    def relocation_target(self, blocking_box: Box, silo: Silo) -> Position:
        # Heavily prioritize entirely empty channels to avoid secondary blocking
        for a in range(1, NUM_AISLES + 1):
            for s in range(1, NUM_SIDES + 1):
                for y in range(1, MAX_Y + 1):
                    for x in range(1, MAX_X + 1):
                        pos_z1 = Position(a, s, x, y, 1)
                        pos_z2 = Position(a, s, x, y, 2)
                        
                        if silo.is_empty(pos_z1) and silo.is_empty(pos_z2):
                            return pos_z2
                            
        # Absolute fallback if all channels have at least 1 box
        for a in range(1, NUM_AISLES + 1):
            for s in range(1, NUM_SIDES + 1):
                for y in range(1, MAX_Y + 1):
                    for x in range(1, MAX_X + 1):
                        pos_z1 = Position(a, s, x, y, 1)
                        pos_z2 = Position(a, s, x, y, 2)
                        
                        if not silo.is_empty(pos_z2) and silo.is_empty(pos_z1):
                            return pos_z1
                            
        raise RuntimeError("No space available for reshuffling!")
