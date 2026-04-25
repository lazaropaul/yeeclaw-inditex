import heapq
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, List, Optional

# Importaciones de tu modelo
from src.model.silo_state import SiloState, Box, SiloPosition
from src.algorithms.storage import StorageEngine
from src.algorithms.retrieval import RetrievalEngine, Task

class EventType(Enum):
    BOX_ARRIVAL = auto()           # Una caja llega al sistema para entrar
    SHUTTLE_TASK_COMPLETE = auto() # Un shuttle termina un viaje/movimiento

@dataclass(order=True)
class Event:
    """
    Un evento en la simulación discreta de eventos (DES).
    Se comparan por 'timestamp' para ordenar la Priority Queue.
    """
    timestamp: float
    event_type: EventType = field(compare=False)
    payload: dict[str, Any] = field(compare=False, default_factory=dict)

class ShuttleState:
    IDLE = "IDLE"                      # Esperando órdenes
    STORING = "STORING"                # Viajando para guardar una caja (Inbound)
    RETRIEVING = "RETRIEVING"          # Viajando para sacar una caja (Outbound)
    RELOCATING = "RELOCATING"          # Moviendo caja bloqueadora (Z=1 a otro hueco)
    RETURNING_EMPTY = "RETURNING_EMPTY"# Volviendo a X=0 sin caja

class Shuttle:
    def __init__(self, y_level: int):
        self.y = y_level
        self.x = 0
        self.state = ShuttleState.IDLE
        
        # Memoria: permite ejecutar secuencias (Ej: RELOCATE seguido de RETRIEVE)
        self.task_queue: List[Task] = [] 

