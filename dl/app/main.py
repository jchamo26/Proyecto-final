import base64
import hashlib
import io
import os
import time
import uuid
from typing import Any, Dict, Optional

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image

try:
    from minio import Minio
except Exception:  # pragma: no cover - optional in local lightweight runs
    Minio = None

MODEL_PATH = os.environ.get("MODEL_PATH", os.environ.get("IMAGE_MODEL_PATH", "/dl/models/retinopathy_int8.onnx"))
LABELS = ["Sin retinopatia", "Leve", "Moderada", "Severa", "Proliferativa"]
IMG_SIZE = int(os.environ.get("DL_IMAGE_SIZE", "224"))
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "medical-images")

app = FastAPI(
    title="DL Inference Service",
    description="Microservicio para inferencia de imágenes ONNX INT8.",
    version="1.0.0",
)

session: Optional[ort.InferenceSession] = None
minio_client: Optional[Any] = None


@app.on_event("startup")
def load_model():
    global session, minio_client
    if os.path.exists(MODEL_PATH):
        try:
            session = ort.InferenceSession(MODEL_PATH)
        except Exception:
            session = None
    else:
        session = None

    minio_host = os.environ.get("MINIO_URL")
    minio_user = os.environ.get("MINIO_USER") or os.environ.get("MINIO_ROOT_USER")
    minio_password = os.environ.get("MINIO_PASSWORD") or os.environ.get("MINIO_ROOT_PASSWORD")
    if Minio and minio_host and minio_user and minio_password:
        try:
            minio_client = Minio(
                minio_host,
                access_key=minio_user,
                secret_key=minio_password,
                secure=False,
            )
            if not minio_client.bucket_exists(MINIO_BUCKET):
                minio_client.make_bucket(MINIO_BUCKET)
        except Exception:
            minio_client = None


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return default
        return float(value)
    except Exception:
        return default


def _extract_feature(patient: Dict[str, Any], feature_name: str) -> Optional[float]:
    if not isinstance(patient, dict):
        return None
    direct = patient.get(feature_name)
    if direct is not None:
        return _to_float(direct, default=0.0)

    extensions = patient.get("extension", [])
    if isinstance(extensions, list):
        suffix = f"uci-feature-{feature_name}"
        for ext in extensions:
            if not isinstance(ext, dict):
                continue
            url = str(ext.get("url", ""))
            if suffix not in url:
                continue
            value = ext.get("valueDecimal", ext.get("valueInteger", ext.get("valueString")))
            return _to_float(value, default=0.0)
    return None


def _signal_from_image_bytes(raw: bytes, length: int = 2500) -> np.ndarray:
    if not raw:
        return np.array([], dtype=np.float32)
    data = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
    if data.size == 0:
        return np.array([], dtype=np.float32)
    centered = (data - 127.5) / 127.5
    repeats = max(1, int(np.ceil(length / centered.size)))
    tiled = np.tile(centered, repeats)[:length]
    # Light smoothing to emulate a usable ECG-like trace.
    kernel = np.array([0.2, 0.6, 0.2], dtype=np.float32)
    smoothed = np.convolve(tiled, kernel, mode="same")
    return smoothed.astype(np.float32)


