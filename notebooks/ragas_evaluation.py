import os

from openai import OpenAI
from ragas import evaluate
from ragas.embeddings import OpenAIEmbeddings
from ragas.llms import llm_factory
from ragas.metrics._answer_relevance import answer_relevancy
from ragas.metrics._context_precision import context_precision
from ragas.metrics._context_recall import context_recall
from ragas.metrics._faithfulness import faithfulness
from datasets import Dataset


llm_endpoint = os.getenv("LLM_ENDPOINT")
if llm_endpoint:
    normalized_endpoint = llm_endpoint.rstrip("/")
    if not normalized_endpoint.endswith("/v1"):
        normalized_endpoint = f"{normalized_endpoint}/v1"
    os.environ.setdefault("OPENAI_BASE_URL", normalized_endpoint)
    os.environ.setdefault("OPENAI_API_BASE", normalized_endpoint)

os.environ.setdefault("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", "local_dummy_key"))

openai_api_key = os.getenv("OPENAI_API_KEY", "local_dummy_key")
openai_base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE") or "http://127.0.0.1:8501/v1"

openai_client = OpenAI(api_key=openai_api_key, base_url=openai_base_url)

llm = llm_factory(
    model="mock-model",
    client=openai_client,
)

class EmbeddingsAdapter:
    def __init__(self, client, model="mock-embedding"):
        self.client = client
        self.model = model

    def embed_query(self, text):
        resp = self.client.embeddings.create(model=self.model, input=text)
        return resp.data[0].embedding

    def embed_documents(self, texts):
        resp = self.client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]


embeddings = EmbeddingsAdapter(client=openai_client, model="mock-embedding")

