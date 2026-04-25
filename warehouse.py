from typing import Dict, List, Optional, Set
from models import Box, Location

class WarehouseState:
    def __init__(self, max_x: int = 50, max_y: int = 10):
        # Dictionary acting as a sparse 3D grid
        # Key: (x, y, z), Value: Box
        self.grid: Dict[tuple[int, int, int], Box] = {}
        self.max_x = max_x
        self.max_y = max_y
        self.active_destinations: Set[str] = set()
        self.reserved_slots: Set[tuple[int, int, int]] = set()

    def add_active_destination(self, dest_code: str):
        if len(self.active_destinations) < 8:
            self.active_destinations.add(dest_code)
        else:
            raise ValueError("Maximum of 8 active pallets reached")

    def remove_active_destination(self, dest_code: str):
        self.active_destinations.discard(dest_code)

    def place_box(self, box: Box, loc: Location):
        self.grid[(loc.x, loc.y, loc.z)] = box
        self.unreserve(loc)

    def remove_box(self, loc: Location) -> Optional[Box]:
        return self.grid.pop((loc.x, loc.y, loc.z), None)

    def get_box(self, loc: Location) -> Optional[Box]:
        return self.grid.get((loc.x, loc.y, loc.z))

    def is_empty(self, loc: Location) -> bool:
        loc_tuple = (loc.x, loc.y, loc.z)
        return loc_tuple not in self.grid and loc_tuple not in self.reserved_slots

    def reserve(self, loc: Location):
        self.reserved_slots.add((loc.x, loc.y, loc.z))
        
    def unreserve(self, loc: Location):
        self.reserved_slots.discard((loc.x, loc.y, loc.z))

warehouse = WarehouseState()
