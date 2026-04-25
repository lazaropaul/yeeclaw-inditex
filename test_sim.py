from models import Box, Shuttle, Location, TaskType
from warehouse import warehouse
from queue_manager import queue
from input_algo import input_algorithm
from output_algo import output_algorithm
import random
import uuid

b1 = Box(id="b1", destination_code="PALLET_1")
t = input_algorithm.assign_storage_location(b1, preferred_y=1)
shuttle = Shuttle(id="s", y_level=1, current_x=0)
move = output_algorithm.get_next_move(shuttle)
print("Move target:", move.target_location)
warehouse.place_box(move.box, move.target_location)
queue.remove_task(move.id)
print("Grid len:", len(warehouse.grid))
for k, v in warehouse.grid.items():
    print(v.destination_code == "PALLET_1")
