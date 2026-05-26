import base64
import hmac
import hashlib
import math
import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.models import AppointmentRecord, AuditEvent, ObservationRecord, PatientRecord, ProcedureLog, VitalSignRecord
from app.db.session import get_db

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12, deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/superuser/login")
def _safe_hash_password(password: str) -> str:
    try:
        return pwd_context.hash(password)
    except Exception:
        # If hashing backend fails at import time (CI/dev environments),
        # fall back to storing the plain password to allow startup.
        return password


fake_users_db = {
    settings.SUPERUSER_EMAIL: {
        "email": settings.SUPERUSER_EMAIL,
        "plain_password": settings.SUPERUSER_PASSWORD,
        "hashed_password": _safe_hash_password(settings.SUPERUSER_PASSWORD),
        "license_number": settings.SUPERUSER_LICENSE,
        "role": "super_user",
    }
}

class Token(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int

class TokenData(BaseModel):
    email: Optional[str] = None

class AccessTokenRequest(BaseModel):
    email: str
    password: str
    license_number: str

class InferenceRequest(BaseModel):
    patient_fhir: Dict[str, Any]
    model: Optional[str] = None
    ecg_image_base64: Optional[str] = None

class DeleteReason(BaseModel):
    reason: str
    icd10_code: str


class ProcedureLogCreate(BaseModel):
    action: str
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    patient_identifier: Optional[str] = None
    comment: str


class ProcedureLogItem(BaseModel):
    id: int
    action: str
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    patient_identifier: Optional[str] = None
    comment: str
    timestamp: str


class VitalSignCreate(BaseModel):
    patient_name: Optional[str] = None
    patient_identifier: Optional[str] = None
    heart_rate: Optional[int] = None
    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None
    respiratory_rate: Optional[int] = None
    temperature_c: Optional[float] = None
    spo2: Optional[int] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    note: Optional[str] = None


class VitalSignItem(BaseModel):
    id: int
    patient_id: str
    patient_name: Optional[str] = None
    patient_identifier: Optional[str] = None
    heart_rate: Optional[int] = None
    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None
    respiratory_rate: Optional[int] = None
    temperature_c: Optional[float] = None
    spo2: Optional[int] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    bmi: Optional[float] = None
    note: Optional[str] = None
    recorded_at: str


class AppointmentCreate(BaseModel):
    patient_id: str
    patient_name: Optional[str] = None
    patient_identifier: Optional[str] = None
    appointment_type: str = "control"
    mode: str = "virtual"
    starts_at: str
    ends_at: str
    status: str = "scheduled"
    reason: Optional[str] = None
    location: Optional[str] = None


class AppointmentItem(BaseModel):
    id: int
    patient_id: str
    patient_name: Optional[str] = None
    patient_identifier: Optional[str] = None
    appointment_type: str
    mode: str
    starts_at: str
    ends_at: str
    status: str
    reason: Optional[str] = None
    location: Optional[str] = None


ID_TYPE_OPTIONS = ("CC", "TI", "CE", "PS")
FEMALE_NAMES = ("Laura", "Sofía", "María", "Valentina", "Camila", "Daniela", "Paula", "Natalia")
MALE_NAMES = ("Juan", "Carlos", "Andrés", "Miguel", "Felipe", "Sebastián", "Diego", "Nicolás")
LAST_NAMES = ("Pérez", "Gómez", "Rodríguez", "López", "Martínez", "Torres", "Díaz", "Morales")

PATHOLOGY_BY_TARGET = {
    0: "Sin evidencia de patología cardíaca",
    1: "Enfermedad cardíaca leve",
    2: "Enfermedad cardíaca moderada",
    3: "Enfermedad cardíaca severa",
    4: "Enfermedad cardíaca crítica",
}


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


def _create_audit(db: Session, user_email: str, action: str, resource_type: str, resource_id: Optional[str] = None, details: Optional[str] = None):
    audit = AuditEvent(
        user_email=user_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    )
    db.add(audit)
    db.commit()


def _get_identifier_hash(identifier: str) -> str:
    return _hash_text(identifier)


def _parse_patient_identifier(patient: Dict[str, Any]) -> Dict[str, str]:
    identifiers = patient.get("identifier", [])
    if not identifiers:
        raise HTTPException(status_code=400, detail="El recurso Patient requiere un identificador.")
    candidate = identifiers[0]
    document_number = candidate.get("value")
    if not document_number:
        raise HTTPException(status_code=400, detail="El identificador del paciente debe incluir value.")
    document_type = "unknown"
    coding = candidate.get("type", {}).get("coding", [])
    if coding:
        document_type = coding[0].get("code", "unknown")
    return {
        "document_number": str(document_number),
        "document_type": document_type,
    }


def _patient_to_fhir(patient: PatientRecord) -> Dict[str, Any]:
    return {
        "resourceType": "Patient",
        "id": str(patient.id),
        "active": patient.active,
        "identifier": [
            {
                "use": "official",
                "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0203", "code": patient.document_type}]},
                "value": "REDACTED",
            }
        ],
        "name": [{"family": patient.last_name, "given": [patient.first_name]}],
        "gender": patient.gender,
        "birthDate": patient.birth_date,
        "meta": {"lastUpdated": patient.updated_at.isoformat() if patient.updated_at else patient.created_at.isoformat()},
    }


