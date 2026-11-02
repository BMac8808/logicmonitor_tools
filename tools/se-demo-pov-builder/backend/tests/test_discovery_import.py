"""Custom questions, "start here" ranking and transcript / question-list import."""

import dataclasses

import httpx

from se_pov_builder.services import transcript as tx

VTT = """WEBVTT

NOTE fictional call

1
00:00:05.000 --> 00:00:09.000
<v Sam SE>How many alerts does the team receive in a typical week?</v>

2
00:00:10.000 --> 00:00:16.500
<v Dana Whitlock>Honestly around three thousand a week, and the NOC ignores most of them.</v>

3
00:00:17.000 --> 00:00:21.000
<v Dana Whitlock>It is real alert fatigue.</v>

4
00:01:02.000 --> 00:01:08.000
<v Dana Whitlock>Our contract renewal date is in March, so we need a decision by then.</v>

5
00:01:30.000 --> 00:01:38.000
<v Dana Whitlock>The core switch outage took ninety minutes to detect and cost us forty shipments an hour.</v>
"""

SRT = """1
00:00:01,000 --> 00:00:04,000
Dana: We had a recent outage on the core switch.

2
00:00:05,000 --> 00:00:08,000
Dana: It took ninety minutes to find.
"""


def test_parse_vtt_merges_speaker_cues_and_keeps_timestamps():
    fmt, segs = tx.parse_transcript(VTT, "call.vtt")
    assert fmt == "vtt"
    assert segs[0].speaker == "Sam SE" and segs[0].start == "00:00:05"
    assert segs[1].speaker == "Dana Whitlock"
    assert segs[1].text.endswith("It is real alert fatigue.")  # consecutive cues merged
    assert all("<" not in s.text for s in segs)


def test_parse_srt_and_plain_text():
    fmt, segs = tx.parse_transcript(SRT, "call.srt")
    assert fmt == "srt" and segs[0].speaker == "Dana" and segs[0].start == "00:00:01"
    assert len(segs) == 1  # same speaker, merged
    fmt, segs = tx.parse_transcript("[00:12:31] Dana Whitlock: We use three tools.\nSam: Thanks.\n", "notes.txt")
    assert fmt == "text"
    assert (segs[0].start, segs[0].speaker, segs[0].text) == ("00:12:31", "Dana Whitlock", "We use three tools.")
    assert segs[1].speaker == "Sam"


def test_keyword_proposals_quote_the_reply_not_the_question(kb):
    from se_pov_builder.services.questions import question_index

    _, segs = tx.parse_transcript(VTT, "call.vtt")
    props = {p.question_id: p for p in tx.keyword_proposals(kb, question_index(kb).values(), segs)}
    assert "tech_alert_noise" in props
    p = props["tech_alert_noise"]
    assert p.speaker == "Dana Whitlock" and "three thousand a week" in p.quote
    assert "How many alerts" not in p.quote
    assert p.quote in " ".join(s.text for s in segs)  # exact words from the call
    assert p.method == "keyword" and p.matched
    # The asked question boosts only the bank question it matches best.
    assert all("reply to this question" not in x.matched for qid, x in props.items() if qid != "tech_alert_noise")
    # Quantity questions pick up answers that give numbers.
    assert "ninety minutes" in props["biz_impact"].quote


def test_ai_proposals_need_a_verbatim_quote(kb):
    from se_pov_builder.services.questions import question_index

    _, segs = tx.parse_transcript(VTT, "call.vtt")
    raw = """Here you go:
    [{"question_id": "biz_trigger", "quote": "our contract renewal date is in March", "answer": "Renewal in March"},
     {"question_id": "biz_trigger", "quote": "We will lose $2m without this", "answer": "invented"},
     {"question_id": "not_a_question", "quote": "It is real alert fatigue.", "answer": "x"}]"""
    kept, rejected = tx.verify_ai_proposals(raw, question_index(kb), segs)
    assert rejected == 2
    assert [k.quote for k in kept] == ["Our contract renewal date is in March"]  # transcript's own casing
    assert kept[0].method == "ai" and kept[0].speaker == "Dana Whitlock"


def test_question_list_parsing():
    text = "Discovery questions:\n1. What does an hour of downtime cost you?\n- Who signs off on the budget?\n\nok\n"
    assert tx.parse_question_list(text) == ["What does an hour of downtime cost you?", "Who signs off on the budget?"]
    assert tx.guess_category("Who signs off on the budget?") == "qualification"
    assert tx.guess_category("Which firewalls do you run?") == "technical"


