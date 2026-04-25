import pulp
from typing import List, Dict, Tuple
from src.model.silo_state import SiloState, Box, SiloPosition

class PalletOptimizer:
    """
    Fase 2: Optimización de Salida (Output).
    Calcula el tiempo óptimo para formar y despachar pallets.
    """
    def __init__(self, state: SiloState):
        self.state = state
        self.total_pallets_completed = 0
        self.total_time_consumed = 0.0

    def optimize_global_output(self):
        """
        Itera sobre todos los destinos y despacha pallets usando lógica de optimización.
        """
        # Agrupar cajas por destino
        dest_groups: Dict[str, List[Box]] = {}
        for box in self.state.box_registry.values():
            if box.position: # Solo si está almacenada
                if box.destination not in dest_groups:
                    dest_groups[box.destination] = []
                dest_groups[box.destination].append(box)

        print("\n📦 ANALIZING EXIT PALLETS (Dinamic Priority)...")
        
        # Para cada destino con suficientes cajas
        for dest, boxes in dest_groups.items():
            while len(boxes) >= 12:
                # Seleccionamos 12 cajas. 
                # EN UN MILP COMPLETO: El solver elegiría cuales 12 minimizan el tiempo.
                # PARA EL HACKATHON (Optimización Híbrida):
                # Ordenamos las cajas por "Costo de Extracción" y tomamos las 12 mejores.
                # Esto simula la "Prioridad Dinámica" del PDF.
                
                sorted_boxes = sorted(boxes, key=lambda b: self._get_extraction_cost(b))
                pallet_candidates = sorted_boxes[:12]
                
                # Calcular tiempo de este pallet
                pallet_time = self._calculate_pallet_time(pallet_candidates)
                
                print(f"   🚛 Destination {dest}: Pallet dispatched in {pallet_time:.1f}s")
                
                # Actualizar métricas
                self.total_pallets_completed += 1
                self.total_time_consumed += pallet_time
                
                # Remover cajas del estado (simulamos que salen)
                for box in pallet_candidates:
                    self.state.remove_box(box.position)
                    boxes.remove(box) # Quitar de la lista local

    def _get_extraction_cost(self, box: Box) -> float:
        """
        Calcula el 'precio' de sacar una caja.
        Costo = Distancia + Penalización Z.
        Menor costo = Mayor prioridad (Prioridad Dinámica).
        """
        if not box.position: return float('inf')
        
        shuttle = self.state.shuttles[box.position.y]
        
        # Tiempo de viaje al origen
        dist_to_box = abs(box.position.x - shuttle.current_x)
        # Tiempo de viaje a la cabeza (salida)
        dist_to_head = box.position.x
        
        # Tiempo base (PDF: 10 + d) * 2 movimientos (Ir a buscar + Volver a cabeza)
        base_time = (10 + dist_to_box) + (10 + dist_to_head)
        
        # Penalización Z
        z_penalty = 0.0
        if box.position.z == 2:
            front_pos = SiloPosition(box.position.aisle, box.position.side, box.position.x, box.position.y, 1)
            front_box = self.state.grid.get(front_pos)
            if front_box is not None:
                z_penalty = 40.0 # Tiempo estimado de reubicación
        
        return base_time + z_penalty

    def _calculate_pallet_time(self, boxes: List[Box]) -> float:
        """
        Suma los tiempos de extracción de las 12 cajas.
        Nota: En un modelo real, los shuttles operan en paralelo.
        Aquí sumamos el Makespan (el tiempo que tarda el cuello de botella).
        """
        # Simplificación para Hackathon: Suma de tiempos por shuttle
        shuttle_times = {}
        
        for box in boxes:
            cost = self._get_extraction_cost(box)
            key = box.position.y
            shuttle_times[key] = shuttle_times.get(key, 0) + cost
            
        # El tiempo del pallet es determinado por el shuttle más ocupado (Makespan)
        return max(shuttle_times.values()) if shuttle_times else 0

    # En src/algorithms/pallet_optimizer.py → método get_metrics()
    def get_metrics(self, total_simulated_seconds: float) -> Dict:
        hours = total_simulated_seconds / 3600.0
        throughput = self.total_pallets_completed / hours if hours > 0 else 0
        
        return {
            "pallets_completed": self.total_pallets_completed,
            "avg_time_per_pallet": self.total_time_consumed / self.total_pallets_completed if self.total_pallets_completed > 0 else 0,
            "throughput_pallets_hour": throughput,
            "simulated_hours": hours
        }
    
    def try_dispatch_if_ready(self):
        for dest, boxes in self.boxes_by_destination.items():
            if len(boxes) >= 12 and dest not in self.active_pallets:
                self.active_pallets.add(dest)
                # Despacha en background (simulado)
                pallet_time = self._calculate_pallet_time(boxes[:12])
                self.total_pallets_completed += 1
                self.total_time_consumed += pallet_time
                # Remueve cajas
                for _ in range(12): boxes.pop(0)
                self.active_pallets.discard(dest)
                print(f"   🚛 Destino {dest}: Pallet despachado en {pallet_time:.1f}s (en paralelo)")
                return # 1 pallet por ciclo para estabilidad