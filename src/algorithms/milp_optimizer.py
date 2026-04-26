import pulp
from typing import List, Tuple
from src.model.silo_state import SiloState, Box, SiloPosition

class MilpOptimizer:
    def __init__(self, state: SiloState):
        self.state = state
        # 🔥 Pesos calibrados para Throughput (PDF: minimizar tiempo total)
        self.w_dist = 0.60    # Distancia a cabeza (X bajo = recuperación rápida)
        self.w_z = 0.25       # Penalización Z (evita reubicaciones costosas)
        self.w_cluster = 0.15 # Agrupación por destino (reduce fragmentación)

    def optimize_storage(self, incoming_boxes: List[Box]) -> List[Tuple[Box, SiloPosition]]:
        if not incoming_boxes:
            return []

        valid_positions = [p for p in self.state.grid if self.state.can_place_at(p)]
        
        if not valid_positions:
            return []

        # 🧠 HACK MILP: Pre-calcular la ocupación actual de cada nivel para balancear la carga
        occupancy_map = {}
        for p, b in self.state.grid.items():
            if b is not None:
                key = (p.aisle, p.y)
                occupancy_map[key] = occupancy_map.get(key, 0) + 1

        prob = pulp.LpProblem("StorageAssignment", pulp.LpMinimize)

        # Variables binarias
        x_vars = pulp.LpVariable.dicts(
            "assign", 
            [(b.box_id, p) for b in incoming_boxes for p in valid_positions],
            cat=pulp.LpBinary
        )

        # 🎯 FUNCIÓN OBJETIVO
        obj_terms = []
        for b in incoming_boxes:
            for p in valid_positions:
                time_cost = 20.0 + p.x
                
                z_penalty = 0.0
                if p.z == 2:
                    front = SiloPosition(p.aisle, p.side, p.x, p.y, 1)
                    front_box = self.state.grid.get(front)
                    if front_box is None:
                        z_penalty = 1000.0  # Imposible
                    elif front_box.destination != b.destination:
                        z_penalty = 50.0    # Futura reubicación
                
                cluster_bonus = 0.0
                for dx in range(-2, 3):
                    nx = p.x + dx
                    if 1 <= nx <= 60:
                        neighbor = self.state.grid.get(SiloPosition(p.aisle, p.side, nx, p.y, p.z))
                        if neighbor and neighbor.destination == b.destination:
                            cluster_bonus -= 10.0
                
                # ⚖️ NUEVO: Penalización por nivel lleno (Load Balancing)
                # Cada caja extra en ese nivel suma 0.5 al costo
                current_occupancy = occupancy_map.get((p.aisle, p.y), 0)
                load_penalty = current_occupancy * 0.5
                
                # Sumamos el load_penalty al costo total
                cost = self.w_dist * time_cost + self.w_z * z_penalty + self.w_cluster * cluster_bonus + load_penalty
                obj_terms.append(cost * x_vars[(b.box_id, p)])

        prob += pulp.lpSum(obj_terms), "TotalCost"

        # 📏 RESTRICCIONES (Se mantienen igual)
        for b in incoming_boxes:
            prob += pulp.lpSum(x_vars[(b.box_id, p)] for p in valid_positions) == 1
            
        for p in valid_positions:
            prob += pulp.lpSum(x_vars[(b.box_id, p)] for b in incoming_boxes) <= 1
            
        for p in valid_positions:
            if p.z == 2:
                front = SiloPosition(p.aisle, p.side, p.x, p.y, 1)
                if self.state.grid.get(front) is None:
                    prob += (pulp.lpSum(x_vars[(b.box_id, front)] for b in incoming_boxes) >= 
                             pulp.lpSum(x_vars[(b.box_id, p)] for b in incoming_boxes))

        # ⚡ SOLVER
        prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=4, gapRel=0.05))

        assignment = []
        if pulp.LpStatus[prob.status] in ['Optimal', 'Feasible']:
            for b in incoming_boxes:
                for p in valid_positions:
                    if pulp.value(x_vars[(b.box_id, p)]) > 0.5:
                        assignment.append((b, p))
                        break
        return assignment