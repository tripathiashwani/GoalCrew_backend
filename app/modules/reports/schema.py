from pydantic import BaseModel
from datetime import date

class ReportRequest(BaseModel):
    start_date: date
    end_date: date
