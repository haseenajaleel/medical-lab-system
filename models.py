from pydantic import BaseModel
from typing import List

class Booking(BaseModel):
    name: str
    phone: str
    test: List[str]   # allows multiple tests ["Blood test", "ECG"]
    time: str