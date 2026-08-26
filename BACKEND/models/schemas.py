from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# =========================
# CONSUMER REPORT
# =========================

class ConsumerReportRequest(BaseModel):
    medicine_batch_id: str
    qr_id: str
    reported_at: datetime
    issue_type: str
    symptoms: str
    description: str
    report_status: str = "OPEN"
    is_synthetic: bool = False