import requests
import json


# Endpoint (copy from the “Keys and Endpoint” page)
ENDPOINT = f"https://hackathon-gdpr-detection.cognitiveservices.azure.com/"
# API key for the Language service
from NER_key import SUBSCRIPTION_KEY

def ner_inference(text: str, mode: int =0):
    """
    Calls Azure Language – Named Entity Recognition (pre‑built) and
    returns the list of detected entities.
    """
    url = f"{ENDPOINT}/language/:analyze-text?api-version=2023-04-01"

    # Build the request payload – one document per call
    payload = {
        "kind": "EntityRecognition",          # pre‑built NER
        "analysisInput": {
            "documents": [
                {
                    "id": "1",
                    "text": text
                }
            ]
        },
        "parameters": {
            "modelVersion": "latest"        # use the most recent model
        }
    }

    headers = {
        "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()  # raise an exception for HTTP errors

    result = response.json()

    print(f"Result: {result}")

    entities = (
        result.get("results", {})
        .get("documents", [{}])[0]
        .get("entities", [])
    )
    simplified = [
        {
            "text": ent["text"],
            "category": ent["category"],
            "confidence": round(ent["confidenceScore"], 3)
        }
        for ent in entities
    ]
    return simplified

# -------------------------------------------------
# Example usage
# -------------------------------------------------
if __name__ == "__main__":
    sample_text = (
        "Acme Ltd, the data controller, collects personal data such as "
        "John Doe's email address (john.doe@example.com) and retains it for "
        "three years. Processing is based on explicit consent."
    )

    detected = ner_inference(sample_text)
    with open("test_data/NER_mock.json", "w", encoding="utf-8") as f:
        json.dump(detected, f, ensure_ascii=False, indent=2)

    print(f"Detected Entities: {detected}")
