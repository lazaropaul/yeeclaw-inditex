from typing import List, Tuple, Set, Optional  # <-- AÑADE Optional
from src.model.silo_state import SiloState, Box, SiloPosition
from src.algorithms.retrieval_optimizer import RetrievalOptimizer

class Task:
    def __init__(self, task_type: str, source: SiloPosition, target: Optional[SiloPosition] = None):
        self.task_type = task_type
        self.source = source
        self.target = target

from typing import List, Tuple, Set, Optional
from src.model.silo_state import SiloState, Box, SiloPosition
from src.algorithms.retrieval_optimizer import RetrievalOptimizer

class Task:
    def __init__(self, task_type: str, source: SiloPosition, target: Optional[SiloPosition] = None):
        self.task_type = task_type
        self.source = source
        self.target = target

class RetrievalEngine:
    """Planifica la siguiente tarea de recuperación y reubicación."""
    def __init__(self, state: SiloState):
        self.state = state
        self.optimizer = RetrievalOptimizer(state)

    def get_next_tasks(self, y_level: int, current_x: float, active_pallets: list, aisle: int) -> List[Task]:
        """
        Devuelve la siguiente tarea heurística detectando cajas bloqueadas 
        y generando reubicaciones automáticas para evitar Deadlocks.
        """
        for pallet in active_pallets:
            # 🚨 HACK: En lugar de usar la posición guardada, iteramos solo por los IDs
            for box_id in list(pallet.pending_boxes.keys()):
                
                # 🚨 Buscamos la posición REAL y actualizada de la caja en el silo
                box = self.state.box_registry.get(box_id)
                if not box or not box.position:
                    continue
                
                pos = box.position # Coordenada 100% real
                
                if pos.aisle != aisle or pos.y != y_level:
                    continue
                
                # Caso 1: La caja requerida está accesible directamente
                if self.state.is_retrievable(pos):
                    return [Task('RETRIEVE', pos)]
                
                # Caso 2: La caja requerida está en Z=2 y está bloqueada
                if pos.z == 2:
                    front_pos = SiloPosition(pos.aisle, pos.side, pos.x, pos.y, 1)
                    if not self.state.is_position_free(front_pos):
                        # Generar tarea RELOCATE para la caja que estorba en Z=1
                        free_spots = [p for p in self.state.get_free_positions() 
                                      if p.aisle == aisle and p.y == y_level]
                        
                        if free_spots:
                            # Elegimos el hueco más cercano para reubicar
                            target_pos = min(free_spots, key=lambda p: abs(p.x - front_pos.x))
                            return [Task('RELOCATE', front_pos, target_pos)]

        return []