def test_all_bank_questions_and_next_up(client, deal):
    qs = client.get(f"/api/deals/{deal['id']}/discovery/questions").json()
    assert len(qs["questions"]) == qs["bank_total"] == 31
    suggested = [q for q in qs["questions"] if q["suggested"]]
    assert 0 < len(suggested) < 31 and qs["total"] == len(suggested)
    assert 3 <= len(qs["next_up"]) <= 5
    first = qs["next_up"][0]
    assert first["reason"].startswith("Covers checklist item")
    # One question per missing checklist item.
    reasons = [n["reason"] for n in qs["next_up"] if n["reason"].startswith("Covers")]
    assert len(reasons) == len(set(reasons))

    # Any bank question can be answered, even one not suggested for this deal.
    hidden = next(q for q in qs["questions"] if not q["suggested"])
    r = client.put(f"/api/deals/{deal['id']}/discovery/answers/{hidden['id']}", json={"answer": "Yes"})
    assert r.status_code == 200
    qs2 = client.get(f"/api/deals/{deal['id']}/discovery/questions").json()
    assert qs2["total"] == qs["total"] + 1 and qs2["answered"] == 1


def test_custom_questions_lifecycle(client, deal):
    base = f"/api/deals/{deal['id']}/discovery"
    cq = f"{base}/custom-questions"
    r = client.post(cq, json={"text": "Which sites have no on-site IT staff?", "category": "technical",
                              "qualification_key": "technical_scope"})
    assert r.status_code == 201, r.text
    q = r.json()
    assert q["id"].startswith("custom-") and q["custom"] is True
    assert client.post(cq, json={"text": "which sites have no on-site IT staff"}).status_code == 409
    assert client.post(cq, json={"text": "Bad key?", "qualification_key": "nope"}).status_code == 422

    qs = client.get(f"{base}/questions").json()
    assert any(x["id"] == q["id"] for x in qs["questions"])
    r = client.put(f"{base}/answers/{q['id']}", json={"answer": "Nine branches", "confidence": "confirmed"})
    assert r.status_code == 200
    gaps = client.get(f"{base}/gaps").json()
    scope = next(i for i in gaps["qualification"] if i["key"] == "technical_scope")
    assert scope["status"] == "confirmed" and q["id"] in scope["question_ids"]

    # Requirements can cite a custom question.
    r = client.post(f"/api/deals/{deal['id']}/requirements",
                    json={"title": "Branch coverage", "source_question_id": q["id"]})
    assert r.status_code == 201

    # The handoff labels custom questions with their text.
    handoff = client.get(f"/api/deals/{deal['id']}/handoff").json()
    item = next(d for d in handoff["discovery"] if d["question_id"] == q["id"])
    assert item["question"] == "Which sites have no on-site IT staff?" and item["category"] == "technical"

    # Bulk add skips duplicates, including bank questions.
    bank_text = qs["questions"][0]["text"]
    r = client.post(f"{cq}/bulk", json={"questions": [
        {"text": "What does an hour of downtime cost?"}, {"text": bank_text},
        {"text": "What does an hour of downtime cost"}]})
    body = r.json()
    assert len(body["created"]) == 1 and len(body["skipped"]) == 2

    # Deleting a custom question removes its answer; other deals can't delete it.
    other = client.post("/api/deals", json={"account_id": deal["account_id"], "name": "Other"}).json()
    assert client.delete(f"/api/deals/{other['id']}/discovery/custom-questions/{q['id']}").status_code == 404
    assert client.delete(f"{cq}/{q['id']}").status_code == 204
    assert client.put(f"{base}/answers/{q['id']}", json={"answer": "x"}).status_code == 404
    assert all(a["question_id"] != q["id"] for a in client.get(f"{base}/questions").json()["unmatched_answers"])


