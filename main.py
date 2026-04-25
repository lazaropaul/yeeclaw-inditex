import os
from pathlib import Path

# Importaciones de tu modelo
from src.utils.csv_loader import load_silo_from_csv
from src.model.silo_state import Box

# Importaciones de los motores que hemos creado
from src.algorithms.storage import StorageEngine
from src.algorithms.retrieval import RetrievalEngine
from src.simulation.simulator import SimulationEngine, Event, EventType

def main():
    # 1. Calcular la ruta al archivo CSV
    project_root = Path(__file__).parent
    csv_path = project_root / 'data' / 'silo-semi-empty.csv'
    
    print("=" * 60)
    print("  INICIALIZANDO SILO DESDE CSV Y ARRANCANDO SIMULADOR")
    print("=" * 60)
    
    if not csv_path.exists():
        print(f"ERROR: Archivo CSV no encontrado en: {csv_path}")
        return
    
    print(f"Cargando datos desde: {csv_path.name}...")
    silo_state = load_silo_from_csv(csv_path)
    
    print("\nResumen del Estado del Silo (CSV):")
    print(f"  Posiciones Totales: {len(silo_state.grid)}")
    print(f"  Cajas Cargadas:     {silo_state.total_boxes()}")
    print(f"  Ocupación:          {silo_state.occupancy_rate():.2%}")
    print("-" * 60)
    
    # 2. Instanciar los Algoritmos (Cerebros)
    # Al pasarle 'silo_state', el StorageEngine debe inicializar sus trackers
    # de posiciones libres basados en la ocupación real del CSV.
    storage = StorageEngine(state=silo_state)
    retrieval = RetrievalEngine(state=silo_state, storage_engine=storage)
    
    # 3. Instanciar el Motor DES (El Director de Orquesta)
    sim = SimulationEngine(
        state=silo_state, 
        storage_engine=storage, 
        retrieval_engine=retrieval
    )
    
    # 4. Crear un Escenario de Prueba (Inyectar Eventos)
    print("\nInyectando eventos de prueba (Llegada de cajas nuevas)...")
    
    caja1 = Box("11111111111111111111", "RECEIVING", "PALLET-01", 1)
    caja2 = Box("22222222222222222222", "RECEIVING", "PALLET-01", 1)
    caja3 = Box("33333333333333333333", "RECEIVING", "PALLET-02", 2)
    
    sim.add_event(Event(timestamp=0.0, event_type=EventType.BOX_ARRIVAL, payload={'box': caja1}))
    sim.add_event(Event(timestamp=5.0, event_type=EventType.BOX_ARRIVAL, payload={'box': caja2}))
    sim.add_event(Event(timestamp=8.0, event_type=EventType.BOX_ARRIVAL, payload={'box': caja3}))
    
    # 5. ¡Ejecutar el motor de simulación!
    print("\n" + "=" * 60)
    sim.run()
    print("=" * 60)
    print("  SIMULACIÓN FINALIZADA")
    print("=" * 60)

if __name__ == "__main__":
    main()