import sys
import os

# Add the 'models' directory to path to allow importing from model.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.model import Simulator, Box, Position, Shuttle, Pallet, PalletStatus, MAX_ACTIVE_PALLETS, PALLET_SIZE

class WarehouseSimulator(Simulator):
    def run(self, incoming_boxes: list[Box]) -> None:
        self.boxes_received = len(incoming_boxes)
        input_queue = incoming_boxes[:]
        
        step = 0
        
        while input_queue or sum(1 for p in self.pallets.values() if p.status != PalletStatus.COMPLETE) > 0:
            step += 1
            action_taken = False
            
            # --- 1. Manage Active Pallets ---
            # Active pallets are those with RESERVED status.
            open_pallets = {k: v for k, v in self.pallets.items() if v.status == PalletStatus.OPEN}
            active_count = sum(1 for p in self.active_pallets)
            
            # Promote open pallets to reserved if there is capacity
            if active_count < MAX_ACTIVE_PALLETS and open_pallets:
                new_actives = self.output_algo.select_active_pallets(open_pallets)
                for p in new_actives:
                    if active_count < MAX_ACTIVE_PALLETS:
                        p.status = PalletStatus.RESERVED
                        self.active_pallets.append(p)
                        active_count += 1
            
            # --- 2. Outbound Step ---
            if self.active_pallets:
                retrieval = self.output_algo.next_retrieval(self.active_pallets, self.silo, self.shuttles)
                if retrieval:
                    action_taken = True
                    target_box, pos = retrieval
                    
                    shuttle = self._get_shuttle(pos.aisle, pos.side, pos.y)
                    
                    # Handle Z=2 Reshuffling if needed
                    if pos.z == 2:
                        z1_pos = Position(pos.aisle, pos.side, pos.x, pos.y, 1)
                        if not self.silo.is_empty(z1_pos):
                            # Reshuffle required
                            blocking_box = self.silo.remove(z1_pos)
                            new_pos = self.relocation_algo.relocation_target(blocking_box, self.silo)
                            self.silo.place(new_pos, blocking_box)
                            # Time penalty: pickup blocking box + travel + drop
                            pickup_time = 10 + abs(shuttle.current_x - pos.x)
                            drop_time = 10 + abs(new_pos.x - pos.x)
                            shuttle.current_time = max(shuttle.current_time, self.current_time) + pickup_time + drop_time
                            shuttle.current_x = new_pos.x
                            
                    # Remove the target box
                    removed_box = self.silo.remove(pos)
                    assert target_box == removed_box, f"Expected {target_box}, got {removed_box} at {pos}"
                    
                    # Add to shuttle work: Dual Command Cycle compatible logic
                    pickup_time = 10 + abs(shuttle.current_x - pos.x)
                    drop_time = 10 + abs(0 - pos.x) # Dropping to head
                    shuttle.current_time += pickup_time + drop_time
                    shuttle.current_x = 0 # Outbound ends at head
                    
                    # Update pallet
                    # Find the pallet that claims this box
                    assigned_pallet = None
                    for p in self.active_pallets:
                        if target_box in p.boxes:
                            assigned_pallet = p
                            break
                    
                    if assigned_pallet:
                        # Rather than modifying assigned_pallet.boxes, we verify if any of its boxes are still in the physical silo.
                        if all(self.silo.find_box(b) is None for b in assigned_pallet.boxes):
                            assigned_pallet.status = PalletStatus.COMPLETE
                            self.active_pallets.remove(assigned_pallet)
                            self.completed_pallets.append(assigned_pallet)
                    else:
                        print(f"Warning: Retrieved box {target_box} not found in any active pallet.")

            # --- 3. Inbound Step ---
            # To ensure the engine progresses without completely emptying the inbound buffer before starting outbound,
            # we can process one box at a time
            if input_queue:
                box = input_queue.pop(0)
                pos = self.input_algo.assign_position(box, self.silo)
                self.silo.place(pos, box)
                
                shuttle = self._get_shuttle(pos.aisle, pos.side, pos.y)
                pickup_time = 10 + abs(shuttle.current_x - 0) # Picking from head
                drop_time = 10 + abs(pos.x - 0)
                shuttle.current_time += pickup_time + drop_time
                shuttle.current_x = pos.x # Inbound ends at destination
                
                # Assign to a pallet or create a new one
                dest = box.destination
                found_pallet = None
                for p_id, p in self.pallets.items():
                    if p.destination == dest and p.status == PalletStatus.OPEN and not p.is_full:
                        found_pallet = p
                        break
                        
                if found_pallet is None:
                    p_id = f"{dest}_{len(self.pallets)}"
                    found_pallet = Pallet(destination=dest)
                    self.pallets[p_id] = found_pallet
                    
                found_pallet.add_box(box)
                action_taken = True
                
            if not action_taken:
                # Deadlock prevention if both algorithms stall
                print("Warning: Simulation deadlocked or no valid moves. Aborting run().")
                break
                
        # Total simulation makespan is the maximum time any single shuttle spent working
        self.current_time = max(s.current_time for s in self.shuttles)

    def _get_shuttle(self, aisle: int, side: int, y: int) -> Shuttle:
        for s in self.shuttles:
            if s.aisle == aisle and s.y == y:
                return s
        raise ValueError(f"Shuttle not found for aisle={aisle}, y={y}")
