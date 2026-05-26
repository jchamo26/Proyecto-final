from flask import Flask, request, jsonify
import threading
import hashlib
import json
import re
import logging
import time
import os
from collections import defaultdict

app = Flask(__name__)

# Configuración desde variables de entorno
API_KEY = os.getenv('OPENAI_API_KEY', 'local_dummy_key')
MOCK_PORT = int(os.getenv('MOCK_PORT', 8501))
MOCK_HOST = os.getenv('MOCK_HOST', '127.0.0.1')
LOG_LEVEL = os.getenv('MOCK_LOG_LEVEL', 'INFO')

# Configurar logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='[%(asctime)s] %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Estadísticas de llamadas
call_stats = defaultdict(int)
call_lock = threading.Lock()

def record_call(metric_type: str):
    """Registra una llamada a una métrica"""
    with call_lock:
        call_stats[metric_type] += 1

@app.route("/v1/models", methods=["GET"])
def models():
    """Endpoint para listar modelos disponibles"""
    # Allow models listing without auth for local testing
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or (API_KEY and auth.split()[1] != API_KEY):
        logger.debug("models endpoint called without valid Authorization - permissive mode for tests")
    return jsonify({"data": [{"id": "mock-model", "object": "model"}]})

@app.route("/stats", methods=["GET"])
def stats():
    """Endpoint para ver estadísticas de llamadas"""
    with call_lock:
        stats_copy = dict(call_stats)
    return jsonify({
        "total_calls": sum(stats_copy.values()),
        "calls_by_metric": stats_copy
    })

@app.route("/health", methods=["GET"])
def health():
    """Endpoint de healthcheck"""
    return jsonify({"status": "healthy", "service": "mock-openai-server"})

@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    """Endpoint para chat completions compatible con OpenAI"""
    try:
        # Allow unauthenticated requests for local testing (tests call endpoints without Authorization)
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or (API_KEY and auth.split()[1] != API_KEY):
            # Log a warning but do not reject the request to keep the mock server permissive for tests
            logger.debug("Authorization header missing or invalid - proceeding in permissive mode for tests")

        body = request.get_json() or {}
        messages = body.get("messages") or body.get("input") or []
        n_completions = body.get("n", 1)  # Número de generaciones solicitadas
        
        # Construir determinísticamente el prompt_text desde los mensajes
        prompt_parts = []
        if isinstance(messages, list) and len(messages) > 0:
            for m in messages:
                if isinstance(m, dict):
                    prompt_parts.append(m.get("content", ""))
                else:
                    prompt_parts.append(str(m))
        elif isinstance(messages, str):
            prompt_parts.append(messages)
        prompt_text = " ".join(prompt_parts)

        prompt_lower = (prompt_text or "").lower()

        # Heuristics to detect ragas metric prompts
        def contains_any(*keys):
            return any(k in prompt_lower for k in keys)

        # Two forms for statements: generator (list of strings) and NLI output (list of objects)
        statements_texts = ["La respuesta es consistente con el contexto."]
        statements_objects = [
            {"statement": "La respuesta es consistente con el contexto.", "reason": "Se encuentra en el contexto.", "verdict": 1}
        ]

        reply_obj = {
            "verdict": 1,
            "reason": "Apoyo de la evidencia proporcionada.",
            "classifications": [
                {
                    "statement": "La afirmación está contenida en el contexto.",
                    "reason": "Encontrado texto coincidente en el contexto.",
                    "attributed": 1,
                }
            ],
            "noncommittal": 0,
            "statements_texts": statements_texts,
            "statements_objects": statements_objects,
            "question": "¿Cuál es el diagnóstico?",
        }

        # Detectar qué métrica RAGAS está siendo usada
        reply_data = None
        detected_metric = "unknown"
        
        if contains_any("response relevance", "response_relevance", "noncommittal"):
            reply_data = {"question": reply_obj["question"], "noncommittal": reply_obj["noncommittal"]}
            detected_metric = "response_relevance"
        elif contains_any("contextrecall", "context recall", "contextrecallclassifications", "attributed"):
            reply_data = {"classifications": reply_obj["classifications"]}
            detected_metric = "context_recall"
        elif contains_any("verification", "verdict", "verify"):
            # Incluir 'statements' objects para satisfacer las expectativas NLIStatementOutput
            reply_data = {"verdict": reply_obj["verdict"], "reason": reply_obj["reason"], "statements": reply_obj["statements_objects"]}
            detected_metric = "verification"
        elif contains_any("statementgenerator", "statement generator", "statements"):
            # Statement generator debe devolver lista de strings
            reply_data = {"statements": reply_obj["statements_texts"]}
            detected_metric = "statement_generator"
        elif contains_any("response relevance output", "response_relevance_output"):
            reply_data = {"question": reply_obj["question"], "noncommittal": reply_obj["noncommittal"]}
            detected_metric = "response_relevance_output"
        elif contains_any("faithfulness", "faithful"):
            # Faithfulness usa NLI, requiere statements con verdict
            reply_data = {"verdict": reply_obj["verdict"], "reason": reply_obj["reason"], "statements": reply_obj["statements_objects"]}
            detected_metric = "faithfulness"
        else:
            # Fallback: devolver JSON compacto con campos comunes
            reply_data = {
                "verdict": reply_obj["verdict"],
                "reason": reply_obj["reason"],
                "noncommittal": reply_obj["noncommittal"],
                "statements": reply_obj["statements_objects"],
            }
            detected_metric = "fallback"
        
        record_call(detected_metric)
        logger.info(f"Chat completion solicitada - Métrica detectada: {detected_metric}, Generaciones solicitadas: {n_completions}")

        # Asegurar que el contenido sea JSON string
        reply = json.dumps(reply_data, ensure_ascii=False)
        
        # Generar múltiples completaciones si se solicitó
        choices = []
        for i in range(n_completions):
            choices.append({
                "index": i,
                "message": {"role": "assistant", "content": reply},
                "finish_reason": "stop",
            })

        response = {
            "id": f"cmpl-mock-{int(time.time() * 1000)}",
            "object": "chat.completion",
            "choices": choices,
            "usage": {"prompt_tokens": len(prompt_text.split()), "completion_tokens": 10, "total_tokens": len(prompt_text.split()) + 10},
        }
        logger.debug(f"Respuesta enviada para {detected_metric}: {n_completions} generaciones")
        return jsonify(response)
    except Exception as e:
        logger.exception(f"Error en chat_completions: {str(e)}")
        # Devolver JSON fallback seguro que coincida con esquemas RAGAS comunes
        fallback = {"verdict": 0, "reason": "mock-fallback", "statements": [{"statement": "fallback", "reason": "fallback", "verdict": 0}], "noncommittal": 0}
        record_call("error")
        return jsonify({
            "id": "cmpl-mock-fallback",
            "object": "chat.completion",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": json.dumps(fallback, ensure_ascii=False)}, "finish_reason": "stop"}],
        })


