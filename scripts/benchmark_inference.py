import statistics
import time
import json
from typing import Dict, List, Tuple

import httpx


ML_URL = "http://127.0.0.1:8100/infer"
DL_URL = "http://127.0.0.1:8200/infer"
ITERATIONS = 20


def _measure(url: str, payload: Dict) -> Tuple[List[float], int, str]:
    samples: List[float] = []
    last_status = 0
    last_body = ""

    with httpx.Client(timeout=10.0) as client:
        for _ in range(ITERATIONS):
            start = time.perf_counter()
            try:
                response = client.post(url, json=payload)
                elapsed_ms = (time.perf_counter() - start) * 1000
                samples.append(elapsed_ms)
                last_status = response.status_code
                try:
                    last_body = str(response.json())
                except Exception:
                    last_body = response.text
            except Exception as exc:
                last_body = str(exc)
                break

    return samples, last_status, last_body


def _summary(samples: List[float]) -> Dict[str, float]:
    return {
        "avg_ms": round(statistics.mean(samples), 2),
        "p95_ms": round(sorted(samples)[int(len(samples) * 0.95) - 1], 2),
        "min_ms": round(min(samples), 2),
        "max_ms": round(max(samples), 2),
    }


def main() -> None:
    ml_payload = {
        "patient": {
            "age": 62,
            "observations": [
                {"code": "2345-7", "value": 145, "unit": "mg/dL"},
                {"code": "55284-4", "value": 8.2, "unit": "%"},
            ],
        },
        "model": {"feature_1": 1.0, "feature_2": 0.7},
    }

    dl_payload = {
        "image_base64": "data:image/png;base64," + ("A" * 1200),
        "patient_id": "demo-1",
    }

    print("== Benchmark ML ==")
    ml_samples, ml_status, ml_body = _measure(ML_URL, ml_payload)
    print(f"status: {ml_status}")
    print(_summary(ml_samples) if ml_samples else {"error": "service unavailable"})
    print(f"sample_response: {ml_body}")

    print("\n== Benchmark DL ==")
    dl_samples, dl_status, dl_body = _measure(DL_URL, dl_payload)
    print(f"status: {dl_status}")
    print(_summary(dl_samples) if dl_samples else {"error": "service unavailable"})
    print(f"sample_response: {dl_body}")

    report = {
        "ml": {
            "url": ML_URL,
            "status": ml_status,
            "metrics": _summary(ml_samples) if ml_samples else None,
            "error": None if ml_samples else ml_body,
        },
        "dl": {
            "url": DL_URL,
            "status": dl_status,
            "metrics": _summary(dl_samples) if dl_samples else None,
            "error": None if dl_samples else dl_body,
        },
        "iterations": ITERATIONS,
    }

    with open("docs/inference_latency_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("\nReporte guardado en docs/inference_latency_report.json")

    print("\nObjetivo sugerido de rúbrica:")
    print("- ML avg_ms < 300")
    print("- DL avg_ms < 500")


if __name__ == "__main__":
    main()
