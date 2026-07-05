# Provenance Guard

Provenance Guard is a backend API system for creative sharing platforms. It analyzes submitted text and returns an attribution assessment showing whether the content appears likely AI-generated, likely human-written, or uncertain.

The goal is not to prove authorship perfectly. Instead, the system combines multiple detection signals, communicates uncertainty clearly, provides reader-facing transparency labels, logs every decision, and gives creators a way to appeal classifications they believe are wrong.

## Project Goals

Provenance Guard was built to support platforms where people share original creative work such as poems, short stories, blog posts, and essays. These platforms need a way to provide attribution context without unfairly accusing creators.

The system supports:

* Text submission for attribution analysis
* Multi-signal AI content detection
* Confidence scoring with uncertainty
* Transparency labels for readers
* Appeals workflow for creators
* Rate limiting to reduce abuse
* Structured audit logging

## Architecture Overview

When a creator submits a piece of text, the request enters the `POST /submit` endpoint with a `creator_id` and `text`.

The API validates the request, generates a unique `content_id`, and sends the text through the detection pipeline. The pipeline uses two signals: a Groq LLM-based classifier and a stylometric heuristic analyzer. Each signal returns a score from `0.0` to `1.0`, where higher means the text appears more likely to be AI-generated.

The confidence scoring component combines both signal scores into one final confidence score. The attribution component maps that score to `likely_ai`, `likely_human`, or `uncertain`. The transparency label generator then creates plain-language label text for readers.

Before returning the response, the system writes a structured audit log entry with the content ID, creator ID, timestamp, signal scores, confidence score, attribution result, label, and status.

If a creator disagrees with a classification, they can submit an appeal through `POST /appeal`. The system updates the content status to `under_review` and logs the appeal alongside the original decision.

## Architecture Diagram

### Submission Flow

```text
Creator / Platform
        |
        | raw text + creator_id
        v
POST /submit endpoint
        |
        | validated text + creator_id
        v
Request Validation
        |
        | valid submission
        v
Content ID Generator
        |
        | content_id + raw text
        v
Detection Pipeline
        |
        |-----------------------------|
        |                             |
        v                             v
Signal 1: Groq LLM Classifier     Signal 2: Stylometric Heuristics
        |                             |
        | llm_score                   | stylometric_score
        |                             |
        |------------- scores --------|
                      |
                      v
Confidence Scoring Component
                      |
                      | combined confidence score
                      v
Attribution Decision Component
                      |
                      | likely_ai / likely_human / uncertain
                      v
Transparency Label Generator
                      |
                      | plain-language label text
                      v
Structured Audit Log
                      |
                      | saved decision record
                      v
JSON Response to User
```

### Appeal Flow

```text
Creator
   |
   | content_id + creator_reasoning
   v
POST /appeal endpoint
   |
   | appeal request
   v
Request Validation
   |
   | validated content_id + reasoning
   v
Original Decision Lookup
   |
   | original classification record
   v
Status Update Component
   |
   | status = under_review
   v
Structured Audit Log
   |
   | original decision + appeal reasoning
   v
JSON Confirmation Response
```

## API Endpoints

### `GET /`

Returns a basic health response showing that the API is running.

### `POST /submit`

Submits a piece of text for attribution analysis.

Example request:

```json
{
  "creator_id": "test-user-1",
  "text": "The submitted poem, story, blog post, or creative writing excerpt goes here."
}
```

Example response:

```json
{
  "attribution": "uncertain",
  "confidence": 0.48,
  "content_id": "5d037cce-fe04-431c-808f-c34a4d9978cd",
  "creator_id": "test-user-appeal",
  "label": "Provenance Guard could not confidently determine whether this content was AI-generated or human-written. The result is uncertain, and readers should avoid making assumptions based on this label alone.",
  "signals": {
    "llm_score": 0.5,
    "llm_reasoning": "The text is well-structured and discusses a complex topic, but the language and tone are formal and could be indicative of either human or AI writing. The lack of personal touch or emotional tone makes it difficult to determine the origin with certainty.",
    "stylometric_score": 0.45,
    "stylometric_metrics": {
      "sentence_length_variance": 0.0,
      "type_token_ratio": 0.0,
      "punctuation_density": 0.0,
      "word_count": 0,
      "sentence_count": 0
    }
  },
  "status": "classified"
}
```

