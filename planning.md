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
