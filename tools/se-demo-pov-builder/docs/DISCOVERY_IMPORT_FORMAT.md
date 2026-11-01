# Discovery import format (`se-demo-pov-builder/discovery-import`, version 1)

> **Status: proposed.** This document defines the format only. The app does not read it
> yet. Today the Discovery tab's **Import transcript / list** accepts pasted text and
> `.txt`, `.vtt` and `.srt` files (implemented). This format is for call-transcript tools
> (for example a "conversation copilot") that want to hand over answers they have already
> found, so the SE can review them in the same screen.

## Why a separate format

A transcript tool knows more than a caption file: who was on the call, which passage
answers which question, and how sure it is. This format carries that, while keeping
the rules the app applies to every import:

1. **Every proposed answer needs a quote**: the customer's exact words from the call.
2. **The SE reviews every item.** Nothing is saved until the SE accepts it.
3. **Accepted answers are saved as `assumed`**, never `confirmed`, whatever the tool's
   confidence. The SE confirms them with the customer later.
4. **Only accepted quotes are stored.** The transcript itself is not saved.
5. **A confirmed answer is never replaced** by an imported one.

## Example

```json
{
  "format": "se-demo-pov-builder/discovery-import",
  "version": 1,
  "generator": "conversation-copilot 0.3.0",
  "generated_at": "2026-11-01T15:04:05Z",
  "data_classification": "synthetic",
  "call": {
    "title": "Technical deep dive (fictional)",
    "date": "2026-10-30",
    "source_file": "deep-dive.vtt",
    "participants": [
      {"name": "Dana Whitlock", "email": "dana.whitlock@example.invalid", "side": "customer"},
      {"name": "Sam Rivera", "side": "vendor"}
    ]
  },
  "segments": [
    {"id": "s12", "speaker": "Dana Whitlock", "start": "00:12:31", "end": "00:12:44",
     "text": "Honestly around three thousand a week, and the NOC ignores most of them."}
  ],
  "answers": [
    {
      "question_id": "tech_alert_noise",
      "answer": "About 3,000 alerts a week; most are ignored by the NOC.",
      "quote": "around three thousand a week, and the NOC ignores most of them",
      "segment_id": "s12",
      "speaker": "Dana Whitlock",
      "start": "00:12:31",
      "tool_confidence": 0.82
    },
    {
      "question_text": "Which branch sites have no on-site IT staff?",
      "answer": "Nine of the 35 warehouses.",
      "quote": "nine of the warehouses have nobody from IT on site",
      "speaker": "Dana Whitlock",
      "start": "00:21:05"
    }
  ],
  "questions": [
    {"text": "How do you decide when a branch outage is escalated to the vendor?", "category": "process"}
  ]
}
```

## Fields

### Top level

| Field | Required | Meaning |
|-------|----------|---------|
| `format` | yes | Always `se-demo-pov-builder/discovery-import`. |
| `version` | yes | `1`. New optional fields keep version 1; anything else increments it. |
| `generator` | yes | Producing tool and version. |
| `generated_at` | yes | ISO 8601 timestamp. |
| `data_classification` | yes | `synthetic` or `customer`, as in the [handoff format](HANDOFF_FORMAT.md). |
| `call` | no | `title`, `date` (ISO date), `source_file`, `participants[]` (`name`, optional `email`, `side`: `customer`, `vendor` or `unknown`). |
| `segments` | no | The transcript passages the answers come from: `id`, `speaker`, `start`, `end` (`hh:mm:ss`), `text`. Send only the passages you need. |
| `answers` | yes (may be empty) | Proposed answers; see below. |
| `questions` | no | Questions asked on the call that are not in the question bank: `text`, optional `category` (`business`, `technical`, `process`, `qualification`, `stakeholder`). Offered as custom questions for the deal. |

### `answers[]`

| Field | Required | Meaning |
|-------|----------|---------|
| `question_id` | one of these two | A question id from `knowledge/discovery_questions.yaml` (`GET /api/library/discovery`), or a deal's custom question id (`custom-<n>`). |
| `question_text` | one of these two | Free text when the tool doesn't know the id. The app matches it to an existing question or offers it as a new custom question. |
| `answer` | yes | Short answer in the customer's terms. The SE can edit it before accepting. |
| `quote` | yes | The customer's exact words. If `segments` are sent, the quote must appear word for word (ignoring case and whitespace) in the referenced segment, or in any segment when `segment_id` is omitted. Items that fail this check are dropped and reported. |
| `segment_id` | no | The `segments[].id` containing the quote. |
| `speaker`, `start` | no | Shown next to the quote. A speaker whose name matches a stakeholder on the deal is recorded as "answered by". |
| `tool_confidence` | no | 0–1. Used only to order the review list. It never changes the saved confidence (`assumed`). |

## What the app will do with it (when implemented)

1. Validate the document (unknown `format` or `version` is refused).
2. Drop answers without a quote, with a quote not found in `segments`, or that target a
   question with a confirmed answer, and say why.
3. Show the rest in the same review list as pasted transcripts: question, quote with
   speaker and time, editable answer, **Accept as assumed** / **Reject**.
4. Store accepted items as `assumed` answers with `evidence_quote` = the quote and
   `evidence_source` = `Transcript: <source_file> @ <start> (<speaker>)`.
5. Offer `questions[]` and unmatched `question_text` items as custom questions; the SE
   picks which to add.

The answer and question endpoints this would reuse already exist:
`POST /api/deals/{id}/discovery/transcript/accept` and
`POST /api/deals/{id}/discovery/custom-questions/bulk`.
