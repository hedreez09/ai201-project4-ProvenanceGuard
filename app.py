import json
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from groq import Groq


load_dotenv()

app = Flask(__name__)

AUDIT_LOG_FILE = "audit_log.json"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def get_timestamp():
    """Return a UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def load_audit_log():
    """Load audit log entries from JSON file."""
    if not os.path.exists(AUDIT_LOG_FILE):
        return []

    try:
        with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError:
        return []


def save_audit_entry(entry):
    """Append one structured entry to the audit log."""
    entries = load_audit_log()
    entries.append(entry)

    with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as file:
        json.dump(entries, file, indent=2)


def classify_with_groq(text):
    """
    First detection signal.

    Uses Groq to estimate whether the text appears AI-generated.
    Returns a score from 0.0 to 1.0, where higher means more likely AI-generated.
    """

    if not GROQ_API_KEY:
        # Safe fallback so the app can still run during local setup.
        return {
            "llm_score": 0.5,
            "llm_reasoning": "GROQ_API_KEY is missing. Returned neutral placeholder score."
        }

    client = Groq(api_key=GROQ_API_KEY)

    prompt = f"""
You are part of Provenance Guard, a system that analyzes creative writing attribution.

Analyze the submitted text and estimate whether it appears AI-generated or human-written.

Return ONLY valid JSON with this exact structure:
{{
  "llm_score": 0.0,
  "llm_reasoning": "brief explanation"
}}

Scoring rules:
- 0.0 means strongly human-written
- 0.5 means uncertain or mixed
- 1.0 means strongly AI-generated

Be careful with false positives. Formal writing, non-native English writing, and polished human writing should not automatically be treated as AI-generated.

Text to analyze:
\"\"\"{text}\"\"\"
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a careful AI-content attribution assistant that returns only JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
        )

        content = response.choices[0].message.content.strip()

        parsed = json.loads(content)

        llm_score = float(parsed.get("llm_score", 0.5))
        llm_score = max(0.0, min(1.0, llm_score))

        return {
            "llm_score": llm_score,
            "llm_reasoning": parsed.get("llm_reasoning", "No reasoning provided.")
        }

    except Exception as error:
        return {
            "llm_score": 0.5,
            "llm_reasoning": f"Groq classification failed, so a neutral score was used. Error: {str(error)}"
        }


def attribution_from_llm_score(llm_score):
    """
    Temporary Milestone 3 attribution using only Signal 1.

    Real combined scoring will be added in Milestone 4.
    """
    if llm_score >= 0.75:
        return "likely_ai"
    if llm_score <= 0.39:
        return "likely_human"
    return "uncertain"


def placeholder_label(attribution):
    """
    Temporary Milestone 3 label.

    Full final label logic will be added in Milestone 5.
    """
    if attribution == "likely_ai":
        return "Placeholder label: this content shows strong AI-like signals based on the first detection signal."
    if attribution == "likely_human":
        return "Placeholder label: this content shows strong human-like signals based on the first detection signal."
    return "Placeholder label: the system is uncertain based on the first detection signal."


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Provenance Guard API is running.",
        "available_routes": [
            "POST /submit",
            "GET /log"
        ]
    })


@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    creator_id = data.get("creator_id")
    text = data.get("text")

    if not creator_id or not text:
        return jsonify({"error": "creator_id and text are required"}), 400

    content_id = str(uuid.uuid4())

    llm_result = classify_with_groq(text)
    llm_score = llm_result["llm_score"]

    attribution = attribution_from_llm_score(llm_score)

    # For Milestone 3, confidence is based only on the first signal.
    # In Milestone 4, this will become combined confidence from both signals.
    confidence = llm_score

    label = placeholder_label(attribution)

    response_body = {
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": confidence,
        "label": label,
        "status": "classified",
        "signals": {
            "llm_score": llm_score,
            "llm_reasoning": llm_result["llm_reasoning"]
        }
    }

    audit_entry = {
        "event_type": "classification",
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": get_timestamp(),
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "llm_reasoning": llm_result["llm_reasoning"],
        "stylometric_score": None,
        "label": label,
        "status": "classified"
    }

    save_audit_entry(audit_entry)

    return jsonify(response_body), 200


@app.route("/log", methods=["GET"])
def get_log():
    entries = load_audit_log()

    return jsonify({
        "entries": entries[-10:]
    })


if __name__ == "__main__":
    app.run(debug=True)