@app.route("/v1/embeddings", methods=["POST"])
def embeddings():
    """Endpoint para generar embeddings determinísticos"""
    try:
        # Allow embeddings requests without auth for local testing
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or (API_KEY and auth.split()[1] != API_KEY):
            logger.debug("embeddings called without valid Authorization - permissive mode for tests")

        body = request.get_json() or {}
        input_data = body.get("input", "")
        if isinstance(input_data, str):
            items = [input_data]
        else:
            items = [str(value) for value in input_data]

        data = []
        for index, text in enumerate(items):
            # Generar embedding determinístico usando SHA256
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            # Mapear bytes a float en rango [-1, 1]
            vector = [round((byte / 255.0) * 2.0 - 1.0, 6) for byte in digest[:32]]
            data.append({"object": "embedding", "index": index, "embedding": vector})

        record_call("embeddings")
        logger.debug(f"Embeddings generados para {len(items)} textos")
        return jsonify({
            "object": "list",
            "data": data,
            "model": body.get("model", "mock-embedding"),
            "usage": {"prompt_tokens": sum(len(t.split()) for t in items), "total_tokens": sum(len(t.split()) for t in items)}
        })
    except Exception as e:
        logger.exception(f"Error en embeddings: {str(e)}")
        record_call("embeddings_error")
        return jsonify({"error": {"message": str(e)}}), 500

if __name__ == "__main__":
    logger.info(f"Iniciando Mock OpenAI Server en {MOCK_HOST}:{MOCK_PORT}")
    logger.info(f"Nivel de logging: {LOG_LEVEL}")
    logger.info(f"Endpoints disponibles:")
    logger.info(f"  - POST /v1/chat/completions (LLM completions)")
    logger.info(f"  - POST /v1/embeddings (Embeddings determinísticos)")
    logger.info(f"  - GET /v1/models (Listar modelos)")
    logger.info(f"  - GET /health (Health check)")
    logger.info(f"  - GET /stats (Estadísticas de llamadas)")
    app.run(host=MOCK_HOST, port=MOCK_PORT, debug=False)
