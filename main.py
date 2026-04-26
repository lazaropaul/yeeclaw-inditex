import os
from pathlib import Path
import sys
import random
from src.model.silo_state import SiloState, initialize_silo
from src.simulation.simulator import SimulationEngine
from src.utils.csv_loader import load_silo_from_csv

sys.path.append(os.path.abspath(os.path.dirname(__file__)))



def generate_realistic_inbound(real_destinations: list, count: int = 2000):
    """
    Genera un flujo de cajas entrantes cuyos destinos coinciden EXACTAMENTE
    con los destinos que ya existen en el CSV, para forzar el cierre de pallets.
    """
    # Si por algún motivo el CSV estaba vacío, ponemos destinos por defecto
    if not real_destinations:
        real_destinations = [f"{i:08d}" for i in range(5)]

    for i in range(count):
        source = "3010028" # Almacén origen (Fijo según PDF)
        # Elegimos un destino real al azar para esta nueva caja
        destination = random.choice(real_destinations)
        bulk = f"{i:05d}"
        
        yield f"{source}{destination}{bulk}"

def main():
    print("🚀 HackUPC 2026 - Algorithms for Greater Logistics Agility")
    print("=" * 55)

    csv_path = Path("data/silo-semi-empty.csv") # Asegúrate de que la carpeta y el archivo existan
    
    if csv_path.exists():
        print(f"📂 Cargando estado inicial desde: {csv_path}...")
        silo = load_silo_from_csv(csv_path)
    else:
        print("⚠️ CSV no encontrado. Inicializando silo vacío...")
        silo = initialize_silo()

    print(f"✅ Silo listo: {silo.occupancy_rate():.1%} ocupado ({len(silo.box_registry)} cajas)")

    engine = SimulationEngine(silo)
    stream = generate_realistic_inbound(real_destinations=[box.destination for box in silo.box_registry.values()], count=2000)

    print("\n📥 Ejecutando simulación (Procesando CSV + Inbound nuevo)...")
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