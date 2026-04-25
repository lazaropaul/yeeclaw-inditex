import heapq
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Iterator, Optional

from src.model.silo_state import SiloState, Box

class EventType(Enum):
    BOX_ARRIVAL = auto()
    SHUTTLE_PICK_COMPLETE = auto()
    SHUTTLE_DROP_COMPLETE = auto()

@dataclass(order=True)
class Event:
    """
    Un evento en la simulación discreta de eventos (DES).
    Se comparan por 'timestamp' para ordenar la Priority Queue.
    """
    timestamp: float
    event_type: EventType = field(compare=False)
    payload: dict[str, Any] = field(compare=False, default_factory=dict)


class SimulationEngine:
    """
    Motor discreto de eventos basado en heapq para procesar la línea de tiempo.
    Permite simular horas en milisegundos evitando time.sleep.
    """
    def __init__(self, state: SiloState, arrival_interval: float = 3.6):
        self.state = state
        self.events: list[Event] = []
        self.arrival_interval = arrival_interval
        
        # Opcional: fuente de cajas. Si es None, podemos usar un parche temporal.
        self.box_stream: Optional[Iterator[Box]] = None

    def set_box_stream(self, boxes: Iterator[Box]) -> None:
        """Inyecta un generador de cajas y programa la primera en t=0"""
        self.box_stream = boxes
        self.schedule_event(0.0, EventType.BOX_ARRIVAL, {})

    def schedule_event(self, delay: float, event_type: EventType, payload: dict[str, Any]) -> None:
        """Programa un nuevo evento a futuro basado en current_time."""
        timestamp = self.state.current_time + delay
        heapq.heappush(self.events, Event(timestamp, event_type, payload))

    def process_event(self, event: Event) -> None:
        """Saca el evento, actualiza el reloj, y lanza la transición de estado correspondiente."""
        # 1. El tiempo avanza instantáneamente hasta este evento.
        self.state.current_time = event.timestamp
        
        # 2. Despachar
        if event.event_type == EventType.BOX_ARRIVAL:
            self._handle_box_arrival(event.payload)
        elif event.event_type == EventType.SHUTTLE_PICK_COMPLETE:
            self._handle_shuttle_pick(event.payload)
        elif event.event_type == EventType.SHUTTLE_DROP_COMPLETE:
            self._handle_shuttle_drop(event.payload)

    def _handle_box_arrival(self, payload: dict[str, Any]) -> None:
        """Una caja nueva llega a la cabeza de línea a razón de la capacidad max (3.6s)."""
        if self.box_stream is None:
            return
            
        try:
            # Pedimos la caja a la fuente
            box = next(self.box_stream)
            box.arrival_time = self.state.current_time
            self.state.incoming_queue.append(box)
            
            # Programar la llegada de la siguiente caja en 3.6s
            self.schedule_event(self.arrival_interval, EventType.BOX_ARRIVAL, {})
            
        except StopIteration:
            # Se acabaron las cajas, terminan las llegadas.
            pass

    def _handle_shuttle_pick(self, payload: dict[str, Any]) -> None:
        # payload['shuttle_id'] -> index o algo
        pass

    def _handle_shuttle_drop(self, payload: dict[str, Any]) -> None:
        # payload['shuttle_id'], payload['position'], etc.
        pass

    def run(self, max_time: float = float('inf')) -> None:
        """Ejecuta todos los eventos en la Priority Queue ordenados por tiempo."""
        while self.events and self.events[0].timestamp <= max_time:
            current_event = heapq.heappop(self.events)
            self.process_event(current_event)
