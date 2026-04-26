import heapq
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, List, Iterator, Set

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


class DummyPallet:
    """Estructura simplificada para un pallet activo (12 cajas reservadas)."""
    def __init__(self, dest: str, boxes: List[Box]):
        self.destination = dest
        # Diccionario {box_id: SiloPosition} de las 12 cajas aún no recuperadas
        self.pending_boxes = {b.box_id: b.position for b in boxes[:12] if b.position is not None}


class SimulationEngine:
    def __init__(self, state: SiloState, storage_engine: StorageEngine, retrieval_engine: RetrievalEngine):
        self.state = state
        self.storage = storage_engine
        self.retrieval = retrieval_engine

        # 32 shuttles (4 pasillos × 8 niveles)
        self.shuttles = {(a, y): Shuttle(aisle=a, y_level=y) for a in range(1, 5) for y in range(1, 9)}

        self.events: List[Event] = []
        self.global_time = 0.0

        # Colas de entrada (inbound) por (pasillo, nivel Y)
        self.inbound_queues = {(a, y): [] for a in range(1, 5) for y in range(1, 9)}

        # Pallets activos (máximo 8 simultáneos)
        self.active_pallets: List[DummyPallet] = []
        self.active_destinations: Set[str] = set()   # para comprobación rápida

        self.box_stream = None
        self.metrics = {
            "boxes_stored": 0,
            "boxes_retrieved": 0,
            "pallets_completed": 0,
            "trip_chains": 0
        }

    def add_event(self, event: Event):
        heapq.heappush(self.events, event)

    def run(self, box_stream: Iterator[str], max_time: float = 3600):
        print("--- Iniciando Simulación Continua con Trip Chaining ---")
        self.box_stream = box_stream
        self._schedule_next_arrival()

        while self.events and self.global_time <= max_time:
            current_event = heapq.heappop(self.events)
            self.global_time = current_event.timestamp
            self.state.current_time = self.global_time

            if current_event.event_type == EventType.BOX_ARRIVAL:
                self._handle_box_arrival(current_event.payload)
            elif current_event.event_type == EventType.SHUTTLE_TASK_COMPLETE:
                self._handle_task_complete(current_event.payload)

    # ==========================================
    # PROGRAMACIÓN DE LLEGADAS
    # ==========================================

    def _schedule_next_arrival(self):
        try:
            box_code = next(self.box_stream)
            box = Box(
                box_id=box_code,
                origin=box_code[:7],
                destination=box_code[7:15],
                bulk_number=box_code[15:20]
            )
            # Llegada cada 0.5 segundos (puedes ajustar para mayor carga)
            self.add_event(Event(self.global_time + 0.5, EventType.BOX_ARRIVAL, {'box': box}))
        except StopIteration:
            pass  # No hay más cajas

    # ==========================================
    # MANEJADOR DE LLEGADA DE CAJA (INBOUND)
    # ==========================================

    def _handle_box_arrival(self, payload: dict):
        self._schedule_next_arrival()

        box_to_store = payload['box']
        target_pos = self.storage.assign_position(box_to_store)

        if target_pos:
            self.inbound_queues[(target_pos.aisle, target_pos.y)].append((box_to_store, target_pos))
            shuttle = self.shuttles[(target_pos.aisle, target_pos.y)]

            if shuttle.state == ShuttleState.IDLE:
                self._assign_next_work(shuttle)

        # Después de almacenar, comprobar si se puede activar un nuevo pallet
        self._check_and_activate_pallets()

    def _check_and_activate_pallets(self):
        """Activa hasta 8 pallets cuando un destino acumula ≥12 cajas."""
        for dest, positions in list(self.state.destination_index.items()):
            if len(self.active_pallets) >= 8:
                break

            if dest in self.active_destinations:
                continue  # Ya hay un pallet activo para este destino

            # Contar cajas reales en silo (ignorando None)
            boxes_in_silo = [self.state.grid[p] for p in positions if self.state.grid.get(p) is not None]
            if len(boxes_in_silo) >= 12:
                print(f"[{self.global_time:.1f}s] 📦 NUEVO PALLET ACTIVO: {dest}")
                pallet = DummyPallet(dest, boxes_in_silo)
                self.active_pallets.append(pallet)
                self.active_destinations.add(dest)

                # Despertar shuttles inactivos que puedan tener cajas de este pallet
                for shuttle in self.shuttles.values():
                    if shuttle.state == ShuttleState.IDLE:
                        self._assign_next_work(shuttle)

    # ==========================================
    # MANEJADOR DE FINALIZACIÓN DE TAREA
    # ==========================================

    def _handle_task_complete(self, payload: dict):
        shuttle = payload['shuttle']

        # Resetear estado
        if shuttle.state in (ShuttleState.STORING, ShuttleState.RETRIEVING,
                             ShuttleState.RELOCATING, ShuttleState.RETURNING_EMPTY):
            shuttle.state = ShuttleState.IDLE

        if payload.get('was_retrieval'):
            self.metrics["boxes_retrieved"] += 1

            # Eliminar pallets que ya no tengan cajas pendientes
            for pallet in self.active_pallets[:]:
                if not pallet.pending_boxes:
                    self.active_pallets.remove(pallet)
                    self.active_destinations.discard(pallet.destination)
                    self.metrics["pallets_completed"] += 1
                    print(f"[{self.global_time:.1f}s] ✅ PALLET COMPLETADO: {pallet.destination}")
                    # Al liberar un hueco, podemos activar nuevos pallets
                    self._check_and_activate_pallets()

        self._assign_next_work(shuttle)

    # ==========================================
    # LÓGICA PRINCIPAL DE ASIGNACIÓN DE TRABAJO
    # ==========================================

    def _assign_next_work(self, shuttle: Shuttle):
        # 1. Si hay tareas pendientes en la cola del shuttle, ejecutar la siguiente
        if shuttle.task_queue:
            next_task = shuttle.task_queue.pop(0)
            self._dispatch_outbound(shuttle, next_task)
            return

        # 2. TRIP CHAINING: si el shuttle está dentro del pasillo (x>0) y hay una caja
        #    que recoger en su mismo nivel y pasillo, la recogemos sin volver a cabeza.
        if shuttle.x > 0:
            out_tasks = self.retrieval.get_next_tasks(
                shuttle.y, shuttle.x, self.active_pallets, aisle=shuttle.aisle
            )
            if out_tasks:
                print(f"[{self.global_time:.1f}s] ⚡ TRIP CHAINING! "
                      f"Shuttle A:{shuttle.aisle} Y:{shuttle.y} desde X:{shuttle.x}")
                self.metrics["trip_chains"] += 1
                shuttle.task_queue.extend(out_tasks)
                self._dispatch_outbound(shuttle, shuttle.task_queue.pop(0))
                return
            else:
                # No hay nada que recoger, volver a cabeza vacío
                self._return_to_head(shuttle)
                return

        # 3. En cabeza (x=0): priorizar inbound si hay cola
        if self.inbound_queues[(shuttle.aisle, shuttle.y)]:
            box, target_pos = self.inbound_queues[(shuttle.aisle, shuttle.y)].pop(0)
            self._dispatch_inbound(shuttle, box, target_pos)
            return

        # 4. En cabeza y sin inbound: buscar outbound (recuperar cajas)
        out_tasks = self.retrieval.get_next_tasks(
            shuttle.y, 0, self.active_pallets, aisle=shuttle.aisle
        )
        if out_tasks:
            shuttle.task_queue.extend(out_tasks)
            self._dispatch_outbound(shuttle, shuttle.task_queue.pop(0))
            return

    # ==========================================
    # DESPACHO DE OPERACIONES CON TIEMPOS CORREGIDOS
    # ==========================================

    def _dispatch_inbound(self, shuttle: Shuttle, box: Box, target_pos: SiloPosition):
        # Verificar si la posición sigue siendo válida (puede haber cambiado por eventos concurrentes)
        if not self.state.can_place_at(target_pos):
            new_pos = self.storage.assign_position(box)
            if new_pos is None:
                print(f"[{self.global_time:.1f}s] ⚠️ No hay espacio para caja {box.box_id}")
                return
            target_pos = new_pos
        dist = abs(shuttle.x - target_pos.x)
        time_needed = 10 + dist + 10      # pick + viaje + drop
        shuttle.state = ShuttleState.STORING
        shuttle.x = target_pos.x
        self.state.place_box(box, target_pos)
        self.metrics["boxes_stored"] += 1
        self.add_event(Event(self.global_time + time_needed,
                            EventType.SHUTTLE_TASK_COMPLETE,
                            {'shuttle': shuttle}))

    def _dispatch_outbound(self, shuttle: Shuttle, task: Task):
        """
        Recuperar o relocalizar una caja.
        Para RETRIEVE:   tiempo = 10 (pick) + dist_origen + 10 (drop en cabeza) + dist_vuelta??
        En realidad, el shuttle parte de x_actual (puede ser 0 o tras un relocate), va a task.source,
        hace pick (10), viaja a x=0 (dist_origen), y allí hace drop (10).
        Total = (10 + dist_ida) + (10 + dist_vuelta) = 20 + dist_ida + dist_vuelta.
        """
        time_needed = 0.0
        is_retrieval = False

        # Tiempo para ir desde la posición actual hasta el origen de la tarea
        time_needed += 10 + abs(shuttle.x - task.source.x)

        if task.task_type == 'RELOCATE':
            # Relocalización: después de recoger en source, ir a target y hacer drop
            time_needed += 10 + abs(task.source.x - task.target.x)  # viaje + drop
            shuttle.state = ShuttleState.RELOCATING
            shuttle.x = task.target.x
        elif task.task_type == 'RETRIEVE':
            # Recuperación: después de recoger en source, volver a cabeza y hacer drop
            time_needed += 10 + task.source.x   # viaje de vuelta a cabeza + drop
            shuttle.state = ShuttleState.RETRIEVING
            shuttle.x = 0
            self.state.remove_box(task.source)
            is_retrieval = True

        self.add_event(Event(self.global_time + time_needed,
                             EventType.SHUTTLE_TASK_COMPLETE,
                             {'shuttle': shuttle, 'was_retrieval': is_retrieval}))

    def _return_to_head(self, shuttle: Shuttle):
        """Moverse en vacío desde la posición actual hasta x=0."""
        time_needed = shuttle.x  # sin handling extra porque no hay pick/drop
        shuttle.state = ShuttleState.RETURNING_EMPTY
        shuttle.x = 0
        self.add_event(Event(self.global_time + time_needed,
                             EventType.SHUTTLE_TASK_COMPLETE,
                             {'shuttle': shuttle}))