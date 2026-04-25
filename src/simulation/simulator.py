import heapq
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Iterator, List
from src.model.silo_state import SiloState, Box, SiloPosition
from src.algorithms.milp_optimizer import MilpOptimizer
from src.algorithms.pallet_manager import PalletManager
from src.algorithms.retrieval_optimizer import RetrievalOptimizer

class EventType(Enum):
    BOX_ARRIVAL = auto()
    OPERATION_COMPLETE = auto()

@dataclass(order=True)
class Event:
    timestamp: float
    event_type: EventType = field(compare=False)
    payload: dict = field(compare=False, default_factory=dict)

class SimulationEngine:
    def __init__(self, state: SiloState):
        self.state = state
        self.events = []
        self.pending_batch: List[Box] = []
        self.optimizer = MilpOptimizer(state)
        self.batch_size = 5 # Optimiza cada 5 cajas
        self.pallet_manager = PalletManager(state)
        self.metrics = {"boxes_in": 0, "pallets_out": 0}
        self.retrieval_optimizer = RetrievalOptimizer(state)
        self.metrics["pallets_completed"] = 0
        self.active_pallets_count = 0
    
    def schedule(self, time_offset: float, type: EventType, payload: dict = None):
        ts = self.state.current_time + time_offset
        heapq.heappush(self.events, Event(ts, type, payload or {}))

    def run(self, box_stream: Iterator[Box], max_time: float = 3600):
        # Programar primera llegada
        self.schedule(0, EventType.BOX_ARRIVAL)
        
        self.box_iter = box_stream

        while self.events:
            event = heapq.heappop(self.events)
            if event.timestamp > max_time:
                break
            
            self.state.current_time = event.timestamp
            
            if event.event_type == EventType.BOX_ARRIVAL:
                self._handle_arrival()
            elif event.event_type == EventType.OPERATION_COMPLETE:
                self._handle_operation(event.payload)

    def _handle_arrival(self):
        try:
            box_code = next(self.box_iter)
            box = Box(box_id=box_code, origin=box_code[:7], destination=box_code[7:15], bulk_number=box_code[15:20])
            
            self.state.incoming_queue.append(box)
            self.pending_batch.append(box)
            
            self.schedule(10.0, EventType.BOX_ARRIVAL)

            if len(self.pending_batch) >= self.batch_size:
                self._solve_milp_batch()
                
        except StopIteration:
            if self.pending_batch:
                self._solve_milp_batch()

    def _solve_milp_batch(self):
        assignment = self.optimizer.optimize_storage(self.pending_batch)
        
        for box, pos in assignment: 
            shuttle = self.state.shuttles[pos.y]
            travel_time = shuttle.travel_time(pos.x)
            start_time = max(self.state.current_time, shuttle.busy_until)
            end_time = start_time + travel_time
            
            shuttle.busy_until = end_time
            shuttle.current_x = pos.x
            
            self.state.place_box(box, pos)
            self.metrics["boxes_in"] += 1
            self.pallet_manager.try_dispatch_if_ready()
            
        self.pending_batch.clear()
    
    def try_dispatch_pallet(self):
        for dest, positions in self.state.destination_index.items():
            if self.active_pallets_count >= 8: break # Límite robots (PDF)
            
            boxes = [self.state.grid[p] for p in positions if self.state.grid[p] is not None]
            if len(boxes) >= 12:
                self.active_pallets_count += 1
                target_boxes = boxes[:12]
                
                print(f"\n Pallet reservado: {dest} | Shuttles optimizando secuencia...")
                
                sequence = self.retrieval_optimizer.optimize_pallet_retrieval(target_boxes)
                
                for box, t_start, reloc in sequence:
                    # Actualizar estado
                    self.state.remove_box(box.position)
                    self.state.shuttles[box.position.y].busy_until = t_start + 10 + abs(box.position.x)
                    self.state.shuttles[box.position.y].current_x = 0.0 
                    
                    print(f"   ⏱️  {box.box_id[-5:]} | Inicio: {t_start:.1f}s | Reubicación Z: {'Sí' if reloc else 'No'}")
                
                self.metrics["pallets_completed"] += 1
                self.active_pallets_count -= 1
                return # Procesa un pallet por ciclo para estabilidad

    def _handle_operation(self, payload):
        pass # Lógica de palletización futura