def _observation_to_fhir(observation: ObservationRecord) -> Dict[str, Any]:
    value_quantity = None
    if observation.value is not None:
        value_quantity = {"value": observation.value}
        if observation.unit:
            value_quantity["unit"] = observation.unit
    return {
        "resourceType": "Observation",
        "id": str(observation.id),
        "status": observation.status,
        "code": {
            "coding": [{"system": "http://loinc.org", "code": observation.loinc_code}]
        },
        "valueQuantity": value_quantity,
        "effectiveDateTime": observation.effective_datetime,
        "subject": {"reference": f"Patient/{observation.patient_id}"},
    }


def _find_patient(db: Session, patient_id: str) -> Optional[PatientRecord]:
    patient = db.query(PatientRecord).filter(PatientRecord.id == patient_id).first()
    if patient:
        return patient
    return db.query(PatientRecord).filter(PatientRecord.external_id == patient_id).first()


def _resolve_patient_by_identifier(db: Session, identifier: str) -> Optional[PatientRecord]:
    if "|" in identifier:
        _, value = identifier.split("|", 1)
    else:
        value = identifier
    identifier_hash = _get_identifier_hash(value)
    return db.query(PatientRecord).filter(PatientRecord.document_number_hash == identifier_hash).first()


def _birth_date_from_age(age_value: Any, row_seed: Optional[int] = None) -> str:
    if age_value is None:
        return "1970-01-01"
    try:
        age_int = int(float(age_value))
    except Exception:
        return "1970-01-01"

    rng = random.Random(row_seed if row_seed is not None else age_int)
    year = datetime.utcnow().year - max(age_int, 0)
    if year < 1900:
        year = 1900
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    return f"{year:04d}-{month:02d}-{day:02d}"


def _clean_dataset_value(value: Any) -> Optional[Any]:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _target_num_from_row(target_row: Optional[Dict[str, Any]]) -> int:
    if not target_row:
        return 0
    raw_value = _clean_dataset_value(target_row.get("num"))
    if raw_value is None:
        return 0
    try:
        return int(float(raw_value))
    except Exception:
        return 0


def _pathology_from_target(target_num: int) -> str:
    return PATHOLOGY_BY_TARGET.get(target_num, "Patología cardíaca no especificada")


