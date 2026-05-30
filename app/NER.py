import os
import requests
from app.NER_modes import NER_MODES

SUBSCRIPTION_KEY = os.getenv("NER_SUBSCRIPTION_KEY", "")

# Endpoint for Azure API
ENDPOINT = f"https://hackathon-gdpr-detection.cognitiveservices.azure.com/"

CONFIDENCE_THRESHOLD = 0.85


def ner_inference(
    text: str,
    mode=None,
    confidence_threshold = CONFIDENCE_THRESHOLD,
):
    """
    Azure NER for a single document.

    • mode=None          → return all categories (no filtering).
    • mode="some_key"   → keep only categories listed in NER_MODES[mode].
    • confidence_threshold (0‑1) → discard entities with a lower confidenceScore.
    Returns a list of simplified entity dictionaries.
    """
    # ----- decide filtering -------------------------------------------------
    if mode is None:
        filter_set = None                     # keep every category
    else:
        try:
            filter_set = NER_MODES[mode]
        except Exception:
            print("[!] NER Mode unknown, using default minimal version")
            filter_set = NER_MODES["gdpr_minimal"]

    url = f"{ENDPOINT}/language/:analyze-text?api-version=2023-04-01"

    payload = {
        "kind": "EntityRecognition",
        "analysisInput": {"documents": [{"id": "1", "text": text}]},
        "parameters": {"modelVersion": "latest"},
    }

    headers = {
        "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
        "Content-Type": "application/json",
    }

    # ----- call Azure --------------------------------------------------------
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    result = response.json()

    # ----- extract entities --------------------------------------------------
    ents = (
        result.get("results", {})
        .get("documents", [{}])[0]
        .get("entities", [])
    )

    # category filter (if a rule‑set was supplied)
    if filter_set is not None:
        ents = [e for e in ents if e["category"] in filter_set]

    # confidence‑score filter
    if confidence_threshold > 0:
        ents = [e for e in ents if e["confidenceScore"] >= confidence_threshold]

    # ----- simplify output ---------------------------------------------------
    simplified = [
        {
            "text": e["text"],
            "category": e["category"],
            "confidence": e["confidenceScore"],
        }
        for e in ents
    ]

    return simplified



def ner_inference_batch(
        texts,
        mode=None,
        confidence_threshold = CONFIDENCE_THRESHOLD):
    """
    Azure NER batch call.
    • mode=None → no filtering (all categories returned)
    • mode=... → keep only categories defined in NER_MODES[mode]
    Returns a list of entity‑lists matching the input order.
    """
    # decide filter set
    if mode is None:
        filter_set = None
    else:
        try:
            filter_set = NER_MODES[mode]
        except Exception:
            print("[!] NER Mode unknown, using default minimal version")
            filter_set = NER_MODES["gdpr_minimal"]

    # build payload
    documents = [{"id": str(i + 1), "text": txt} for i, txt in enumerate(texts)]
    payload = {
        "kind": "EntityRecognition",
        "analysisInput": {"documents": documents},
        "parameters": {"modelVersion": "latest"},
    }

    url = f"{ENDPOINT}/language/:analyze-text?api-version=2023-04-01"
    headers = {
        "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
        "Content-Type": "application/json",
    }

    # call Azure
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    result = response.json()

    # parse & (optionally) filter
    entities_by_id = {}
    for doc in result.get("results", {}).get("documents", []):
        ents = doc.get("entities", [])

        # category filter (if a rule‑set was supplied)
        if filter_set is not None:
            ents = [e for e in ents if e["category"] in filter_set]

        # confidence‑score filter (if a threshold > 0 was provided)
        if confidence_threshold > 0:
            ents = [
                e for e in ents
                if e["confidenceScore"] >= confidence_threshold
            ]

        # store the simplified representation
        entities_by_id[doc["id"]] = [
            {
                "text": e["text"],
                "category": e["category"],
                "confidence": e["confidenceScore"]
            }
            for e in ents
        ]

    # return in original order
    return [entities_by_id[str(i + 1)] for i in range(len(texts))]


# -------------------------------------------------
# Example usage
# -------------------------------------------------
if __name__ == "__main__":
    sample_text = (
        "Acme Ltd, the data controller, collects personal data such as "
        "John Doe's email address (john.doe@example.com) and retains it for "
        "three years. Processing is based on explicit consent."
    )

    sample_text2 = "Definition of KPIs stopped, what should be done now? Delayed by at least 2 years laskjkdawjdajsdj Was machen wir  und warum"

    detected = ner_inference_batch([sample_text, sample_text2])

    print(f"Detected Entities: {detected}")
