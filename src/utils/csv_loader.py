import csv
from pathlib import Path

from src.model.silo_state import SiloState, SiloPosition, parse_box, initialize_silo

def parse_position_code(pos_code: str) -> SiloPosition:
    """
    Parsea el código de posición del CSV.
    Formato esperado: 11 dígitos, pj. '01010010101'
    Aisle (2) + Side (2) + X (3) + Y (2) + Z (2)
    """
    if len(pos_code) != 11:
        raise ValueError(f"El código de posición debe tener 11 dígitos: {pos_code}")
    
    aisle = int(pos_code[0:2])
    side = int(pos_code[2:4])
    x = int(pos_code[4:7])
    y = int(pos_code[7:9])
    z = int(pos_code[9:11])
    
    return SiloPosition(aisle, side, x, y, z)


def load_silo_from_csv(csv_path: str | Path, num_destinations: int = 40) -> SiloState:
    """
    Inicializa un silo vacío y lo pobla con las cajas desde el archivo CSV de hackathon (posicion, etiqueta).
    """
    silo = initialize_silo(num_destinations=num_destinations)
    
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pos_str = row['posicion'].strip()
            box_id_str = row['etiqueta'].strip()
            
            if not box_id_str:
                continue
                
            pos = parse_position_code(pos_str)
            box = parse_box(box_id_str)
            
            silo.grid[pos] = box
            box.position = pos
            silo.box_registry[box.box_id] = box
            silo.destination_index[box.destination].append(pos)
    
    return silo
