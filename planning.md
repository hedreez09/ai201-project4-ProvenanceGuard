# Provenance Guard Planning

## Project Overview

Provenance Guard is a backend system that helps creative platforms analyze submitted text and provide attribution context. The system does not try to prove authorship perfectly. Instead, it uses multiple detection signals, returns a confidence score, displays a transparency label, logs every decision, and gives creators a way to appeal if they believe their work was misclassified.

The system will analyze text-based content such as poems, short stories, blog posts, and creative writing excerpts.

## Architecture Narrative

When a creator submits a piece of text to Provenance Guard, the request enters the `POST /submit` endpoint with two required fields: `creator_id` and `text`.

The API first validates the request to make sure both fields are present. If the request is missing required information, the system returns an error response.

If the request is valid, the system creates a unique `content_id` for the submission. The submitted text is then passed into the detection pipeline.

The detection pipeline uses two separate signals. The first signal is an LLM-based classifier using Groq. This signal reviews the text holistically and estimates whether the writing appears AI-generated or human-written. The second signal is a stylometric heuristic analyzer. This signal measures structural writing patterns such as sentence length variation, vocabulary diversity, and punctuation density.

Each signal returns a score from `0.0` to `1.0`, where a higher score means the text appears more likely to be AI-generated. The confidence scoring component combines both signal scores into one final confidence score.

The attribution decision component then maps the combined score into one of three categories: `likely_ai`, `likely_human`, or `uncertain`.

After the attribution decision is made, the transparency label generator creates a plain-language label that explains the result to readers. The label is designed to communicate uncertainty clearly and avoid making absolute claims.

Before returning the response, the system writes a structured audit log entry. The log stores the content ID, creator ID, timestamp, signal scores, combined confidence score, attribution result, label text, and status.

Finally, the API returns a JSON response containing the content ID, attribution result, confidence score, transparency label, signal scores, and status.

## Detection Signals

Provenance Guard will use two distinct detection signals. These signals are different because one uses semantic judgment from an LLM, while the other uses measurable writing statistics.

### Signal 1: Groq LLM-Based Classification

The first signal uses Groq with the `llama-3.3-70b-versatile` model.

This signal measures the overall style, tone, structure, and coherence of the submitted text. It looks for patterns such as overly polished language, generic phrasing, repetitive transitions, very smooth structure, and writing that feels formulaic.

This property may differ between human and AI writing because AI-generated text often has a polished, balanced, and predictable structure. Human writing is often more uneven, personal, specific, or irregular.

The signal will return a score from `0.0` to `1.0`.

* `0.0` means strongly human-written.
* `0.5` means uncertain.
* `1.0` means strongly AI-generated.

Example output:

```json
{
  "llm_score": 0.82,
  "llm_reasoning": "The text uses polished, generic phrasing and highly uniform structure."
}
```

Blind spot: this signal may misclassify formal human writing, academic writing, professional writing, or writing from non-native English speakers as AI-generated because those styles can appear polished or structured.

### Signal 2: Stylometric Heuristics

The second signal uses pure Python stylometric heuristics.

This signal measures statistical properties of the text, including:

* Sentence length variance
* Type-token ratio, meaning vocabulary diversity
* Punctuation density

This property may differ between human and AI writing because AI-generated text often has more uniform sentence structure, smoother phrasing, and predictable vocabulary patterns. Human writing may have more variation in sentence length, more informal punctuation, and less predictable rhythm.

The signal will return a score from `0.0` to `1.0`, where a higher score means the text appears more AI-generated.

Example output:

```json
{
  "stylometric_score": 0.64,
  "metrics": {
    "sentence_length_variance": 4.2,
    "type_token_ratio": 0.48,
    "punctuation_density": 0.06
  }
}
```

Blind spot: this signal may perform poorly on short texts, poems, repetitive creative writing, heavily edited human writing, or simple writing. A short poem may not have enough sentences for reliable sentence length variance, and a formal essay may look statistically similar to AI-generated text.

## False Positive Scenario

A false positive happens when the system labels human-written work as likely AI-generated. This is especially harmful on a creative platform because it can damage the creator’s reputation and make readers doubt their originality.

Example scenario: a creator submits a formal short essay that they wrote themselves. Because the writing is polished and structured, the Groq LLM signal gives it a moderately high AI score. The stylometric signal also gives it a moderately high score because the sentence structure is consistent.