# Conjunto de evaluación: mínimo 20 preguntas clínicas sobre la temática
eval_data = {
    "question": [
        "¿Cuál es el riesgo de diabetes para este paciente?",
        "¿Qué observaciones clínicas apoyan el diagnóstico?",
        "¿El valor de glucosa en ayunas sugiere diabetes o prediabetes?",
        "¿Cómo interpretar un IMC de 32 en este contexto clínico?",
        "¿Qué riesgo cardiovascular implica una presión arterial de 145/90?",
        "¿Qué hallazgos apoyan síndrome metabólico en este caso?",
        "¿La HbA1c reportada está en meta terapéutica?",
        "¿Qué evidencia clínica sugiere riesgo de nefropatía diabética?",
        "¿Cuándo corresponde solicitar fondo de ojo en diabetes tipo 2?",
        "¿Cómo clasificar el riesgo global del paciente con obesidad e hipertensión?",
        "¿Qué valor clínico tiene una troponina elevada en dolor torácico?",
        "¿Qué indica un dímero D elevado en este escenario?",
        "¿Cuándo sospechar sepsis con base en lactato y signos clínicos?",
        "¿Qué parámetros orientan a insuficiencia cardiaca?",
        "¿Cuáles son los criterios clínicos de exacerbación de EPOC?",
        "¿Cómo identificar asma no controlada en seguimiento?",
        "¿Qué marcadores apoyan diagnóstico de anemia ferropénica?",
        "¿Qué patrón de laboratorio sugiere hipotiroidismo primario?",
        "¿Qué hallazgos sugieren enfermedad renal crónica en progresión?",
        "¿Qué medidas reducen eventos cardiovasculares en alto riesgo?",
        "¿Qué datos apoyan hígado graso asociado a disfunción metabólica?",
    ],
    "answer": [
        "El paciente presenta riesgo alto de diabetes según niveles de glucosa y BMI.",
        "La presión arterial elevada y la glucosa en ayunas apoyan el diagnóstico.",
        "Una glucosa en ayunas de 130 mg/dL es compatible con diabetes si se confirma en más de una medición.",
        "Un IMC de 32 kg/m2 corresponde a obesidad y aumenta el riesgo cardiometabólico.",
        "Una presión arterial de 145/90 se clasifica como hipertensión y eleva el riesgo cardiovascular.",
        "La combinación de hiperglucemia, obesidad y presión elevada sugiere síndrome metabólico.",
        "La HbA1c está en meta si es menor a 7% para la mayoría de adultos, con individualización clínica.",
        "Albuminuria persistente y caída de TFG sugieren riesgo de nefropatía diabética.",
        "En diabetes tipo 2 se recomienda fondo de ojo desde el diagnóstico y luego control periódico.",
        "El riesgo global es moderado-alto por coexistencia de obesidad, hipertensión y alteraciones glucémicas.",
        "Troponina elevada con clínica compatible apoya síndrome coronario agudo.",
        "Un dímero D elevado puede sugerir trombosis cuando la probabilidad clínica no es baja.",
        "Lactato elevado con sospecha de infección y disfunción orgánica orienta a sepsis.",
        "BNP o NT-proBNP altos apoyan insuficiencia cardiaca en contexto clínico compatible.",
        "Aumento de disnea y cambios en esputo son consistentes con exacerbación de EPOC.",
        "Síntomas frecuentes y uso repetido de rescate sugieren asma no controlada.",
        "Hemoglobina baja junto con ferritina disminuida orienta a anemia ferropénica.",
        "TSH alta con T4 libre baja sugiere hipotiroidismo primario.",
        "Creatinina en ascenso, TFG baja y albuminuria persistente sugieren progresión renal crónica.",
        "Control de PA, glucosa, LDL y actividad física reduce eventos cardiovasculares.",
        "Elevación persistente de ALT/AST en contexto metabólico sugiere hígado graso.",
    ],
    "contexts": [
        ["Glucosa en ayunas 130 mg/dL", "BMI 32"],
        ["Presión arterial 145/90", "Glucosa en ayunas 130 mg/dL"],
        ["Glucosa en ayunas >=126 mg/dL", "Confirmación en medición repetida"],
        ["IMC 32 kg/m2", "Obesidad incrementa riesgo metabólico"],
        ["PA 145/90 mmHg", "Hipertensión estadio 2"],
        ["Obesidad abdominal", "Hiperglucemia e hipertensión"],
        ["Objetivo HbA1c <7%", "Individualizar por comorbilidades"],
        ["Microalbuminuria persistente", "Descenso de TFG"],
        ["Diabetes tipo 2", "Tamizaje de retinopatía anual"],
        ["Obesidad + hipertensión", "Riesgo cardiometabólico acumulado"],
        ["Dolor torácico típico", "Troponina elevada"],
        ["Probabilidad clínica intermedia", "Dímero D elevado"],
        ["Lactato elevado", "Disfunción orgánica por infección"],
        ["NT-proBNP elevado", "Síntomas de insuficiencia cardiaca"],
        ["Disnea aumentada", "Cambios de esputo"],
        ["Síntomas diurnos frecuentes", "Uso frecuente de inhalador de rescate"],
        ["Hemoglobina baja", "Ferritina baja"],
        ["TSH elevada", "T4 libre baja"],
        ["TFG disminuida", "Albuminuria persistente"],
        ["Control de presión arterial", "Control de LDL y glucosa"],
        ["ALT/AST elevadas", "Contexto de síndrome metabólico"],
    ],
    "ground_truth": [
        "Riesgo alto de diabetes.",
        "La evidencia clínica incluye presión arterial elevada y glucosa alta.",
        "El valor de glucosa cumple criterio de diabetes con confirmación.",
        "El IMC indica obesidad y riesgo cardiometabólico elevado.",
        "La PA reportada indica hipertensión con riesgo cardiovascular aumentado.",
        "Existe un patrón compatible con síndrome metabólico.",
        "La meta general de HbA1c es menor a 7% con ajuste individual.",
        "Hay indicios de nefropatía diabética por albuminuria y TFG.",
        "El fondo de ojo debe iniciarse al diagnóstico en DM2.",
        "Comorbilidades metabólicas elevan el riesgo global.",
        "Troponina elevada favorece síndrome coronario agudo.",
        "Dímero D alto puede apoyar sospecha trombótica según probabilidad.",
        "Lactato alto con infección sugiere sepsis.",
        "BNP o NT-proBNP altos apoyan falla cardiaca.",
        "Los síntomas descritos son de exacerbación de EPOC.",
        "El patrón clínico sugiere asma no controlada.",
        "La combinación Hb baja y ferritina baja sugiere anemia ferropénica.",
        "TSH alta y T4 baja sugieren hipotiroidismo primario.",
        "Datos de función renal sugieren progresión de ERC.",
        "La prevención cardiovascular requiere control multimodal.",
        "El perfil hepático y metabólico sugiere hígado graso.",
    ],
}

dataset = Dataset.from_dict(eval_data)

result = evaluate(
    dataset=dataset,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    llm=llm,
    embeddings=embeddings,
)

print(result)
result.to_pandas().to_json("ragas_report.json", orient="records", indent=2)

faithfulness_score = result.to_pandas()["faithfulness"].dropna().mean()

if faithfulness_score < 0.75:
    print("ADVERTENCIA: Faithfulness < 0.75 → Penalización del 10% en nota final")
