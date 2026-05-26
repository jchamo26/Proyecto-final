import httpx
from typing import Any, Dict, Optional

from app.config import settings

async def query_fhir(patient_id: str, loinc_code: Optional[str] = None) -> Dict[str, Any]:
    search_path = f"{settings.FHIR_SERVER_URL}/Observation?patient={patient_id}"
    if loinc_code:
        search_path += f"&code={loinc_code}"

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(search_path)
        response.raise_for_status()
        return {
            "request_url": search_path,
            "status_code": response.status_code,
            "data": response.json(),
        }


async def query_patient_clinical_data(patient_id: str) -> Dict[str, Any]:
    base_url = settings.FHIR_SERVER_URL.rstrip("/")
    patient_url = f"{base_url}/Patient/{patient_id}"
    obs_url = f"{base_url}/Observation?patient={patient_id}&_count=50"
    cond_url = f"{base_url}/Condition?subject=Patient/{patient_id}&_count=50"

    async with httpx.AsyncClient(timeout=20.0) as client:
        patient_response = await client.get(patient_url)
        observations_response = await client.get(obs_url)
        conditions_response = await client.get(cond_url)

    patient_response.raise_for_status()
    observations_response.raise_for_status()
    conditions_response.raise_for_status()

    return {
        "patient": patient_response.json(),
        "observations_bundle": observations_response.json(),
        "conditions_bundle": conditions_response.json(),
        "request_urls": {
            "patient": patient_url,
            "observations": obs_url,
            "conditions": cond_url,
        },
    }

async def invoke_ml_model(model_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized_type = "tabular" if model_type == "tabular" else "image"
    url = settings.ML_SERVICE_URL if normalized_type == "tabular" else settings.DL_SERVICE_URL
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(f"{url}/infer", json=payload)
        response.raise_for_status()
        return response.json()

async def create_diagnostic_report(report_payload: Dict[str, Any]) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(f"{settings.FHIR_SERVER_URL}/DiagnosticReport", json=report_payload)
        response.raise_for_status()
        return response.json()