### `POST /appeal`

Submits an appeal for a classification decision.

Example request:

```json
{
  "content_id": "5d037cce-fe04-431c-808f-c34a4d9978cd",
  "creator_reasoning": "I wrote this myself from personal experience. My writing may look formal because I revised it carefully."
}
```

Example response:

```json
{
  "content_id": "5d037cce-fe04-431c-808f-c34a4d9978cd",
  "message": "Appeal received and content status updated to under review.",
  "status": "under_review"
}
```

### `GET /log`

Returns recent structured audit log entries.

In a real production system, this endpoint would require authentication. For this project, it is visible to make the audit log easy to inspect and document.

## Detection Signals

Provenance Guard uses two distinct detection signals.

### Signal 1: Groq LLM-Based Classification

The first signal uses Groq with the `llama-3.3-70b-versatile` model.

This signal evaluates the submitted writing holistically. It looks at tone, structure, polish, repetition, generic phrasing, coherence, and whether the text appears more human-written or AI-generated.

The LLM signal returns:

```json
{
  "llm_score": 0.82,
  "llm_reasoning": "The text uses polished, generic phrasing and highly uniform structure."
}
```

A higher `llm_score` means the text appears more likely to be AI-generated.

Why I chose this signal: an LLM can evaluate broad semantic and stylistic patterns that simple statistics cannot capture.

What it misses: the LLM may misclassify formal human writing, academic writing, professional writing, or writing from non-native English speakers as AI-generated because those styles can appear polished or structured.

### Signal 2: Stylometric Heuristics

The second signal uses pure Python heuristics to measure structural writing features.

The stylometric signal calculates:

* Sentence length variance
* Type-token ratio, meaning vocabulary diversity
* Punctuation density
* Word count
* Sentence count

The stylometric signal returns:

```json
{
  "stylometric_score": 0.45,
  "metrics": {
    "sentence_length_variance": 12.4,
    "type_token_ratio": 0.72,
    "punctuation_density": 0.04,
    "word_count": 51,
    "sentence_count": 3
  }
}
```

A higher `stylometric_score` means the text structure appears more AI-like.

Why I chose this signal: AI-generated text often has smoother and more uniform sentence patterns, while human writing may have more variation, irregular rhythm, informal punctuation, and less predictable structure.

What it misses: stylometric heuristics can be unreliable for short texts, poems, repetitive writing, heavily edited human writing, or simple creative writing.

## Confidence Scoring

Both detection signals return scores from `0.0` to `1.0`.

The final confidence score is calculated using the weighted formula from `planning.md`:

```text
combined_score = (0.6 * llm_score) + (0.4 * stylometric_score)
```

The LLM signal receives slightly more weight because it evaluates the broader meaning, tone, and coherence of the text. The stylometric signal still receives significant weight because it provides an independent structural measurement.

The combined score maps to three attribution categories:

| Combined Score Range | Attribution Result | Meaning                   |
| -------------------- | ------------------ | ------------------------- |
| `0.75 - 1.00`        | `likely_ai`        | Strong AI-like signals    |
| `0.40 - 0.74`        | `uncertain`        | Mixed or weak evidence    |
| `0.00 - 0.39`        | `likely_human`     | Strong human-like signals |

The uncertain range is intentionally wide because false positives are harmful on creative platforms. If a human writer is wrongly labeled as AI-generated, it can damage trust in their work. The system avoids making strong AI-generated claims unless the combined confidence is at least `0.75`.

## Confidence Score Examples

### Example 1: Lower-confidence uncertain case

Input:

```text
The relationship between creativity and technology has changed rapidly in recent years. Writers now face new questions about originality, assistance, and trust. A fair system should give readers context without unfairly accusing creators.
```

Output:

```json
{
  "attribution": "uncertain",
  "confidence": 0.48,
  "llm_score": 0.5,
  "stylometric_score": 0.45
}
```

This result is uncertain because both signals are near the middle. The system does not have enough evidence to make a strong claim.

### Example 2: Human-like case

Input:

```text
The sun dipped below the horizon, painting the sky in hues of amber and rose. I sat on the porch, coffee in hand, watching the neighborhood slowly go quiet.
```

