"""
src/algorithms/output_algorithm.py
Algoritmo de Salida (Outbound / Ruteo de Extracción)
Gestiona la formación de palés (hasta 8 activos simultáneamente, 12 cajas por palé).
"""

import sys
from pathlib import Path
from typing import Optional

from src.model.silo_state import SiloState, SiloPosition, Box

def compute_retrieval_weights(silo: SiloState) -> dict[str, float]:
    """
    Pesos dinámicos para la salida.
    Priorizamos siempre librar primero las cajas que desbloquean Z=2,
    y luego el balance de cercanía / cola de shuttles.
    """
    return {
        "proximity": 0.30,
        "shuttle":   0.40,  # Muy importante para no ahogar un pasillo concreto al sacar
        "unlock":    0.30,  # Importante sacar de Z=1 si tiene una caja útil en Z=2 detrás
    }

def score_retrieval(pos: SiloPosition, silo: SiloState, weights: dict[str, float]) -> float:
    """Calcula el score logístico de extraer la caja en la posición pos."""
    
    # 1. Proximidad a la salida (x=0)
    proximity_score = 1.0 - ((pos.x - 1) / 59.0)
    
    # 2. Shuttle availability
    shuttle = silo.shuttles.get((pos.aisle, pos.y))
    q_len = len(shuttle.pending_ops) if shuttle else 0
    shuttle_score = 1.0 / (1.0 + q_len)
    
    # 3. Unlock Bonus (Premio por liberar una caja atrapada atrás)
    unlock_bonus = 0.0
    if pos.z == 1:
        # Verificar la caja que hay en Z=2 justo detrás
        rear_pos = SiloPosition(pos.aisle, pos.side, pos.x, pos.y, z=2)
        rear_box = silo.grid.get(rear_pos)
        if rear_box is not None:
            # Si hay caja detrás, da puntos sacarla de en medio
            # Podríamos dar más si es del MISMO destino (doble combo), pero
            # en cualquier caso despejar Z=1 siempre es útil.
            unlock_bonus = 1.0
            
    score = (
        weights["proximity"] * proximity_score +
        weights["shuttle"]   * shuttle_score +
        weights["unlock"]    * unlock_bonus
    )
    
    return score

def find_best_retrieval(destination: str, silo: SiloState) -> Optional[SiloPosition]:
    """Busca la mejor caja retirabe para un destino específico."""
    candidates = []
    
    # Iterar las posiciones donde reside este destino
    for pos in silo.destination_index.get(destination, []):
        if silo.is_retrievable(pos):
            candidates.append(pos)
            
    if not candidates:
        return None
        
    weights = compute_retrieval_weights(silo)
    
    best_pos = None
    best_score = -1.0
    
    for pos in candidates:
        score = score_retrieval(pos, silo, weights)
        if score > best_score:
            best_score = score
            best_pos = pos
            
    return best_pos

def process_pallet_fulfillment(silo: SiloState, destination: str) -> bool:
    """
    Intenta extraer 1 caja para la preparación del palé de 'destination'.
    Maneja el ciclo de vida del palé (lo abre si es posible, y lo cierra a las 12 cajas).
    Devuelve True si sacó una caja, False si no encontró ninguna.
    """
    # 1. Verificar si el palé ya existe o podemos abrir uno nuevo
    if destination not in silo.active_pallets:
        if len(silo.active_pallets) >= silo.MAX_ACTIVE_PALLETS:
            return False # No podemos abrir más palés de preparación
        silo.active_pallets[destination] = []
        
    # 2. Localizar la mejor caja en el silo a extraer
    best_pos = find_best_retrieval(destination, silo)
    if not best_pos:
        return False
        
    # 3. Extraer y procesar
    box = silo.remove_box(best_pos)
    silo.active_pallets[destination].append(box.box_id)
    
    # 4. Check si se completó el pallet
    if len(silo.active_pallets[destination]) == silo.BOXES_PER_PALLET:
        # Pallet finalizado!
        completed_ids = silo.active_pallets.pop(destination)
        silo.completed_pallets.append({
            "destination": destination,
            "box_ids": completed_ids,
            "completion_time": silo.current_time
        })
        
    return True

if __name__ == "__main__":
    # Prueba del algoritmo de salida
    project_root = Path(__file__).parent.parent.parent
    sys.path.append(str(project_root))
    
    from src.utils.csv_loader import load_silo_from_csv
    
    csv_path = project_root / 'data' / 'silo-semi-empty.csv'
    silo = load_silo_from_csv(csv_path)
    
    print("=" * 60)
    print("TEST DEL OUTPUT_ALGORITHM (PREPARACIÓN DE PALETES)")
    print("=" * 60)
    
    destination_target = "01220930"  # Destino muy común en el CSV
    
    # Extraemos 14 cajas para ver cómo cierra un pallet a las 12 y empieza el siguiente (máximo de pallets activos = 8)
    for i in range(14):
        success = process_pallet_fulfillment(silo, destination_target)
        if success:
            last_pallet = silo.active_pallets.get(destination_target, [])
            current_count = len(last_pallet)
            if current_count == 0:
                print(f"[{i+1}/14] Palé para destino {destination_target} ha sido ¡COMPLETADO!")
            else:
                print(f"[{i+1}/14] Extraída caja -> Palé {destination_target} lleva {current_count}/{silo.BOXES_PER_PALLET} cajas.")
        else:
            print(f"[{i+1}/14] Fallo -> No se encontraron cajas retirábles para {destination_target} o palets llenos.")
            
    print("-" * 60)
    print(f"Palets activos actuales: {list(silo.active_pallets.keys())}")
    print(f"Palets formados (en zona expedición): {len(silo.completed_pallets)}")
