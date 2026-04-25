from enum import Enum
from pydantic import BaseModel
from typing import Optional

class TaskType(str, Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"
    RELOCATION = "RELOCATION"

class Location(BaseModel):
    x: int
    y: int
    z: int  # 1 for front, 2 for back

class Box(BaseModel):
    id: str
    destination_code: str

class Shuttle(BaseModel):
    id: str
    y_level: int
    current_x: int

class Task(BaseModel):
    id: str
    task_type: TaskType
    box: Box
    target_location: Location
    dropoff_location: Optional[Location] = None
    is_active: bool = False  # Set to True when the destination code becomes active
