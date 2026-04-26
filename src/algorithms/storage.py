from typing import Optional
from src.model.silo_state import SiloState, SiloPosition, Box

class StorageEngine:
    def __init__(self, state: SiloState):
        self.state = state
        self.reserved_positions = set()

    def assign_position(self, box: Box) -> Optional[SiloPosition]:
        """Asigna y reserva una posición rápidamente."""
        pos = self.peek_best_position(box)
        if pos:
            self.reserved_positions.add(pos)
        return pos

    def peek_best_position(self, box: Box) -> Optional[SiloPosition]:
        # 1. Limpieza de reservas: leemos el diccionario directamente para mayor velocidad
        self.reserved_positions = {p for p in self.reserved_positions if self.state.grid.get(p) is None}
        
        # 2. Pre-cálculo de cargas por nivel Y
        y_load = {y: 0 for y in range(1, 9)}
        total_boxes = 0
        
        # Iteramos una sola vez sobre el grid para contar ocupación física y reservas
        for pos, b in self.state.grid.items():
            if b is not None:
                y_load[pos.y] += 1
                total_boxes += 1
        
        for res_pos in self.reserved_positions:
            y_load[res_pos.y] += 1
            total_boxes += 1
                
        avg_load = total_boxes / 8.0 if total_boxes > 0 else 0
        
        # Pre-calculamos las penalizaciones de altura fuera del bucle principal
        y_penalties = {y: 4.0 * abs(y_load[y] - avg_load) for y in range(1, 9)}

        # 3. Búsqueda de Score Mínimo (O(N) optimizado)
        best_score = float('inf')
        best_pos = None

        # Acceso directo a los ítems del grid para evitar llamadas a funciones
        for pos, occupied_box in self.state.grid.items():
            # Saltamos si está ocupada o ya reservada
            if occupied_box is not None or pos in self.reserved_positions:
                continue
            
            # Validación rápida de Regla Z sin crear objetos innecesarios
            if pos.z == 2:
                # Comprobamos si el frontal (Z=1) está vacío
                front_pos = SiloPosition(pos.aisle, pos.side, pos.x, pos.y, 1)
                if self.state.grid.get(front_pos) is None:
                    continue # Z=2 requiere Z=1 ocupado

            # Cálculo de Score simplificado
            z_penalty = 0.0 if pos.z == 1 else 6.0
            score = pos.x + y_penalties[pos.y] + z_penalty

            if score < best_score:
                best_score = score
                best_pos = pos

        return best_pos