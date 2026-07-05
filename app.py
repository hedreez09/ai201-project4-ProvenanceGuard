import json
import os
import re
import string
import uuid
from datetime import datetime, timezone
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from groq import Groq


load_dotenv()

app = Flask(__name__)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

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


def clamp_score(value):
    """Keep a score between 0.0 and 1.0."""
    return max(0.0, min(1.0, float(value)))


def classify_with_groq(text):
    """
    Signal 1: Groq LLM classifier.

    Returns:
        {
            "llm_score": float between 0.0 and 1.0,
            "llm_reasoning": str
        }
    """

    if not GROQ_API_KEY:
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

        return {
            "llm_score": clamp_score(parsed.get("llm_score", 0.5)),
            "llm_reasoning": parsed.get("llm_reasoning", "No reasoning provided.")
        }

    except Exception as error:
        return {
            "llm_score": 0.5,
            "llm_reasoning": f"Groq classification failed, so a neutral score was used. Error: {str(error)}"
        }


def split_sentences(text):
    """Split text into basic sentences."""
    sentences = re.split(r"[.!?]+", text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def tokenize_words(text):
    """Extract lowercase word tokens."""
    return re.findall(r"\b[a-zA-Z']+\b", text.lower())


def calculate_sentence_length_variance(sentences):
    """Calculate sentence length variance based on word counts."""
    if len(sentences) < 2:
        return 0.0

    lengths = [len(tokenize_words(sentence)) for sentence in sentences]
    mean_length = sum(lengths) / len(lengths)
    variance = sum((length - mean_length) ** 2 for length in lengths) / len(lengths)

    return round(variance, 3)


def calculate_type_token_ratio(words):
    """Calculate vocabulary diversity."""
    if not words:
        return 0.0

    unique_words = set(words)
    return round(len(unique_words) / len(words), 3)


def calculate_punctuation_density(text, words):
    """Calculate punctuation count divided by word count."""
    if not words:
        return 0.0

    punctuation_count = sum(1 for char in text if char in string.punctuation)
    return round(punctuation_count / len(words), 3)


def stylometric_signal(text):
    """
    Signal 2: Stylometric heuristics.

    Returns:
        {
            "stylometric_score": float between 0.0 and 1.0,
            "metrics": {
                "sentence_length_variance": float,
                "type_token_ratio": float,
                "punctuation_density": float,
                "word_count": int,
                "sentence_count": int
            }
        }

    Higher score means the structure appears more AI-like.
    """

    sentences = split_sentences(text)
    words = tokenize_words(text)

    sentence_length_variance = calculate_sentence_length_variance(sentences)
    type_token_ratio = calculate_type_token_ratio(words)
    punctuation_density = calculate_punctuation_density(text, words)

    word_count = len(words)
    sentence_count = len(sentences)

    # Short text is hard to judge, so keep it near uncertain.
    if word_count < 30 or sentence_count < 2:
        stylometric_score = 0.5
    else:
        # Lower sentence variance can look more AI-like.
        if sentence_length_variance < 8:
            variance_score = 0.75
        elif sentence_length_variance < 25:
            variance_score = 0.5
        else:
            variance_score = 0.25

        # Very low vocabulary diversity can look more repetitive/AI-like.
        if type_token_ratio < 0.45:
            vocabulary_score = 0.75
        elif type_token_ratio < 0.70:
            vocabulary_score = 0.5
        else:
            vocabulary_score = 0.25

        # Very low punctuation density can look smoother/more uniform.
        if punctuation_density < 0.03:
            punctuation_score = 0.65
        elif punctuation_density < 0.08:
            punctuation_score = 0.45
        else:
            punctuation_score = 0.25

        stylometric_score = (
            0.4 * variance_score
            + 0.4 * vocabulary_score
            + 0.2 * punctuation_score
        )

    return {
        "stylometric_score": round(clamp_score(stylometric_score), 3),
        "metrics": {
            "sentence_length_variance": sentence_length_variance,
            "type_token_ratio": type_token_ratio,
            "punctuation_density": punctuation_density,
            "word_count": word_count,
            "sentence_count": sentence_count
        }
    }


def combine_scores(llm_score, stylometric_score):
    """
    Combine both signals using the planning.md weighting.

    combined_score = (0.6 * llm_score) + (0.4 * stylometric_score)
    """
    combined_score = (0.6 * llm_score) + (0.4 * stylometric_score)
    return round(clamp_score(combined_score), 3)


def attribution_from_confidence(confidence):
    """Map combined confidence score to attribution category."""
    if confidence >= 0.75:
        return "likely_ai"
    if confidence <= 0.39:
        return "likely_human"
    return "uncertain"


def generate_transparency_label(attribution):
    """Return the final reader-facing transparency label."""
    labels = {
        "likely_ai": (
            "Provenance Guard found strong signals that this content may have been "
            "AI-generated. This label is based on automated analysis and may not be perfect."
        ),
        "likely_human": (
            "Provenance Guard found strong signals that this content appears to be "
            "human-written. This label is based on automated analysis and should be "
            "understood as a confidence-based assessment, not absolute proof."
        ),
        "uncertain": (
            "Provenance Guard could not confidently determine whether this content was "
            "AI-generated or human-written. The result is uncertain, and readers should "
            "avoid making assumptions based on this label alone."
        ),
    }

    return labels.get(attribution, labels["uncertain"])

def find_latest_classification(content_id):
    """Find the latest classification log entry for a content ID."""
    entries = load_audit_log()

    for entry in reversed(entries):
        if (
            entry.get("content_id") == content_id
            and entry.get("event_type") == "classification"
        ):
            return entry

    return None


def has_existing_appeal(content_id):
    """Check whether an appeal has already been filed for a content ID."""
    entries = load_audit_log()

    return any(
        entry.get("content_id") == content_id
        and entry.get("event_type") == "appeal"
        for entry in entries
    )


def update_classification_status(content_id, new_status):
    """
    Update the latest matching classification entry status in audit_log.json.

    This keeps the log simple for the project while allowing /log to show
    that the original content is now under review.
    """
    entries = load_audit_log()
    updated = False

    for entry in reversed(entries):
        if (
            entry.get("content_id") == content_id
            and entry.get("event_type") == "classification"
        ):
            entry["status"] = new_status
            updated = True
            break

    if updated:
        with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as file:
            json.dump(entries, file, indent=2)

    return updated


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Provenance Guard API is running.",
        "available_routes": [
            "POST /submit",
            "POST /appeal",
            "GET /log"
        ]
    })

