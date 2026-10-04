import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List

from fastapi import FastAPI, HTTPException
import httpx

from app.schemas.interaction import DrugCheckRequest, DrugCheckResponse
from app.services.rxclass_service import (
    detect_therapeutic_overlaps,
    get_all_atc_classes,
)
from app.services.rxnorm_service import get_rxcui_by_name


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage persistent HTTP client session during app lifecycle."""
    app.state.client = httpx.AsyncClient(timeout=10.0)
    yield
    await app.state.client.aclose()


app = FastAPI(
    title="TheraOverlap Engine",
    description="Clinical decision support API for drug redundancy and ATC overlap detection.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> dict:
    """Return service health status."""
    return {"status": "ok", "service": "TheraOverlap"}


@app.get("/api/v1/classes", response_model=List[str])
async def list_atc_classes() -> List[str]:
    """Return all official ATC drug classes available for selection."""
    if getattr(app.state, "atc_classes", None):
        return app.state.atc_classes
    classes = await get_all_atc_classes(app.state.client)
    app.state.atc_classes = classes
    return classes


@app.post("/api/v1/check", response_model=DrugCheckResponse)
async def check_drugs(payload: DrugCheckRequest) -> DrugCheckResponse:
    """Analyze a drug list for identity overlaps and ATC pharmacological redundancies."""
    raw_names = list(dict.fromkeys([d.strip() for d in payload.drugs if d.strip()]))
    if not raw_names:
        raise HTTPException(status_code=400, detail="Drug list cannot be empty.")

    client: httpx.AsyncClient = app.state.client

    # Concurrent resolution of RxCUIs via RxNorm
    tasks = [get_rxcui_by_name(name, client) for name in raw_names]
    results = await asyncio.gather(*tasks)

    resolved_drugs = []
    unresolved_drugs = []

    for name, res in zip(raw_names, results):
        if res and res.get("rxcui"):
            resolved_drugs.append(res)
        else:
            unresolved_drugs.append(name)

    # Duplicate active substance check (same RxCUI under distinct input names)
    rxcuis_seen = {}
    duplicate_alerts = []
    for item in resolved_drugs:
        cui = item["rxcui"]
        if cui in rxcuis_seen:
            duplicate_alerts.append(
                {
                    "severity_raw": "high",
                    "level": "Danger",
                    "drugs_involved": [rxcuis_seen[cui], item["input_name"]],
                    "description": (
                        f"Surdosage potentiel : '{rxcuis_seen[cui]}' et '{item['input_name']}' "
                        f"partagent le même identifiant de principe actif (RxCUI {cui})."
                    ),
                }
            )
        else:
            rxcuis_seen[cui] = item["input_name"]

    # Therapeutic class overlap check via RxClass ATC API
    report = await detect_therapeutic_overlaps(resolved_drugs, client)

    # Consolidate alerts
    all_interactions = duplicate_alerts + report.get("interactions", [])
    if duplicate_alerts:
        report["status"] = "Danger"
    report["total_alerts"] = len(all_interactions)
    report["interactions"] = all_interactions

    return DrugCheckResponse(
        resolved_drugs=resolved_drugs,
        unresolved_drugs=unresolved_drugs,
        report=report,
    )