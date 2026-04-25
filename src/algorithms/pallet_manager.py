# src/algorithms/pallet_manager.py
from collections import defaultdict
from typing import Dict, List
from src.model.silo_state import SiloState, Box

class PalletManager:
    def __init__(self, state: SiloState):
        self.state = state
        self.boxes_by_destination: Dict[str, List[Box]] = defaultdict(list)
        self.completed_pallets = 0
        self.total_time_consumed = 0.0
        self.active_pallets_count = 0  # Límite: 8 pallets simultáneos (PDF)

    def register_box(self, box: Box):
        """Registra una caja almacenada y dispara despacho si hay 12 del mismo destino."""
        self.boxes_by_destination[box.destination].append(box)
        self.try_dispatch_if_ready()

    def try_dispatch_if_ready(self):
        """Despacha hasta 8 pallets en paralelo respetando disponibilidad de shuttles."""
        available_slots = 8 - self.active_pallets_count
        if available_slots <= 0: return

        dispatched = 0
        for dest, boxes in list(self.boxes_by_destination.items()):
            if dispatched >= available_slots: break
            if len(boxes) < 12: continue

            pallet_boxes = boxes[:12]
            pallet_time = self._calculate_parallel_pallet_time(pallet_boxes)
            
            self.completed_pallets += 1
            self.total_time_consumed += pallet_time
            
            # Retirar cajas del silo
            for box in pallet_boxes:
                if box.position:
                    try: self.state.remove_box(box.position)
                    except ValueError: pass
            
            self.boxes_by_destination[dest] = boxes[12:]
            if not self.boxes_by_destination[dest]:
                del self.boxes_by_destination[dest]
                
            dispatched += 1
            print(f"   🚛 Destino {dest}: Pallet despachado en {pallet_time:.1f}s (paralelo)")

    def _calculate_parallel_pallet_time(self, boxes: List[Box]) -> float:
        y_times = defaultdict(float)
        
        for box in boxes:
            if not box.position: continue
            shuttle = self.state.shuttles[box.position.y]
            
            # Ciclo completo según PDF: cabeza → caja → cabeza
            dist_to_box = abs(box.position.x - shuttle.current_x)
            dist_to_head = box.position.x  # Vuelta a X=0
            
            # t = (10 + d_ida) + (10 + d_vuelta)
            cycle_time = (10 + dist_to_box) + (10 + dist_to_head)
            
            # Penalización Z predictiva
            if box.position.z == 2:
                front_pos = type(box.position)(box.position.aisle, box.position.side, 
                                            box.position.x, box.position.y, 1)
                if self.state.grid.get(front_pos) is not None:
                    cycle_time += 40.0  # Reubicación estimada

            y_times[box.position.y] += cycle_time
            
            # Actualizar posición del shuttle para siguiente caja del mismo nivel
            shuttle.current_x = box.position.x  # Simula que el shuttle termina en X=0 tras entregar

        # Makespan: el tiempo lo dicta el nivel Y más cargado (trabajo paralelo real)
        return max(y_times.values()) if y_times else 0.0

    def get_metrics(self, simulated_seconds: float) -> Dict:
        hours = simulated_seconds / 3600.0
        return {
            "pallets_completed": self.completed_pallets,
            "avg_time_per_pallet": self.total_time_consumed / self.completed_pallets if self.completed_pallets > 0 else 0,
            "throughput_pallets_hour": self.completed_pallets / hours if hours > 0 else 0,
            "simulated_hours": hours
        }