Output:

```json
{
  "attribution": "likely_human",
  "confidence": 0.0,
  "llm_score": 0.0,
  "stylometric_score": 0.0
}
```

This result was classified as likely human-written because the LLM signal identified a personal and descriptive style with less formulaic structure.

## Transparency Labels

The system returns one of three reader-facing transparency labels.

| Attribution Result | Exact Label Text                                                                                                                                                                                                  |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `likely_ai`        | `"Provenance Guard found strong signals that this content may have been AI-generated. This label is based on automated analysis and may not be perfect."`                                                         |
| `likely_human`     | `"Provenance Guard found strong signals that this content appears to be human-written. This label is based on automated analysis and should be understood as a confidence-based assessment, not absolute proof."` |
| `uncertain`        | `"Provenance Guard could not confidently determine whether this content was AI-generated or human-written. The result is uncertain, and readers should avoid making assumptions based on this label alone."`      |

These labels are designed to avoid absolute claims. The system communicates that the result is based on automated analysis and may not be perfect.

## Appeals Workflow

Creators can appeal a classification by calling `POST /appeal` with a `content_id` and `creator_reasoning`.

When an appeal is received, the system:

1. Validates that `content_id` and `creator_reasoning` are present.
2. Looks up the original classification decision.
3. Updates the content status to `under_review`.
4. Saves the creator’s reasoning.
5. Adds an appeal entry to the audit log.
6. Returns a confirmation response.

Appeal test result:

```json
{
  "content_id": "5d037cce-fe04-431c-808f-c34a4d9978cd",
  "message": "Appeal received and content status updated to under review.",
  "status": "under_review"
}
```

Duplicate appeals are blocked. When the same `content_id` was appealed again, the API returned:

```json
{
  "error": "an appeal has already been filed for this content_id"
}
```

Invalid appeal input is also handled.

Missing `creator_reasoning` returns:

```json
{
  "error": "content_id and creator_reasoning are required"
}
```

Invalid `content_id` returns:

```json
{
  "error": "content_id not found"
}
```

## Rate Limiting

The `POST /submit` endpoint uses Flask-Limiter.

Chosen limits:

```text
10 submissions per minute
100 submissions per day
```

I chose these limits because a normal creator is unlikely to submit more than 10 pieces of writing in one minute. The daily limit of 100 allows active testing and reasonable use while helping prevent automated abuse.

Rate limit test:

```text
1 -> 200
2 -> 200
3 -> 200
4 -> 200
5 -> 200
6 -> 200
7 -> 200
8 -> 200
9 -> 200
10 -> 200
11 -> 429
12 -> 429
```

This confirms that rapid submissions are blocked after the allowed request limit.

## Audit Log

Every classification decision and appeal is saved in a structured JSON audit log.

Each classification entry includes:

* `event_type`
* `content_id`
* `creator_id`
* `timestamp`
* `attribution`
* `confidence`
* `llm_score`
* `llm_reasoning`
* `stylometric_score`
* `stylometric_metrics`
* `label`
* `status`

Each appeal entry includes:

* `event_type`
* `content_id`
* `creator_id`
* `timestamp`
* `appeal_reasoning`
* `original_attribution`
* `original_confidence`
* `original_llm_score`
* `original_stylometric_score`
* `previous_status`
* `new_status`
* `status`

Example audit log entries:

```json
[
  {
    "event_type": "classification",
    "content_id": "0043968a-e205-4c11-a528-bdba326937a1",
    "creator_id": "test-user-1",
    "timestamp": "2026-07-05T05:49:59.523874+00:00",
    "attribution": "likely_human",
    "confidence": 0.0,
    "llm_score": 0.0,
    "llm_reasoning": "The text features a poetic and descriptive style, but its simplicity, personal touch, and lack of overly complex vocabulary or sentence structures suggest it is likely human-written.",
    "stylometric_score": null,
    "label": "Placeholder label: this content shows strong human-like signals based on the first detection signal.",
    "status": "classified"
  },
  {
    "event_type": "classification",
    "content_id": "5d037cce-fe04-431c-808f-c34a4d9978cd",
    "creator_id": "test-user-appeal",
    "timestamp": "2026-07-05T06:15:00.000000+00:00",
    "attribution": "uncertain",
    "confidence": 0.48,
    "llm_score": 0.5,
    "stylometric_score": 0.45,
    "label": "Provenance Guard could not confidently determine whether this content was AI-generated or human-written. The result is uncertain, and readers should avoid making assumptions based on this label alone.",
    "status": "under_review"
  },
  {
    "event_type": "appeal",
    "content_id": "5d037cce-fe04-431c-808f-c34a4d9978cd",
    "creator_id": "test-user-appeal",
    "timestamp": "2026-07-05T06:18:00.000000+00:00",
    "appeal_reasoning": "I wrote this myself from personal experience. My writing may look formal because I revised it carefully.",
    "original_attribution": "uncertain",
    "original_confidence": 0.48,
    "original_llm_score": 0.5,
    "original_stylometric_score": 0.45,
    "previous_status": "classified",
    "new_status": "under_review",
    "status": "under_review"
  }
]
```

