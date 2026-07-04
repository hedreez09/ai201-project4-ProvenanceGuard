When a creator submits a piece of text to Provenance Guard, the request enters the POST /submit endpoint with the submitted text and creator ID. The API first validates that the request includes the required fields. Then the text is passed into the detection pipeline.

The detection pipeline uses two separate signals. The first signal is an LLM-based classifier using Groq, which evaluates the writing holistically and returns a score estimating whether the content appears AI-generated. The second signal is a stylometric heuristic analyzer, which measures structural writing patterns such as sentence length variation, vocabulary diversity, and punctuation density.

After both signals produce scores, the confidence scoring component combines them into one final confidence score. That score is mapped to an attribution category: likely AI-generated, likely human-written, or uncertain. The transparency label component then converts the result into plain-language text that a normal reader can understand.

Finally, the system writes a structured audit log entry containing the content ID, creator ID, timestamp, signal scores, final confidence score, attribution result, label text, and status. The API returns a structured JSON response to the user with the content ID, attribution result, confidence score, and transparency label.


## Architecture

### Submission Flow

```text
Creator / Platform
        |
        | raw text + creator_id
        v
POST /submit endpoint
        |
        | validated text
        v
Detection Pipeline
        |
        |-----------------------------|
        |                             |
        v                             v
Signal 1: Groq LLM Classifier     Signal 2: Stylometric Heuristics
        |                             |
        | llm_score                   | stylometric_score
        |-----------------------------|
                      |
                      v
Confidence Scoring Component
                      |
                      | combined confidence score
                      v
Attribution Decision
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
   | locate original content decision
   v
Update Content Status
   |
   | status = under_review
   v
Structured Audit Log
   |
   | original decision + appeal reasoning
   v
JSON Confirmation Response
```

In the submission flow, a creator sends text and a creator ID to the system. The system validates the request, runs two detection signals, combines their scores into a confidence score, maps the result to a transparency label, saves the decision in the audit log, and returns the result.

In the appeal flow, a creator submits a content ID and explanation. The system updates the content status to “under_review,” records the appeal in the audit log, and returns a confirmation response.
