import os
from pathlib import Path
from src.model.silo_state import initialize_silo

# Importaciones de los motores que hemos creado
from src.algorithms.storage import StorageEngine
from src.algorithms.retrieval import RetrievalEngine
from src.simulation.simulator import SimulationEngine

def generate_dummy_boxes(count=2000, num_destinations=5):
    """Generador de códigos de cajas ficticios para la prueba."""
    for i in range(count):
        source = "3010028"
        destination = f"{(i % num_destinations):08d}"
        bulk = f"{i:05d}"
        yield f"{source}{destination}{bulk}"

def main():
    print("🚀 HackUPC 2026 - Algorithms for Greater Logistics Agility")
    print("=" * 60)

    # 1. Inicializar Silo
    silo = initialize_silo()
    
    # 2. Instanciar los Motores (Algoritmos)
    storage = StorageEngine(state=silo)
    retrieval = RetrievalEngine(state=silo, storage_engine=storage)
    
    # 3. Arrancar Simulador (AQUÍ ESTÁ LA VARIABLE 'engine' QUE FALTABA)
    engine = SimulationEngine(state=silo, storage_engine=storage, retrieval_engine=retrieval)
    
    # Generamos flujo de cajas (Ej: 1200 cajas, unos 100 pallets potenciales)
    stream = generate_dummy_boxes(count=2000, num_destinations=5)
    
    # ¡A VOLAR! Simulamos 10 horas de tiempo de almacén máximo (36000 segundos)
    print("Iniciando inyección de cajas y optimización en tiempo real...")
    engine.run(stream, max_time=1000) 

    # 4. Métricas Finales y Transformación a KPIs Inditex
    simulated_seconds = engine.global_time
    simulated_hours = simulated_seconds / 3600.0
    
    # 1 Pallet completo = 12 cajas extraídas
    pallets_completed = engine.metrics.get("boxes_retrieved", 0) // 12
    
    if pallets_completed > 0:
        avg_time_pallet = simulated_seconds / pallets_completed 
        throughput = pallets_completed / simulated_hours
    else:
        avg_time_pallet = 0.0
        throughput = 0.0

    total_pallets_posibles = engine.metrics.get("boxes_stored", 0) // 12
    if total_pallets_posibles > 0:
        full_pallet_pct = (pallets_completed / total_pallets_posibles) * 100.0
    else:
        full_pallet_pct = 0.0

    # Dashboard Final
    print("\n" + "=" * 55)
    print("📊 FINAL METRICS (KPIs Inditex)")
    print("=" * 55)
    print(f"📦 Pallets Completed:      {pallets_completed}")
    print(f"📈 Full Pallets (%):       {full_pallet_pct:.1f}%")
    print(f"⏱️  Avg Time/Pallet:        {avg_time_pallet:.2f}s")
    print(f"⚡ Throughput:             {throughput:.2f} pallets/hour")
    print(f"📉 Final Silo Occupancy:   {silo.occupancy_rate():.1%}")
    print(f"⏱️  Simulated Time:         {simulated_hours:.2f} hours")

if __name__ == "__main__":
    main()