import uuid
from typing import Optional
from models import Shuttle, Task, TaskType, Box, Location
import queue_manager as qm_mod
import warehouse as wh_mod
import input_algo as ia_mod

class OutputAlgorithm:
    @staticmethod
    @staticmethod
    def _find_nearest_neighbor_empty(start_x: int, y: int) -> Location:
        """Finds the absolute closest empty location using multidirectional NN expansion."""
        max_x = wh_mod.warehouse.max_x
        # We start checking right at the neighborhood
        for offset in range(1, max_x):
            # Check left & right
            candidates_x = [start_x - offset, start_x + offset]
            for cx in candidates_x:
                if 1 <= cx <= max_x:
                    # Prefer Z=2 for density
                    z2 = Location(x=cx, y=y, z=2)
                    if wh_mod.warehouse.is_empty(z2):
                        return z2
                    z1 = Location(x=cx, y=y, z=1)
                    if wh_mod.warehouse.is_empty(z1):
                        return z1
        # Fallback to standard input algo if grid is dense
        return None

    @staticmethod
    def get_next_move(shuttle: Shuttle) -> Optional[Task]:
        # Gather all valid candidates
        relocations = qm_mod.queue.get_pending_relocation_tasks(shuttle.y_level)
        outbounds = qm_mod.queue.get_active_outbound_tasks(shuttle.y_level)
        inbounds = qm_mod.queue.get_pending_inbound_tasks(shuttle.y_level)
        
        # Priority override: ALWAYS do active Relocations first to clear aisles
        if relocations:
            all_candidates = relocations
        else:
            all_candidates = outbounds + inbounds
            
        if not all_candidates:
            return None
            
        def get_pickup_x(task: Task) -> int:
            if task.task_type == TaskType.INBOUND: return 0
            return task.target_location.x

        def get_dropoff_x(task: Task) -> int:
            if task.task_type == TaskType.INBOUND: return task.target_location.x
            if task.task_type == TaskType.OUTBOUND: return 0
            return task.dropoff_location.x

        best_task = None
        min_cost = float('inf')
        
        # TSP Proxy: 2-step Deep Lookahead Sequence evaluation
        for task1 in all_candidates:
            pickup1 = get_pickup_x(task1)
            dropoff1 = get_dropoff_x(task1)
            
            c1 = abs(shuttle.current_x - pickup1) + abs(pickup1 - dropoff1)
            
            remaining = [t for t in all_candidates if t != task1]
            best_c2 = float('inf')
            
            if not remaining:
                # No tasks left, assume return to 0
                best_c2 = abs(dropoff1 - 0)
            else:
                for task2 in remaining:
                    pickup2 = get_pickup_x(task2)
                    dropoff2 = get_dropoff_x(task2)
                    c2 = abs(dropoff1 - pickup2) + abs(pickup2 - dropoff2)
                    
                    # 1 more shallow lookahead to avoid getting stranded
                    dist_to_third = 0
                    if len(remaining) > 1:
                        dist_to_third = min([abs(dropoff2 - get_pickup_x(t3)) for t3 in remaining if t3 != task2])
                    else:
                        dist_to_third = abs(dropoff2 - 0)
                        
                    if c2 + dist_to_third < best_c2:
                        best_c2 = c2 + dist_to_third
                        
            total_cost = c1 + best_c2
            if total_cost < min_cost:
                min_cost = total_cost
                best_task = task1
                
        # Blockage Check for OUTBOUND at Z=2
        if best_task.task_type == TaskType.OUTBOUND and best_task.target_location.z == 2:
            front_loc = Location(x=best_task.target_location.x, y=best_task.target_location.y, z=1)
            front_box = wh_mod.warehouse.get_box(front_loc)
            
            if front_box is not None:
                is_front_active = any(
                    t.task_type == TaskType.OUTBOUND and t.box.id == front_box.id and t.is_active 
                    for t in outbounds
                )
                if is_front_active:
                    # Pull front box first
                    best_task = next(t for t in outbounds if t.box.id == front_box.id)
                else:
                    # BLOCKAGE: Generate Relocation via Nearest Neighbor
                    nn_empty_loc = OutputAlgorithm._find_nearest_neighbor_empty(front_loc.x, shuttle.y_level)
                    
                    if not nn_empty_loc:
                        # Fallback mathematically finding the worst case via input_algo
                        wh_mod.warehouse.remove_box(front_loc)
                        fallback_task = ia_mod.input_algorithm.assign_storage_location(front_box, preferred_y=shuttle.y_level)
                        nn_empty_loc = fallback_task.target_location
                        wh_mod.warehouse.place_box(front_box, front_loc)
                        qm_mod.queue.remove_task(fallback_task.id)

                    new_reloc_task = Task(
                        id=str(uuid.uuid4()),
                        task_type=TaskType.RELOCATION,
                        box=front_box,
                        target_location=front_loc, 
                        dropoff_location=nn_empty_loc,
                        is_active=True
                    )
                    qm_mod.queue.add_task(new_reloc_task)
                    
                    # Reserve the dropoff physically so others don't claim it
                    wh_mod.warehouse.reserve(nn_empty_loc)
                    
                    return new_reloc_task
                    
        return best_task

output_algorithm = OutputAlgorithm()
