from typing import List
from models import Task, TaskType
import warehouse as wh_mod

class QueueManager:
    def __init__(self):
        # Interruptible, state-aware pool of tasks
        self.pending_tasks: List[Task] = []

    def add_task(self, task: Task):
        # Add to the pool
        self.pending_tasks.append(task)
        # If it's an outbound task for an already active destination, activate it immediately
        if task.task_type == TaskType.OUTBOUND and task.box.destination_code in wh_mod.warehouse.active_destinations:
            task.is_active = True

    def intervene(self, destination_code: str):
        """The Intervention Trigger!"""
        # Register the code in warehouse state (max 8)
        wh_mod.warehouse.add_active_destination(destination_code)
        
        # Instantly flag all existing pending OUTBOUND tasks that match this code
        # as "Active/High Priority" and thus available for the Output Algorithm.
        for task in self.pending_tasks:
            if task.task_type == TaskType.OUTBOUND and task.box.destination_code == destination_code:
                task.is_active = True

    def complete_pallet(self, destination_code: str):
        """Frees up one of the active slots"""
        wh_mod.warehouse.remove_active_destination(destination_code)

    def get_active_outbound_tasks(self, y_level: int) -> List[Task]:
        return [t for t in self.pending_tasks 
                if t.task_type == TaskType.OUTBOUND 
                and t.is_active 
                and t.target_location.y == y_level]

    def get_pending_inbound_tasks(self, y_level: int) -> List[Task]:
        return [t for t in self.pending_tasks 
                if t.task_type == TaskType.INBOUND 
                and t.target_location.y == y_level]

    def get_pending_relocation_tasks(self, y_level: int) -> List[Task]:
        return [t for t in self.pending_tasks
                if t.task_type == TaskType.RELOCATION
                and t.target_location.y == y_level]

    def get_all_tasks(self) -> List[Task]:
        return self.pending_tasks

    def remove_task(self, task_id: str):
        self.pending_tasks = [t for t in self.pending_tasks if t.id != task_id]

queue = QueueManager()
