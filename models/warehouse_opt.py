"""
Warehouse Silo Box-Assignment Optimisation
==========================================
HackUPC 2026 – Yeeclaw

Rewritten from amplpy → PuLP (open-source, no AMPL license required).
Uses the HiGHS solver bundled with PuLP.
"""
import pulp

# ── 1. Problem dimensions ──────────────────────────────────────
NUM_AISLES = 2
NUM_SIDES  = 2
NUM_X      = 5    # X-positions (use 60 for full problem)
NUM_Y      = 2    # Y-levels (one shuttle each)
NUM_Z      = 2    # Z-depths
NUM_BOXES  = 4    # boxes in this batch
HANDLING   = 10   # seconds base handling time per pick/drop

AISLES  = list(range(1, NUM_AISLES + 1))
SIDES   = list(range(1, NUM_SIDES + 1))
XPOS    = list(range(1, NUM_X + 1))
YLEVELS = list(range(1, NUM_Y + 1))
ZDEPTHS = list(range(1, NUM_Z + 1))

boxes = [f"BOX_{i:02d}" for i in range(1, NUM_BOXES + 1)]
box_dest = {b: "DEST_01220930" for b in boxes}

# Pre-occupied slots — all empty for this demo
occupied = {}   # key: (a,s,x,y,z) → 1 if occupied

# ── 2. Build the MIP ──────────────────────────────────────────
prob = pulp.LpProblem("WarehouseSilo", pulp.LpMinimize)

# Decision variables: Assign[b,a,s,x,y,z] ∈ {0,1}
Assign = {
    (b, a, s, x, y, z): pulp.LpVariable(
        f"Assign_{b}_{a}_{s}_{x}_{y}_{z}", cat="Binary"
    )
    for b in boxes
    for a in AISLES
    for s in SIDES
    for x in XPOS
    for y in YLEVELS
    for z in ZDEPTHS
}

# Makespan variable (continuous)
Makespan = pulp.LpVariable("Makespan", lowBound=0)

# ── Objective ─────────────────────────────────────────────────
prob += Makespan, "MinMakespan"

# ── C1: Every box goes to exactly one location ────────────────
for b in boxes:
    prob += (
        pulp.lpSum(Assign[b, a, s, x, y, z]
                   for a in AISLES for s in SIDES
                   for x in XPOS   for y in YLEVELS for z in ZDEPTHS) == 1,
        f"OneLocation_{b}"
    )

# ── C2: At most one new box per slot (respect existing inventory) ──
for a in AISLES:
    for s in SIDES:
        for x in XPOS:
            for y in YLEVELS:
                for z in ZDEPTHS:
                    occ = occupied.get((a, s, x, y, z), 0)
                    prob += (
                        pulp.lpSum(Assign[b, a, s, x, y, z] for b in boxes) + occ <= 1,
                        f"SlotCapacity_{a}_{s}_{x}_{y}_{z}"
                    )

# ── C3: Depth precedence — z=2 only when z=1 is filled ───────
for a in AISLES:
    for s in SIDES:
        for x in XPOS:
            for y in YLEVELS:
                occ_z1 = occupied.get((a, s, x, y, 1), 0)
                prob += (
                    pulp.lpSum(Assign[b, a, s, x, y, 2] for b in boxes)
                    <= occ_z1 + pulp.lpSum(Assign[b, a, s, x, y, 1] for b in boxes),
                    f"DepthPrecedence_{a}_{s}_{x}_{y}"
                )

# ── C4: Shuttle time ≤ Makespan (per aisle × Y-level) ────────
#  Round-trip cost per box at position x = 2 * (handling + x)
for a in AISLES:
    for y in YLEVELS:
        prob += (
            pulp.lpSum(
                Assign[b, a, s, x, y, z] * 2 * (HANDLING + x)
                for b in boxes for s in SIDES for x in XPOS for z in ZDEPTHS
            ) <= Makespan,
            f"ShuttleTime_{a}_{y}"
        )

# ── 3. Solve ──────────────────────────────────────────────────
print("Solving warehouse box-assignment problem …\n")
solver = pulp.PULP_CBC_CMD(msg=False)
status = prob.solve(solver)

# ── 4. Report ─────────────────────────────────────────────────
print(f"{'='*60}")
print(f"  Solve status : {pulp.LpStatus[prob.status]}")
print(f"  Makespan     : {pulp.value(Makespan):.1f} seconds")
print(f"{'='*60}\n")

print(f"{'Box':<10} {'Aisle':>6} {'Side':>6} {'X':>4} {'Y':>4} {'Z':>4}  {'RoundTrip':>10}")
print("-" * 52)

for b in boxes:
    for a in AISLES:
        for s in SIDES:
            for x in XPOS:
                for y in YLEVELS:
                    for z in ZDEPTHS:
                        if pulp.value(Assign[b, a, s, x, y, z]) > 0.5:
                            rt = 2 * (HANDLING + x)
                            print(f"{b:<10} {a:>6} {s:>6} {x:>4} {y:>4} {z:>4}  {rt:>8.0f} s")

total_slots = NUM_AISLES * NUM_SIDES * NUM_X * NUM_Y * NUM_Z
print(f"\nGrid size  : {NUM_AISLES}A × {NUM_SIDES}S × {NUM_X}X × {NUM_Y}Y × {NUM_Z}Z = {total_slots} slots")
print(f"Variables  : {len(boxes)} boxes × {total_slots} slots = {len(boxes)*total_slots} binary + 1 continuous")
