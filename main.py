import os
from pathlib import Path
from src.utils.csv_loader import load_silo_from_csv

def main():
    # Calcular la ruta al archivo CSV
    project_root = Path(__file__).parent
    csv_path = project_root / 'data' / 'silo-semi-empty.csv'
    
    print("=" * 60)
    print("  INICIALIZANDO SILO DESDE CSV")
    print("=" * 60)
    
    if not csv_path.exists():
        print(f"ERROR: Archivo CSV no encontrado en: {csv_path}")
        return
    
    print(f"Cargando datos desde: {csv_path.name}...")
    silo_state = load_silo_from_csv(csv_path)
    
    print("\nResumen del Estado del Silo:")
    print(f"  Posiciones Totales: {len(silo_state.grid)}")
    print(f"  Cajas Cargadas:     {silo_state.total_boxes()}")
    print(f"  Ocupación:          {silo_state.occupancy_rate():.2%}")
    print(f"  Shuttles Activos:   {len(silo_state.shuttles)}")
    
    print("\nComprobando reglas operativas básicas...")
    free_positions = silo_state.get_free_positions()
    print(f"  Posiciones libres que cumplen regla Z (para colocar): {len(free_positions)}")
    
    print("\nProceso exitoso. El sistema está listo para pruebas de algoritmos.")
    print("=" * 60)

if __name__ == "__main__":
    main()
