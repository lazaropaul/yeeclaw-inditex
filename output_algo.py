import uuid
from typing import Optional
from models import Shuttle, Task, TaskType, Box, Location
import queue_manager as qm_mod
import warehouse as wh_mod
import input_algo as ia_mod

class OutputAlgorithm:
    @staticmethod
    def get_next_move(shuttle: Shuttle) -> Optional[Task]:
        # Gather all valid candidates
        relocations = qm_mod.queue.get_pending_relocation_tasks(shuttle.y_level)
        outbounds = qm_mod.queue.get_active_outbound_tasks(shuttle.y_level)
        inbounds = qm_mod.queue.get_pending_inbound_tasks(shuttle.y_level)
        
        all_candidates = relocations + outbounds + inbounds
        if not all_candidates:
            return None
            
        def get_pickup_x(task: Task) -> int:
            if task.task_type == TaskType.INBOUND:
                return 0 # Inbound boxes originate at the head
            return task.target_location.x

        best_task = None
        min_d = float('inf')
        
        for task in all_candidates:
            d = abs(shuttle.current_x - get_pickup_x(task))
            if d < min_d:
                min_d = d
                best_task = task
                
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
                    # IRA optimization: Pull the front box first since it perfectly aligns with our pallet needs
                    best_task = next(t for t in outbounds if t.box.id == front_box.id)
                else:
                    # BLOCKAGE: Generate immediate Relocation Task
                    # First, use input_repo basically to find a new empty slot
                    # Hack: temporarily remove front_box from grid so Input Algo doesn't see it there
                    wh_mod.warehouse.remove_box(front_loc)
                    reloc_inbound_sim = ia_mod.input_algorithm.assign_storage_location(front_box, preferred_y=shuttle.y_level)
                    wh_mod.warehouse.place_box(front_box, front_loc) # put it back
                    
                    # Remove the simulated inbound task we just made from the queue
                    qm_mod.queue.remove_task(reloc_inbound_sim.id)
                    
                    new_reloc_task = Task(
                        id=str(uuid.uuid4()),
                        task_type=TaskType.RELOCATION,
                        box=front_box,
                        target_location=front_loc, # pick up from here
                        dropoff_location=reloc_inbound_sim.target_location, # drop it here
                        is_active=True
                    )
                    qm_mod.queue.add_task(new_reloc_task)
                    
                    # Return the relocation task immediately as the highest priority interrupt
                    return new_reloc_task
                    
        return best_task

output_algorithm = OutputAlgorithm()