## Known Limitations

Provenance Guard cannot prove true authorship. It only provides a confidence-based assessment using two signals.

One specific limitation is short creative writing. A short poem or quote may not contain enough sentences or words for reliable stylometric analysis. Sentence length variance and vocabulary diversity can become misleading when the text is very short.

Another limitation is formal human writing. Academic essays, professional writing, and writing by non-native English speakers may appear polished or structured, which can cause the LLM signal or stylometric signal to score the text as more AI-like than it really is.

A third limitation is lightly edited AI-generated text. If someone edits AI output to add personal tone or irregular structure, the system may return an uncertain or human-like score.

Because of these limitations, the system uses an uncertain category and includes an appeals workflow.

## Spec Reflection

The planning spec helped guide implementation by defining the signal outputs and confidence thresholds before code was written. Because the spec said both signals should return scores from `0.0` to `1.0`, the implementation could cleanly combine them using the weighted formula.

One way the implementation diverged from the original spec is that the audit log uses a simple JSON file instead of SQLite. This was intentional because JSON is easier to inspect, easier to show in the README, and sufficient for the project requirements. In a production system, I would use a database with authentication, indexing, and better data integrity.

## AI Usage

AI assistance was used during the project, but the generated code and structure were reviewed and revised to match the project spec.

### AI Usage Example 1: Flask App Skeleton and First Signal

I used AI assistance to help generate the initial Flask app structure, including the `POST /submit` route, request validation, Groq classification function, and simple audit log helpers.

I revised the output to match my planning document by making sure the Groq function returned a score from `0.0` to `1.0`, adding `content_id` to the response, and ensuring each submission wrote a structured audit log entry.

### AI Usage Example 2: Stylometric Signal and Confidence Scoring

I used AI assistance to help design the stylometric heuristic function and confidence scoring logic.

I revised the output to match the planned formula:

```text
combined_score = (0.6 * llm_score) + (0.4 * stylometric_score)
```

I also made sure the response and audit log included both individual signal scores and the combined confidence score.

### AI Usage Example 3: Production Layer

I used AI assistance to help add the production features: final transparency labels, `POST /appeal`, status updates, duplicate appeal handling, and Flask-Limiter rate limiting.

I revised the implementation to ensure the label text exactly matched the planning document and that appeals were logged alongside the original classification decision.

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/hedreez09/ai201-project4-ProvenanceGuard.git
cd ai201-project4-ProvenanceGuard
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Mac/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create `.env`

Create a `.env` file in the project root:

```text
GROQ_API_KEY=your_groq_api_key_here
```

The `.env` file should not be committed.

### 5. Run the app

```bash
python app.py
```

The app will run at:

```text
http://localhost:5000
```

## Testing Commands

### Test `/submit`

PowerShell:

```powershell
$body = @{
  creator_id = "test-user-1"
  text = "The relationship between creativity and technology has changed rapidly in recent years. Writers now face new questions about originality, assistance, and trust. A fair system should give readers context without unfairly accusing creators."
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:5000/submit" -Method POST -Body $body -ContentType "application/json"
```

### Test `/appeal`

PowerShell:

```powershell
$appealBody = @{
  content_id = "PASTE-CONTENT-ID-HERE"
  creator_reasoning = "I wrote this myself from personal experience. My writing may look formal because I revised it carefully."
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:5000/appeal" -Method POST -Body $appealBody -ContentType "application/json"
```

