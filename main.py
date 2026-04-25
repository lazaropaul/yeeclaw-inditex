import sys
import os
import random

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from models.model import Box
from simulator.engine import WarehouseSimulator
from algorithms.advanced import OptimizedInputAlgorithm, OptimizedOutputAlgorithm, OptimizedRelocationAlgorithm

def main():
    print("Initializing Warehouse Simulator with Advanced Algorithms...")
    input_algo = OptimizedInputAlgorithm()
    output_algo = OptimizedOutputAlgorithm()
    reloc_algo = OptimizedRelocationAlgorithm()
    
    sim = WarehouseSimulator(
        input_algo=input_algo,
        output_algo=output_algo,
        relocation_algo=reloc_algo
    )

    # Generate some mock data
    # Box code: 20-digit string
    # We want to simulate ~1000 boxes per hour.
    # 1000 boxes / 12 boxes per pallet = 83 full pallets + 4 noise boxes.
    print("Generating incoming boxes (1000 boxes/hr rate)...")
    boxes = []
    
    num_full_pallets = 83
    destinations = [f"0122{i:04d}" for i in range(1, num_full_pallets + 1)]
    
    for dest in destinations:
        for i in range(12):
            boxes.append(Box(code=f"1111111{dest}{i:05d}"))
            
    # Add 4 noise boxes to reach exactly 1000 incoming boxes
    for i in range(4):
        boxes.append(Box(code=f"111111199999999{i:05d}"))
        
    # Shuffle the arrival order to simulate realistic random inbound warehouse streams
    # rather than receiving them perfectly batched by pallet.
    random.shuffle(boxes)

    print(f"Total incoming boxes: {len(boxes)}")
    print("Running simulation...")
    sim.run(boxes)
    
    report = sim.report()
    print("\n--- Simulation Report ---")
    for k, v in report.items():
        if isinstance(v, float):
            print(f"{k}: {v:.2f}")
        else:
            print(f"{k}: {v}")

if __name__ == "__main__":
    main()
