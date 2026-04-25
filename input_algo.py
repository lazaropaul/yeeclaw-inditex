import uuid
from models import Box, Location, Task, TaskType
import warehouse as wh_mod
import queue_manager as qm_mod

class InputAlgorithm:
    @staticmethod
    def assign_storage_location(box: Box, preferred_y: int = 1) -> Task:
        """
        Finds the optimal storage location for the incoming box using:
        1. Class-Based Storage: Strictly evaluates from X=1 outwards to minimize D.
        2. Association Rule Mining (ARM): Forces identical destination codes together in the Z-axis.
        """
        # Class-Based loop: forces items into lowest possible X positions first.
        best_loc = None
        
        # We will scan Y starting from preferred_y, then expanding out if full
        # But for hackathon simulation, let's just do a simple nested loop logic.
        for y in range(1, wh_mod.warehouse.max_y + 1):
            for x in range(1, wh_mod.warehouse.max_x + 1):
                # Try to place at Z=2 first
                loc_z2 = Location(x=x, y=y, z=2)
                loc_z1 = Location(x=x, y=y, z=1)
                
                # Condition 1: Both Z=1 and Z=2 are empty
                if wh_mod.warehouse.is_empty(loc_z2) and wh_mod.warehouse.is_empty(loc_z1):
                    best_loc = loc_z2
                    break
                
                # Condition 2: Z=2 is occupied but Z=1 is empty
                if not wh_mod.warehouse.is_empty(loc_z2) and wh_mod.warehouse.is_empty(loc_z1):
                    # Z-Axis Homogeneity Check!
                    rear_box = wh_mod.warehouse.get_box(loc_z2)
                    if rear_box and rear_box.destination_code == box.destination_code:
                        best_loc = loc_z1
                        break
            if best_loc:
                break
                
        if not best_loc:
            raise Exception("Warehouse is full or no homogeneously valid slots remain!")
            
        # Reserve it physically so next box doesn't take it
        wh_mod.warehouse.reserve(best_loc)
            
        # Create Task
        task = Task(
            id=str(uuid.uuid4()),
            task_type=TaskType.INBOUND,
            box=box,
            target_location=best_loc
        )
        
        # Add task to queue
        qm_mod.queue.add_task(task)
        
        # Note: Box is physically "placed" in the warehouse state when the Output Algorithm 
        # actually completes the shuttle move, not here!
        return task

input_algorithm = InputAlgorithm()
