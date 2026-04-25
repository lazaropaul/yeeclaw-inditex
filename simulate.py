"""
Dynamic, tick-based IRA Warehouse Simulation.

Boxes arrive continuously while shuttles concurrently handle INBOUND,
OUTBOUND, and RELOCATION tasks in every tick. Pallet activations happen
mid-stream once enough stock has been stored.
"""

from models import Box, Shuttle, Location, Task, TaskType
import warehouse as wh_mod
import queue_manager as qm_mod
import input_algo as ia_mod
import output_algo as oa_mod
import batch_algo as ba_mod
import random
import uuid


def run_simulation(seed=42):
    random.seed(seed)

    print("=" * 60)
    print("   DYNAMIC IRA Warehouse Simulation (Tick-Based)")
    print("=" * 60)

    # ── Configuration ────────────────────────────────────────────
    NUM_PALLETS = 40
    BOXES_PER_PALLET = 12
    MAX_X = 50
    MAX_Y = 10
    SHUTTLE_COUNT = MAX_Y
    MAX_ACTIVE_PALLETS = 8
    ARRIVAL_RATE = 3  # boxes arriving per tick

    # ── Fresh state (reset module-level singletons) ──────────────
    from warehouse import WarehouseState
    from queue_manager import QueueManager

    wh = WarehouseState(max_x=MAX_X, max_y=MAX_Y)
    qm = QueueManager()

    # Patch ALL module-level singletons
    wh_mod.warehouse = wh
    qm_mod.warehouse = wh
    qm_mod.queue = qm

    # ── Generate the full box manifest ───────────────────────────
    pallets = [f"PALLET_{i:02d}" for i in range(1, NUM_PALLETS + 1)]
    all_boxes = []
    for pallet in pallets:
        for _ in range(BOXES_PER_PALLET):
            all_boxes.append(Box(id=str(uuid.uuid4())[:8], destination_code=pallet))
    random.shuffle(all_boxes)

    arrival_queue = list(all_boxes)

    # ── Shuttle fleet ────────────────────────────────────────────
    shuttles = [Shuttle(id=f"shuttle_{y}", y_level=y, current_x=0)
                for y in range(1, SHUTTLE_COUNT + 1)]

    # ── Pallet activation state ──────────────────────────────────
    pallets_waiting = list(pallets)
    active_pallets: set[str] = set()
    pallet_box_retrieved: dict[str, int] = {p: 0 for p in pallets}

    # ── Metrics ──────────────────────────────────────────────────
    total_distance = 0
    total_time_cost = 0
    inbound_count = 0
    outbound_count = 0
    relocations_triggered = 0
    completed_pallets = 0
    dual_weave_count = 0

    tick = 0
    MAX_TICKS = 10000

    def activate_pallets_up_to_cap():
        """Activate pallets and generate OUTBOUND tasks for boxes already in grid."""
        needed = MAX_ACTIVE_PALLETS - len(active_pallets)
        if needed > 0 and pallets_waiting:
            # Use Simulated Annealing to pick optimal batch
            best_batch = ba_mod.batch_algo.get_optimal_batch(pallets_waiting, min(needed, len(pallets_waiting)))
            
            for code in best_batch:
                pallets_waiting.remove(code)
                active_pallets.add(code)
                qm.intervene(code)
                # Scan warehouse grid for boxes matching this code
                for loc_tuple, box in list(wh.grid.items()):
                    if box.destination_code == code:
                        # Avoid duplicate OUTBOUND tasks
                        already_has_task = any(
                            t.task_type == TaskType.OUTBOUND and t.box.id == box.id
                            for t in qm.pending_tasks
                        )
                        if not already_has_task:
                            loc = Location(x=loc_tuple[0], y=loc_tuple[1], z=loc_tuple[2])
                            task = Task(
                                id=str(uuid.uuid4()),
                                task_type=TaskType.OUTBOUND,
                                box=box,
                                target_location=loc,
                                is_active=True,
                            )
                            qm.add_task(task)

    def create_outbound_if_active(box: Box, loc: Location):
        """When a box is physically stored, check if its pallet is already active.
        If so, immediately create an OUTBOUND task for it."""
        if box.destination_code in active_pallets:
            already_has_task = any(
                t.task_type == TaskType.OUTBOUND and t.box.id == box.id
                for t in qm.pending_tasks
            )
            if not already_has_task:
                task = Task(
                    id=str(uuid.uuid4()),
                    task_type=TaskType.OUTBOUND,
                    box=box,
                    target_location=loc,
                    is_active=True,
                )
                qm.add_task(task)

    # ── Activate initial batch (grid is empty, so no OUTBOUND yet) ──
    activate_pallets_up_to_cap()

    print(f"Config: {NUM_PALLETS} pallets × {BOXES_PER_PALLET} boxes = "
          f"{len(all_boxes)} total boxes")
    print(f"Shuttles: {SHUTTLE_COUNT} | Arrival rate: {ARRIVAL_RATE}/tick | "
          f"Max active pallets: {MAX_ACTIVE_PALLETS}")
    print(f"Active pallets at start: {list(active_pallets)}")
    print("-" * 60)

    # ════════════════════════════════════════════════════════════
    #  MAIN SIMULATION LOOP
    # ════════════════════════════════════════════════════════════
    while tick < MAX_TICKS:
        tick += 1
        anything_happened = False

        # ── 1. ARRIVALS ──────────────────────────────────────────
        arrivals_this_tick = min(ARRIVAL_RATE, len(arrival_queue))
        for _ in range(arrivals_this_tick):
            box = arrival_queue.pop(0)
            prefer_y = random.randint(1, MAX_Y)
            try:
                ia_mod.input_algorithm.assign_storage_location(box, preferred_y=prefer_y)
                anything_happened = True
            except Exception:
                arrival_queue.append(box)

        # ── 2. SHUTTLE MOVES ─────────────────────────────────────
        for shuttle in shuttles:
            move = oa_mod.output_algorithm.get_next_move(shuttle)
            if not move:
                continue

            anything_happened = True

            # Determine pickup X
            if move.task_type == TaskType.INBOUND:
                pickup_x = 0
            else:
                pickup_x = move.target_location.x

            d = abs(shuttle.current_x - pickup_x)

            # Detect dual-command weaving
            if move.task_type != TaskType.INBOUND and shuttle.current_x != 0:
                dual_weave_count += 1

            total_distance += d
            total_time_cost += 10 + d

            # Execute the move
            if move.task_type == TaskType.INBOUND:
                shuttle.current_x = move.target_location.x
                wh.place_box(move.box, move.target_location)
                inbound_count += 1
                # KEY: if this box's pallet is already active, create OUTBOUND immediately
                create_outbound_if_active(move.box, move.target_location)

            elif move.task_type == TaskType.OUTBOUND:
                shuttle.current_x = 0
                wh.remove_box(move.target_location)
                outbound_count += 1

                dest = move.box.destination_code
                pallet_box_retrieved[dest] += 1
                if pallet_box_retrieved[dest] >= BOXES_PER_PALLET:
                    active_pallets.discard(dest)
                    qm.complete_pallet(dest)
                    completed_pallets += 1
                    activate_pallets_up_to_cap()

            elif move.task_type == TaskType.RELOCATION:
                shuttle.current_x = move.dropoff_location.x
                wh.remove_box(move.target_location)
                wh.place_box(move.box, move.dropoff_location)
                relocations_triggered += 1

            qm.remove_task(move.id)

        # ── 3. Termination check ─────────────────────────────────
        if completed_pallets >= NUM_PALLETS:
            break

        # If nothing happened and there are still pallets to complete,
        # try to activate more pallets (boxes are in grid but no outbound tasks yet)
        if not anything_happened:
            if completed_pallets < NUM_PALLETS and (pallets_waiting or active_pallets):
                # Force re-check: scan the grid for active-pallet boxes that
                # don't have an outbound task yet
                for code in list(active_pallets):
                    for loc_tuple, box in list(wh.grid.items()):
                        if box.destination_code == code:
                            already = any(
                                t.task_type == TaskType.OUTBOUND and t.box.id == box.id
                                for t in qm.pending_tasks
                            )
                            if not already:
                                loc = Location(x=loc_tuple[0], y=loc_tuple[1], z=loc_tuple[2])
                                task = Task(
                                    id=str(uuid.uuid4()),
                                    task_type=TaskType.OUTBOUND,
                                    box=box,
                                    target_location=loc,
                                    is_active=True,
                                )
                                qm.add_task(task)
                                anything_happened = True

            if not anything_happened and not arrival_queue and not qm.get_all_tasks():
                print(f"WARNING: Stall at tick {tick}. "
                      f"Completed {completed_pallets}/{NUM_PALLETS} pallets. "
                      f"Grid: {len(wh.grid)} boxes. Breaking.")
                break

    # ════════════════════════════════════════════════════════════
    #  STATISTICS
    # ════════════════════════════════════════════════════════════
    total_ops = inbound_count + outbound_count + relocations_triggered
    avg_dist = total_distance / total_ops if total_ops else 0

    naive_avg_d = MAX_X
    naive_total_d = naive_avg_d * total_ops
    naive_total_t = total_ops * (10 + naive_avg_d)
    improvement_d = (1 - total_distance / naive_total_d) * 100 if naive_total_d else 0
    improvement_t = (1 - total_time_cost / naive_total_t) * 100 if naive_total_t else 0

    print()
    print("=" * 60)
    print("              DYNAMIC SIMULATION RESULTS")
    print("=" * 60)
    print(f"Simulation ticks elapsed:       {tick}")
    print(f"Boxes remaining in arrival Q:   {len(arrival_queue)}")
    print(f"Boxes still in warehouse grid:  {len(wh.grid)}")
    print()
    print("── Operations ─────────────────────────────────────────")
    print(f"  Inbounds completed:           {inbound_count}")
    print(f"  Outbounds completed:          {outbound_count}")
    print(f"  Relocations triggered:        {relocations_triggered}")
    print(f"  Pallets fully completed:      {completed_pallets}/{NUM_PALLETS}")
    print()
    print("── IRA Performance ────────────────────────────────────")
    print(f"  Total Distance (d):           {total_distance:,} grid units")
    print(f"  Total Time Cost (10+d):       {total_time_cost:,} seconds")
    print(f"  Average Distance per Op:      {avg_dist:.2f}")
    print(f"  Dual-Command Weaves:          {dual_weave_count}")
    print()
    print("── vs Naive FIFO Baseline ─────────────────────────────")
    print(f"  Naive Total Distance:         {naive_total_d:,} (avg {naive_avg_d} per op)")
    print(f"  Naive Total Time:             {naive_total_t:,}")
    print(f"  Distance Improvement:         {improvement_d:.1f}%")
    print(f"  Time Improvement:             {improvement_t:.1f}%")
    print("=" * 60)


if __name__ == "__main__":
    run_simulation()
