# TheraOverlap: Pharmacological Redundancy and ATC Overlap Detection Engine

TheraOverlap is an automated clinical decision support (CDS) application and interactive dashboard designed to detect therapeutic duplications, pharmacological redundancies, and Anatomical Therapeutic Chemical (ATC) class overlaps in multi-drug regimens.

The system resolves free-text pharmaceutical trade names and active pharmaceutical ingredients into standardized RxNorm Concept Unique Identifiers (RxCUIs), queries official National Library of Medicine (NLM) RxClass ontologies, and applies hierarchical collision algorithms to identify contraindications and duplicate mechanisms of action in real time.

---

* **Live Interactive Application:** [Launch the Dashboard](https://theraoverlap-frontend.onrender.com)
* **Source Code Repository:** [GitHub Project](https://github.com/Ikeepmyideas/TheraOverlap)

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Ontological Model and Collision Logic](#ontological-model-and-collision-logic)
3. [Repository Structure & File Responsibilities](#repository-structure--file-responsibilities)
4. [API Specification](#api-specification)
5. [Local Development and Setup](#local-development-and-setup)
6. [Automated Testing Suite](#automated-testing-suite)
7. [Cloud Deployment Strategy (Render)](#cloud-deployment-strategy-render)
8. [Cold-Start and Resilience Engineering](#cold-start-and-resilience-engineering)
9. [Regulatory and Clinical Disclaimer](#regulatory-and-clinical-disclaimer)

---

## System Architecture

TheraOverlap operates on a decoupled client-server architecture:

```
+-----------------------------------------------------------+
|                    Streamlit Frontend                     |
|  - Dynamic ATC class multiselect                          |
|  - Custom drug entity input management                    |
|  - Automated retry with exponential backoff               |
+-----------------------------+-----------------------------+
                              |
                              | HTTP REST / JSON
                              v
+-----------------------------------------------------------+
|                      FastAPI Backend                      |
|  - Asynchronous request handling via Uvicorn              |
|  - Pydantic v2 input validation & schema enforcement      |
|  - Lifespan in-memory pre-caching of official ATC classes |
+--------------+-----------------------------+--------------+
               |                             |
               v                             v
+-----------------------------+ +---------------------------+
|       NLM RxNorm API        | |     NLM RxClass API       |
| Entity resolution to RxCUI  | | ATC class mapping by RxCUI|
+-----------------------------+ +---------------------------+
```

### Request Execution Flow

1. **Client Input:** The clinician selects standardized ATC classes or submits free-text brand names (e.g., Synthroid, Glucophage, Aldactone, Advil).
2. **Preprocessing:** The Streamlit interface cleans and deduplicates the list before issuing a POST request to `/api/v1/check`.
3. **Entity Resolution:** The FastAPI service delegates to `rxnorm_service.py` to query the RxNorm REST API (`/REST/rxcui.json?name=...`) and convert terms into canonical `RxCUI` identifiers.
4. **Ontological Traversal & Collision Analysis:** `rxclass_service.py` queries the RxClass API (`/REST/rxclass/class/byRxcui.json?rxcui=...&relaSource=ATC`) using each resolved `RxCUI` to extract assigned ATC classes (`classId`, `className`) and evaluates overlap by aggregating co-prescribed molecules under identical ATC groups (`len(cid) >= 4`).
5. **Payload Serialization:** FastAPI serializes the interaction alerts and assigns the safety status (`Safe` vs `Danger`) before returning the structured report.

[▲ Back to Top](#table-of-contents)

---

## Ontological Model and Collision Logic

### Anatomical Therapeutic Chemical (ATC) Hierarchy

The WHO ATC classification system structures active substances into a five-tier hierarchy:

* **Level 1 (Anatomical Main Group):** Single letter (e.g., `M` — Musculo-skeletal system).
* **Level 2 (Therapeutic Main Group):** Two digits (e.g., `M01` — Anti-inflammatory and antirheumatic products).
* **Level 3 (Therapeutic / Pharmacological Subgroup):** Single letter (e.g., `M01A` — Anti-inflammatory and antirheumatic agents, non-steroids).
* **Level 4 (Chemical / Therapeutic / Pharmacological Subgroup):** Single letter (e.g., `M01AE` — Propionic acid derivatives).
* **Level 5 (Chemical Substance):** Two digits identifying the specific substance (e.g., `M01AE01` for Ibuprofen, `M01AE03` for Ketoprofen).

### Overlap Detection Matrix (`rxclass_service.py`)

The detection engine parses active substance codes returned from NLM RxClass:

* **ATC Group Aggregation:** The engine maps each resolved drug to its ATC classes via `get_atc_classes_for_rxcui()`. It retains all classes where `len(cid) >= 4` (targeting pharmacological and chemical subgroups such as `M01A` and `M01AE`).
* **Collision Evaluation:** Drugs sharing an identical `(class_id, class_name)` tuple are grouped in a hash table (`defaultdict(list)`). When `len(unique_drugs) > 1`, a critical duplication alert (`level: Danger`, `severity_raw: high`) is raised.
* **Safe Evaluation:** When no two drugs share the same Level 4 / 5 ATC classification, zero alerts are compiled and the regimen receives a `Safe` clinical status.

[▲ Back to Top](#table-of-contents)

---

## Repository Structure & File Responsibilities

```
theraoverlap/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI application factory, lifespan context & routing
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── interaction.py          # Pydantic v2 data models, request/response validation
│   └── services/
│       ├── __init__.py
│       ├── rxnorm_service.py       # Asynchronous RxNorm entity resolution (Text -> RxCUI)
│       └── rxclass_service.py      # RxClass ATC retrieval & class intersection collision engine
├── tests/
│   ├── __init__.py
│   └── test_api.py                 # Pytest suite with HTTPX ASGI asynchronous test client
├── frontend.py                     # Streamlit web dashboard with retry logic and caching
├── requirements.txt                # Pinned production dependencies
├── render.yaml                     # Infrastructure as Code specification for Render
└── README.md                       # Technical documentation
```

### Exact Code Responsibilities

* **`app/services/rxnorm_service.py` :**
  * Manages asynchronous HTTP sessions to the National Library of Medicine (NLM) RxNorm REST API.
  * Cleans free-text queries, applies string sanitation, and resolves brand/generic trade names into canonical Concept Unique Identifiers (`RxCUI`).
* **`app/services/rxclass_service.py` :**
  * **`get_all_atc_classes(client)`:** Fetches and deduplicates all official ATC class names from NLM via `/REST/rxclass/allClasses.json?classType=ATC` for UI catalogue population.
  * **`get_atc_classes_for_rxcui(rxcui, client)`:** Navigates the NLM RxClass ontology graph (`relaSource=ATC`) for each resolved `RxCUI` to retrieve `classId` and `className`.
  * **`detect_therapeutic_overlaps(drug_items, client)`:** Implements the **collision engine**. Filters classes with `len(cid) >= 4`, aggregates co-prescribed drugs by `(cid, class_name)`, flags multi-drug intersections (`len(unique_drugs) > 1`), and outputs structured `Danger` alerts.
* **`app/main.py` :**
  * Registers REST endpoints (`/health`, `/api/v1/classes`, `/api/v1/check`).
  * Manages the FastAPI `lifespan` context to pre-fetch and cache the official WHO ATC catalog into memory at boot time via `get_all_atc_classes()`.

[▲ Back to Top](#table-of-contents)

---

## API Specification

### 1. Healthcheck

* **Method:** `GET`
* **Path:** `/health`
* **Description:** Verifies microservice operational readiness.
* **Response (200 OK):**

```json
{
  "status": "ok",
  "service": "TheraOverlap"
}
```

### 2. ATC Class Catalog

* **Method:** `GET`
* **Path:** `/api/v1/classes`
* **Description:** Returns the catalog of standardized ATC classes cached in application memory during startup.
* **Response (200 OK):**

```json
[
  "A10BA - Biguanides",
  "C09AA - ACE inhibitors, plain",
  "M01AE - Propionic acid derivatives"
]
```

### 3. Interaction Analysis

* **Method:** `POST`
* **Path:** `/api/v1/check`
* **Description:** Ingests a list of drug terms, resolves them via RxNorm, and flags ontological overlaps.
* **Request Headers:** `Content-Type: application/json`
* **Request Body:**

```json
{
  "drugs": [
    "Advil",
    "Ketoprofen",
    "Metformin"
  ]
}
```

* **Response (200 OK):**

```json
{
  "resolved_drugs": [
    {
      "name": "Advil",
      "rxcui": "5640",
      "atc_codes": ["M01AE01"]
    },
    {
      "name": "Ketoprofen",
      "rxcui": "6130",
      "atc_codes": ["M01AE03"]
    },
    {
      "name": "Metformin",
      "rxcui": "6809",
      "atc_codes": ["A10BA02"]
    }
  ],
  "unresolved_drugs": [],
  "report": {
    "status": "Danger",
    "total_alerts": 1,
    "interactions": [
      {
        "severity_raw": "high",
        "level": "Danger",
        "drugs_involved": [
          "Advil",
          "Ketoprofen"
        ],
        "description": "Therapeutic overlap detected (ATC Class M01AE - Propionic acid derivatives): concomitant use of multiple drugs with identical pharmacological intent."
      }
    ],
    "disclaimer": "Academic demonstration tool. Does not constitute medical advice."
  }
}
```

[▲ Back to Top](#table-of-contents)

---

## Local Development and Setup

### Prerequisites

* Python 3.10 or 3.11 installed.
* Outbound HTTPS connectivity (to reach `rxnav.nlm.nih.gov`).

### 1. Environment Preparation

```bash
git clone https://github.com/Ikeepmyideas/TheraOverlap.git
cd theraoverlap

python -m venv venv
source venv/bin/activate       # On Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Launch FastAPI Backend

Run the ASGI server through Uvicorn:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

* API Base URL: `http://localhost:8000`
* Interactive OpenAPI Specification: `http://localhost:8000/docs`
* ReDoc Documentation: `http://localhost:8000/redoc`

### 3. Launch Streamlit Frontend

In a separate terminal:

```bash
export BACKEND_URL="http://localhost:8000"
streamlit run frontend.py
```

Access the user interface at `http://localhost:8501`.

[▲ Back to Top](#table-of-contents)

---

## Automated Testing Suite

The testing pipeline validates request serialization, schema models, asynchronous lifespan hooks, and clinical matrix rules without requiring live external calls.

```bash
pytest tests/ -v -s
```

### Covered Test Cases

* `test_healthcheck`: Validates HTTP 200 and schema consistency on `/health`.
* `test_empty_payload`: Validates HTTP 400/422 status rejection when the input list is empty.
* `test_safe_regimen`: Confirms zero alerts on unrelated therapeutic classes (e.g., Synthroid, Metformin, Paracetamol).
* `test_danger_overlap`: Confirms collision flagging when two active ingredients match on the same Level 4 ATC prefix (e.g., Advil and Ketoprofen).

[▲ Back to Top](#table-of-contents)

---

## Cloud Deployment Strategy (Render)

TheraOverlap is configured for synchronized multi-service deployment using Render Blueprints (`render.yaml`).

```yaml
services:
  - type: web
    name: theraoverlap-backend
    env: python
    region: frankfurt
    plan: free
    buildCommand: "pip install -r requirements.txt"
    startCommand: "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0

  - type: web
    name: theraoverlap-frontend
    env: python
    region: frankfurt
    plan: free
    buildCommand: "pip install -r requirements.txt"
    startCommand: "streamlit run frontend.py --server.port $PORT --server.address 0.0.0.0 --server.headless true"
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: BACKEND_URL
        fromService:
          type: web
          name: theraoverlap-backend
          property: host
```

[▲ Back to Top](#table-of-contents)

---

## Cold-Start and Resilience Engineering

Free-tier cloud containers enter an idle spin-down state after periods of inactivity. TheraOverlap implements three specific architectural safeguards to handle container wake-up latency:

1. **Client-Side Exponential Retries:** The Streamlit frontend intercepts HTTP 502, 503, and 504 gateway responses during container boot cycles, performing automatic retries spaced by backoff delays.
2. **Selective Cache Eviction:** Streamlit data caching (`@st.cache_data`) only stores non-empty lists, preventing transient startup failures from freezing the application in a degraded state.
3. **Lifespan Warmup:** The backend pre-loads the full ATC ontology into memory during Uvicorn initialization via FastAPI's `lifespan` handler, ensuring all subsequent lookup requests execute in sub-millisecond time.

[▲ Back to Top](#table-of-contents)

---

## Regulatory and Clinical Disclaimer

> **IMPORTANT MEDICAL NOTICE**
>
> TheraOverlap is an experimental clinical decision support (CDS) prototype developed solely for educational, research, and technical demonstration purposes.
>
> * **Not a Certified Medical Device:** This application has not been evaluated, cleared, or approved by the U.S. Food and Drug Administration (FDA), the European Medicines Agency (EMA), or any other national or international regulatory health authority.
> * **No Clinical Substitution:** Under no circumstances should this software replace professional clinical judgment, physician prescription guidelines, clinical pharmacology consultations, or official pharmacovigilance monographs.
> * **Data Accuracy & Omissions:** While queries reference official National Library of Medicine (NLM) endpoints and WHO ATC taxonomies, the authors and contributors disclaim all liability for inadvertent classification omissions, API latency, network timeouts, or clinical outcomes resulting from the use of this software.

[▲ Back to Top](#table-of-contents)