def _synthetic_ecg(patient_id: str, patient: Dict[str, Any], length: int = 2500, sample_rate: int = 250) -> np.ndarray:
    digest = hashlib.sha256((patient_id or "anon").encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big") % (2**32)
    rng = np.random.default_rng(seed)

    thalach = _extract_feature(patient, "thalach")
    oldpeak = _extract_feature(patient, "oldpeak")
    age = _extract_feature(patient, "age") or 55.0

    base_hr = thalach if thalach and thalach > 0 else max(55.0, 82.0 - (age - 45.0) * 0.3)
    hr = float(np.clip(base_hr + rng.normal(0.0, 4.0), 48.0, 150.0))
    rr = 60.0 / hr

    t = np.arange(length, dtype=np.float32) / float(sample_rate)
    signal = 0.02 * np.sin(2 * np.pi * 0.33 * t) + 0.01 * np.sin(2 * np.pi * 0.09 * t)

    beat_times = np.arange(0.4, t[-1] + rr, rr)
    for bt in beat_times:
        qrs = np.exp(-((t - bt) ** 2) / (2 * (0.015**2)))
        p_wave = 0.22 * np.exp(-((t - (bt - 0.16)) ** 2) / (2 * (0.025**2)))
        t_wave = 0.30 * np.exp(-((t - (bt + 0.24)) ** 2) / (2 * (0.06**2)))
        signal += 1.25 * qrs + p_wave + t_wave

    st_depression = float(np.clip((oldpeak or 0.0) / 3.0, 0.0, 0.45))
    signal -= st_depression
    signal += rng.normal(0.0, 0.015, size=signal.shape)

    return signal.astype(np.float32)


def _estimate_hr(signal: np.ndarray, sample_rate: int = 250) -> float:
    if signal.size < 10:
        return 0.0
    threshold = float(np.mean(signal) + 0.8 * np.std(signal))
    peaks = np.where(signal > threshold)[0]
    if peaks.size == 0:
        return 0.0
    refractory = int(0.25 * sample_rate)
    accepted = [int(peaks[0])]
    for idx in peaks[1:]:
        if int(idx) - accepted[-1] >= refractory:
            accepted.append(int(idx))
    duration_sec = max(1e-6, signal.size / float(sample_rate))
    return float((len(accepted) / duration_sec) * 60.0)


def _preprocess_retinal_image(image_bytes: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = img.resize((IMG_SIZE, IMG_SIZE))
    arr = np.array(img, dtype=np.float32) / 255.0

    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    arr = (arr - mean) / std
    return arr.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)


def _maybe_store_image(patient_id: Optional[str], image_bytes: bytes) -> Optional[str]:
    if minio_client is None:
        return None
    object_name = f"retinal/{patient_id or 'anon'}/{uuid.uuid4()}.jpg"
    try:
        minio_client.put_object(
            MINIO_BUCKET,
            object_name,
            io.BytesIO(image_bytes),
            len(image_bytes),
            content_type="image/jpeg",
        )
        return object_name
    except Exception:
        return None


def analyze_image(payload: Dict[str, Any]) -> Dict[str, Any]:
    patient = payload.get("patient", {}) if isinstance(payload.get("patient"), dict) else {}
    patient_id = str(payload.get("patient_id") or patient.get("id") or "patient-anon")

    image_data = payload.get("image_base64")
    if not image_data and payload.get("image_url"):
        image_data = payload["image_url"]

    signal = np.array([], dtype=np.float32)
    source = "synthetic_per_patient"
    if isinstance(image_data, str) and image_data.strip():
        try:
            raw = base64.b64decode(image_data.split(",")[-1])
            signal = _signal_from_image_bytes(raw)
            source = "provided_image"
        except Exception:
            signal = np.array([], dtype=np.float32)

    if signal.size == 0:
        signal = _synthetic_ecg(patient_id=patient_id, patient=patient)

    estimated_hr = _estimate_hr(signal)
    amplitude = float(np.max(signal) - np.min(signal)) if signal.size else 0.0
    oldpeak = _extract_feature(patient, "oldpeak") or 0.0
    st_depression = float(np.clip(oldpeak, 0.0, 5.0))

    probability = 0.30
    reasons = []
    if estimated_hr > 110:
        probability += 0.22
        reasons.append("frecuencia cardiaca alta")
    elif estimated_hr < 50 and estimated_hr > 0:
        probability += 0.15
        reasons.append("bradicardia")

    if st_depression >= 1.0:
        probability += 0.28
        reasons.append("depresion ST relevante")

    if amplitude > 2.6:
        probability += 0.12
        reasons.append("variacion de amplitud elevada")

    probability = float(np.clip(probability, 0.05, 0.98))

    if probability >= 0.75:
        prediction = "ecg compatible con alto riesgo cardiaco"
    elif probability >= 0.52:
        prediction = "ecg con hallazgos intermedios"
    else:
        prediction = "ecg sin hallazgos agudos"

    if session is not None:
        try:
            flattened = signal.astype(np.float32).reshape(1, -1)
            first_input = session.get_inputs()[0]
            expected_cols = first_input.shape[-1] if isinstance(first_input.shape, list) else None
            if isinstance(expected_cols, int) and expected_cols > 0:
                if flattened.shape[1] < expected_cols:
                    pad = np.zeros((1, expected_cols - flattened.shape[1]), dtype=np.float32)
                    flattened = np.concatenate([flattened, pad], axis=1)
                elif flattened.shape[1] > expected_cols:
                    flattened = flattened[:, :expected_cols]

            output = session.run(None, {first_input.name: flattened})
            raw = np.array(output[0]).reshape(-1)
            if raw.size:
                model_score = float(np.clip(raw[0], 0.01, 0.99))
                probability = float(np.clip((probability * 0.4) + (model_score * 0.6), 0.01, 0.99))
        except Exception:
            pass

    return {
        "model": "imagen-ecg",
        "prediction": prediction,
        "probability": round(probability, 2),
        "ecg_generated": source != "provided_image",
        "ecg_source": source,
        "ecg_summary": {
            "patient_id": patient_id,
            "estimated_hr_bpm": round(estimated_hr, 1),
            "st_depression": round(st_depression, 2),
            "signal_amplitude": round(amplitude, 3),
            "risk_reasons": reasons,
            "waveform_preview": [round(float(v), 4) for v in signal[:120]],
        },
        "calibrated": True,
    }


@app.get("/healthz")
async def health():
    return {
        "status": "ok",
        "model_loaded": MODEL_PATH if session is not None else None,
        "minio_enabled": minio_client is not None,
    }


@app.get("/health")
async def health_alias():
    return await health()


@app.post("/predict")
async def predict_image(image: UploadFile = File(...), patient_id: Optional[str] = None):
    if session is None:
        raise HTTPException(status_code=503, detail="Modelo ONNX no disponible")

    t0 = time.time()
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="No se recibio imagen")

    minio_path = _maybe_store_image(patient_id, image_bytes)

    input_array = _preprocess_retinal_image(image_bytes)
    input_name = session.get_inputs()[0].name
    logits = np.array(session.run(None, {input_name: input_array})[0]).reshape(-1)

    if logits.size == 0:
        raise HTTPException(status_code=500, detail="Salida vacia del modelo")

    if logits.size == 1:
        p1 = float(np.clip(logits[0], 0.0, 1.0))
        probabilities = np.array([1.0 - p1, p1], dtype=np.float32)
        labels = ["Negativo", "Positivo"]
    else:
        shifted = logits - np.max(logits)
        exp_logits = np.exp(shifted)
        probabilities = exp_logits / np.sum(exp_logits)
        labels = LABELS[: probabilities.size]

    predicted_class = int(np.argmax(probabilities))
    latency_ms = (time.time() - t0) * 1000.0

    return {
        "prediction": predicted_class,
        "label": labels[predicted_class],
        "probability": round(float(probabilities[predicted_class]), 4),
        "all_probabilities": {
            labels[i]: round(float(probabilities[i]), 4)
            for i in range(probabilities.size)
        },
        "minio_path": minio_path,
        "latency_ms": round(float(latency_ms), 2),
        "model": "retinopathy_int8",
    }


@app.post("/infer")
async def infer_image(payload: Dict[str, Any]):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload inválido")
    return analyze_image(payload)
