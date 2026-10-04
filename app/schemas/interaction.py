from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class DrugCheckRequest(BaseModel):
    """Payload sent by the user containing raw drug names """

    drugs: List[str] = Field(
        ...,
        min_length=1,
        description="List of brand names or active ingredients to evaluate",
        example=["Advil", "Nurofen"],
    )

class ResolvedDrug(BaseModel):
    """ Resolved entity mapping the input string to standard RxCUI """
    input_name: str
    rxcui: str

class InteractionAlert(BaseModel):
    """ Single clinical interaction or overdose warning """
    level: str
    severity_raw: str
    drugs_involved: List[Optional[str]]
    description: str

class AnalysisReport(BaseModel):
    """ Normalized analysis response from TheraOverlap engine """
    status: str
    total_alerts: int
    interactions: List[InteractionAlert]
    disclaimer: str
    message: Optional[str] = None

class DrugCheckResponse(BaseModel):
    """ Complete endpoint response schema """
    resolved_drugs: List[ResolvedDrug]
    unresolved_drugs: List[str]
    report: Dict[str, Any]