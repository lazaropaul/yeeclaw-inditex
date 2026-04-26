from typing import Optional
from src.model.silo_state import SiloState, Box, SiloPosition

class StorageEngine:
    """Asignación de posiciones con balanceo de carga (Round-Robin)."""
    def __init__(self, state: SiloState):
        self.state = state
        self.shuttles = list(state.shuttles.keys())  # Lista de todos los (aisle, y_level)
        self.rr_index = 0

    def assign_position(self, box: Box) -> Optional[SiloPosition]:
        """Devuelve la mejor posición distribuyendo la carga entre todos los shuttles."""
        valid_positions = self.state.get_free_positions()
        if not valid_positions:
            return None
        
        # Intentar encontrar hueco balanceando entre todos los pasillos y niveles
        for _ in range(len(self.shuttles)):
            target_aisle, target_y = self.shuttles[self.rr_index]
            
            # Avanzar el turno al siguiente shuttle para la próxima caja
            self.rr_index = (self.rr_index + 1) % len(self.shuttles)
            
            # Filtrar huecos disponibles solo para este pasillo y nivel
            level_spots = [p for p in valid_positions if p.aisle == target_aisle and p.y == target_y]
            
            if level_spots:
                # Priorizar menor distancia (X) y preferir no bloquear (Z=1)
                best_spot = min(level_spots, key=lambda p: (p.x, p.z))
                return best_spot
        
        return None