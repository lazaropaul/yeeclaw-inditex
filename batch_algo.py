import math
import random
from typing import List, Set
import warehouse as wh_mod

class SimulatedAnnealingBatcher:
    @staticmethod
    def get_optimal_batch(pallets_waiting: List[str], num_needed: int) -> List[str]:
        """
        Uses Simulated Annealing to select `num_needed` pallets from `pallets_waiting`
        that minimizes the variance of box distribution across Y-levels (balancing shuttle workload).
        """
        if not pallets_waiting or num_needed <= 0:
            return []
            
        if len(pallets_waiting) <= num_needed:
            return list(pallets_waiting)
            
        # Precompute the Y-distribution and X-distance for every waiting pallet
        pallet_y_counts = {p: {y: 0 for y in range(1, wh_mod.warehouse.max_y + 1)} for p in pallets_waiting}
        pallet_x_sum = {p: 0 for p in pallets_waiting}
        
        for loc_tuple, box in wh_mod.warehouse.grid.items():
            if box.destination_code in pallet_y_counts:
                x = loc_tuple[0]
                y = loc_tuple[1]
                pallet_y_counts[box.destination_code][y] += 1
                pallet_x_sum[box.destination_code] += x
                
        def calculate_cost(batch: List[str]) -> float:
            total_y_counts = {y: 0 for y in range(1, wh_mod.warehouse.max_y + 1)}
            total_x_dist = 0
            
            for p in batch:
                total_x_dist += pallet_x_sum[p]
                for y, count in pallet_y_counts[p].items():
                    total_y_counts[y] += count
            
            # primary cost: variance across Y levels to ensure shuttles are balanced
            counts = list(total_y_counts.values())
            mean = sum(counts) / len(counts)
            variance = sum((c - mean) ** 2 for c in counts) / len(counts)
            
            # secondary cost: total X travel distance
            # combining them: multiply variance so it dominates, but X distance breaks ties / optimizes
            return (variance * 10000.0) + total_x_dist

        # Initial random batch
        current_batch = random.sample(pallets_waiting, num_needed)
        current_cost = calculate_cost(current_batch)
        
        best_batch = list(current_batch)
        best_cost = current_cost
        
        # SA Parameters
        T = 100.0
        T_min = 0.1
        alpha = 0.9
        
        while T > T_min:
            # Generate neighbor: swap one element
            neighbor_batch = list(current_batch)
            swap_out_idx = random.randrange(num_needed)
            
            # Find a candidate not in current batch
            available_for_swap = [p for p in pallets_waiting if p not in current_batch]
            if not available_for_swap:
                break
                
            swap_in = random.choice(available_for_swap)
            neighbor_batch[swap_out_idx] = swap_in
            
            neighbor_cost = calculate_cost(neighbor_batch)
            
            # Accept if better
            if neighbor_cost < current_cost:
                current_batch = neighbor_batch
                current_cost = neighbor_cost
                if neighbor_cost < best_cost:
                    best_batch = list(neighbor_batch)
                    best_cost = neighbor_cost
            else:
                # Accept worse with probability
                delta = neighbor_cost - current_cost
                probability = math.exp(-delta / T)
                if random.random() < probability:
                    current_batch = neighbor_batch
                    current_cost = neighbor_cost
                    
            T *= alpha
            
        return best_batch

batch_algo = SimulatedAnnealingBatcher()
