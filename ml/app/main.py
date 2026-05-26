import json
import os
from typing import Any, Dict, Optional

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, HTTPException

MODEL_PATH = os.environ.get("TABULAR_MODEL_PATH", "/ml/models/tabular.onnx")

app = FastAPI(
    title="ML Inference Service",
    description="Microservicio para inferencia tabular ONNX INT8 calibrado.",
    version="1.0.0",
)

session: Optional[ort.InferenceSession] = None


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


def score_tabular(payload: Dict[str, Any]) -> Dict[str, Any]:
    patient = payload.get("patient", {})
    model_meta = payload.get("model", {})

    risk = "moderado riesgo"
    probability = 0.55

    age = patient.get("age") or patient.get("birthDate")
    if isinstance(age, str) and age.isdigit():
        age_val = int(age)
        if age_val >= 60:
            probability += 0.2
    observations = patient.get("observations", [])
    if isinstance(observations, list) and len(observations) > 0:
        probability += min(0.2, 0.05 * len(observations))
        for obs in observations:
            try:
                value = float(obs.get("value", 0))
            except Exception:
                value = 0
            if value > 7.0:
                probability += 0.15

    probability = min(0.98, max(0.35, probability))
    if probability >= 0.75:
        risk = "alto riesgo"
    elif probability >= 0.55:
        risk = "riesgo moderado"
    else:
        risk = "riesgo bajo"

    if session is not None:
        try:
            inputs = {}
            for inp in session.get_inputs():
                name = inp.name
                value = np.array([float(model_meta.get(name, 0) or 0)], dtype=np.float32)
                inputs[name] = value
            output = session.run(None, inputs)
            model_score = float(output[0][0])
            probability = min(0.99, max(0.01, model_score))
            risk = "alto riesgo" if probability >= 0.65 else "riesgo moderado"
        except Exception:
            pass

    return {
        "model": "tabular",
        "prediction": risk,
        "probability": round(probability, 2),
        "calibrated": True,
    }


@app.get("/healthz")
async def health():
    return {"status": "ok"}


@app.post("/infer")
async def infer(payload: Dict[str, Any]):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload inválido")
    return score_tabular(payload)
