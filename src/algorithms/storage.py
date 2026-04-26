from typing import Optional
from src.model.silo_state import SiloState, Box, SiloPosition
from src.algorithms.milp_optimizer import MilpOptimizer

class StorageEngine:
    def __init__(self, state: SiloState):
        self.state = state
        self.optimizer = MilpOptimizer(state)

    def assign_position(self, box: Box) -> Optional[SiloPosition]:
        assignment = self.optimizer.optimize_storage([box])
        if assignment:
            return assignment[0][1]
        return None