from pydantic import BaseModel
from typing import Optional


class CritiqueRefineResult(BaseModel):
    final_content: str
    run_log: str
    error: Optional[str] = None
