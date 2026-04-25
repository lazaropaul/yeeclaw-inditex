from typing import Optional
from src.model.silo_state import SiloState, SiloPosition, Box

class StorageEngine:
    def __init__(self, state: SiloState):
        self.state = state
        
        # Trackers para optimizar el cálculo (evitar recorrer todo el silo)
        # Diccionario: Y (1-8) -> int (cantidad de cajas asignadas/almacenadas)
        self.y_load = {y: 0 for y in range(1, 9)}
        
        # Diccionario: Y (1-8) -> set de SiloPositions libres
        self.free_slots_by_y = {y: set() for y in range(1, 9)}
        self._initialize_trackers()

    def _initialize_trackers(self):
        """Llena los trackers basándose en el estado inicial del silo."""
        # Nota: Asumo que en SiloState tienes una forma de iterar todas las posiciones 
        # y verificar si están ocupadas. Si tu SiloState es un dict de ocupación:
        for y in range(1, 9):
            # Aquí deberás adaptar la iteración según cómo guardes las celdas en SiloState
            pass 
            # TODO: Llenar self.y_load y self.free_slots_by_y con el estado actual
            # (Lo haremos al conectar con el CSV loader)

    def assign_position(self, box: Box) -> Optional[SiloPosition]:
        """
        Asigna la mejor posición a una caja entrante usando la fórmula de Scoring:
        Score = X + 4.0 * abs(Carga_Y - Carga_Media) + (0 if Z == 1 else 6.0)
        """
        total_boxes = sum(self.y_load.values())
        avg_load = total_boxes / 8.0

        best_score = float('inf')
        best_pos = None

        for y in range(1, 9):
            for pos in self.free_slots_by_y[y]:
                # Regla Z-Guard: No considerar Z=2 si Z=1 está libre en esa X,Y
                # (Asumimos que si la caja entra, prefiere Z=1)
                z_penalty = 0.0 if pos.z == 1 else 6.0
                
                # Fórmula multi-objetivo
                score = (
                    pos.x 
                    + 4.0 * abs(self.y_load[y] - avg_load) 
                    + z_penalty
                )

                if score < best_score:
                    best_score = score
                    best_pos = pos

        if best_pos is None:
            return None # El silo está completamente lleno

        # Realizar la reserva atómica
        self._reserve_position(best_pos, box)
        return best_pos

    def _reserve_position(self, pos: SiloPosition, box: Box):
        """Actualiza los trackers internos tras una asignación."""
        self.free_slots_by_y[pos.y].remove(pos)
        self.y_load[pos.y] += 1
        # Aquí también deberías notificar al SiloState global
        # self.state.occupancy[pos] = box