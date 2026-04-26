import pulp
from typing import List, Tuple
from src.model.silo_state import SiloState, Box, SiloPosition

class RetrievalOptimizer:
    """
    MILP para secuenciar la recuperación de pallets.
    Resuelve: Orden óptimo, gestión de shuttles compartidos (por nivel Y) y reubicaciones Z.
    """
    def __init__(self, state: SiloState):
        self.state = state

    def optimize_pallet_retrieval(self, pallet_boxes: List[Box]) -> List[Tuple[Box, float, bool]]:
        """
        Retorna: [(caja, tiempo_inicio, necesita_reubicacion), ...] ordenado por tiempo.
        """
        if len(pallet_boxes) != 12:
            raise ValueError("Un pallet debe tener exactamente 12 cajas.")

        prob = pulp.LpProblem("PalletRetrieval", pulp.LpMinimize)
        n = len(pallet_boxes)
        
        # Variables
        start_time = pulp.LpVariable.dicts("start", range(n), lowBound=0, cat=pulp.LpContinuous)
        makespan = pulp.LpVariable("makespan", lowBound=0, cat=pulp.LpContinuous)
        # seq[i][j] = 1 si caja i se recupera antes que j (solo si comparten shuttle)
        seq = pulp.LpVariable.dicts("seq", [(i, j) for i in range(n) for j in range(n) if i != j], cat=pulp.LpBinary)

        # Parámetros calculados
        durations = []
        needs_reloc = []
        shuttles = []
        
        for i, box in enumerate(pallet_boxes):
            pos = box.position
            shuttle_key = (pos.aisle, pos.y)
            shuttles.append(self.state.shuttles[shuttle_key])
            
            # Tiempo de movimiento: t = 10 + d (PDF)
            dist = abs(pos.x - shuttles[-1].current_x)
            dur = 10.0 + dist
            
            # ¿Requiere reubicación Z?
            reloc = False
            if pos.z == 2:
                front = SiloPosition(pos.aisle, pos.side, pos.x, pos.y, 1)
                if self.state.grid.get(front) is not None:
                    reloc = True
                    dur += 30.0  # Penalización estimada: mover Z1 + volver + mover Z2
            
            durations.append(dur)
            needs_reloc.append(reloc)

        # 🎯 Objetivo: Minimizar tiempo total (makespan)
        prob += makespan

        # 📏 Restricciones Lineales
        M = 10000.0  # Big-M para lógica condicional lineal
        
        for i in range(n):
            # 1. Tiempo mínimo de inicio (shuttle debe estar libre)
            prob += start_time[i] >= max(self.state.current_time, shuttles[i].busy_until), f"Earliest_{i}"
            
            # 2. Makespan
            prob += start_time[i] + durations[i] <= makespan, f"Makespan_{i}"
            
            # 3. No solapamiento de shuttles (mismo Aisle + Y)
            for j in range(n):
                if i == j: continue
                if shuttles[i].aisle == shuttles[j].aisle and shuttles[i].y_level == shuttles[j].y_level:
                    # Si comparten recurso, uno debe terminar antes que el otro empiece
                    prob += start_time[i] + durations[i] <= start_time[j] + M * (1 - seq[(i, j)]), f"NoOverlap_{i}_{j}_a"
                    prob += start_time[j] + durations[j] <= start_time[i] + M * seq[(i, j)], f"NoOverlap_{i}_{j}_b"

        # ⚡ Resolver
        # 1 segundo de tiempo límite, y un "Gap" del 10%
        prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=1, gapRel=0.1))

        # 📦 Extraer secuencia óptima
        result = []
        if pulp.LpStatus[prob.status] in ['Optimal', 'Feasible']:
            for i, box in enumerate(pallet_boxes):
                result.append((box, pulp.value(start_time[i]), needs_reloc[i]))
            # Ordenar por tiempo de inicio (Prioridad Dinámica resuelta matemáticamente)
            result.sort(key=lambda x: x[1])
            
        return result