Instead of immediately making a strong accusation, the system uses a wide uncertain range. If the combined confidence score is not high enough, the result becomes `uncertain` rather than `likely_ai`.

The transparency label should avoid saying the creator definitely used AI. It should explain that the system could not confidently determine whether the work was AI-generated or human-written.

If the creator disagrees with the classification, they can submit an appeal using the `POST /appeal` endpoint. The appeal includes the `content_id` and the creator’s reasoning. The system updates the content status to `under_review` and writes the appeal into the audit log alongside the original classification decision.

This design protects creators by avoiding overconfident labels and giving them a path to contest the result.

## API Surface

### POST /submit

The `POST /submit` endpoint accepts submitted text and returns an attribution analysis.

Request body:

```json
{
  "creator_id": "test-user-1",
  "text": "The submitted poem, story, blog post, or creative writing excerpt goes here."
}
```

Response body:

```json
{
  "content_id": "uuid-value-here",
  "creator_id": "test-user-1",
  "attribution": "likely_ai",
  "confidence": 0.82,
  "label": "Provenance Guard found strong signals that this content may have been AI-generated. This label is based on automated analysis and may not be perfect.",
  "status": "classified",
  "signals": {
    "llm_score": 0.85,
    "stylometric_score": 0.78
  }
}
```

System components touched:

1. `POST /submit` endpoint receives the request.
2. Request validation checks for `creator_id` and `text`.
3. Content ID generator creates a unique ID.
4. Groq LLM classifier produces the first signal score.
5. Stylometric heuristic analyzer produces the second signal score.
6. Confidence scoring combines the scores.
7. Attribution decision maps the score to a category.
8. Transparency label generator creates reader-facing label text.
9. Audit log records the decision.
10. JSON response is returned to the user.

### POST /appeal

The `POST /appeal` endpoint allows a creator to contest a classification.

Request body:

```json
{
  "content_id": "uuid-value-here",
  "creator_reasoning": "I wrote this myself from personal experience. My writing may look formal because English is not my first language."
}
```

Response body:

```json
{
  "content_id": "uuid-value-here",
  "status": "under_review",
  "message": "Appeal received and content status updated to under review."
}
```

System components touched:

1. `POST /appeal` endpoint receives the appeal.
2. Request validation checks for `content_id` and `creator_reasoning`.
3. The system finds the original decision by content ID.
4. The content status is updated to `under_review`.
5. The creator’s appeal reasoning is saved.
6. Audit log records the appeal.
7. JSON confirmation response is returned.

### GET /log

The `GET /log` endpoint returns recent structured audit log entries.

Response body:

```json
{
  "entries": [
    {
      "content_id": "uuid-value-here",
      "creator_id": "test-user-1",
      "timestamp": "2026-07-04T14:32:10Z",
      "attribution": "likely_ai",
      "confidence": 0.82,
      "llm_score": 0.85,
      "stylometric_score": 0.78,
      "label": "Provenance Guard found strong signals that this content may have been AI-generated. This label is based on automated analysis and may not be perfect.",
      "status": "classified"
    }
  ]
}
```

This endpoint is mainly for project documentation and grading visibility. In a real production system, this endpoint would require authentication.

## Architecture

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

## Milestone 1 Checkpoint

At the end of Milestone 1, I can describe the full path of a submitted piece of text from submission to final label.

The text enters through `POST /submit`, passes through validation, receives a content ID, goes through two detection signals, gets a combined confidence score, is mapped to an attribution result, receives a transparency label, is saved in the audit log, and returns a JSON response.

I have chosen two detection signals:

1. Groq LLM-based classification
2. Stylometric heuristics

I have defined the API endpoints needed:

1. `POST /submit`
2. `POST /appeal`
3. `GET /log`

I have also created diagrams for both the submission flow and the appeal flow.


## Detection Signals

Provenance Guard will use two distinct detection signals. The system will not rely on one detector because single-signal detection can be misleading. Instead, it will combine one semantic signal and one structural signal.

### Signal 1: Groq LLM-Based Classification

The first detection signal will use Groq with the `llama-3.3-70b-versatile` model.