### Test `/log`

PowerShell:

```powershell
Invoke-RestMethod -Uri "http://localhost:5000/log" -Method GET
```

### Test rate limiting

PowerShell:

```powershell
for ($i = 1; $i -le 12; $i++) {
  $body = @{
    creator_id = "ratelimit-test"
    text = "This is a test submission for rate limit testing purposes only."
  } | ConvertTo-Json

  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:5000/submit" -Method POST -Body $body -ContentType "application/json"
    Write-Output "$i -> $($response.StatusCode)"
  }
  catch {
    Write-Output "$i -> $($_.Exception.Response.StatusCode.value__)"
  }
}
```


## Audit Log Evidence

The system stores structured audit log entries for both classification decisions and appeals. Below are three sample entries from `GET /log`.

```json
[
  {
    "attribution": "likely_human",
    "confidence": 0.1,
    "content_id": "14996a40-5205-4f38-99e1-8b01c40cd7d9",
    "creator_id": "test-human",
    "event_type": "classification",
    "label": "Placeholder label: this content shows strong human-like signals based on the combined detection pipeline.",
    "llm_reasoning": "The text features informal language, colloquial expressions, and personal opinions, which are characteristic of human-written content. The use of slang, such as 'ok so' and 'honestly?', and the casual tone also suggest a human author.",
    "llm_score": 0.0,
    "status": "classified",
    "stylometric_metrics": {
      "punctuation_density": 0.091,
      "sentence_count": 5,
      "sentence_length_variance": 45.2,
      "type_token_ratio": 0.873,
      "word_count": 55
    },
    "stylometric_score": 0.25,
    "timestamp": "2026-07-05T16:47:14.619560+00:00"
  },
  {
    "attribution": "uncertain",
    "confidence": 0.48,
    "content_id": "5d037cce-fe04-431c-808f-c34a4d9978cd",
    "creator_id": "test-user-appeal",
    "event_type": "classification",
    "label": "Provenance Guard could not confidently determine whether this content was AI-generated or human-written. The result is uncertain, and readers should avoid making assumptions based on this label alone.",
    "llm_reasoning": "The text is well-structured and discusses a complex topic, but the language and tone are formal and could be indicative of either human or AI writing. The lack of personal touch or emotional tone makes it difficult to determine the origin with certainty.",
    "llm_score": 0.5,
    "status": "under_review",
    "stylometric_metrics": {
      "punctuation_density": 0.152,
      "sentence_count": 3,
      "sentence_length_variance": 0.667,
      "type_token_ratio": 0.97,
      "word_count": 33
    },
    "stylometric_score": 0.45,
    "timestamp": "2026-07-05T20:33:09.744891+00:00"
  },
  {
    "appeal_reasoning": "I wrote this myself from personal experience. My writing may look formal because I revised it carefully.",
    "content_id": "5d037cce-fe04-431c-808f-c34a4d9978cd",
    "creator_id": "test-user-appeal",
    "event_type": "appeal",
    "new_status": "under_review",
    "original_attribution": "uncertain",
    "original_confidence": 0.48,
    "original_llm_score": 0.5,
    "original_stylometric_score": 0.45,
    "previous_status": "classified",
    "status": "under_review",
    "timestamp": "2026-07-05T20:35:02.228528+00:00"
  }
]
```



## Walkthrough Video

The walkthrough video demonstrates the project working end-to-end. It covers:

1. The project folder and key files: `app.py`, `planning.md`, and `README.md`.
2. The Flask app running locally.
3. A successful `POST /submit` request.
4. The returned attribution result, confidence score, transparency label, and signal scores.
5. A successful `POST /appeal` request.
6. The audit log showing classification and appeal entries.
7. The rate limit test returning `429`.

The video also explains why the system uses two detection signals, why uncertainty matters, and how the appeal workflow protects creators from false positives.

## Final Submission Checklist

* GitHub repository link
* `planning.md` in the repo root
* `README.md` with architecture, detection signals, confidence scoring, transparency labels, rate limiting, limitations, spec reflection, and AI usage
* Working Flask backend
* `POST /submit`
* `POST /appeal`
* `GET /log`
* Structured audit log evidence
* Rate limit evidence
* Short walkthrough video

