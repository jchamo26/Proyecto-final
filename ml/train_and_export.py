"""
Entrena un modelo tabular, calibra probabilidades y exporta ONNX INT8.

Uso:
    python train_and_export.py --data-path data/diabetes.csv

Notas:
- Por defecto usa PIMA Diabetes (archivo CSV local).
- Registra métricas y artefactos en MLflow si MLFLOW_TRACKING_URI esta configurado.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Dict, Tuple

import mlflow
import numpy as np
import onnx
import pandas as pd
from onnxruntime.quantization import QuantType, quantize_dynamic
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import classification_report, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType

FEATURE_COLS = {
    "Pregnancies": "11996-6",
    "Glucose": "2339-0",
    "BloodPressure": "8462-4",
    "SkinThickness": "41909-3",
    "Insulin": "20448-7",
    "BMI": "39156-5",
    "DiabetesPedigreeFunction": "None",
    "Age": "30525-0",
}
TARGET = "Outcome"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train and export diabetes model to ONNX INT8")
    parser.add_argument("--data-path", type=str, default="data/diabetes.csv")
    parser.add_argument("--output-dir", type=str, default="models")
    parser.add_argument("--experiment", type=str, default="diabetes-classification")
    parser.add_argument("--run-name", type=str, default="GBM-Calibrated-v1")
    return parser.parse_args()


def load_dataset(data_path: str) -> Tuple[np.ndarray, np.ndarray]:
    df = pd.read_csv(data_path)
    expected = set(FEATURE_COLS.keys()) | {TARGET}
    missing = sorted(expected - set(df.columns))
    if missing:
        raise ValueError(f"Columnas faltantes en dataset: {missing}")

    X = df[list(FEATURE_COLS.keys())].values.astype(np.float32)
    y = df[TARGET].values
    return X, y


def train_calibrated_model(X: np.ndarray, y: np.ndarray) -> Tuple[CalibratedClassifierCV, Dict[str, float], str]:
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    base_clf = GradientBoostingClassifier(
        n_estimators=200,
        learning_rate=0.05,
        subsample=0.8,
        random_state=42,
    )

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", base_clf),
    ])

    calibrated = CalibratedClassifierCV(
        pipeline,
        cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=42),
        method="isotonic",
    )

    calibrated.fit(X_train, y_train)

    y_pred = calibrated.predict(X_test)
    y_proba = calibrated.predict_proba(X_test)[:, 1]

    metrics = {
        "f1_weighted": float(f1_score(y_test, y_pred, average="weighted")),
        "auc_roc": float(roc_auc_score(y_test, y_proba)),
    }
    report = classification_report(y_test, y_pred)
    return calibrated, metrics, report


def export_onnx_int8(model: CalibratedClassifierCV, output_dir: str) -> Tuple[str, str]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    fp32_path = out_dir / "diabetes_fp32.onnx"
    int8_path = out_dir / "diabetes_int8.onnx"

    initial_type = [("float_input", FloatTensorType([None, len(FEATURE_COLS)]))]
    onnx_model = convert_sklearn(
        model,
        initial_types=initial_type,
        target_opset=17,
        options={id(model): {"zipmap": False}},
    )

    onnx.save(onnx_model, fp32_path.as_posix())
    quantize_dynamic(fp32_path.as_posix(), int8_path.as_posix(), weight_type=QuantType.QInt8)

    return fp32_path.as_posix(), int8_path.as_posix()


def main() -> None:
    args = parse_args()

    X, y = load_dataset(args.data_path)
    mlflow_tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    mlflow.set_tracking_uri(mlflow_tracking_uri)
    mlflow.set_experiment(args.experiment)

    with mlflow.start_run(run_name=args.run_name):
        model, metrics, report = train_calibrated_model(X, y)

        mlflow.log_params(
            {
                "model": "GradientBoosting + CalibratedClassifierCV",
                "calibration": "isotonic",
                "cv_folds": 5,
                "n_estimators": 200,
                "features": list(FEATURE_COLS.keys()),
                "target": TARGET,
            }
        )
        mlflow.log_metrics(metrics)

        fp32_path, int8_path = export_onnx_int8(model, args.output_dir)
        mlflow.log_artifact(fp32_path)
        mlflow.log_artifact(int8_path)

        print(f"F1 Score (weighted): {metrics['f1_weighted']:.4f}")
        print(f"AUC-ROC:             {metrics['auc_roc']:.4f}")
        print(report)
        print(f"Modelo FP32: {fp32_path}")
        print(f"Modelo INT8: {int8_path}")


if __name__ == "__main__":
    main()
