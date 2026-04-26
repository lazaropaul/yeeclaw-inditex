import heapq
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, List, Iterator, Set, Dict, Optional

from src.model.silo_state import SiloState, Box, SiloPosition
from src.algorithms.storage import StorageEngine
from src.algorithms.retrieval import RetrievalEngine, Task


class EventType(Enum):
    BOX_ARRIVAL = auto()
    SHUTTLE_TASK_COMPLETE = auto()

@dataclass(order=True)
class Event:
    timestamp: float
    event_type: EventType = field(compare=False)
    payload: dict = field(compare=False, default_factory=dict)


class ShuttleState:
    IDLE = "IDLE"
    STORING = "STORING"
    RETRIEVING = "RETRIEVING"
    RELOCATING = "RELOCATING"
    RETURNING_EMPTY = "RETURNING_EMPTY"


class DummyPallet:
    def __init__(self, dest: str, boxes: List[Box]):
        self.destination = dest
        self.pending_boxes = {b.box_id: b.position for b in boxes if b.position is not None}


class SimulationEngine:
    def __init__(self, state: SiloState):
        self.state = state
        self.storage = StorageEngine(state)
        self.retrieval = RetrievalEngine(state)
        self.shuttles = state.shuttles  # dict (aisle, y) -> Shuttle
        self.events: List[Event] = []
        self.inbound_queues: Dict[tuple, List[tuple]] = {(a, y): [] for a in state.AISLES for y in state.Y_RANGE}
        self.active_pallets: List[DummyPallet] = []
        self.active_destinations: Set[str] = set()
        self.metrics = {
            "boxes_stored": 0,
            "boxes_retrieved": 0,
            "pallets_completed": 0,
            "trip_chains": 0
        }
        self.box_stream = None

    def add_event(self, event: Event):
        heapq.heappush(self.events, event)

    def run(self, box_stream: Iterator[str], max_time: float = 3600):
        print("--- Iniciando Simulación Continua con Trip Chaining ---")
        self.box_stream = box_stream
        self._schedule_next_arrival()

        while self.events and self.state.current_time <= max_time:
            event = heapq.heappop(self.events)
            self.state.current_time = event.timestamp
            if event.event_type == EventType.BOX_ARRIVAL:
                self._handle_box_arrival(event.payload)
            elif event.event_type == EventType.SHUTTLE_TASK_COMPLETE:
                self._handle_task_complete(event.payload)

    # ------------------------------------------------------------
    # Llegada de cajas
    # ------------------------------------------------------------
    def _schedule_next_arrival(self):
        try:
            box_code = next(self.box_stream)
            box = Box(box_id=box_code,
                      origin=box_code[:7],
                      destination=box_code[7:15],
                      bulk_number=box_code[15:20])
            self.add_event(Event(self.state.current_time + 0.5,
                                 EventType.BOX_ARRIVAL, {'box': box}))
        except StopIteration:
            pass

    def _handle_box_arrival(self, payload: dict):
        self._schedule_next_arrival()
        box = payload['box']
        pos = self.storage.assign_position(box)
        if pos:
            self.inbound_queues[(pos.aisle, pos.y)].append((box, pos))
            shuttle = self.shuttles[(pos.aisle, pos.y)]
            if not shuttle.is_busy:
                self._assign_next_work(shuttle)
        self._check_and_activate_pallets()

    def _check_and_activate_pallets(self):
            for dest, positions in list(self.state.destination_index.items()):
                if len(self.active_pallets) >= 8:
                    break
                if dest in self.active_destinations:
                    continue
                boxes = [self.state.grid[p] for p in positions if self.state.grid.get(p) is not None]
                if len(boxes) >= 12:
                    # 🇬🇧 INGLÉS: Nuevo pallet
                    print(f"[{self.state.current_time:.1f}s] 📦 NEW ACTIVE PALLET: Dest {dest}")
                    
                    best_boxes = sorted(boxes, key=lambda b: (b.position.z, b.position.x))
                    pallet = DummyPallet(dest, best_boxes[:12]) 
                    self.active_pallets.append(pallet)
                    self.active_destinations.add(dest)
                    for shuttle in self.shuttles.values():
                        if not shuttle.is_busy:
                            self._assign_next_work(shuttle)

    # ------------------------------------------------------------
    # Finalización de tareas
    # ------------------------------------------------------------
    def _handle_task_complete(self, payload: dict):
            shuttle = payload['shuttle']
            shuttle.is_busy = False
            
            if payload.get('was_retrieval', False):
                self.metrics["boxes_retrieved"] += 1
                retrieved_box_id = payload.get('box_id')
                
                for pallet in self.active_pallets[:]:
                    if retrieved_box_id in pallet.pending_boxes:
                        del pallet.pending_boxes[retrieved_box_id]
                    
                    if not pallet.pending_boxes:
                        self.active_pallets.remove(pallet)
                        self.active_destinations.discard(pallet.destination)
                        self.metrics["pallets_completed"] += 1
                        # 🇬🇧 INGLÉS: Pallet completado
                        print(f"[{self.state.current_time:.1f}s] ✅ PALLET COMPLETED: Dest {pallet.destination}")
                        self._check_and_activate_pallets()
                        
            self._assign_next_work(shuttle)

    # ------------------------------------------------------------
    # Asignación de trabajo con Trip Chaining
    # ------------------------------------------------------------
    def _assign_next_work(self, shuttle: Any):
            if shuttle.pending_ops:
                task = shuttle.pending_ops.popleft()
                self._dispatch_outbound(shuttle, task)
                return

            # 2. Trip chaining
            if shuttle.current_x > 0:
                tasks = self.retrieval.get_next_tasks(shuttle.y_level, shuttle.current_x,
                                                    self.active_pallets, shuttle.aisle)
                if tasks:
                    first_task = tasks[0]
                    box = self.state.grid.get(first_task.source)
                    
                    if box:
                        box_info = f"📦 ID:{box.box_id[-5:]} Dest:{box.destination}" 
                    else:
                        box_info = "📦 (Blocked/Relocating)"

                    # 🌟 FORMATO CLARO DE POSICIÓN
                    pos = first_task.source
                    pos_str = f"A:{pos.aisle} S:{pos.side} X:{pos.x:03d} Y:{pos.y} Z:{pos.z}"

                    print(f"[{self.state.current_time:.1f}s] ⚡ TRIP CHAINING! "
                        f"Shuttle A:{shuttle.aisle} Y:{shuttle.y_level} from X:{shuttle.current_x:.0f} "
                        f"-> 🎯 {first_task.task_type} {box_info} at {pos_str}")
                    
                    self.metrics["trip_chains"] += 1
                    for t in tasks:
                        shuttle.pending_ops.append(t)
                    self._dispatch_outbound(shuttle, shuttle.pending_ops.popleft())
                    return
                else:
                    self._return_to_head(shuttle)
                    return

            # 3. En cabeza (x=0): priorizar inbound
            if self.inbound_queues.get((shuttle.aisle, shuttle.y_level), []):
                box, pos = self.inbound_queues[(shuttle.aisle, shuttle.y_level)].pop(0)
                self._dispatch_inbound(shuttle, box, pos)
                return

            # 4. En cabeza sin inbound: buscar outbound
            tasks = self.retrieval.get_next_tasks(shuttle.y_level, 0, self.active_pallets, shuttle.aisle)
            if tasks:
                first_task = tasks[0]
                box = self.state.grid.get(first_task.source)
                if box:
                    # 🌟 FORMATO CLARO DE POSICIÓN
                    pos = first_task.source
                    pos_str = f"A:{pos.aisle} S:{pos.side} X:{pos.x:03d} Y:{pos.y} Z:{pos.z}"
                    
                    print(f"[{self.state.current_time:.1f}s] 📤 OUTBOUND: Shuttle A:{shuttle.aisle} Y:{shuttle.y_level} from Head (X:0) "
                        f"-> 🎯 RETRIEVE 📦 ID:{box.box_id[-5:]} Dest:{box.destination} at {pos_str}")
                
                for t in tasks:
                    shuttle.pending_ops.append(t)
                self._dispatch_outbound(shuttle, shuttle.pending_ops.popleft())

    # ------------------------------------------------------------
    # Despacho de operaciones con tiempos correctos
    # ------------------------------------------------------------
    def _dispatch_inbound(self, shuttle: Any, box: Box, target_pos: SiloPosition):
        if not self.state.can_place_at(target_pos):
            new_pos = self.storage.assign_position(box)
            if new_pos is None:
                print(f"[{self.state.current_time:.1f}s] ⚠️ No space available for 📦 ID:{box.box_id[-5:]}")
                return
            target_pos = new_pos

        dist_ida = abs(shuttle.current_x - target_pos.x)
        time_needed = 10 + dist_ida + 10   # pick + viaje + drop
        shuttle.current_x = target_pos.x
        self.state.place_box(box, target_pos)
        self.metrics["boxes_stored"] += 1
        shuttle.is_busy = True
        
        # 🇬🇧 INGLÉS + ORIGIN + FORMATO CLARO
        print(f"[{self.state.current_time:.1f}s] 📥 INBOUND: 📦 ID:{box.box_id[-5:]} from Origin:{box.origin} "
              f"-> A:{target_pos.aisle} S:{target_pos.side} X:{target_pos.x:03d} Y:{target_pos.y} Z:{target_pos.z}")

        self.add_event(Event(self.state.current_time + time_needed,
                             EventType.SHUTTLE_TASK_COMPLETE,
                             {'shuttle': shuttle, 'was_retrieval': False}))
        

    def _dispatch_outbound(self, shuttle: Any, task: Task):
        time_needed = 10 + abs(shuttle.current_x - task.source.x)
        box_id = None
        
        if task.task_type == 'RETRIEVE':
            box = self.state.grid.get(task.source)
            if box:
                box_id = box.box_id
                
            time_needed += 10 + task.source.x
            shuttle.current_x = 0
            self.state.remove_box(task.source)
            was_retrieval = True
        else:  # RELOCATE
            time_needed += 10 + abs(task.source.x - task.target.x)
            shuttle.current_x = task.target.x
            box = self.state.grid[task.source]
            if box:
                self.state.remove_box(task.source)
                self.state.place_box(box, task.target)
                
                # 🇬🇧 INGLÉS + FORMATO CLARO DE ORIGEN Y DESTINO
                src = task.source
                tgt = task.target
                src_str = f"A:{src.aisle} S:{src.side} X:{src.x:03d} Y:{src.y} Z:{src.z}"
                tgt_str = f"A:{tgt.aisle} S:{tgt.side} X:{tgt.x:03d} Y:{tgt.y} Z:{tgt.z}"
                
                print(f"[{self.state.current_time:.1f}s] 🔄 RELOCATE: 📦 ID:{box.box_id[-5:]} moved from {src_str} -> to {tgt_str}")
            was_retrieval = False

        shuttle.is_busy = True
        self.add_event(Event(self.state.current_time + time_needed,
                             EventType.SHUTTLE_TASK_COMPLETE,
                             {'shuttle': shuttle, 'was_retrieval': was_retrieval, 'box_id': box_id}))

    def _return_to_head(self, shuttle: Any):
        time_needed = shuttle.current_x   # solo movimiento, sin handling
        shuttle.current_x = 0
        shuttle.is_busy = True
        self.add_event(Event(self.state.current_time + time_needed,
                             EventType.SHUTTLE_TASK_COMPLETE,
                             {'shuttle': shuttle, 'was_retrieval': False}))