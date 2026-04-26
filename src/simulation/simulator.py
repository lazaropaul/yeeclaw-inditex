import heapq
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, List, Iterator

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
    payload: dict[str, Any] = field(compare=False, default_factory=dict)

class ShuttleState:
    IDLE = "IDLE"                      
    STORING = "STORING"                
    RETRIEVING = "RETRIEVING"          
    RELOCATING = "RELOCATING"          
    RETURNING_EMPTY = "RETURNING_EMPTY"

class Shuttle:
    def __init__(self, aisle: int, y_level: int):
        self.aisle = aisle
        self.y = y_level
        self.x = 0
        self.state = ShuttleState.IDLE
        self.task_queue: List[Task] = [] 

class SimulationEngine:
    def __init__(self, state: SiloState, storage_engine: StorageEngine, retrieval_engine: RetrievalEngine):
        self.state = state
        self.storage = storage_engine
        self.retrieval = retrieval_engine
        
        # 32 Shuttles (4 pasillos x 8 niveles)
        self.shuttles = {(a, y): Shuttle(aisle=a, y_level=y) for a in range(1, 5) for y in range(1, 9)}
        
        self.events: List[Event] = []
        self.global_time = 0.0 
        
        # Colas de Inbound separadas por Pasillo y Nivel Y
        self.inbound_queues = {(a, y): [] for a in range(1, 5) for y in range(1, 9)} 
        
        # Pallets que han alcanzado 12 cajas y están listos para salir
        self.active_pallets = [] 
        
        # Stream de cajas entrantes y métricas
        self.box_stream = None
        self.metrics = {"boxes_stored": 0, "boxes_retrieved": 0, "pallets_completed": 0, "trip_chains": 0}

    def add_event(self, event: Event):
        heapq.heappush(self.events, event)

    def run(self, box_stream: Iterator[str], max_time: float = 3600):
        print("--- Iniciando Simulación Continua con Trip Chaining ---")
        self.box_stream = box_stream
        
        # Disparamos la llegada de la primera caja
        self._schedule_next_arrival()

        while self.events and self.global_time <= max_time:
            current_event = heapq.heappop(self.events)
            self.global_time = current_event.timestamp
            self.state.current_time = self.global_time # Sincronizar reloj del state
            
            if current_event.event_type == EventType.BOX_ARRIVAL:
                self._handle_box_arrival(current_event.payload)
            elif current_event.event_type == EventType.SHUTTLE_TASK_COMPLETE:
                self._handle_task_complete(current_event.payload)

    # ==========================================
    # MANEJADORES DE EVENTOS
    # ==========================================

    def _schedule_next_arrival(self):
        """Saca la siguiente caja del generador y la programa para dentro de unos segundos."""
        try:
            box_code = next(self.box_stream)
            box = Box(box_id=box_code, origin=box_code[:7], destination=box_code[7:15], bulk_number=box_code[15:20])
            # Simulamos que llega una caja cada 5 segundos al sistema
            self.add_event(Event(self.global_time + 5.0, EventType.BOX_ARRIVAL, {'box': box}))
        except StopIteration:
            pass # No hay más cajas entrantes

    def _handle_box_arrival(self, payload: dict):
        self._schedule_next_arrival() # Programar la siguiente
        
        box_to_store = payload['box']
        target_pos = self.storage.assign_position(box_to_store)
        
        if target_pos:
            self.inbound_queues[(target_pos.aisle, target_pos.y)].append((box_to_store, target_pos))
            shuttle = self.shuttles[(target_pos.aisle, target_pos.y)]
            
            if shuttle.state == ShuttleState.IDLE:
                self._assign_next_work(shuttle)
        
        # Comprobar si al meter esta caja se ha completado algún pallet
        self._check_and_activate_pallets()

    def _check_and_activate_pallets(self):
        """Revisa si hay destinos con >= 12 cajas y los convierte en Pallets Activos para la salida."""
        for dest, positions in list(self.state.destination_index.items()):
            if len(self.active_pallets) >= 8: 
                break # Límite de 8 pallets simultáneos
                
            # Cajas reales (ignorando None por si acaso)
            boxes_in_silo = [self.state.grid[p] for p in positions if self.state.grid.get(p) is not None]
            
            if len(boxes_in_silo) >= 12:
                # Si no está ya en la lista de pallets activos
                if not any(hasattr(p, 'destination') and p.destination == dest for p in self.active_pallets):
                    print(f"[{self.global_time:.1f}s] 📦 NUEVO PALLET ACTIVO: {dest} (12 cajas listas)")
                    
                    # NOTA: Asegúrate de que tu RetrievalEngine entienda esta estructura o usa una clase Pallet
                    class DummyPallet:
                        def __init__(self, d, boxes):
                            self.destination = d
                            # Diccionario {box_id: SiloPosition} como esperaba el Retrieval original
                            self.pending_boxes = {b.box_id: b.position for b in boxes[:12]}
                            
                    self.active_pallets.append(DummyPallet(dest, boxes_in_silo))
                    
                    # Despertamos a todos los shuttles inactivos por si tienen cajas de este pallet
                    for s in self.shuttles.values():
                        if s.state == ShuttleState.IDLE:
                            self._assign_next_work(s)

    def _handle_task_complete(self, payload: dict):
        shuttle = payload['shuttle']
        if shuttle.state in (ShuttleState.STORING, ShuttleState.RETRIEVING, ShuttleState.RELOCATING, ShuttleState.RETURNING_EMPTY):
            shuttle.state = ShuttleState.IDLE
            
        if payload.get('was_retrieval'):
            self.metrics["boxes_retrieved"] += 1
            # Aquí deberíamos borrar la caja de DummyPallet.pending_boxes para saber cuándo acaba
            
        self._assign_next_work(shuttle)

    # ==========================================
    # LÓGICA DE ASIGNACIÓN (El Cerebro)
    # ==========================================

    def _assign_next_work(self, shuttle: Shuttle):
        if shuttle.task_queue:
            next_task = shuttle.task_queue.pop(0)
            self._dispatch_outbound(shuttle, next_task)
            return

        # 🔥 LA MAGIA DEL TRIP CHAINING 🔥
        if shuttle.x > 0:
            # Está en el pasillo. ¿Hay algo que sacar en SU pasillo y nivel?
            outbound_tasks = self.retrieval.get_next_tasks(shuttle.y, shuttle.x, self.active_pallets, aisle=shuttle.aisle)
            if outbound_tasks:
                print(f"[{self.global_time:.1f}s] ⚡ TRIP CHAINING! Shuttle A:{shuttle.aisle} Y:{shuttle.y} saca caja desde X:{shuttle.x}")
                self.metrics["trip_chains"] += 1
                shuttle.task_queue.extend(outbound_tasks)
                self._dispatch_outbound(shuttle, shuttle.task_queue.pop(0))
                return
            else:
                self._return_to_head(shuttle)
                return

        # Si está en cabecera (X=0)
        if self.inbound_queues[(shuttle.aisle, shuttle.y)]:
            box, target_pos = self.inbound_queues[(shuttle.aisle, shuttle.y)].pop(0)
            self._dispatch_inbound(shuttle, box, target_pos)
            return

        outbound_tasks = self.retrieval.get_next_tasks(shuttle.y, 0, self.active_pallets, aisle=shuttle.aisle)
        if outbound_tasks:
            shuttle.task_queue.extend(outbound_tasks)
            self._dispatch_outbound(shuttle, shuttle.task_queue.pop(0))
            return

    # ==========================================
    # FUNCIONES DE DESPACHO
    # ==========================================

    def _dispatch_inbound(self, shuttle: Shuttle, box: Box, target_pos: SiloPosition):
        time_needed = 10 + abs(shuttle.x - target_pos.x)
        shuttle.state = ShuttleState.STORING
        shuttle.x = target_pos.x
        self.state.place_box(box, target_pos)
        self.metrics["boxes_stored"] += 1
        
        self.add_event(Event(self.global_time + time_needed, EventType.SHUTTLE_TASK_COMPLETE, {'shuttle': shuttle}))

    def _dispatch_outbound(self, shuttle: Shuttle, task: Task):
        time_needed = 10 + abs(shuttle.x - task.source.x)
        is_retrieval = False
        
        if task.task_type == 'RELOCATE':
            shuttle.state = ShuttleState.RELOCATING
            time_needed += abs(task.source.x - task.target.x)
            shuttle.x = task.target.x
        elif task.task_type == 'RETRIEVE':
            shuttle.state = ShuttleState.RETRIEVING
            time_needed += task.source.x
            shuttle.x = 0
            self.state.remove_box(task.source)
            is_retrieval = True

        self.add_event(Event(self.global_time + time_needed, EventType.SHUTTLE_TASK_COMPLETE, {'shuttle': shuttle, 'was_retrieval': is_retrieval}))

    def _return_to_head(self, shuttle: Shuttle):
        time_needed = shuttle.x
        shuttle.state = ShuttleState.RETURNING_EMPTY
        shuttle.x = 0
        self.add_event(Event(self.global_time + time_needed, EventType.SHUTTLE_TASK_COMPLETE, {'shuttle': shuttle}))