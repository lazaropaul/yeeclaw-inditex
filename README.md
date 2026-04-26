# yeeclaw-inditex | Hack The Flow: Inditex Logistics Optimizer
**HackUPC 2026 - Challenge: Algorithms for Greater Logistics Agility**

Implementation of a high-performance automated silo management system for Inditex. Designed to maximize *Throughput* (pallets per hour), minimize bottlenecks, and manage real-time 3D logistics through mathematical optimization and dynamic priority scheduling.

## Key Performance Indicators (KPIs)
Our algorithm has been calibrated to guarantee stability and speed under severe physical constraints:
* **Full Pallets:** 100% efficiency in the consolidation of pallets (12 boxes per destination).
* **Base Throughput:** ~12 pallets/hour (Base metric that scales linearly with injection volume and warehouse size).
* **Z-Rule Compliance:** 100% success in managing double depth, detecting blockages, and automatically generating `RELOCATE` tasks.

---

## The Challenge
Inditex distribution centers handle hundreds of thousands of boxes. The goal is to orchestrate the "intelligence" of the *shuttles*, coordinating simultaneous input and output flows to form pallets, while managing a critical resource limitation: **only 1 shared Shuttle per height level (Y)**.

---

## Architecture and Core Algorithms

We built the system focusing on computational speed ($O(1)$ in memory operations), physical traceability, and movement efficiency.

### 1. Hybrid Optimization: MILP + Heuristics
* **Inbound (MILP Storage):** We use Mixed-Integer Linear Programming (`PuLP`) to decide the optimal empty coordinate for incoming boxes. The model penalizes the use of depth Z=2 and balances the load across Y levels to prevent shuttle bottlenecks.
* **Outbound (Dynamic Priority):** When retrieving boxes, the algorithm dynamically reorders the sequence based on extraction cost. It minimizes the *makespan* by calculating distances and blockages in real-time.

### 2. Trip Chaining (Maximizing Shuttle Utilization)
The core of our efficiency. Shuttles never travel empty if it can be avoided. The system interleaves operations, allowing a shuttle that just stored a box to immediately pick up a nearby box for output. Empty travel is the enemy of logistics!

### 3. Discrete Event Simulation (DES) Engine
Instead of artificial delays (`time.sleep`), we built a simulator based on priority queues (`heapq`). It processes hours of logistics operations in fractions of a second with chronometric precision using the official Inditex formula: $t = 10 + d$.

### 4. Separation of Logic and Physical Identity
The system models the warehouse state by separating two distinct concepts:
* **Logical ID (20 digits):** `30100280122093090329` (Origin, Destination, Bulk). Used for pallet grouping.
* **Physical Address (11 digits):** `01_02_003_04_01` (Aisle, Side, X, Y, Z). Controls robot movement.

---

## Project Structure

```text
yeeclaw-inditex/
├── data/
│   └── silo-semi-empty.csv         # Deterministic initial warehouse state
├── src/
│   ├── algorithms/
│   │   ├── milp_optimizer.py       # Inbound: Mathematical solver for optimal spatial assignment
│   │   ├── storage.py              # Inbound: Interface bridging simulator and MILP optimizer
│   │   ├── retrieval_optimizer.py  # Outbound: MILP sequencer to minimize Makespan and avoid collisions
│   │   └── retrieval.py            # Outbound: Task generator and Deadlock evasion (RELOCATEs)
│   ├── model/
│   │   └── silo_state.py           # In-RAM Database (Dataclasses, slots=True, O(1))
│   ├── simulation/
│   │   └── simulator.py            # Discrete event engine (DES) and shuttle controller
│   └── utils/
│       └── csv_loader.py           # Initial physical state parser (11-digit coords)
├── main.py                         # Entry point and orchestrator
└── README.md
```

---

## Technologies Used
* **Language:** Python 3.10+
* **Mathematical Modeling:** `PuLP` (Coin-OR Branch and Cut Solver).
* **Data Structures:** `dataclasses` (immutability and *slots* for maximum RAM efficiency), `collections.deque`, `heapq`.
* **Zero Dependencies (Almost):** *Plug & Play* architecture designed to run without external databases.

---

## Installation & Execution

The project runs autonomously without the need for containers or complex environment variables.

1. **Install mathematical dependencies:**
   ```bash
   pip install pulp
   ```

2. **Run the simulation:**
   From the project root, ensure the PYTHONPATH is set and run the orchestrator:
   ```bash
   export PYTHONPATH=$PYTHONPATH:.
   python3 main.py
   ```

### Console Guide (Real-Time Operations)
The system displays a dashboard with detailed operational logs:
* `📥 INBOUND`: Incoming boxes (Origin) and their optimal physical assignment (A, S, X, Y, Z).
* `📤 OUTBOUND`: Shuttles departing to retrieve items for pallet consolidation.
* `🔄 RELOCATE`: Automatic relocations to clear blockages in Z=1.
* `⚡ TRIP CHAINING`: Shuttles executing combined tasks without returning to the head.
* `✅ PALLET COMPLETED`: Pallets successfully dispatched after collecting all 12 units.

Upon completion, a final scorecard with logistics metrics will be printed.

---
*Designed and coded for HackUPC 2026.*


