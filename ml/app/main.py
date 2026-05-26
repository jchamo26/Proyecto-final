import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

MODEL_PATH = os.environ.get(
    "MODEL_PATH",
    os.environ.get("TABULAR_MODEL_PATH", "/ml/models/diabetes_int8.onnx"),
)

app = FastAPI(
    title="ML Inference Service",
    description="Microservicio para inferencia tabular ONNX INT8 calibrado.",
    version="1.0.0",
)

session: Optional[ort.InferenceSession] = None

DIABETES_FEATURE_ORDER = [
    "pregnancies",
    "glucose",
    "blood_pressure",
    "skin_thickness",
    "insulin",
    "bmi",
    "diabetes_pedigree",
    "age",
]


class DiabetesInput(BaseModel):
    pregnancies: float
    glucose: float
    blood_pressure: float
    skin_thickness: float
    insulin: float
    bmi: float
    diabetes_pedigree: float
    age: float

PATHOLOGY_BY_LEVEL = {
    0: "Sin evidencia de patologia cardiaca",
    1: "Enfermedad cardiaca leve",
    2: "Enfermedad cardiaca moderada",
    3: "Enfermedad cardiaca severa",
    4: "Enfermedad cardiaca critica",
}


@app.on_event("startup")
def load_model():
    global session
    if os.path.exists(MODEL_PATH):
        try:
            session = ort.InferenceSession(MODEL_PATH)
        except Exception:
            session = None
    else:
        session = None


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
        return float(value)
    except Exception:
        return None


def _extract_age(patient: Dict[str, Any]) -> Optional[float]:
    direct_age = _to_float(patient.get("age"))
    if direct_age is not None:
        return direct_age

    birth_date = patient.get("birthDate")
    if isinstance(birth_date, str) and len(birth_date) >= 4:
        try:
            birth_year = int(birth_date[:4])
            now = datetime.utcnow()
            return float(max(0, now.year - birth_year))
        except Exception:
            return None
    return None


def _extract_uci_features(payload: Dict[str, Any]) -> Dict[str, float]:
    patient = payload.get("patient", {}) or {}
    model_meta = payload.get("model", {}) or {}

    features: Dict[str, float] = {}

    age = _extract_age(patient)
    if age is not None:
        features["age"] = age

    extensions = patient.get("extension", [])
    if isinstance(extensions, list):
        for ext in extensions:
            if not isinstance(ext, dict):
                continue
            url = str(ext.get("url", ""))
            if "uci-feature-" not in url:
                continue
            feature_name = url.rsplit("uci-feature-", 1)[-1].strip().lower()
            candidate_value = (
                ext.get("valueDecimal")
                if "valueDecimal" in ext
                else ext.get("valueInteger", ext.get("valueString"))
            )
            numeric_value = _to_float(candidate_value)
            if numeric_value is not None:
                features[feature_name] = numeric_value

    if isinstance(model_meta, dict):
        for key, value in model_meta.items():
            numeric_value = _to_float(value)
            if numeric_value is not None:
                features[str(key).lower()] = numeric_value

    return features


def _rule_based_risk(features: Dict[str, float], observations: List[Dict[str, Any]]) -> Dict[str, Any]:
    probability = 0.35
    factors: List[str] = []

    age = features.get("age")
    if age is not None and age >= 60:
        probability += 0.10
        factors.append("edad >= 60 anos")

    trestbps = features.get("trestbps")
    if trestbps is not None and trestbps >= 140:
        probability += 0.10
        factors.append("presion arterial en reposo elevada")

    chol = features.get("chol")
    if chol is not None and chol >= 240:
        probability += 0.08
        factors.append("colesterol total alto")

    thalach = features.get("thalach")
    if thalach is not None and thalach < 120:
        probability += 0.10
        factors.append("frecuencia cardiaca maxima baja")

    oldpeak = features.get("oldpeak")
    if oldpeak is not None and oldpeak >= 2.0:
        probability += 0.12
        factors.append("depresion ST (oldpeak) significativa")

    ca = features.get("ca")
    if ca is not None and ca >= 2:
        probability += 0.12
        factors.append("mayor carga de vasos afectados (ca)")

    cp = features.get("cp")
    if cp is not None and int(cp) >= 3:
        probability += 0.06
        factors.append("tipo de dolor toracico de mayor riesgo")

    for obs in observations:
        if not isinstance(obs, dict):
            continue
        value = _to_float(obs.get("value"))
        if value is None:
            continue
        if value > 7.0:
            probability += 0.05

    probability = min(0.98, max(0.05, probability))

    if probability >= 0.86:
        severity = 4
    elif probability >= 0.72:
        severity = 3
    elif probability >= 0.58:
        severity = 2
    elif probability >= 0.43:
        severity = 1
    else:
        severity = 0

    return {
        "probability": probability,
        "severity": severity,
        "pathology": PATHOLOGY_BY_LEVEL[severity],
        "risk_factors": factors,
    }