def test_transcript_proposals_are_stateless_and_accept_saves_assumed(client, deal):
    base = f"/api/deals/{deal['id']}/discovery"
    stakeholder = client.post(f"/api/deals/{deal['id']}/stakeholders",
                              json={"name": "Dana Whitlock", "persona_id": "champion"}).json()
    before = client.get(f"{base}/questions").json()
    r = client.post(f"{base}/transcript/proposals", json={"text": VTT, "filename": "call.vtt"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["format"] == "vtt" and out["segments"] == 4 and out["ai_used"] is False
    props = {p["question_id"]: p for p in out["proposals"]}
    assert "tech_alert_noise" in props
    assert client.get(f"{base}/questions").json() == before  # nothing stored

    p = props["tech_alert_noise"]
    r = client.post(f"{base}/transcript/accept", json={
        "question_id": p["question_id"], "answer": "About 3,000 alerts a week, mostly ignored", "quote": p["quote"],
        "speaker": p["speaker"], "timestamp": p["timestamp"], "filename": "call.vtt"})
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["confidence"] == "assumed"
    assert saved["evidence_quote"] == p["quote"]
    assert saved["evidence_source"] == "Transcript: call.vtt @ 00:00:10 (Dana Whitlock)"
    assert saved["stakeholder_id"] == stakeholder["id"]

    # A confirmed answer is never replaced, and confirmed questions are not searched.
    client.put(f"{base}/answers/tech_alert_noise", json={"answer": "Confirmed by NOC lead", "confidence": "confirmed"})
    r = client.post(f"{base}/transcript/accept", json={"question_id": "tech_alert_noise", "answer": "x", "quote": "y"})
    assert r.status_code == 409
    out = client.post(f"{base}/transcript/proposals", json={"text": VTT}).json()
    assert "tech_alert_noise" not in {p["question_id"] for p in out["proposals"]}
    assert any("already confirmed" in n for n in out["notes"])


def test_transcript_ai_disabled_falls_back_to_keywords(client, deal):
    out = client.post(f"/api/deals/{deal['id']}/discovery/transcript/proposals",
                      json={"text": VTT, "use_ai": True}).json()
    assert out["ai_used"] is False and any("not configured" in n for n in out["notes"])
    assert out["proposals"]


def test_transcript_ai_keeps_only_verbatim_quotes(settings):
    from fastapi.testclient import TestClient

    from se_pov_builder.app import create_app

    reply = ('[{"question_id": "biz_trigger", "quote": "Our contract renewal date is in March",'
             ' "answer": "March renewal"},'
             ' {"question_id": "biz_impact", "quote": "We lost two million dollars", "answer": "invented"}]')

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": reply}}]})

    settings = dataclasses.replace(settings, llm_provider="openai_compatible", llm_base_url="http://llm.invalid",
                                   llm_model="test")
    app = create_app(settings)
    with TestClient(app) as c:
        from se_pov_builder.llm import OpenAICompatibleProvider

        app.state.llm = OpenAICompatibleProvider("http://llm.invalid", "test", transport=httpx.MockTransport(handler))
        account = c.post("/api/accounts", json={"name": "AI Co (fictional)"}).json()
        deal = c.post("/api/deals", json={"account_id": account["id"], "name": "AI deal"}).json()
        out = c.post(f"/api/deals/{deal['id']}/discovery/transcript/proposals",
                     json={"text": VTT, "use_ai": True}).json()
    assert out["ai_used"] is True
    ai = [p for p in out["proposals"] if p["method"] == "ai"]
    assert [(p["question_id"], p["quote"]) for p in ai] == [("biz_trigger", "Our contract renewal date is in March")]
    assert any("not word for word" in n for n in out["notes"])


def test_question_list_proposals_flag_duplicates(client, deal):
    r = client.post(f"/api/deals/{deal['id']}/discovery/question-list/proposals", json={
        "text": "- How many monitoring tools do you run today, and what do they cost?\n"
                "- Which branch sites flap most?"})
    props = r.json()["proposals"]
    assert props[0]["duplicate_of"] == "biz_tool_cost" and props[0]["duplicate_level"] == "likely"
    assert props[1]["duplicate_of"] is None and props[1]["category"] == "technical"
    assert props[1]["duplicate_level"] is None


def test_question_list_hints_at_reworded_questions(client, deal):
    # A natural rewording shares too few words to be a likely duplicate; it is shown as a hint.
    r = client.post(f"/api/deals/{deal['id']}/discovery/question-list/proposals", json={
        "text": "- Roughly how many alerts do you get each week, and how many actually need action?\n"
                "- Who receives alert notifications after hours, and is there an on-call rotation?"})
    props = r.json()["proposals"]
    assert props[0]["duplicate_of"] == "tech_alert_noise" and props[0]["duplicate_level"] == "possible"
    assert props[1]["duplicate_of"] is None and props[1]["duplicate_level"] is None