This signal measures the overall style and meaning of the submitted text. It evaluates whether the writing appears more human-written or AI-generated based on tone, structure, polish, repetition, generic phrasing, and coherence.

This signal is useful because AI-generated text often has a polished, balanced, and predictable style. It may use generic phrases, smooth transitions, and a structure that feels less personal or less irregular than human writing.

The output will be a score from `0.0` to `1.0`.

* `0.0` means strongly human-written.
* `0.5` means uncertain.
* `1.0` means strongly AI-generated.

Expected output format:

```json
{
  "llm_score": 0.82,
  "llm_reasoning": "The text uses polished, generic phrasing and highly uniform structure."
}
```

Blind spot: the LLM signal may misclassify formal human writing, academic writing, professional writing, or writing from non-native English speakers as AI-generated because those styles can appear structured or polished.

### Signal 2: Stylometric Heuristics

The second detection signal will use pure Python stylometric heuristics.

This signal measures statistical and structural properties of the text. It does not ask an AI model to judge the content. Instead, it calculates measurable writing features.

The heuristics will include:

1. Sentence length variance
2. Type-token ratio, meaning vocabulary diversity
3. Punctuation density

This signal is useful because AI-generated writing often has smoother and more uniform sentence patterns. Human writing may have more variation, uneven rhythm, informal punctuation, and less predictable structure.

The output will be a score from `0.0` to `1.0`.

* `0.0` means strongly human-written.
* `0.5` means uncertain.
* `1.0` means strongly AI-generated.

Expected output format:

```json
{
  "stylometric_score": 0.64,
  "metrics": {
    "sentence_length_variance": 4.2,
    "type_token_ratio": 0.48,
    "punctuation_density": 0.06
  }
}
```

Blind spot: stylometric heuristics may perform poorly on short texts, poems, repetitive creative writing, simple writing, or heavily edited human writing. A short poem may not provide enough data for reliable sentence length variance.

## Uncertainty Representation

The system will combine the two signal scores into one final confidence score.

Both detection signals return scores from `0.0` to `1.0`, where higher means more likely AI-generated.

The combined score will use a weighted average:

```text
combined_score = (0.6 * llm_score) + (0.4 * stylometric_score)
```

The LLM signal receives slightly more weight because it can evaluate the broader meaning, style, and coherence of the text. The stylometric signal still receives significant weight because it provides an independent structural measurement.

The combined score will be mapped to three attribution categories:

| Combined Score Range | Attribution Result | Meaning                                                                        |
| -------------------- | ------------------ | ------------------------------------------------------------------------------ |
| `0.75 - 1.00`        | `likely_ai`        | The system has high confidence that the text appears AI-generated.             |
| `0.40 - 0.74`        | `uncertain`        | The system does not have enough confidence to make a strong attribution claim. |
| `0.00 - 0.39`        | `likely_human`     | The system has high confidence that the text appears human-written.            |

A confidence score of `0.60` means the system sees some AI-like patterns, but the evidence is not strong enough to label the text as likely AI-generated. In this range, the system will return `uncertain`.

A confidence score of `0.95` means both signals strongly suggest AI-generated writing. In that case, the system can return `likely_ai`.

A confidence score of `0.20` means both signals strongly suggest human-written writing. In that case, the system can return `likely_human`.

Because false positives can harm creators, the system intentionally uses a wide uncertain range from `0.40` to `0.74`. The system should avoid labeling content as likely AI-generated unless the combined score is at least `0.75`.

## Transparency Label Design

The transparency label will turn the technical result into plain language that a reader can understand. The label must be careful, fair, and confidence-based. It should not claim absolute proof.

### High-Confidence AI Label

Exact label text:

```text
"Provenance Guard found strong signals that this content may have been AI-generated. This label is based on automated analysis and may not be perfect."
```

This label will be used when the attribution result is `likely_ai`.

### High-Confidence Human Label

Exact label text:

```text
"Provenance Guard found strong signals that this content appears to be human-written. This label is based on automated analysis and should be understood as a confidence-based assessment, not absolute proof."
```

This label will be used when the attribution result is `likely_human`.

### Uncertain Label

Exact label text:

```text
"Provenance Guard could not confidently determine whether this content was AI-generated or human-written. The result is uncertain, and readers should avoid making assumptions based on this label alone."
```

This label will be used when the attribution result is `uncertain`.

