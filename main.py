import os
from pathlib import Path
from src.model.silo_state import SiloState, initialize_silo
from src.simulation.simulator import SimulationEngine


def generate_dummy_boxes(count=2000, num_destinations=5):
    for i in range(count):
        source = "3010028"
        destination = f"{(i % num_destinations):08d}"
        bulk = f"{i:05d}"
        yield f"{source}{destination}{bulk}"

def main():
    print("🚀 HackUPC 2026 - Algorithms for Greater Logistics Agility")
    print("=" * 55)

    silo = initialize_silo()      
    print(f"✅ Silo inicializado: {silo.occupancy_rate():.1%} ocupado")

    engine = SimulationEngine(silo)
    stream = generate_dummy_boxes(count=2000, num_destinations=5)

    print("\n📥 Fase 1 y 2: Almacenamiento + Recuperación continua con Trip Chaining...")
    engine.run(stream, max_time=1000)  # Simular 1000 segundos

    # Métricas finales
    actual_time = silo.current_time
    hours = actual_time / 3600.0
    throughput = engine.metrics["pallets_completed"] / hours if hours > 0 else 0

    print("\n" + "=" * 55)
    print("📊 MÉTRICAS FINALES")
    print("=" * 55)
    print(f"📦 Pallets completados:   {engine.metrics['pallets_completed']}")
    print(f"📦 Cajas almacenadas:     {engine.metrics['boxes_stored']}")
    print(f"📤 Cajas recuperadas:     {engine.metrics['boxes_retrieved']}")
    print(f"⚡ Trip chainings:        {engine.metrics['trip_chains']}")
    print(f"⏱️  Throughput:           {throughput:.2f} pallets/hora")
    print(f"📉 Ocupación final silo:  {silo.occupancy_rate():.1%}")
    print(f"⏱️  Tiempo simulado:      {actual_time:.1f}s ({hours:.2f}h)")
    print("=" * 55)

if __name__ == "__main__":
    main()