def _parse_iso_datetime(value: str) -> datetime:
    cleaned = (value or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Se requiere una fecha/hora válida en formato ISO 8601.")
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use ISO 8601, por ejemplo 2026-06-01T14:30:00.")


def _build_vital_item(row: VitalSignRecord) -> Dict[str, Any]:
    bmi = None
    if row.weight_kg and row.height_cm and row.height_cm > 0:
        height_m = row.height_cm / 100.0
        bmi = round(row.weight_kg / (height_m * height_m), 2)
    return {
        "id": row.id,
        "patient_id": row.patient_id,
        "patient_name": row.patient_name,
        "patient_identifier": row.patient_identifier,
        "heart_rate": row.heart_rate,
        "systolic_bp": row.systolic_bp,
        "diastolic_bp": row.diastolic_bp,
        "respiratory_rate": row.respiratory_rate,
        "temperature_c": row.temperature_c,
        "spo2": row.spo2,
        "weight_kg": row.weight_kg,
        "height_cm": row.height_cm,
        "bmi": bmi,
        "note": row.note,
        "recorded_at": row.recorded_at.isoformat() if row.recorded_at else datetime.utcnow().isoformat(),
    }


def _random_identity_for_row(row_index: int) -> Dict[str, str]:
    rng = random.Random(45000 + row_index)
    gender = rng.choice(["female", "male"])
    given_name = rng.choice(FEMALE_NAMES if gender == "female" else MALE_NAMES)
    family = f"{rng.choice(LAST_NAMES)} {rng.choice(LAST_NAMES)}"
    document_type = rng.choice(ID_TYPE_OPTIONS)
    document_number = str(rng.randint(10_000_000, 99_999_999))

    return {
        "gender": gender,
        "given": given_name,
        "family": family,
        "document_type": document_type,
        "document_number": document_number,
    }


def _build_uci_patient_payload(row_index: int, features_row: Dict[str, Any], target_row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    synthetic = _random_identity_for_row(row_index)
    document_type = synthetic["document_type"]
    identifier_value = synthetic["document_number"]

    age_value = _clean_dataset_value(features_row.get("age"))
    birth_date = _birth_date_from_age(age_value, row_seed=row_index)

    target_num = _target_num_from_row(target_row)
    pathology = _pathology_from_target(target_num)

    extensions = [
        {
            "url": "https://pechychon.local/fhir/StructureDefinition/dataset-source",
            "valueString": "UCI Heart Disease (id=45)",
        },
        {
            "url": "https://pechychon.local/fhir/StructureDefinition/heart-disease-pathology",
            "valueString": pathology,
        },
    ]

    if target_num is not None:
        extensions.append(
            {
                "url": "https://pechychon.local/fhir/StructureDefinition/heart-disease-target",
                "valueInteger": int(target_num),
            }
        )

    for feature_key in ["cp", "trestbps", "chol", "fbs", "thalach", "oldpeak", "ca"]:
        feature_value = _clean_dataset_value(features_row.get(feature_key))
        if feature_value is None:
            continue
        extension: Dict[str, Any] = {
            "url": f"https://pechychon.local/fhir/StructureDefinition/uci-feature-{feature_key}"
        }
        if isinstance(feature_value, (int, float)):
            extension["valueDecimal"] = float(feature_value)
        else:
            extension["valueString"] = str(feature_value)
        extensions.append(extension)

    patient_payload = {
        "resourceType": "Patient",
        "active": True,
        "identifier": [
            {
                "use": "official",
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                            "code": document_type,
                        }
                    ]
                },
                "value": identifier_value,
            }
        ],
        "name": [
            {
                "family": synthetic["family"],
                "given": [synthetic["given"]],
            }
        ],
        "gender": synthetic["gender"],
        "birthDate": birth_date,
        "extension": extensions,
    }

    return {
        "patient": patient_payload,
        "identifier": f"{document_type}|{identifier_value}",
        "name": f"{synthetic['given']} {synthetic['family']}",
        "gender": synthetic["gender"],
        "birthDate": birth_date,
        "pathology": pathology,
        "target_num": target_num,
    }