The uncertain label is especially important because the system should avoid overclaiming when the evidence is mixed.

## Appeals Workflow

Creators can submit an appeal if they believe their content was misclassified.

For this project, an appeal can be submitted by sending the content ID and the creator’s explanation to the `POST /appeal` endpoint.

The appeal request will include:

```json
{
  "content_id": "uuid-value-here",
  "creator_reasoning": "I wrote this myself from personal experience. My writing may look formal because English is not my first language."
}
```

When an appeal is received, the system will:

1. Validate that `content_id` and `creator_reasoning` are present.
2. Look up the original classification decision using the `content_id`.
3. Update the content status from `classified` to `under_review`.
4. Save the creator’s appeal reasoning.
5. Add an appeal record to the audit log.
6. Return a confirmation response.

The appeal response will look like this:

```json
{
  "content_id": "uuid-value-here",
  "status": "under_review",
  "message": "Appeal received and content status updated to under review."
}
```

Automated reclassification is not required. A human reviewer would review the original text, attribution result, confidence score, individual signal scores, transparency label, and creator reasoning.

A human reviewer should be able to see:

* Content ID
* Creator ID
* Original attribution result
* Original confidence score
* LLM score
* Stylometric score
* Original transparency label
* Creator appeal reasoning
* Current status: `under_review`

## Anticipated Edge Cases

### Edge Case 1: Formal Human Writing

A student essay, academic paragraph, or professional article may be human-written but still appear polished and structured. The LLM signal may score it as AI-generated because it resembles common AI writing patterns.

The system handles this by using a wide uncertain range instead of immediately labeling borderline cases as AI-generated.

### Edge Case 2: Short Creative Text

Short poems, quotes, or very brief stories may not provide enough text for reliable stylometric analysis. Sentence length variance and vocabulary diversity may be misleading when the text is too short.

The system should treat very short submissions with caution because the stylometric signal may be weak.

### Edge Case 3: Non-Native English Writing

A non-native English speaker may write in a formal, simplified, or structured style. This can confuse both the LLM signal and the stylometric signal.

The appeal workflow is important in this case because the creator can explain their writing context.

### Edge Case 4: Repetitive Poetry or Song-Like Writing

Creative writing sometimes intentionally uses repetition, simple vocabulary, or unusual punctuation. A poem with repeated phrases may look statistically uniform even though it was written by a person.

The stylometric signal may misread this as AI-like structure.

### Edge Case 5: Lightly Edited AI Text

A creator may lightly edit AI-generated text to make it appear more human. This could reduce the AI score and push the result into the uncertain range.

The system cannot prove true authorship, so it should communicate that the result is a confidence-based assessment.

## API Contract

### POST /submit

Purpose: Submit text for attribution analysis.

Request body:

```json
{
  "creator_id": "test-user-1",
  "text": "The submitted poem, story, blog post, or creative writing excerpt goes here."
}
```

Successful response:

```json
{
  "content_id": "uuid-value-here",
  "creator_id": "test-user-1",
  "attribution": "likely_ai",
  "confidence": 0.82,
  "label": "Provenance Guard found strong signals that this content may have been AI-generated. This label is based on automated analysis and may not be perfect.",
  "status": "classified",
  "signals": {
    "llm_score": 0.85,
    "stylometric_score": 0.78
  }
}
```

Error response if required fields are missing:

```json
{
  "error": "creator_id and text are required"
}
```

### POST /appeal

Purpose: Submit an appeal for a classification decision.

Request body:

```json
{
  "content_id": "uuid-value-here",
  "creator_reasoning": "I wrote this myself from personal experience."
}
```

Successful response:

```json
{
  "content_id": "uuid-value-here",
  "status": "under_review",
  "message": "Appeal received and content status updated to under review."
}
```

Error response if required fields are missing:

```json
{
  "error": "content_id and creator_reasoning are required"
}
```

Error response if content ID is not found:

```json
{
  "error": "content_id not found"
}
```

### GET /log

Purpose: Return recent structured audit log entries for documentation and grading visibility.

Successful response:

