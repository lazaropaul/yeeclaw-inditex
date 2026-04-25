import os
from pathlib import Path
from src.model.silo_state import initialize_silo
from src.simulation.simulator import SimulationEngine
from src.algorithms.pallet_optimizer import PalletOptimizer

def generate_dummy_boxes(count=1200, num_destinations=10):
    for i in range(count):
        source = "3010028"
        destination = f"{(i % num_destinations):08d}"
        bulk = f"{i:05d}"
        yield f"{source}{destination}{bulk}"

def main():
    print("🚀 HackUPC 2026 - Algorithms for Greater Logistics Agility")
    print("=" * 55)

    silo = initialize_silo()
    print(f"✅ Silo initialized: {silo.occupancy_rate():.1%} occupied")
    
    engine = SimulationEngine(silo)
    stream = generate_dummy_boxes(count=1200, num_destinations=10)
    
    print("\n📥 Phase 1: Entry Assignment (MILP Storage)...")
    engine.run(stream, max_time=12000) 
    print(f"✅ Phase 1 completed. Boxes stored: {silo.total_boxes()}")
    
    print("\n📤 Phase 2: Pallet Dispatching (Dynamic Priority Retrieval)...")
    pallet_opt = PalletOptimizer(silo)
    pallet_opt.optimize_global_output()

    # 📊 Métricas finales robustas
    actual_simulated_seconds = silo.current_time
    metrics = pallet_opt.get_metrics(total_simulated_seconds=actual_simulated_seconds)
    
    remaining_boxes = silo.total_boxes()
    potential_pallets = remaining_boxes // 12
    total_pallets_evaluated = metrics["pallets_completed"] + potential_pallets
    full_pallet_pct = (metrics["pallets_completed"] / total_pallets_evaluated * 100) \
                      if total_pallets_evaluated > 0 else 0

    print("\n" + "=" * 55)
    print("📊 FINAL METRICS (KPIs Inditex)")
    print("=" * 55)
    print(f"📦 Pallets Completed:      {metrics['pallets_completed']}")
    print(f"📈 Full Pallets (%):       {full_pallet_pct:.1f}%")
    print(f"⏱️  Avg Time/Pallet:       {metrics['avg_time_per_pallet']:.2f}s")
    print(f"⚡ Throughput:             {metrics['throughput_pallets_hour']:.2f} pallets/hour")
    print(f"📉 Final Silo Occupancy:   {silo.occupancy_rate():.1%}")
    print(f"⏱️  Simulated Time:        {actual_simulated_seconds/3600:.2f} hours")
    print("=" * 55)

if __name__ == "__main__":
    main()