class SimulationEngine:
    def __init__(self, state: SiloState, storage_engine: StorageEngine, retrieval_engine: RetrievalEngine):
        self.state = state
        self.storage = storage_engine
        self.retrieval = retrieval_engine
        
        # 8 shuttles (uno por nivel Y)
        self.shuttles = {y: Shuttle(y_level=y) for y in range(1, 9)}
        
        # Motor DES: Priority Queue de eventos y Reloj Global
        self.events: List[Event] = []
        self.global_time = 0.0 
        
        # Colas de trabajo
        # Solución robusta: Una cola de Inbound por cada nivel Y
        self.inbound_queues_by_y = {y: [] for y in range(1, 9)} 
        self.active_pallets = [] # Lista de pallets armándose en la salida

    def add_event(self, event: Event):
        """Añade un evento a la línea temporal."""
        heapq.heappush(self.events, event)

    def run(self):
        """Bucle principal de la simulación. Avanza por eventos, no por ticks."""
        print("--- Iniciando Simulación DES ---")
        while self.events:
            # 1. Saltamos en el tiempo al instante exacto del siguiente evento
            current_event = heapq.heappop(self.events)
            self.global_time = current_event.timestamp
            
            # 2. Despachamos según el tipo de evento
            if current_event.event_type == EventType.BOX_ARRIVAL:
                self._handle_box_arrival(current_event.payload)
            
            elif current_event.event_type == EventType.SHUTTLE_TASK_COMPLETE:
                self._handle_task_complete(current_event.payload)

    # ==========================================
    # MANEJADORES DE EVENTOS
    # ==========================================

    def _handle_box_arrival(self, payload: dict):
        """Se ejecuta cuando el sistema notifica que hay una caja nueva para Inbound."""
        box_to_store = payload['box']
        
        # Preguntamos al cerebro de Inbound dónde colocarla
        target_pos = self.storage.assign_position(box_to_store)
        
        if target_pos:
            # CAMBIO AQUÍ: box_to_store.box_id
            print(f"[{self.global_time:.1f}s] INBOUND: Caja {box_to_store.box_id} asignada a Y:{target_pos.y}, X:{target_pos.x}, Z:{target_pos.z}")
            # Encolamos la orden al shuttle del nivel correcto
            self.inbound_queues_by_y[target_pos.y].append((box_to_store, target_pos))
            
            # Avisamos al shuttle por si estaba dormido
            shuttle = self.shuttles[target_pos.y]
            if shuttle.state == ShuttleState.IDLE:
                self._assign_next_work(shuttle)
        else:
            # CAMBIO AQUÍ: box_to_store.box_id
            print(f"[{self.global_time:.1f}s] WARNING: Silo lleno, no se pudo asignar la caja {box_to_store.box_id}")

    def _handle_task_complete(self, payload: dict):
        """Se ejecuta cuando un shuttle termina de moverse."""
        shuttle = payload['shuttle']
        
        if shuttle.state in (ShuttleState.STORING, ShuttleState.RETRIEVING, ShuttleState.RELOCATING, ShuttleState.RETURNING_EMPTY):
            # Liberamos el shuttle. (Si hizo STORING, se queda en su X actual listo para Trip Chaining)
            shuttle.state = ShuttleState.IDLE

        # Inmediatamente después de terminar, el cerebro busca qué hacer
        self._assign_next_work(shuttle)

    # ==========================================
    # LÓGICA DE ASIGNACIÓN (El Cerebro del Shuttle)
    # ==========================================

    def _assign_next_work(self, shuttle: Shuttle):
        """Decide y despacha la siguiente orden para el shuttle."""
        
        # Prioridad 0: Completar secuencias en memoria (Ej: Acaba de hacer RELOCATE, ahora toca el RETRIEVE)
        if shuttle.task_queue:
            next_task = shuttle.task_queue.pop(0)
            self._dispatch_outbound(shuttle, next_task)
            return

        # Prioridad 1: Inbound (Condición: estar en cabecera X=0 y tener cajas en su cola)
        if shuttle.x == 0 and self.inbound_queues_by_y[shuttle.y]:
            box, target_pos = self.inbound_queues_by_y[shuttle.y].pop(0)
            self._dispatch_inbound(shuttle, box, target_pos)
            return

        # Prioridad 2: Outbound (Preguntamos al cerebro de Retrieval si hay cajas de pallets que sacar)
        outbound_tasks = self.retrieval.get_next_tasks(shuttle.y, shuttle.x, self.active_pallets)
        
        if outbound_tasks:
            # Guardamos la secuencia entera (puede ser 1 o 2 tareas si hubo bloqueo en Z)
            shuttle.task_queue.extend(outbound_tasks)
            first_task = shuttle.task_queue.pop(0)
            self._dispatch_outbound(shuttle, first_task)
            return

        # Prioridad 3: Reposicionamiento. Si no hay nada, pero está metido en el pasillo, vuelve a X=0.
        if shuttle.x > 0:
            self._return_to_head(shuttle)

    # ==========================================
    # FUNCIONES DE DESPACHO (Calculan tiempo y programan eventos)
    # ==========================================

    def _dispatch_inbound(self, shuttle: Shuttle, box: Box, target_pos: SiloPosition):
        dist_x = abs(shuttle.x - target_pos.x)
        time_needed = 10 + dist_x  # t = 10 + d
        
        shuttle.state = ShuttleState.STORING
        shuttle.x = target_pos.x # Físicamente se queda en la nueva posición
        
        print(f"[{self.global_time:.1f}s] Shuttle Y:{shuttle.y} -> STORING en X:{shuttle.x} (Duración: {time_needed}s)")
        
        self.add_event(Event(
            timestamp=self.global_time + time_needed,
            event_type=EventType.SHUTTLE_TASK_COMPLETE,
            payload={'shuttle': shuttle}
        ))

    def _dispatch_outbound(self, shuttle: Shuttle, task: Task):
        dist_x = abs(shuttle.x - task.source.x)
        time_needed = 10 + dist_x
        
        if task.task_type == 'RELOCATE':
            shuttle.state = ShuttleState.RELOCATING
            time_needed += abs(task.source.x - task.target.x) # Sumar viaje hasta el hueco destino
            shuttle.x = task.target.x
            print(f"[{self.global_time:.1f}s] Shuttle Y:{shuttle.y} -> RELOCATING Z=1 (X:{task.source.x} a X:{task.target.x})")
            
        elif task.task_type == 'RETRIEVE':
            shuttle.state = ShuttleState.RETRIEVING
            time_needed += task.source.x # Sumar viaje de vuelta a X=0 con la caja a cuestas
            shuttle.x = 0
            print(f"[{self.global_time:.1f}s] Shuttle Y:{shuttle.y} -> RETRIEVING caja {task.box_id} a Cabecera")

        self.add_event(Event(
            timestamp=self.global_time + time_needed,
            event_type=EventType.SHUTTLE_TASK_COMPLETE,
            payload={'shuttle': shuttle}
        ))

    def _return_to_head(self, shuttle: Shuttle):
        time_needed = shuttle.x # Viaje de vuelta vacío
        shuttle.state = ShuttleState.RETURNING_EMPTY
        shuttle.x = 0
        
        print(f"[{self.global_time:.1f}s] Shuttle Y:{shuttle.y} -> VOLVIENDO VACÍO a X:0")
        
        self.add_event(Event(
            timestamp=self.global_time + time_needed,
            event_type=EventType.SHUTTLE_TASK_COMPLETE,
            payload={'shuttle': shuttle}
        ))