async def _fhir_request(method: str, endpoint: str, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{settings.FHIR_SERVER_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.request(method, url, json=json, params=params, headers={"Content-Type": "application/fhir+json"})
        response.raise_for_status()
        return response.json()


def verify_password(plain_password, hashed_password):
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def authenticate_superuser(email: str, password: str, license_number: str):
    if not hmac.compare_digest(email, settings.SUPERUSER_EMAIL):
        return None
    user = fake_users_db.get(settings.SUPERUSER_EMAIL)
    if not user:
        return None
    plain_ok = hmac.compare_digest(password, settings.SUPERUSER_PASSWORD)
    hashed_ok = verify_password(password, user["hashed_password"])
    if not (plain_ok or hashed_ok):
        return None
    if not hmac.compare_digest(license_number, settings.SUPERUSER_LICENSE):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def get_current_superuser(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar el token de autenticación.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    user = fake_users_db.get(token_data.email)
    if user is None or user.get("role") != "super_user":
        raise credentials_exception
    return user

@router.post("/auth/superuser/login", response_model=Token)
@limiter.limit("20/minute")
async def login_superuser(request: Request, form_data: AccessTokenRequest):
    user = authenticate_superuser(form_data.email, form_data.password, form_data.license_number)
    if not user:
        raise HTTPException(status_code=400, detail="Credenciales inválidas")
    access_token = create_access_token(data={"sub": user["email"], "role": user["role"]})
    return {"access_token": access_token, "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES}

@router.get("/superuser/patients")
@limiter.limit("60/minute")
async def search_patient(request: Request, identifier: str, current_user: Dict = Depends(get_current_superuser), db: Session = Depends(get_db)):
    bundle = await _fhir_request("GET", "Patient", params={"identifier": identifier})
    _create_audit(db, current_user["email"], "search_patient", "Patient", None, f"identifier={identifier}")
    return bundle

@router.post("/superuser/patients", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_patient(request: Request, patient: Dict[str, Any], current_user: Dict = Depends(get_current_superuser), db: Session = Depends(get_db)):
    parsed = _parse_patient_identifier(patient)
    existing = _resolve_patient_by_identifier(db, f"{parsed['document_type']}|{parsed['document_number']}")
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El paciente ya existe.")

    try:
        result = await _fhir_request("POST", "Patient", json=patient)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == status.HTTP_409_CONFLICT:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El paciente ya existe en el servidor FHIR.")
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)

    external_id = result.get("id")
    if external_id:
        name = patient.get("name", [{}])[0]
        first_name = " ".join(name.get("given", [])) or "Paciente"
        last_name = name.get("family", "Desconocido")
        gender = patient.get("gender", "unknown")
        birth_date = patient.get("birthDate", "1970-01-01")

        db_patient = PatientRecord(
            external_id=external_id,
            document_type=parsed["document_type"],
            document_number_hash=_get_identifier_hash(parsed["document_number"]),
            document_number=parsed["document_number"],
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            birth_date=birth_date,
            active=True,
        )
        db.add(db_patient)
        db.commit()
        db.refresh(db_patient)

    _create_audit(db, current_user["email"], "create_patient", "Patient", external_id, f"identifier={parsed['document_type']}|{parsed['document_number']}")
    return result


@router.post("/superuser/patients/import/heart-disease")
@limiter.limit("5/minute")
async def import_heart_disease_patients(
    request: Request,
    limit: int = 303,
    offset: int = 0,
    current_user: Dict = Depends(get_current_superuser),
    db: Session = Depends(get_db),
):
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="limit debe estar entre 1 y 1000.")
    if offset < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="offset debe ser mayor o igual que 0.")

    try:
        from ucimlrepo import fetch_ucirepo
        heart_disease = fetch_ucirepo(id=45)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No se pudo cargar el dataset UCI Heart Disease: {exc}",
        )

    features = heart_disease.data.features
    targets = heart_disease.data.targets
    if features is None or len(features) == 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El dataset UCI Heart Disease no devolvió registros de pacientes.",
        )

    total_rows = int(len(features))
    start = min(offset, total_rows)
    end = min(start + limit, total_rows)

    created: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    patients: List[Dict[str, Any]] = []
    fhir_warning: Optional[str] = None
    fhir_unavailable_mode = False

    for idx in range(start, end):
        feature_row = features.iloc[idx].to_dict()
        target_row = targets.iloc[idx].to_dict() if targets is not None and idx < len(targets) else None
        synthesized = _build_uci_patient_payload(idx, feature_row, target_row)
        patient_payload = synthesized["patient"]

        parsed = _parse_patient_identifier(patient_payload)
        identifier = f"{parsed['document_type']}|{parsed['document_number']}"

        if fhir_unavailable_mode:
            synthetic_id = f"dataset-row-{idx + 1:04d}"
            patients.append(
                {
                    "row": idx,
                    "id": synthetic_id,
                    "name": synthesized["name"],
                    "identifier": identifier,
                    "gender": synthesized["gender"],
                    "birthDate": synthesized["birthDate"],
                    "heart_pathology": synthesized["pathology"],
                    "heart_target": synthesized["target_num"],
                    "status": "generated_not_persisted",
                }
            )
            skipped.append({"row": idx, "identifier": identifier, "reason": "fhir_unavailable"})
            continue

        existing = _resolve_patient_by_identifier(db, identifier)
        if existing:
            skipped.append({"row": idx, "identifier": identifier, "reason": "already_exists_local"})
            patients.append(
                {
                    "row": idx,
                    "id": existing.external_id,
                    "name": synthesized["name"],
                    "identifier": identifier,
                    "gender": synthesized["gender"],
                    "birthDate": synthesized["birthDate"],
                    "heart_pathology": synthesized["pathology"],
                    "heart_target": synthesized["target_num"],
                    "status": "already_exists_local",
                }
            )
            continue

        try:
            result = await _fhir_request("POST", "Patient", json=patient_payload)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == status.HTTP_409_CONFLICT:
                skipped.append({"row": idx, "identifier": identifier, "reason": "already_exists_fhir"})
                existing_fhir_id = None
                try:
                    lookup = await _fhir_request("GET", "Patient", params={"identifier": identifier})
                    entries = lookup.get("entry", []) if isinstance(lookup, dict) else []
                    if entries:
                        existing_fhir_id = entries[0].get("resource", {}).get("id")
                except Exception:
                    existing_fhir_id = None

                patients.append(
                    {
                        "row": idx,
                        "id": existing_fhir_id,
                        "name": synthesized["name"],
                        "identifier": identifier,
                        "gender": synthesized["gender"],
                        "birthDate": synthesized["birthDate"],
                        "heart_pathology": synthesized["pathology"],
                        "heart_target": synthesized["target_num"],
                        "status": "already_exists_fhir",
                    }
                )
                continue
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
        except httpx.RequestError as exc:
            # If FHIR is down, still return a full dataset-driven list for UI usage.
            fhir_warning = f"FHIR no disponible: {exc}"
            fhir_unavailable_mode = True
            synthetic_id = f"dataset-row-{idx + 1:04d}"
            patients.append(
                {
                    "row": idx,
                    "id": synthetic_id,
                    "name": synthesized["name"],
                    "identifier": identifier,
                    "gender": synthesized["gender"],
                    "birthDate": synthesized["birthDate"],
                    "heart_pathology": synthesized["pathology"],
                    "heart_target": synthesized["target_num"],
                    "status": "generated_not_persisted",
                }
            )
            skipped.append({"row": idx, "identifier": identifier, "reason": "fhir_unavailable"})
            continue

        external_id = result.get("id")
        condition_id = None
        if external_id and synthesized["target_num"] > 0:
            condition_payload = {
                "resourceType": "Condition",
                "clinicalStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                            "code": "active",
                        }
                    ]
                },
                "verificationStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                            "code": "confirmed",
                        }
                    ]
                },
                "code": {
                    "coding": [
                        {
                            "system": "http://snomed.info/sct",
                            "code": "53741008",
                            "display": "Coronary arteriosclerosis",
                        }
                    ],
                    "text": synthesized["pathology"],
                },
                "subject": {"reference": f"Patient/{external_id}"},
                "note": [{"text": f"Dataset UCI Heart Disease target={synthesized['target_num']}"}],
            }
            try:
                condition_result = await _fhir_request("POST", "Condition", json=condition_payload)
                condition_id = condition_result.get("id")
            except Exception:
                condition_id = None

        if external_id:
            name = patient_payload.get("name", [{}])[0]
            first_name = " ".join(name.get("given", [])) or "Paciente"
            last_name = name.get("family", "Dataset")

            db_patient = PatientRecord(
                external_id=external_id,
                document_type=parsed["document_type"],
                document_number_hash=_get_identifier_hash(parsed["document_number"]),
                document_number=parsed["document_number"],
                first_name=first_name,
                last_name=last_name,
                gender=patient_payload.get("gender", "unknown"),
                birth_date=patient_payload.get("birthDate", "1970-01-01"),
                active=True,
            )
            db.add(db_patient)
            db.commit()

        created.append(
            {
                "row": idx,
                "id": external_id,
                "name": synthesized["name"],
                "identifier": identifier,
                "gender": synthesized["gender"],
                "birthDate": synthesized["birthDate"],
                "heart_pathology": synthesized["pathology"],
                "heart_target": synthesized["target_num"],
                "status": "created",
                "condition_id": condition_id,
            }
        )

        patients.append(
            {
                "row": idx,
                "id": external_id,
                "name": synthesized["name"],
                "identifier": identifier,
                "gender": synthesized["gender"],
                "birthDate": synthesized["birthDate"],
                "heart_pathology": synthesized["pathology"],
                "heart_target": synthesized["target_num"],
                "status": "created",
                "condition_id": condition_id,
            }
        )

    _create_audit(
        db,
        current_user["email"],
        "import_heart_dataset_patients",
        "Patient",
        None,
        f"offset={offset}, limit={limit}, created={len(created)}, skipped={len(skipped)}",
    )

    return {
        "dataset": "uci-heart-disease-45",
        "total_available": total_rows,
        "offset": offset,
        "limit": limit,
        "processed": end - start,
        "created_count": len(created),
        "skipped_count": len(skipped),
        "fhir_warning": fhir_warning,
        "patients": patients,
        "created": created,
        "skipped": skipped,
    }

