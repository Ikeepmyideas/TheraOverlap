from collections import defaultdict
from typing import Any, Dict, List, Set
import httpx

RXCLASS_BASE_URL = "https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json"


async def get_atc_classes_for_rxcui(
    rxcui: str, client: httpx.AsyncClient
) -> List[Dict[str, str]]:
    """Retrieve ATC drug classes for a given RxCUI from NLM RxClass API.

    Args:
        rxcui: Canonical RxCUI identifier.
        client: Active HTTPX asynchronous client session.

    Returns:
        List of dicts containing classId and className.
    """
    params = {"rxcui": rxcui, "relaSource": "ATC"}
    try:
        response = await client.get(RXCLASS_BASE_URL, params=params, timeout=8.0)
        if response.status_code != 200:
            return []

        data = response.json()
        entries = (
            data.get("rxclassDrugInfoList", {}).get("rxclassDrugInfo", [])
        )

        classes = []
        for entry in entries:
            concept = entry.get("rxclassMinConceptItem", {})
            class_id = concept.get("classId")
            class_name = concept.get("className")
            if class_id and class_name:
                classes.append({"class_id": class_id, "class_name": class_name})
        return classes
    except (httpx.RequestError, httpx.TimeoutException):
        return []


async def detect_therapeutic_overlaps(
    drug_items: List[Dict[str, str]], client: httpx.AsyncClient
) -> Dict[str, Any]:
    """Detect therapeutic redundancies by computing class intersections.

    Args:
        drug_items: List of resolved drugs [{'input_name': ..., 'rxcui': ...}].
        client: Active HTTPX asynchronous client session.

    Returns:
        Structured analysis report with alerts on therapeutic overlap.
    """
    if len(drug_items) < 2:
        return {
            "status": "Safe",
            "total_alerts": 0,
            "interactions": [],
            "message": "At least two drugs are required to evaluate overlap.",
        }

    # Map each drug to its set of ATC classes
    class_to_drugs = defaultdict(list)

    for item in drug_items:
        rxcui = item["rxcui"]
        classes = await get_atc_classes_for_rxcui(rxcui, client)
        # Retain 4th level ATC classes (pharmacological group, like M01AE)
        seen_classes: Set[str] = set()
        for c in classes:
            cid = c["class_id"]
            if len(cid) >= 4 and cid not in seen_classes:
                seen_classes.add(cid)
                class_to_drugs[(cid, c["class_name"])].append(item["input_name"])

    parsed_alerts = []
    for (cid, cname), drugs in class_to_drugs.items():
        unique_drugs = sorted(list(set(drugs)))
        if len(unique_drugs) > 1:
            parsed_alerts.append(
                {
                    "severity_raw": "high",
                    "level": "Danger",
                    "drugs_involved": unique_drugs,
                    "description": (
                        f"Chevauchement thérapeutique détecté (Classe ATC {cid} - {cname}) : "
                        f"cumul de plusieurs molécules de même visée pharmacologique."
                    ),
                }
            )

    status = "Danger" if parsed_alerts else "Safe"

    return {
        "status": status,
        "total_alerts": len(parsed_alerts),
        "interactions": parsed_alerts,
        "disclaimer": "Academic demonstration tool. Does not constitute medical advice.",
    }