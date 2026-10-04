import os
from typing import List
import requests
import streamlit as st

raw_backend_url = os.getenv("BACKEND_URL", "http://localhost:8000").strip()

if not raw_backend_url.startswith("http://") and not raw_backend_url.startswith(
    "https://"
):
    BACKEND_BASE_URL = f"https://{raw_backend_url}".rstrip("/")
else:
    BACKEND_BASE_URL = raw_backend_url.rstrip("/")

st.set_page_config(
    page_title="TheraOverlap UI",
    page_icon="💊",
    layout="centered",
)

st.title("💊 TheraOverlap — Therapeutic Control")
st.markdown(
    "Detect pharmacological redundancies and ATC class overlaps in real time."
)


# 2. Récupération résiliente sans cacher les erreurs
def get_classes_from_api() -> List[str]:
    """Retrieve all official ATC classes via the backend proxy endpoint"""
    url = f"{BACKEND_BASE_URL}/api/v1/classes"
    try:
        response = requests.get(url, timeout=50.0)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and data:
                return data
        else:
            st.error(f"Backend HTTP {response.status_code} sur {url}")
    except requests.exceptions.RequestException as err:
        st.error(f"Erreur de connexion au backend ({url}) : {err}")
    return []


@st.cache_data(ttl=3600)
def fetch_all_classes_cached() -> List[str]:
    return get_classes_from_api()


with st.spinner("Connecting to backend engine (this may take ~40s if waking up)..."):
    available_classes = fetch_all_classes_cached()

    if not available_classes:
        available_classes = get_classes_from_api()


if "custom_drugs_list" not in st.session_state:
    st.session_state.custom_drugs_list = []

selected_classes = st.multiselect(
    f"Search and select from {len(available_classes)} official ATC classes:",
    options=available_classes,
    default=[],
)

col1, col2 = st.columns([3, 1])
with col1:
    new_drug = st.text_input(
        "Add a specific drug or brand name (e.g., Synthroid, Glucophage, Aldactone):",
        key="drug_input",
    )
with col2:
    st.write("")
    st.write("")
    if st.button("➕ Add"):
        cleaned = new_drug.strip()
        if cleaned and cleaned not in st.session_state.custom_drugs_list:
            st.session_state.custom_drugs_list.append(cleaned)

if st.session_state.custom_drugs_list:
    st.write("**Custom drugs added:**")
    cols = st.columns(len(st.session_state.custom_drugs_list))
    for i, drug in enumerate(list(st.session_state.custom_drugs_list)):
        if cols[i].button(f"❌ {drug}", key=f"remove_{drug}_{i}"):
            st.session_state.custom_drugs_list.remove(drug)
            st.rerun()

all_selected_items = list(
    set(selected_classes + st.session_state.custom_drugs_list)
)

if all_selected_items:
    st.info(f"**Total selection to analyze ({len(all_selected_items)}):** {', '.join(all_selected_items)}")

st.divider()

if st.button(" Run interaction analysis", type="primary"):
    if len(all_selected_items) < 2:
        st.warning("Please select at least two drugs or classes to evaluate overlaps.")
    else:
        with st.spinner("Evaluating therapeutic overlaps via TheraOverlap engine..."):
            try:
                response = requests.post(
                    f"{BACKEND_BASE_URL}/api/v1/check",
                    json={"drugs": all_selected_items},
                    timeout=30.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    report = data.get("report", {})
                    status = report.get("status", "Unknown")

                    if status == "Danger":
                        st.error(
                            f"⚠️ Status: **{status}** ({report.get('total_alerts', 0)} alert(s))"
                        )
                    else:
                        st.success(f"✅ Status: **{status}**")

                    interactions = report.get("interactions", [])
                    if interactions:
                        st.subheader("Detected alerts:")
                        for alert in interactions:
                            involved = " + ".join(alert.get("drugs_involved", []))
                            st.warning(
                                f"**{alert.get('level')}**: {involved}\n\n{alert.get('description')}"
                            )
                    else:
                        st.info(report.get("message", "No critical overlaps detected."))

                    with st.expander("View resolved RxNorm entities (RxCUI)"):
                        st.json(data.get("resolved_drugs", []))
                        if data.get("unresolved_drugs"):
                            st.caption(f"Unresolved entities: {data.get('unresolved_drugs')}")
                else:
                    st.error(f"Backend returned HTTP {response.status_code}: {response.text}")
            except requests.exceptions.RequestException as exc:
                st.error(f"Failed to reach FastAPI backend ({BACKEND_BASE_URL}): {exc}")

st.divider()
st.caption(
    "⚖ **Medical Disclaimer:** This prototype is a clinical decision support tool "
    "intended purely for demonstration and research purposes. It does not replace "
    "professional medical consultation, clinical expertise, or official pharmacovigilance guidelines."
)