@router.get("/superuser/patients/{patient_id}/observations")
@limiter.limit("60/minute")
async def get_observations(request: Request, patient_id: str, loinc_code: Optional[str] = None, _count: int = 50, current_user: Dict = Depends(get_current_superuser), db: Session = Depends(get_db)):
    params = {"subject": f"Patient/{patient_id}", "_count": str(_count)}
    if loinc_code:
        params["code"] = loinc_code
    bundle = await _fhir_request("GET", "Observation", params=params)
    _create_audit(db, current_user["email"], "get_observations", "Observation", patient_id, f"loinc_code={loinc_code}")
    return bundle

@router.post("/superuser/patients/{patient_id}/observations", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def add_observation(request: Request, patient_id: str, observation: Dict[str, Any], current_user: Dict = Depends(get_current_superuser), db: Session = Depends(get_db)):
    observation["subject"] = {"reference": f"Patient/{patient_id}"}
    result = await _fhir_request("POST", "Observation", json=observation)
    _create_audit(db, current_user["email"], "create_observation", "Observation", result.get("id"), f"patient_id={patient_id}")
    return result


@router.post("/superuser/patients/{patient_id}/vitals", response_model=VitalSignItem, status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute")
async def create_vital_sign(
    request: Request,
    patient_id: str,
    payload: VitalSignCreate,
    current_user: Dict = Depends(get_current_superuser),
    db: Session = Depends(get_db),
):
    entry = VitalSignRecord(
        patient_id=str(patient_id),
        patient_name=(payload.patient_name or "").strip() or None,
        patient_identifier=(payload.patient_identifier or "").strip() or None,
        heart_rate=payload.heart_rate,
        systolic_bp=payload.systolic_bp,
        diastolic_bp=payload.diastolic_bp,
        respiratory_rate=payload.respiratory_rate,
        temperature_c=payload.temperature_c,
        spo2=payload.spo2,
        weight_kg=payload.weight_kg,
        height_cm=payload.height_cm,
        note=(payload.note or "").strip() or None,
        created_by=current_user["email"],
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    _create_audit(db, current_user["email"], "create_vital_sign", "VitalSign", str(entry.id), f"patient_id={patient_id}")
    return _build_vital_item(entry)


@router.get("/superuser/patients/{patient_id}/vitals", response_model=List[VitalSignItem])
@limiter.limit("120/minute")
async def list_vital_signs(
    request: Request,
    patient_id: str,
    limit: int = 30,
    current_user: Dict = Depends(get_current_superuser),
    db: Session = Depends(get_db),
):
    safe_limit = max(1, min(limit, 200))
    rows = (
        db.query(VitalSignRecord)
        .filter(VitalSignRecord.patient_id == str(patient_id))
        .order_by(VitalSignRecord.recorded_at.desc(), VitalSignRecord.id.desc())
        .limit(safe_limit)
        .all()
    )
    _create_audit(db, current_user["email"], "list_vital_signs", "VitalSign", str(patient_id), f"limit={safe_limit}")
    return [_build_vital_item(item) for item in rows]


@router.post("/superuser/appointments", response_model=AppointmentItem, status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute")
async def create_appointment(
    request: Request,
    payload: AppointmentCreate,
    current_user: Dict = Depends(get_current_superuser),
    db: Session = Depends(get_db),
):
    starts_at = _parse_iso_datetime(payload.starts_at)
    ends_at = _parse_iso_datetime(payload.ends_at)
    if ends_at <= starts_at:
        raise HTTPException(status_code=400, detail="La hora de fin debe ser mayor a la hora de inicio.")

    entry = AppointmentRecord(
        patient_id=str(payload.patient_id),
        patient_name=(payload.patient_name or "").strip() or None,
        patient_identifier=(payload.patient_identifier or "").strip() or None,
        appointment_type=(payload.appointment_type or "control").strip() or "control",
        mode=(payload.mode or "virtual").strip() or "virtual",
        starts_at=starts_at,
        ends_at=ends_at,
        status=(payload.status or "scheduled").strip() or "scheduled",
        reason=(payload.reason or "").strip() or None,
        location=(payload.location or "").strip() or None,
        created_by=current_user["email"],
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    _create_audit(db, current_user["email"], "create_appointment", "Appointment", str(entry.id), f"patient_id={entry.patient_id}")
    return {
        "id": entry.id,
        "patient_id": entry.patient_id,
        "patient_name": entry.patient_name,
        "patient_identifier": entry.patient_identifier,
        "appointment_type": entry.appointment_type,
        "mode": entry.mode,
        "starts_at": entry.starts_at.isoformat(),
        "ends_at": entry.ends_at.isoformat(),
        "status": entry.status,
        "reason": entry.reason,
        "location": entry.location,
    }


@router.get("/superuser/appointments", response_model=List[AppointmentItem])
@limiter.limit("120/minute")
async def list_appointments(
    request: Request,
    start: Optional[str] = None,
    end: Optional[str] = None,
    patient_id: Optional[str] = None,
    current_user: Dict = Depends(get_current_superuser),
    db: Session = Depends(get_db),
):
    query = db.query(AppointmentRecord)
    if patient_id:
        query = query.filter(AppointmentRecord.patient_id == str(patient_id))
    if start:
        query = query.filter(AppointmentRecord.starts_at >= _parse_iso_datetime(start))
    if end:
        query = query.filter(AppointmentRecord.starts_at <= _parse_iso_datetime(end))

    rows = query.order_by(AppointmentRecord.starts_at.asc(), AppointmentRecord.id.asc()).limit(500).all()
    _create_audit(db, current_user["email"], "list_appointments", "Appointment", patient_id, f"start={start}, end={end}")
    return [
        {
            "id": item.id,
            "patient_id": item.patient_id,
            "patient_name": item.patient_name,
            "patient_identifier": item.patient_identifier,
            "appointment_type": item.appointment_type,
            "mode": item.mode,
            "starts_at": item.starts_at.isoformat(),
            "ends_at": item.ends_at.isoformat(),
            "status": item.status,
            "reason": item.reason,
            "location": item.location,
        }
        for item in rows
    ]

@router.post("/superuser/inference/{model_type}")
@limiter.limit("30/minute")
async def inference(request: Request, model_type: str, body: InferenceRequest, current_user: Dict = Depends(get_current_superuser), db: Session = Depends(get_db)):
    if model_type not in {"tabular", "image"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="model_type debe ser 'tabular' o 'image'.")

    patient_id = body.patient_fhir.get("id")
    if not patient_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El recurso Patient debe contener un id válido.")

    url = settings.ML_SERVICE_URL if model_type == "tabular" else settings.DL_SERVICE_URL
    payload = {
        "patient": body.patient_fhir,
        "patient_id": patient_id,
        "model": body.model,
    }
    if model_type == "image" and body.ecg_image_base64:
        payload["image_base64"] = body.ecg_image_base64
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            result = await client.post(f"{url}/infer", json=payload)
            result.raise_for_status()
            inference_result = result.json()
    except httpx.RequestError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Error de comunicación con el servicio de inferencia: {exc}")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=f"Servicio de inferencia respondió con error: {exc.response.text}")

    if model_type == "image" and isinstance(inference_result, dict):
        prediction_text = str(inference_result.get("prediction", "")).lower()
        if "retinop" in prediction_text:
            probability = inference_result.get("probability")
            probability_value = float(probability) if isinstance(probability, (int, float)) else 0.5
            if probability_value >= 0.75:
                mapped = "ecg compatible con alto riesgo cardiaco"
            elif probability_value >= 0.52:
                mapped = "ecg con hallazgos intermedios"
            else:
                mapped = "ecg sin hallazgos agudos"
            inference_result["prediction"] = mapped
            inference_result["clinical_interpretation"] = "Prediccion normalizada a terminologia cardiaca"

    risk_assessment = {
        "resourceType": "RiskAssessment",
        "status": "final",
        "subject": {"reference": f"Patient/{patient_id}"},
        "probability": {"value": inference_result.get("probability")},
        "prediction": inference_result.get("prediction"),
        "method": {
            "coding": [{"system": "http://loinc.org", "code": "LP173421-1", "display": "Predicción de riesgo clínico"}]
        },
    }

    report_text = f"Predicción: {inference_result.get('prediction')} con probabilidad {inference_result.get('probability')}"
    diagnostic_report = {
        "resourceType": "DiagnosticReport",
        "status": "final",
        "code": {
            "coding": [{"system": "http://loinc.org", "code": "LP29708-2", "display": "Informe de inferencia clínica"}]
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "conclusion": report_text,
        "presentedForm": [
            {
                "contentType": "text/plain",
                "data": base64.b64encode(report_text.encode("utf-8")).decode("utf-8"),
            }
        ],
    }

    created_risk_assessment = None
    created_diagnostic_report = None
    fhir_warning = None
    try:
        created_risk_assessment = await _fhir_request("POST", "RiskAssessment", json=risk_assessment)
        created_diagnostic_report = await _fhir_request("POST", "DiagnosticReport", json=diagnostic_report)
    except httpx.HTTPStatusError as exc:
        fhir_warning = f"No se pudo persistir el resultado en FHIR: {exc.response.text}"
    except httpx.RequestError as exc:
        fhir_warning = f"No se pudo persistir el resultado en FHIR: {exc}"

    latest_vitals_row = (
        db.query(VitalSignRecord)
        .filter(VitalSignRecord.patient_id == str(patient_id))
        .order_by(VitalSignRecord.recorded_at.desc(), VitalSignRecord.id.desc())
        .first()
    )
    latest_vitals = _build_vital_item(latest_vitals_row) if latest_vitals_row else None

    _create_audit(db, current_user["email"], "infer_patient", "RiskAssessment", patient_id, f"model_type={model_type}")
    return {
        "prediction": inference_result.get("prediction"),
        "probability": inference_result.get("probability"),
        "calibrated": inference_result.get("calibrated", True),
        "model": inference_result.get("model", model_type),
        "clinical_interpretation": inference_result.get("clinical_interpretation"),
        "analysis": inference_result.get("analysis"),
        "ecg_summary": inference_result.get("ecg_summary"),
        "ecg_source": inference_result.get("ecg_source"),
        "risk_reasons": inference_result.get("risk_reasons"),
        "vital_signs": latest_vitals,
        "fhir_risk_assessment": created_risk_assessment,
        "fhir_diagnostic_report": created_diagnostic_report,
        "fhir_warning": fhir_warning,
    }

@router.delete("/superuser/patients/{patient_id}")
@limiter.limit("20/minute")
async def soft_delete_patient(request: Request, patient_id: str, payload: DeleteReason, current_user: Dict = Depends(get_current_superuser), db: Session = Depends(get_db)):
    body = {"resourceType": "Patient", "id": patient_id, "active": False}
    result = await _fhir_request("PUT", f"Patient/{patient_id}", json=body)

    patient = _find_patient(db, patient_id)
    if patient:
        patient.active = False
        db.add(patient)
        db.commit()

    _create_audit(db, current_user["email"], "soft_delete_patient", "Patient", patient_id, f"reason={payload.reason}, icd10={payload.icd10_code}")
    return {"id": patient_id, "active": False, "reason": payload.reason, "icd10_code": payload.icd10_code, "fhir": result}


@router.post("/superuser/procedure-logs", status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute")
async def create_procedure_log(
    request: Request,
    payload: ProcedureLogCreate,
    current_user: Dict = Depends(get_current_superuser),
    db: Session = Depends(get_db),
):
    comment = (payload.comment or "").strip()
    action = (payload.action or "").strip()
    if not action:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La acción del procedimiento es obligatoria.")
    if not comment:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El comentario del procedimiento es obligatorio.")

    entry = ProcedureLog(
        user_email=current_user["email"],
        action=action,
        patient_id=(payload.patient_id or "").strip() or None,
        patient_name=(payload.patient_name or "").strip() or None,
        patient_identifier=(payload.patient_identifier or "").strip() or None,
        comment=comment,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    _create_audit(
        db,
        current_user["email"],
        "create_procedure_log",
        "ProcedureLog",
        str(entry.id),
        f"action={action}, patient_id={entry.patient_id or 'none'}",
    )

    return {
        "id": entry.id,
        "action": entry.action,
        "patient_id": entry.patient_id,
        "patient_name": entry.patient_name,
        "patient_identifier": entry.patient_identifier,
        "comment": entry.comment,
        "timestamp": entry.created_at.isoformat() if entry.created_at else datetime.utcnow().isoformat(),
    }


@router.get("/superuser/procedure-logs", response_model=List[ProcedureLogItem])
@limiter.limit("60/minute")
async def list_procedure_logs(
    request: Request,
    patient_id: Optional[str] = None,
    limit: int = 100,
    current_user: Dict = Depends(get_current_superuser),
    db: Session = Depends(get_db),
):
    safe_limit = max(1, min(limit, 200))
    query = db.query(ProcedureLog).order_by(ProcedureLog.id.desc())
    if patient_id:
        query = query.filter(ProcedureLog.patient_id == patient_id)

    logs = query.limit(safe_limit).all()
    _create_audit(
        db,
        current_user["email"],
        "list_procedure_logs",
        "ProcedureLog",
        patient_id,
        f"limit={safe_limit}",
    )

    return [
        {
            "id": item.id,
            "action": item.action,
            "patient_id": item.patient_id,
            "patient_name": item.patient_name,
            "patient_identifier": item.patient_identifier,
            "comment": item.comment,
            "timestamp": item.created_at.isoformat() if item.created_at else datetime.utcnow().isoformat(),
        }
        for item in logs
    ]
