from typing import Any, Dict, Optional

import httpx

BASE_URL = "https://rxnav.nlm.nih.gov/REST"

async def get_rxcui_by_name(
        drug_name: str,
        client: httpx.AsyncClient,
) -> Optional[Dict[str, str]]:
    """ Resolve a drug brand name or active substance to its canonical RxCUI.
    Args: 
        drug_name: The raw commercial or chemical drug name provided.
        client: An active HTTPX asynchronous client session.

    Returns:
        A dictionnary containing the input name and the resolved RxCUI string
        or None if no matching identifier is found or if a network error occurs.
    """
    clean_name = drug_name.strip()
    if not clean_name:
        return None

    url = f"{BASE_URL}/rxcui.json"
    params = {"name": clean_name, "search":1}

    try:
        response = await client.get(url, params=params, timeout=5.0)
        if response.status_code != 200:
            return None

        payload: Dict[str, Any] = response.json()
        id_group = payload.get("idGroup", {})
        rxnorm_ids = id_group.get("rxnormId", [])

        if not rxnorm_ids:
            return None

        return{
            "input_name": clean_name,
            "rxcui": str(rxnorm_ids[0]),
        }
    except (httpx.RequestError, httpx.TimeoutException):
        return None