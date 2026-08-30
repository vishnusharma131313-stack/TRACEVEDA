"""
Request models shared between routers.

Route-local models stay in their own route module; only shapes used from more
than one place, or long enough to bury a route, live here.
"""

from datetime import datetime

from pydantic import BaseModel, Field


# =========================
# CONSUMER REPORT
# =========================

class ConsumerReportRequest(BaseModel):
    """
    An adverse-event or suspect-product report from a member of the public.

    `report_status` is deliberately absent: a new report is always OPEN, and
    the field used to be settable from the request body, which let a report
    be filed already marked RESOLVED. Moving a report through its workflow is
    PATCH /api/consumer/reports/{id}/status, which requires a regulator.
    """

    medicine_batch_id: str = Field(min_length=1, max_length=64)
    qr_id: str = Field(min_length=1, max_length=64)
    reported_at: datetime
    issue_type: str = Field(min_length=1, max_length=100)
    symptoms: str = Field(min_length=1, max_length=2000)
    description: str = Field(min_length=1, max_length=5000)
    is_synthetic: bool = False