def _onnx_score(features: Dict[str, float], model_meta: Dict[str, Any]) -> Optional[float]:
    if session is None:
        return None
    try:
        inputs = {}
        for inp in session.get_inputs():
            name = inp.name
            fallback = _to_float(model_meta.get(name)) if isinstance(model_meta, dict) else None
            value = features.get(name.lower(), fallback if fallback is not None else 0.0)
            inputs[name] = np.array([float(value)], dtype=np.float32)

        output = session.run(None, inputs)
        if not output:
            return None
        raw = np.array(output[0]).reshape(-1)
        if raw.size == 0:
            return None
        score = float(raw[0])
        return min(0.99, max(0.01, score))
    except Exception:
        return None


def _prepare_tabular_matrix(features: List[float]) -> np.ndarray:
    return np.array([features], dtype=np.float32)


def _run_diabetes_onnx(features: List[float]) -> Dict[str, Any]:
    if session is None:
        raise HTTPException(status_code=503, detail="Modelo ONNX no disponible")

    input_array = _prepare_tabular_matrix(features)
    input_name = session.get_inputs()[0].name

    t0 = time.time()
    outputs = session.run(None, {input_name: input_array})
    latency_ms = (time.time() - t0) * 1000

    prediction = 0
    probability_positive = 0.5
    probability_negative = 0.5

    if len(outputs) >= 2:
        pred_raw = np.array(outputs[0]).reshape(-1)
        proba_raw = np.array(outputs[1]).reshape(-1)
        if pred_raw.size:
            prediction = int(round(float(pred_raw[0])))
        if proba_raw.size >= 2:
            probability_negative = float(proba_raw[0])
            probability_positive = float(proba_raw[1])
        elif proba_raw.size == 1:
            probability_positive = float(proba_raw[0])
            probability_negative = 1.0 - probability_positive
    elif len(outputs) == 1:
        raw = np.array(outputs[0]).reshape(-1)
        if raw.size:
            score = float(raw[0])
            probability_positive = max(0.0, min(1.0, score))
            probability_negative = 1.0 - probability_positive
            prediction = int(probability_positive >= 0.5)

    return {
        "prediction": int(prediction),
        "probability": round(float(probability_positive), 4),
        "probability_negative": round(float(probability_negative), 4),
        "calibrated": True,
        "latency_ms": round(float(latency_ms), 2),
        "model": "diabetes_gbm_int8",
        "risk_level": "alto" if probability_positive > 0.5 else "bajo",
    }


def score_tabular(payload: Dict[str, Any]) -> Dict[str, Any]:
    patient = payload.get("patient", {})
    model_meta = payload.get("model", {})

    observations = patient.get("observations", []) if isinstance(patient, dict) else []
    features = _extract_uci_features(payload)

    rules = _rule_based_risk(features, observations if isinstance(observations, list) else [])
    probability = rules["probability"]
    severity = rules["severity"]

    model_score = _onnx_score(features, model_meta if isinstance(model_meta, dict) else {})
    if model_score is not None:
        probability = round((probability * 0.45) + (model_score * 0.55), 4)
        if probability >= 0.86:
            severity = 4
        elif probability >= 0.72:
            severity = 3
        elif probability >= 0.58:
            severity = 2
        elif probability >= 0.43:
            severity = 1
        else:
            severity = 0

    if probability >= 0.72:
        risk = "alto riesgo"
    elif probability >= 0.50:
        risk = "riesgo moderado"
    else:
        risk = "riesgo bajo"

    analysis = {
        "dataset": "uci-heart-disease-45",
        "pathology_level": severity,
        "pathology_label": PATHOLOGY_BY_LEVEL[severity],
        "risk_factors": rules["risk_factors"],
        "extracted_features": {
            key: round(float(value), 4)
            for key, value in sorted(features.items())
            if key in {"age", "cp", "trestbps", "chol", "fbs", "thalach", "oldpeak", "ca"}
        },
    }

    return {
        "model": "tabular",
        "prediction": risk,
        "probability": round(probability, 2),
        "clinical_interpretation": rules["pathology"],
        "analysis": analysis,
        "calibrated": True,
    }


@app.get("/healthz")
async def health():
    return {"status": "ok", "model_loaded": MODEL_PATH if session is not None else None}


@app.get("/health")
async def health_alias():
    return await health()


@app.post("/predict")
async def predict(data: DiabetesInput):
    features = [
        data.pregnancies,
        data.glucose,
        data.blood_pressure,
        data.skin_thickness,
        data.insulin,
        data.bmi,
        data.diabetes_pedigree,
        data.age,
    ]
    return _run_diabetes_onnx(features)


@app.post("/infer")
async def infer(payload: Dict[str, Any]):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload inválido")

    # Compatibility path: accepts direct diabetes fields in /infer.
    if all(field in payload for field in DIABETES_FEATURE_ORDER):
        features = [float(payload[field]) for field in DIABETES_FEATURE_ORDER]
        return _run_diabetes_onnx(features)

    return score_tabular(payload)
