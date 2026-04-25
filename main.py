from fastapi import FastAPI, HTTPException
from typing import Optional
from models import Box, Location, Shuttle, Task, TaskType
from input_algo import input_algorithm
from output_algo import output_algorithm
from queue_manager import queue
from warehouse import warehouse
import uuid

app = FastAPI(title="Hack the Flow Logistics API - IRA Mode")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Inditex Tech Hackathon API! IRA Algorithm is active."}

@app.post("/boxes/inbound", response_model=Task)
def register_inbound_box(box: Box, preferred_y: int = 1):
    """Register a new box at X=0, creates a Storage Task."""
    try:
        task = input_algorithm.assign_storage_location(box, preferred_y)
        return task
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/pallets/activate/{destination_code}")
def activate_pallet(destination_code: str):
    """The Intervention Trigger! Activates a destination code, creating high priority tasks."""
    try:
        queue.intervene(destination_code)
        
        # Scan warehouse for any boxes matching this code, and push OUTBOUND tasks
        # to the queue since they are now part of an active pallet!
        count = 0
        for loc_tuple, box in warehouse.grid.items():
            if box.destination_code == destination_code:
                # Check if an OUTBOUND task already exists for this box
                if not any(t.task_type == TaskType.OUTBOUND and t.box.id == box.id for t in queue.get_all_tasks()):
                    loc = Location(x=loc_tuple[0], y=loc_tuple[1], z=loc_tuple[2])
                    task = Task(
                        id=str(uuid.uuid4()),
                        task_type=TaskType.OUTBOUND,
                        box=box,
                        target_location=loc,
                        is_active=True
                    )
                    queue.add_task(task)
                    count += 1
        return {"status": "Intervention activated", "tasks_generated": count}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/pallets/complete/{destination_code}")
def complete_pallet(destination_code: str):
    """Frees up an active pallet slot."""
    queue.complete_pallet(destination_code)
    return {"status": "Pallet completed, queue slot freed"}

@app.post("/shuttles/next-task", response_model=Optional[Task])
def get_shuttle_next_task(shuttle: Shuttle):
    """The Output Algorithm router! Returns the next optimal task for this shuttle."""
    task = output_algorithm.get_next_move(shuttle)
    return task

@app.post("/shuttles/complete-task/{task_id}")
def complete_shuttle_task(task_id: str):
    """Simulates physical completion of the task, updating the overall Warehouse state."""
    all_tasks = queue.get_all_tasks()
    task = next((t for t in all_tasks if t.id == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    # Apply warehouse state changes
    if task.task_type == TaskType.INBOUND:
        warehouse.place_box(task.box, task.target_location)
    elif task.task_type == TaskType.OUTBOUND:
        warehouse.remove_box(task.target_location)
    elif task.task_type == TaskType.RELOCATION:
        warehouse.remove_box(task.target_location)
        warehouse.place_box(task.box, task.dropoff_location)
        
    # Remove from queue
    queue.remove_task(task_id)
    return {"status": "Task physically completed and state updated!"}
