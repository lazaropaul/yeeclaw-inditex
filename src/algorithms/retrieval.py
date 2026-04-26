from typing import List, Optional
from src.model.silo_state import SiloState, SiloPosition, Box
from src.algorithms.storage import StorageEngine

class Task:
    def __init__(self, task_type: str, box_id: str, source: SiloPosition, target: Optional[SiloPosition] = None):
        self.task_type = task_type 
        self.box_id = box_id
        self.source = source
        self.target = target

    def __repr__(self):
        return f"Task({self.task_type}, Box:{self.box_id})"

class RetrievalEngine:
    def __init__(self, state: SiloState, storage_engine: StorageEngine):
        self.state = state
        self.storage = storage_engine

    def get_next_tasks(self, shuttle_y: int, shuttle_x: int, active_pallets: list, aisle: int) -> List[Task]:
        best_box_info = None
        min_score = float('inf')
        best_relocation_pos = None
        best_pallet = None

        for pallet in active_pallets:
            boxes_left = len(pallet.pending_boxes)
            if boxes_left == 0:
                continue

            for box_id, box_pos in list(pallet.pending_boxes.items()):
                # Filtro: El shuttle solo saca cajas de su Pasillo y su Nivel Y
                if box_pos.y != shuttle_y or box_pos.aisle != aisle:
                    continue
                    
                # Doble check de seguridad por si otro proceso movió la caja
                actual_box = self.state.grid.get(box_pos)
                if actual_box is None or actual_box.box_id != box_id:
                    continue 

                # Calcular Score Base
                dist_x = abs(shuttle_x - box_pos.x)
                score = dist_x
                relocation_pos = None
                
                # Penalización Z y Cálculo de Relocalización
                if box_pos.z == 2:
                    z1_pos = SiloPosition(box_pos.aisle, box_pos.side, box_pos.x, box_pos.y, 1)
                    blocking_box = self.state.grid.get(z1_pos)
                    
                    if blocking_box is not None:
                        relocation_pos = self.storage.peek_best_position(blocking_box)
                        if relocation_pos:
                            dist_mover = abs(z1_pos.x - relocation_pos.x)
                            score += 10 + dist_mover
                        else:
                            score += 1000 # Penalización extrema si no hay huecos

                # Prioridad por pallet casi terminado
                urgency_bonus = (12 - boxes_left) * 2 
                score -= urgency_bonus

                # Elegir ganador
                if score < min_score:
                    min_score = score
                    best_box_info = (box_id, box_pos)
                    best_relocation_pos = relocation_pos
                    best_pallet = pallet

        if not best_box_info:
            return [] # Nada que sacar para este shuttle

        target_box_id, target_box_pos = best_box_info
        tasks = []

        # Tarea A: Relocalizar (Si estaba bloqueada)
        if best_relocation_pos is not None:
            z1_pos = SiloPosition(target_box_pos.aisle, target_box_pos.side, target_box_pos.x, target_box_pos.y, 1)
            blocking_box = self.state.grid.get(z1_pos)
            if blocking_box:
                tasks.append(Task('RELOCATE', blocking_box.box_id, z1_pos, best_relocation_pos))

        # Tarea B: Extracción Real (El target es un dummy en cabecera)
        head_pos = SiloPosition(aisle, 1, 0, shuttle_y, 1)
        tasks.append(Task('RETRIEVE', target_box_id, target_box_pos, head_pos))

        # Marcar la caja como "En Proceso" eliminándola del pallet
        if target_box_id in best_pallet.pending_boxes:
            del best_pallet.pending_boxes[target_box_id]

        return tasks