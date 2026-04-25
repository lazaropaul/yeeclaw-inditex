"""
main_simulation.py
Conector principal End-to-End. Corre el Motor DES con Input y Output coordinados,
y genera estadísticas e insights de tiempos.
"""

import sys
import random
import itertools
from pathlib import Path
from collections import deque

project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src.utils.csv_loader import load_silo_from_csv
from src.model.silo_state import Box, parse_box
from src.model.simulation import SimulationEngine, EventType
from src.algorithms.input_algorithm import assign_incoming_box
from src.algorithms.output_algorithm import process_pallet_fulfillment

def box_generator(destinations: list[str]):
    """Generador infinito de cajas aleatorias simulando stream en vivo."""
    for i in itertools.count():
        dest = random.choice(destinations)
        bulk = f"{i % 100000:05d}"
        box_id = f"1010000{dest}{bulk}"
        yield parse_box(box_id)

class HackathonSimulationEngine(SimulationEngine):
    """
    Subclase del motor que conecta los eventos al Input / Output real.
    """
    def __init__(self, state, destinations):
        super().__init__(state)
        self.destinations = destinations
        
        # Empezamos el reloj de extracciones (Output) en paralelo al Input
        # Reutilizamos un tipo de evento para el 'Output Tick'
        self.schedule_event(1.0, EventType.SHUTTLE_DROP_COMPLETE, {"is_output_tick": True})
        
    def _handle_box_arrival(self, payload) -> None:
        # Ignorando el payload. Implementación base para poner la caja:
        if self.box_stream:
            try:
                box = next(self.box_stream)
                box.arrival_time = self.state.current_time
                self.state.incoming_queue.append(box)
                self.schedule_event(self.arrival_interval, EventType.BOX_ARRIVAL, {})
            except StopIteration:
                pass
                
        # >>> ALGORITMO DE INPUT <<<
        # Procesamos la cola entera intentando colocar
        unplaced = []
        while self.state.incoming_queue:
            box = self.state.incoming_queue.popleft()
            success = assign_incoming_box(box, self.state)
            if not success:
                unplaced.append(box)
                
        # Devolvemos las cajas atascadas al frente de la cola
        self.state.incoming_queue.extend(unplaced)


    def _handle_shuttle_drop(self, payload) -> None:
        """Aquí lo usamos como el ciclo de bombeo de Extracciones (Output)"""
        # >>> ALGORITMO DE OUTPUT <<<
        
        active = list(self.state.active_pallets.keys())
        needed = self.state.MAX_ACTIVE_PALLETS - len(active)
        
        # 1. Rellenar huecos de palets trabajando si hay menos de 8
        if needed > 0:
            # Seleccionar destinos de forma ponderada (que tengan cajas en el almacén y no estén activos)
            available_dests = [d for d in self.destinations if d not in active and len(self.state.destination_index.get(d, [])) > 0]
            random.shuffle(available_dests)
            for dest in available_dests[:needed]:
                active.append(dest)
                
        # 2. Intentar sacar una caja para cada palé activo
        for dest in active:
            process_pallet_fulfillment(self.state, dest)
            
        # 3. Agendamos el siguiente intento de extracción.
        # Operacionalmente, si tenemos 32 shuttles, sacar múltiples cajas lleva pocos segundos globales.
        self.schedule_event(3.0, EventType.SHUTTLE_DROP_COMPLETE, {"is_output_tick": True})


def run_simulation(num_destinations: int = 20, hours_to_simulate: float = 2.0):
    print("=" * 60)
    print("🚀 INICIANDO SIMULACIÓN MAGISTRAL END-TO-END 🚀")
    print("=" * 60)
    
    csv_path = project_root / 'data' / 'silo-semi-empty.csv'
    
    print(f"1. Cargando matriz Z=1 / Z=2 desde {csv_path.name}")
    silo = load_silo_from_csv(csv_path, num_destinations)
    
    # 2. Configurar la lista de N destinos recogiendo del silo para facilitar vaciado
    existing_dests = list(silo.destination_index.keys())
    if len(existing_dests) >= num_destinations:
        sim_destinations = random.sample(existing_dests, num_destinations)
    else:
        sim_destinations = existing_dests.copy()
        while len(sim_destinations) < num_destinations:
            sim_destinations.append(f"{len(sim_destinations):08d}")
    
    # 3. Arrancar Motor DES
    engine = HackathonSimulationEngine(silo, sim_destinations)
    engine.set_box_stream(box_generator(sim_destinations))
    
    max_seconds = hours_to_simulate * 3600
    
    print(f"2. Parámetros de Simulación:")
    print(f"   Destinos concurrentes: {num_destinations}")
    print(f"   Horas de operación:    {hours_to_simulate} h. ({max_seconds:,.0f} segundos)")
    print(f"   Ocupación partiendo:   {silo.occupancy_rate():.2%}")
    print(f"\n⏳ Ejecutando motor de prioridad heapq sin bloqueos temporales...")
    
    # Run
    engine.run(max_time=max_seconds)
    
    # Métricas y Cierre
    completed = len(silo.completed_pallets)
    active = len(silo.active_pallets)
    occupancy = silo.occupancy_rate()
    throughput = completed / hours_to_simulate if hours_to_simulate > 0 else 0
    total_blocked = len(silo.incoming_queue)
    
    print("\n" + "=" * 60)
    print("📊 RESULTADOS E INSIGHTS DE LA SIMULACIÓN 📊")
    print("=" * 60)
    print(f"⏱️  Tiempo Final:              {silo.current_time:,.1f} s")
    print(f"📦 Ocupación del Silo:        {occupancy:.2%} ")
    print(f"🏗️  Cajas p/ procesar (Queue): {total_blocked} cajas bloqueadas en head port")
    print(f"✅ Palés Cerrados Completos:  {completed} unidades")
    print(f"🔄 Palés Incompletos:         {active} armándose. (Total {sum(len(l) for l in silo.active_pallets.values())} cajas sueltas)")
    if throughput == 0 and active > 0:
         print(f"⚠️  THROUGHPUT:                0.0 palés/h (Atascados en Output, revisen el balanceo)")
    else:
         print(f"🚀 THROUGHPUT:                {throughput:,.2f} palés/hora")
    print("=" * 60)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Hackathon Inditex Yeeclaw Simulador")
    parser.add_argument("--dests", type=int, default=20, help="Nº Destinos Activos")
    parser.add_argument("--hours", type=float, default=2.0, help="Horas a simular")
    args = parser.parse_args()
    
    run_simulation(args.dests, args.hours)