@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
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

    stylometric_result = stylometric_signal(text)
    stylometric_score = stylometric_result["stylometric_score"]

    confidence = combine_scores(llm_score, stylometric_score)
    attribution = attribution_from_confidence(confidence)
    label = generate_transparency_label(attribution)

    response_body = {
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": confidence,
        "label": label,
        "status": "classified",
        "signals": {
            "llm_score": llm_score,
            "llm_reasoning": llm_result["llm_reasoning"],
            "stylometric_score": stylometric_score,
            "stylometric_metrics": stylometric_result["metrics"]
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
        "stylometric_score": stylometric_score,
        "stylometric_metrics": stylometric_result["metrics"],
        "label": label,
        "status": "classified"
    }

    save_audit_entry(audit_entry)

    return jsonify(response_body), 200


@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    content_id = data.get("content_id")
    creator_reasoning = data.get("creator_reasoning")

    if not content_id or not creator_reasoning:
        return jsonify({"error": "content_id and creator_reasoning are required"}), 400

    original_decision = find_latest_classification(content_id)

    if not original_decision:
        return jsonify({"error": "content_id not found"}), 404

    if has_existing_appeal(content_id):
        return jsonify({"error": "an appeal has already been filed for this content_id"}), 409

    previous_status = original_decision.get("status", "classified")
    new_status = "under_review"

    update_classification_status(content_id, new_status)

    appeal_entry = {
        "event_type": "appeal",
        "content_id": content_id,
        "creator_id": original_decision.get("creator_id"),
        "timestamp": get_timestamp(),
        "appeal_reasoning": creator_reasoning,
        "original_attribution": original_decision.get("attribution"),
        "original_confidence": original_decision.get("confidence"),
        "original_llm_score": original_decision.get("llm_score"),
        "original_stylometric_score": original_decision.get("stylometric_score"),
        "previous_status": previous_status,
        "new_status": new_status,
        "status": new_status,
    }

    save_audit_entry(appeal_entry)

    return jsonify({
        "content_id": content_id,
        "status": new_status,
        "message": "Appeal received and content status updated to under review."
    }), 200

@app.route("/log", methods=["GET"])
def get_log():
    entries = load_audit_log()

    return jsonify({
        "entries": entries[-10:]
    })


if __name__ == "__main__":
    app.run(debug=True)