import requests
import json

BASE = "http://127.0.0.1:8501"
HEADERS = {"Authorization": "Bearer local_dummy_key", "Content-Type": "application/json"}

prompts = {
    "verification": "You are running the 'Verification' metric. Please answer with JSON containing 'verdict' and 'reason'.",
    "response_relevance": "You are running the 'ResponseRelevanceOutput' metric. Return JSON with 'question' and 'noncommittal'.",
    "context_recall": "You are running the 'ContextRecallClassifications' metric. Return JSON with 'classifications' list containing 'statement','reason','attributed'.",
    "statement_generator": "You are running the 'StatementGeneratorOutput' metric. Return JSON with 'statements' list.",
    "unknown": "A normal user question: Explain the likely diagnosis in one sentence."
}


def call_chat(prompt):
    payload = {"messages": [{"role": "user", "content": prompt}]}
    r = requests.post(f"{BASE}/v1/chat/completions", headers=HEADERS, json=payload, timeout=5)
    r.raise_for_status()
    return r.json()


for name, prompt in prompts.items():
    print("---", name)
    try:
        resp = call_chat(prompt)
        content = resp.get("choices", [])[0].get("message", {}).get("content", "")
        print("raw:", content)
        try:
            parsed = json.loads(content)
            print("parsed JSON:", json.dumps(parsed, ensure_ascii=False))
            # simple checks
            if name == "verification":
                ok = "verdict" in parsed and "reason" in parsed
            elif name == "response_relevance":
                ok = "question" in parsed and "noncommittal" in parsed
            elif name == "context_recall":
                ok = "classifications" in parsed and isinstance(parsed["classifications"], list)
            elif name == "statement_generator":
                ok = "statements" in parsed and isinstance(parsed["statements"], list)
            else:
                ok = True
            print("valid:", ok)
        except json.JSONDecodeError:
            print("INVALID JSON")
    except Exception as e:
        print("ERROR", e)

print("done")
