"""Small compatible project for browser CRUD/measurement workflows."""

import sys
from decimal import Decimal
from estimator.data.schedule import (
    ScheduleDatabase,
    ScheduleItemModel,
    ResourceItemModel,
)
from estimator.undo import Stack

db = ScheduleDatabase(Stack())
db.create_new_database(sys.argv[1])
rate = Decimal(sys.argv[2]) if len(sys.argv) > 2 else Decimal("10")
resource = ResourceItemModel(
    "R",
    "Material",
    "kg",
    rate,
    Decimal("0"),
    Decimal("0"),
    category="Materials",
)
item = ScheduleItemModel(
    "A", "Foundation", "m3", rate * 2, Decimal("1"), category="Work"
)
item.resources = {"R": resource}
item.add_ana_group("Materials")
item.add_ana_res(["R", Decimal("2"), ""], 0)
item.add_ana_sum("Total")
db.insert_item(item)
db.close_database()
