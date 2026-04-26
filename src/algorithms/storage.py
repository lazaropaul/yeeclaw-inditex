from typing import Optional
from src.model.silo_state import SiloState, SiloPosition, Box

class StorageEngine:
    def __init__(self, state: SiloState):
        self.state = state
        # Ya no se usa self.reserved_positions

    def assign_position(self, box: Box) -> Optional[SiloPosition]:
        return self.peek_best_position(box)

    def peek_best_position(self, box: Box) -> Optional[SiloPosition]:
        y_load = {y: 0 for y in range(1, 9)}
        total_boxes = 0
        for pos, b in self.state.grid.items():
            if b is not None:
                y_load[pos.y] += 1
                total_boxes += 1
        avg_load = total_boxes / 8.0 if total_boxes > 0 else 0
        y_penalties = {y: 4.0 * abs(y_load[y] - avg_load) for y in range(1, 9)}

        best_score = float('inf')
        best_pos = None
        for pos, occupied in self.state.grid.items():
            if occupied is not None:
                continue
            if pos.z == 2:
                front = SiloPosition(pos.aisle, pos.side, pos.x, pos.y, 1)
                if self.state.grid.get(front) is None:
                    continue
            z_penalty = 0.0 if pos.z == 1 else 6.0
            score = pos.x + y_penalties[pos.y] + z_penalty
            if score < best_score:
                best_score = score
                best_pos = pos
        return best_pos