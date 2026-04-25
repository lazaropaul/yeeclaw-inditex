"""
src/algorithms/input_algorithm.py
Algoritmo de ruteo de entrada para el silo logístico.
Fase 1: Filtrado duro
Fase 2: Scoring compuesto dinámico
"""

import sys
from pathlib import Path
from typing import Optional

from src.model.silo_state import SiloState, SiloPosition, Box

MAX_SHUTTLE_QUEUE_THRESHOLD = 5

def compute_weights(silo: SiloState) -> dict[str, float]:
    """Calcula pesos dinámicos según la ocupación actual del silo."""
    occ = silo.occupancy_rate()  # float 0.0 a 1.0
    return {
        "proximity":  0.20 + 0.30 * occ,
        "anti_block": 0.30 + 0.20 * occ,
        "cluster":    0.30,
        "shuttle":    0.20 - 0.10 * occ,
    }

def filter_candidates(box: Box, silo: SiloState) -> list[SiloPosition]:
    """
    Filtro duro que elimina posiciones que no cumplen las reglas operativas o de Z.
    """
    candidates = []
    
    # Recorremos todas las posiciones del grid para validarlas
    for pos, current_box in silo.grid.items():
        if current_box is not None:
            continue
            
        # Restricción 1: Límite de la cola de trabajo del shuttle
        shuttle = silo.shuttles.get((pos.aisle, pos.y))
        if shuttle and len(shuttle.pending_ops) > MAX_SHUTTLE_QUEUE_THRESHOLD:
            continue
            
        # Restricción 2: Regla Z
        if pos.z == 1:
            candidates.append(pos)
        else:  # pos.z == 2
            front = SiloPosition(pos.aisle, pos.side, pos.x, pos.y, z=1)
            front_box = silo.grid.get(front)
            # Solo si Z=1 no está vacío Y tienen el mismo destino
            if front_box is not None and front_box.destination == box.destination:
                candidates.append(pos)
                
    return candidates

def score_position(pos: SiloPosition, box: Box, silo: SiloState, weights: dict[str, float]) -> float:
    """Calcula el score multicriterio de una posición."""
    # 1. Proximidad (1 is clostest to x=1, 0 is furthest at x=60)
    proximity_score = 1.0 - ((pos.x - 1) / 59.0)
    
    # 2. Anti-block / Cluster front
    if pos.z == 2:
        same_dest_z1_bonus = 1.0
    else:
        same_dest_z1_bonus = 0.5
    anti_block_score = same_dest_z1_bonus
    
    # 3. Cluster density
    # Contamos cuántas cajas del mismo destino hay cerca de esta X en este mismo pasillo
    cluster_count = 0
    for other_pos in silo.destination_index.get(box.destination, []):
        if other_pos.aisle == pos.aisle and abs(other_pos.x - pos.x) <= 3:
            cluster_count += 1
            
    # El umbral máximo lo situamos en sobre 10 cajas según la métrica
    cluster_density = min(1.0, cluster_count / 10.0)
    
    # 4. Shuttle availability
    shuttle = silo.shuttles.get((pos.aisle, pos.y))
    q_len = len(shuttle.pending_ops) if shuttle else 0
    shuttle_score = 1.0 / (1.0 + q_len)
    
    # Suma ponderada final
    score = (
        weights["proximity"] * proximity_score +
        weights["anti_block"] * anti_block_score +
        weights["cluster"] * cluster_density +
        weights["shuttle"] * shuttle_score
    )
    
    return score

def find_best_position(box: Box, silo: SiloState) -> Optional[SiloPosition]:
    """Busca y evalúa la mejor posición válida."""
    candidates = filter_candidates(box, silo)
    if not candidates:
        return None
        
    weights = compute_weights(silo)
    
    best_pos = None
    best_score = -1.0
    
    for pos in candidates:
        score = score_position(pos, box, silo, weights)
        if score > best_score:
            best_score = score
            best_pos = pos
            
    return best_pos

def assign_incoming_box(box: Box, silo: SiloState) -> bool:
    """
    Asigna una caja entrante a la mejor posición del grid.
    Si no hay sitio disponible, se deja en espera en el incoming_queue.
    """
    pos = find_best_position(box, silo)
    if pos is not None:
        silo.place_box(box, pos)
        return True
    
    # Si falla la inserción por saturación, retiene en streaming real
    silo.incoming_queue.append(box)
    return False

if __name__ == "__main__":
    # Test block
    # Agregar raíz al sys.path para importaciones
    project_root = Path(__file__).parent.parent.parent
    sys.path.append(str(project_root))
    
    from src.utils.csv_loader import load_silo_from_csv
    from src.model.silo_state import parse_box
    
    csv_path = project_root / 'data' / 'silo-semi-empty.csv'
    silo = load_silo_from_csv(csv_path)
    
    # Vamos a obtener los destinos de algunas cajas del CSV para usarlos:
    # 01220930, 00011111 (un destino nuevo para forzar que vaya a un Z=1), 12345678
    codes = [
        "30100280122093090329", # Destino ya existente (01220930) seguramente use Z=2 si hay alguna en Z=1
        "30100281111111190000", # Destino nuevo, usará Z=1
        "30100282222222280000", # Otro destino nuevo
    ]
    boxes = [parse_box(c) for c in codes]
    
    print("=" * 60)
    print("TEST DEL INPUT_ALGORITHM")
    print("=" * 60)
    
    # Test del cálculo de pesos dinámicos
    weights = compute_weights(silo)
    print(f"Ocupación actual: {silo.occupancy_rate():.2%}")
    print(f"Pesos calculados: {weights}")
    print("-" * 60)
    
    for box in boxes:
        best_pos = find_best_position(box, silo)
        if best_pos:
            score = score_position(best_pos, box, silo, weights)
            print(f"Caja {box.box_id} (Dest: {box.destination})")
            print(f"   -> Asignada a: {best_pos} (Score: {score:.4f})")
            # Efectivamente colocarla
            assign_incoming_box(box, silo)
        else:
            print(f"Caja {box.box_id} -> NO HAY RESULTADO VÁLIDO. Bloqueada.")