```json
{
  "entries": [
    {
      "content_id": "uuid-value-here",
      "creator_id": "test-user-1",
      "timestamp": "2026-07-04T14:32:10Z",
      "attribution": "likely_ai",
      "confidence": 0.82,
      "llm_score": 0.85,
      "stylometric_score": 0.78,
      "label": "Provenance Guard found strong signals that this content may have been AI-generated. This label is based on automated analysis and may not be perfect.",
      "status": "classified"
    }
  ]
}
```

In a real production system, this endpoint would require authentication. For this project, it will remain visible so the audit log can be documented and inspected.

## Rate Limiting Plan

The submission endpoint will use Flask-Limiter.

Chosen limits:

```text
10 submissions per minute
100 submissions per day
```

These limits are reasonable for a creative writing platform because a normal creator is unlikely to submit more than 10 pieces of writing in one minute. The daily limit of 100 allows testing and active use while still limiting abuse.

The limit also helps prevent an attacker from flooding the system with automated submissions.

The planned Flask-Limiter setup is:

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)
```

The `POST /submit` route will use:

```python
@limiter.limit("10 per minute;100 per day")
```

## Audit Log Plan

Every attribution decision and appeal will be saved in a structured audit log.

The audit log will use JSON for this project because it is simple, readable, and easy to show in the README.

Each submission log entry will include:

* `event_type`
* `content_id`
* `creator_id`
* `timestamp`
* `attribution`
* `confidence`
* `llm_score`
* `stylometric_score`
* `label`
* `status`

Example submission log entry:

```json
{
  "event_type": "classification",
  "content_id": "3f7a2b1e-example",
  "creator_id": "test-user-1",
  "timestamp": "2026-07-04T14:32:10Z",
  "attribution": "likely_ai",
  "confidence": 0.82,
  "llm_score": 0.85,
  "stylometric_score": 0.78,
  "label": "Provenance Guard found strong signals that this content may have been AI-generated. This label is based on automated analysis and may not be perfect.",
  "status": "classified"
}
```

Each appeal log entry will include:

* `event_type`
* `content_id`
* `timestamp`
* `appeal_reasoning`
* `previous_status`
* `new_status`

Example appeal log entry:

```json
{
  "event_type": "appeal",
  "content_id": "3f7a2b1e-example",
  "timestamp": "2026-07-04T14:40:02Z",
  "appeal_reasoning": "I wrote this myself from personal experience.",
  "previous_status": "classified",
  "new_status": "under_review"
}
```

## AI Tool Plan

### Milestone 3: Submission Endpoint and First Detection Signal

For Milestone 3, I will provide the AI tool with these planning sections:

* Architecture
* API Contract
* Detection Signals
* Audit Log Plan

I will ask the AI tool to generate:

* A Flask app skeleton
* A `POST /submit` route
* Request validation for `text` and `creator_id`
* A Groq-based LLM classification function
* A simple structured audit log helper
* A `GET /log` endpoint

I will verify the output by:

* Running the Flask app locally
* Sending a test request to `POST /submit`
* Checking that the response includes `content_id`, `attribution`, `confidence`, and `label`
* Checking that `GET /log` returns a structured log entry

### Milestone 4: Second Signal and Confidence Scoring

For Milestone 4, I will provide the AI tool with these planning sections:

* Detection Signals
* Uncertainty Representation
* Architecture
* Audit Log Plan

I will ask the AI tool to generate:

* A stylometric heuristic function
* Sentence length variance calculation
* Type-token ratio calculation
* Punctuation density calculation
* Confidence scoring logic
* Attribution mapping logic

I will verify the output by:

* Testing at least four different input texts
* Comparing clearly AI-like text with clearly human-like text
* Confirming that scores vary meaningfully
* Checking that both individual signal scores appear in the audit log

### Milestone 5: Production Layer

For Milestone 5, I will provide the AI tool with these planning sections:

* Transparency Label Design
* Appeals Workflow
* Uncertainty Representation
* Rate Limiting Plan
* Audit Log Plan
* Architecture

I will ask the AI tool to generate:

* A transparency label generation function
* A `POST /appeal` endpoint
* Status update logic for appealed content
* Audit log updates for appeals
* Flask-Limiter setup for rate limiting

I will verify the output by:

* Testing that all three label variants are reachable
* Submitting an appeal using a real `content_id`
* Confirming the appealed content status changes to `under_review`
* Checking that the appeal appears in `GET /log`
* Sending more than the allowed number of requests to confirm rate limiting returns HTTP 429

