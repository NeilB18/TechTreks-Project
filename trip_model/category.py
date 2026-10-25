# class Category(Enum):          # fixed set, not a free-form list
#     LODGING, TRANSPORT, FOOD, DRINKS, ACTIVITIES, OTHER, SETTLEMENT

from enum import Enum

class Category(Enum):
    LODGING = 1
    TRANSPORT = 2
    FOOD = 3
    DRINKS = 4
    ACTIVITIES = 5
    OTHER = 6
    SETTLEMENT = 7
