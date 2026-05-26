import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _count_ragas_questions() -> int:
    notebook_path = ROOT / "notebooks" / "ragas_evaluation.py"
    text = notebook_path.read_text(encoding="utf-8")
    marker = '"question": ['
    idx = text.find(marker)
    if idx == -1:
        return 0
    block = text[idx:]
    end = block.find('],')
    if end == -1:
        return 0
    question_block = block[:end]
    return question_block.count('"') // 2


def _has_rate_limit() -> bool:
    backend = (ROOT / "backend" / "app" / "api" / "superuser.py").read_text(encoding="utf-8")
    agent = (ROOT / "agent" / "app" / "main.py").read_text(encoding="utf-8")
    return "@limiter.limit" in backend and "@limiter.limit" in agent


def _has_bcrypt_rounds() -> bool:
    superuser = (ROOT / "backend" / "app" / "api" / "superuser.py").read_text(encoding="utf-8")
    return "schemes=[\"bcrypt\"]" in superuser and "bcrypt__rounds=12" in superuser


def _has_safe_env_placeholders() -> bool:
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    checks = [
        "<CHANGE_ME_POSTGRES_PASSWORD>",
        "<CHANGE_ME_SUPERUSER_PASSWORD>",
        "<CHANGE_ME_MINIO_PASSWORD>",
    ]
    return all(item in env for item in checks)


def _rag_docs_count() -> int:
    docs_file = ROOT / "agent" / "app" / "rag" / "clinical_docs.py"
    text = docs_file.read_text(encoding="utf-8")
    return text.count('"id": "doc-')


def main() -> None:
    report = {
        "rag_docs_count": _rag_docs_count(),
        "ragas_question_count": _count_ragas_questions(),
        "rate_limiting_implemented": _has_rate_limit(),
        "bcrypt_rounds_12": _has_bcrypt_rounds(),
        "safe_env_placeholders": _has_safe_env_placeholders(),
    }

    report["ready_minimum_targets"] = all(
        [
            report["rag_docs_count"] >= 20,
            report["ragas_question_count"] >= 20,
            report["rate_limiting_implemented"],
            report["bcrypt_rounds_12"],
            report["safe_env_placeholders"],
        ]
    )

    output_path = ROOT / "docs" / "rubric_readiness_report.json"
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nReporte escrito en: {output_path}")


if __name__ == "__main__":
    main()
