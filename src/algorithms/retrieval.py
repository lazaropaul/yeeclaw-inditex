from typing import List, Optional, Tuple
# Asegúrate de importar tus clases reales de modelo
from src.model.silo_state import SiloState, SiloPosition, Box
from src.algorithms.storage import StorageEngine

class Task:
    """Representa una tarea que el Shuttle debe ejecutar."""
    def __init__(self, task_type: str, box_id: str, source: SiloPosition, target: Optional[SiloPosition] = None):
        self.task_type = task_type  # 'RETRIEVE' o 'RELOCATE'
        self.box_id = box_id
        self.source = source
        self.target = target        # Solo se usa si es RELOCATE (nueva posición) o RETRIEVE (Head, X=0)

    def __repr__(self):
        return f"Task({self.task_type}, Box:{self.box_id}, From:{self.source.x}, To:{self.target.x if self.target else 'Head'})"

class RetrievalEngine:
    def __init__(self, state: SiloState, storage_engine: StorageEngine):
        self.state = state
        self.storage_engine = storage_engine

    def get_next_tasks(self, shuttle_y: int, shuttle_x: int, active_pallets: list) -> List[Task]:
        """
        Calcula la siguiente mejor caja a extraer para un shuttle específico y 
        devuelve la secuencia de tareas necesaria (1 o 2 tareas si hay bloqueo).
        """
        best_box_info = None
        min_score = float('inf')
        best_pallet = None
        best_relocation_pos = None

        # 1 y 2. Recopilación y Filtrado por Nivel Y
        for pallet in active_pallets:
            boxes_left = len(pallet.pending_boxes)
            if boxes_left == 0:
                continue

            for box_id, box_pos in pallet.pending_boxes.items():
                if box_pos.y != shuttle_y:
                    continue  # El shuttle solo puede sacar cajas de su propio nivel

                # 3. Cálculo de Scores (Multi-Objetivo)
                dist_x = abs(shuttle_x - box_pos.x)
                score = dist_x
                
                relocation_pos = None
                
                # Penalización Z (Gestión Explícita de Relocalización)
                if box_pos.z == 2:
                    # Comprobar si Z=1 está ocupada (Caja bloqueadora)
                    z1_pos = SiloPosition(box_pos.x, box_pos.y, 1, box_pos.side, box_pos.aisle)
                    blocking_box = self.state.get_box_at(z1_pos)
                    
                    if blocking_box is not None:
                        # Preguntamos al StorageEngine dónde podemos poner esta caja bloqueadora
                        # Simulamos que es una caja nueva para buscarle hueco
                        relocation_pos = self.storage_engine.peek_best_position(blocking_box)
                        
                        if relocation_pos:
                            dist_mover_bloqueador = abs(z1_pos.x - relocation_pos.x)
                            relocation_penalty = 10 + dist_mover_bloqueador
                        else:
                            # Si el silo está tan lleno que no hay dónde reubicar, penalización extrema
                            relocation_penalty = 1000 
                            
                        score += relocation_penalty

                # Bonus Completitud
                # Corrección matemática respecto al MD: Si queremos priorizar los que tienen MENOS cajas,
                # restamos más puntos a los que les faltan pocas cajas (Ej: asumiendo 12 max por pallet).
                urgency_bonus = (12 - boxes_left) * 2 
                score -= urgency_bonus

                # 4. Selección del Ganador
                if score < min_score:
                    min_score = score
                    best_box_info = (box_id, box_pos)
                    best_pallet = pallet
                    best_relocation_pos = relocation_pos

        # 5. Generación de Tareas
        if not best_box_info:
            return [] # No hay cajas accesibles/pendientes en este nivel Y

        target_box_id, target_box_pos = best_box_info
        tasks = []

        # Si había una posición de reubicación calculada, significa que la caja ganadora estaba bloqueada
        if best_relocation_pos is not None:
            z1_pos = SiloPosition(target_box_pos.x, target_box_pos.y, 1, target_box_pos.side, target_box_pos.aisle)
            blocking_box = self.state.get_box_at(z1_pos)
            
            # Task A: RELOCATE la caja bloqueadora
            task_a = Task(
                task_type='RELOCATE', 
                box_id=blocking_box.box_id, 
                source=z1_pos, 
                target=best_relocation_pos
            )
            tasks.append(task_a)

            # Opcional pero recomendado: Reservar físicamente la posición de reubicación 
            # en el StorageEngine para que otro shuttle no la quite mientras tanto.

        # Task B: RETRIEVE la caja objetivo (Target = X:0, la cabecera)
        head_pos = SiloPosition(x=0, y=shuttle_y, z=0, side='N/A', aisle='N/A')
        task_b = Task(
            task_type='RETRIEVE', 
            box_id=target_box_id, 
            source=target_box_pos, 
            target=head_pos
        )
        tasks.append(task_b)

        return tasks