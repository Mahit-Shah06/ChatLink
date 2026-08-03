"""
Phase 2 tests: capture, channel resolution, syllabus parsing.

    python -m pytest tests/test_capture.py -q
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from learning.capture import CaptureEngine
from learning.models import Attachment, ChannelContext, IncomingMessage
from learning.syllabus import ChannelRegistry, Syllabus, infer_context, load_syllabus

CN = ChannelContext(external_id="101", label="computer-networks", category="SEMESTER 3",
                    context_kind="semester", context_value="sem3",
                    subject_key="computer_networks", origin="syllabus")
REF = ChannelContext(external_id="900", label="resources", category="REFERENCE",
                     context_kind="reference", origin="syllabus")


@pytest.fixture
def engine(tmp_path):
    return CaptureEngine(db_path=tmp_path / "cap.db", syllabus=Syllabus())


def msg(text="the OSI model has seven layers", ext="m1", channel=CN, **kw):
    return IncomingMessage(content=text, source="test", external_id=ext,
                           author_id="7", author_name="raj", channel=channel, **kw)


# --------------------------------------------------------------- attachments
@pytest.mark.parametrize("filename,ctype,expected", [
    ("notes.pdf", "application/pdf", "document"),
    ("diagram.png", "image/png", "image"),
    ("osi.JPEG", "", "image"),
    ("lecture.mp3", "", "audio"),
    ("demo.mp4", "video/mp4", "video"),
    ("weird.xyz", "", "other"),
])
def test_attachment_kind_detection(filename, ctype, expected):
    assert Attachment(filename=filename, content_type=ctype).kind == expected


# ----------------------------------------------------------------- filtering
def test_captures_a_normal_message(engine):
    assert engine.capture(msg()) is not None


@pytest.mark.parametrize("text", ["!help", "/start", ".ping", "?x", "ok", "", "  "])
def test_filters_commands_and_noise(engine, text):
    assert engine.capture(msg(text, ext="f1")) is None


def test_captures_image_with_no_caption(engine):
    """A diagram posted bare is still worth keeping."""
    m = msg("", ext="img", attachments=[Attachment(filename="osi.png", content_type="image/png")])
    assert engine.capture(m) is not None


def test_reference_channels_are_never_captured(engine):
    """Stable material shouldn't flood the analytics."""
    assert engine.capture(msg("textbook chapter 3", ext="r1", channel=REF)) is None


def test_disabled_channel_is_skipped(engine):
    off = ChannelContext(external_id="5", label="x", enabled=False)
    assert engine.capture(msg("real content here", ext="d1", channel=off)) is None


# ------------------------------------------------------------------ storage
def test_message_is_stored_with_context(engine):
    engine.capture(msg("revised subnetting today"))
    row = engine.repo.recent(1)[0]
    assert row["channel_label"] == "computer-networks"
    assert row["author_name"] == "raj"
    assert row["local_hour"] is not None


def test_recapture_is_idempotent(engine):
    engine.capture(msg(ext="same"))
    engine.capture(msg(ext="same"))
    assert engine.repo.summary()["messages"] == 1


def test_edit_updates_content_and_stamps_edited_at(engine):
    engine.capture(msg("first version of the note", ext="e1"))
    engine.capture(msg("second version of the note", ext="e1"))
    row = engine.db.query_one("SELECT content, edited_at FROM messages")
    assert row["content"] == "second version of the note"
    assert row["edited_at"] is not None


def test_reingesting_identical_content_does_not_mark_edited(engine):
    engine.capture(msg("unchanged text", ext="e2"))
    engine.capture(msg("unchanged text", ext="e2"))
    assert engine.db.query_one("SELECT edited_at FROM messages")["edited_at"] is None


def test_attachments_are_stored_and_typed(engine):
    m = msg("unit 3 slides", ext="a1", attachments=[
        Attachment(filename="unit3.pdf", content_type="application/pdf", size_bytes=900),
        Attachment(filename="graph.png", content_type="image/png"),
    ])
    engine.capture(m)
    kinds = {r["kind"] for r in engine.db.query("SELECT kind FROM attachments")}
    assert kinds == {"document", "image"}
    assert engine.repo.summary()["attachments"] == 2


def test_reingest_replaces_attachments_without_duplicating(engine):
    m = msg("slides", ext="a2", attachments=[Attachment(filename="a.pdf")])
    engine.capture(m)
    engine.capture(m)
    assert engine.repo.summary()["attachments"] == 1


def test_soft_delete_hides_message(engine):
    engine.capture(msg(ext="del1"))
    assert engine.forget("test", "del1") is True
    assert engine.repo.summary()["messages"] == 0


def test_search_finds_captured_text(engine):
    engine.capture(msg("the sliding window protocol controls flow", ext="s1"))
    engine.capture(msg("something entirely different", ext="s2"))
    assert len(engine.repo.search("sliding")) == 1


def test_daily_counts_group_by_local_date(engine):
    base = datetime.now(timezone.utc)
    for i in range(3):
        engine.capture(msg(f"studied routing day {i}", ext=f"d{i}",
                           created_at=base - timedelta(days=i)))
    assert len(engine.repo.daily_counts()) == 3


# ---------------------------------------------------------------- inference
def test_category_supplies_semester_channel_supplies_subject():
    ctx = infer_context("computer-networks", "SEMESTER 3")
    assert ctx.context_kind == "semester"
    assert ctx.context_value == "sem3"
    assert ctx.subject_key == "computer_networks"


def test_semester_in_channel_name_also_works():
    ctx = infer_context("sem4-dbms", "")
    assert ctx.context_value == "sem4"


def test_exam_category_detected():
    ctx = infer_context("gate-pyqs", "GATE")
    assert ctx.context_kind == "exam" and ctx.context_value == "gate"


def test_reference_channels_recognised():
    assert infer_context("resources", "REFERENCE").context_kind == "reference"
    assert infer_context("syllabus", "").context_kind == "reference"


def test_unrelated_channels_are_ignored():
    assert infer_context("general", "") is None
    assert infer_context("memes", "OFF TOPIC") is None


# ----------------------------------------------------------------- registry
def test_explicit_mapping_beats_inference(tmp_path):
    path = tmp_path / "channels.json"
    path.write_text(json.dumps({"channels": [{
        "id": "555", "label": "cn", "context_kind": "semester",
        "context_value": "sem3", "subject_key": "computer_networks",
        "enabled": True, "origin": "syllabus",
    }]}))
    reg = ChannelRegistry(map_path=path, syllabus=Syllabus())
    # inference would read this as sem7; the explicit entry must win
    ctx = reg.resolve("555", "sem7-something", "SEMESTER 7")
    assert ctx.context_value == "sem3" and ctx.origin == "syllabus"


def test_falls_back_to_inference_when_unmapped(tmp_path):
    reg = ChannelRegistry(map_path=tmp_path / "none.json", syllabus=Syllabus())
    ctx = reg.resolve("999", "dbms", "SEMESTER 3")
    assert ctx is not None and ctx.origin == "inferred"


def test_unknown_channel_is_ignored_by_default(tmp_path):
    reg = ChannelRegistry(map_path=tmp_path / "none.json", syllabus=Syllabus())
    assert reg.resolve("123", "random-chat", "SOCIAL") is None


def test_watch_all_captures_everything(tmp_path):
    reg = ChannelRegistry(map_path=tmp_path / "none.json", syllabus=Syllabus(), watch_all=True)
    assert reg.resolve("123", "random-chat", "SOCIAL") is not None


def test_registry_round_trips_through_disk(tmp_path):
    path = tmp_path / "channels.json"
    reg = ChannelRegistry(map_path=path, syllabus=Syllabus())
    reg.register(CN)
    assert ChannelRegistry(map_path=path, syllabus=Syllabus()).resolve("101").subject_key \
        == "computer_networks"


def test_corrupt_channel_map_does_not_crash(tmp_path):
    path = tmp_path / "channels.json"
    path.write_text("{ not json")
    reg = ChannelRegistry(map_path=path, syllabus=Syllabus())
    assert reg.all() == []


# ----------------------------------------------------------------- syllabus
def test_syllabus_nests_exams_inside_the_semester_category(tmp_path):
    """One category per semester: subjects and exam channels together."""
    path = tmp_path / "syllabus.json"
    path.write_text(json.dumps({
        "version": 2,
        "semesters": [{
            "id": "sem5", "name": "Semester 5", "category": "SEMESTER 5", "active": True,
            "subjects": [{"key": "computer_networks", "name": "CN",
                          "channel": "computer-networks", "syllabus": "Unit 1 - OSI model"}],
            "exams": [{"key": None, "name": "Mid Sem 1", "channel": "midsem-1"},
                      {"key": None, "name": "Final", "channel": "final-exam"}],
        }],
    }))
    syl = load_syllabus(path)
    assert len(syl.categories) == 1
    assert syl.channel_count == 3
    assert syl.find("midsem-1").context_value == "sem5"
    assert syl.find("midsem-1").context_kind == "exam"
    assert syl.find("computer-networks").syllabus_text.startswith("Unit 1")


def test_top_level_exams_still_supported(tmp_path):
    """Cross-semester exams (GATE etc) keep their own category."""
    path = tmp_path / "syllabus.json"
    path.write_text(json.dumps({
        "semesters": [],
        "exams": [{"id": "gate", "category": "GATE", "active": True,
                   "channels": [{"name": "Prep", "channel": "gate-prep"}]}],
    }))
    syl = load_syllabus(path)
    assert syl.find("gate-prep").context_value == "gate"


def test_subjects_without_syllabus_text_are_fine(tmp_path):
    path = tmp_path / "syllabus.json"
    path.write_text(json.dumps({"semesters": [{
        "id": "sem5", "category": "S5",
        "subjects": [{"key": "dbms", "channel": "dbms"}],
    }]}))
    assert load_syllabus(path).find("dbms").syllabus_text == ""


def test_inactive_semesters_are_skipped(tmp_path):
    path = tmp_path / "syllabus.json"
    path.write_text(json.dumps({"semesters": [
        {"id": "sem5", "category": "S5", "active": True,
         "subjects": [{"key": "a", "channel": "a"}]},
        {"id": "sem6", "category": "S6", "active": False,
         "subjects": [{"key": "b", "channel": "b"}]},
    ]}))
    assert load_syllabus(path).channel_count == 1


def test_missing_syllabus_is_not_an_error(tmp_path):
    assert load_syllabus(tmp_path / "nope.json").channel_count == 0


def test_channel_name_derived_from_key_when_omitted(tmp_path):
    path = tmp_path / "syllabus.json"
    path.write_text(json.dumps({"semesters": [{
        "id": "sem5", "category": "S5",
        "subjects": [{"key": "computer_networks", "name": "CN"}],
    }]}))
    assert load_syllabus(path).find("computer-networks") is not None


# ==========================================================================
# Phase 3/4 : classification and topic detection
# ==========================================================================

from learning.classifiers.rules import RuleBasedClassifier
from learning.models import Label
from learning.topics.matcher import TaxonomyTopicExtractor

clf = RuleBasedClassifier()
ext = TaxonomyTopicExtractor()


def label_of(text, channel=None):
    m = IncomingMessage(content=text, channel=channel or ChannelContext())
    topics, _ = ext.extract(m)
    return clf.classify(m, topics).label


@pytest.mark.parametrize("text,expected", [
    ("why does TCP need a three way handshake?", Label.QUESTION),
    ("what is the difference between apriori and fp growth", Label.QUESTION),
    ("confused about how gini index differs from entropy", Label.QUESTION),
    ("stuck on backpropagation math", Label.QUESTION),
    ("the OSI model consists of 7 layers each handling one concern", Label.NOTE),
    ("overfitting means the model memorises the training data", Label.NOTE),
    ("groupby splits the dataframe then applies a function to each group", Label.NOTE),
    ("HIRA means hazard identification and risk assessment", Label.NOTE),
    ("what if I built a visualiser for decision trees", Label.IDEA),
    ("thinking of making a dashboard for my notes", Label.IDEA),
    ("solved 30 questions on routing protocols", Label.PROGRESS),
    ("finished the whole clustering unit", Label.PROGRESS),
    ("completed 15 numpy exercises", Label.PROGRESS),
    ("revised subnetting again today", Label.REVISION),
    ("went through gradient descent one more time", Label.REVISION),
    ("revised the factories act provisions again", Label.REVISION),
    ("https://youtube.com/playlist?list=x good pandas playlist", Label.RESOURCE),
    ("lol same", Label.RANDOM),
    ("bruh", Label.RANDOM),
])
def test_classification_accuracy(text, expected):
    assert label_of(text) == expected


def test_question_beats_resource():
    assert label_of("should I use this playlist for ML? https://youtube.com/x") == Label.QUESTION


def test_revision_beats_progress():
    assert label_of("revised 30 questions on clustering again today") == Label.REVISION


def test_pdf_attachment_is_resource():
    m = IncomingMessage(content="unit 3 slides",
                        attachments=[Attachment(filename="u3.pdf", content_type="application/pdf")])
    assert clf.classify(m, []).label == Label.RESOURCE


def test_classifier_never_raises():
    for junk in ["", "   ", "🙂🙂", "```\n```", "?" * 300, "\x00"]:
        assert clf.classify(IncomingMessage(content=junk)).label in list(Label)


def test_scores_and_evidence_recorded():
    c = clf.classify(IncomingMessage(content="why is apriori slow on large datasets?"))
    assert set(c.scores) == set(Label.values())
    assert c.evidence and 0 <= c.confidence <= 1


# ----------------------------------------------------------- topic matching
def test_detects_topic_and_rolls_up():
    topics, _ = ext.extract(IncomingMessage(content="the OSI model has seven layers"))
    keys = {t.node_key for t in topics}
    assert "osi_model" in keys and "computer_networks" in keys


def test_detects_subtopic_chain():
    topics, _ = ext.extract(IncomingMessage(content="revising the transport layer"))
    keys = {t.node_key for t in topics}
    assert {"transport_layer", "osi_model", "computer_networks"} <= keys


def test_detects_all_six_subjects():
    cases = {
        "subnetting and routing tables": "computer_networks",
        "apriori generates frequent itemsets": "data_mining",
        "gradient descent and backpropagation": "machine_learning",
        "pandas dataframe groupby": "python_ds",
        "react hooks and useEffect": "web_development",
        "hazard identification and risk assessment": "ohs_management",
    }
    for text, subject in cases.items():
        topics, _ = ext.extract(IncomingMessage(content=text))
        assert subject in {t.subject_key for t in topics}, f"{text!r} missed {subject}"


def test_channel_prior_when_no_topic_named():
    ctx = ChannelContext(external_id="1", label="data-mining", subject_key="data_mining")
    topics, _ = ext.extract(IncomingMessage(content="that was harder than expected", channel=ctx))
    assert {t.node_key for t in topics} == {"data_mining"}


def test_urls_do_not_pollute_matching():
    topics, _ = ext.extract(IncomingMessage(content="https://x.com/pandas-clustering-react"))
    assert topics == []


def test_unknown_terms_become_candidates():
    _, cands = ext.extract(IncomingMessage(content="Professor Zorkian covered Blarnix Theory"))
    assert any("Zorkian" in c or "Blarnix" in c for c in cands)


# ------------------------------------------------------------- integration
def test_capture_stores_label_and_topics(engine):
    p = engine.capture(msg("why does TCP need a three way handshake?", ext="c1"))
    assert p.classification.label == Label.QUESTION
    assert p.topics
    row = engine.repo.entries()[0]
    assert row["label"] == "question" and row["topics"]


def test_human_relabel_supersedes(engine):
    p = engine.capture(msg("the OSI model is layered", ext="c2"))
    assert engine.repo.relabel(p.message_id, "revision")
    row = engine.repo.entries()[0]
    assert row["label"] == "revision" and row["label_source"] == "human"
    assert engine.db.scalar("SELECT COUNT(*) FROM classifications") == 2


def test_reclassify_preserves_message_count(engine):
    engine.capture(msg("revised the transport layer", ext="rc1"))
    engine.capture(msg("what is a socket?", ext="rc2"))
    before = engine.repo.summary()["messages"]
    assert engine.reclassify_all()["reclassified"] == before
    assert engine.repo.summary()["messages"] == before


def test_cooccurrence_edges_learned(engine):
    engine.capture(msg("used pandas to preprocess data before clustering", ext="co1"))
    assert any(e["relation"] == "co_occurs" for e in engine.repo.graph()["edges"])


def test_weak_topics_surface_unresolved(engine):
    for i in range(3):
        engine.capture(msg(f"why is apriori so confusing? case {i}", ext=f"w{i}"))
    assert any("Apriori" in t["name"] or "Association" in t["name"]
               for t in engine.repo.weak_topics())


def test_analytics_endpoints_shape(engine):
    engine.capture(msg("revised subnetting again", ext="a1"))
    assert engine.repo.label_counts()
    assert engine.repo.hourly_pattern()
    assert engine.repo.daily_activity(7)
    assert engine.repo.streak() >= 1


# ------------------------------------------------- notes written in code blocks
def test_note_inside_a_code_block_is_still_understood():
    """Writing notes in a fenced block is natural — it renders monospaced and
    stands out. Stripping the block would lose the whole message."""
    text = "```\nClosed itemset: no immediate superset has the same support count.\n```"
    topics, _ = ext.extract(IncomingMessage(content=text))
    assert any(t.node_key == "association_rules" for t in topics)
    assert label_of(text) == Label.NOTE


def test_code_sample_inside_prose_is_still_ignored():
    """A short block inside a longer message is code being shown, not a note.
    Its contents must not leak into topic matching."""
    text = ("tried looping over the rows manually\n"
            "```python\nfor i in range(10):\n    print(i)\n```\n"
            "but pandas groupby was much faster")
    topics, _ = ext.extract(IncomingMessage(content=text))
    names = {t.node_key for t in topics}
    assert "pandas" in names
    # "range" is an alias for a Data Mining statistics topic; it must not fire
    assert "dm_statistics" not in names


def test_long_message_converted_to_attachment_is_flagged(engine):
    """Discord turns a >2000 character message into an empty message plus a
    message.txt attachment. The text is gone, so all the engine can record is
    that something was posted."""
    m = msg("", ext="toolong", attachments=[
        Attachment(filename="message.txt", content_type="text/plain", size_bytes=57000)])
    processed = engine.capture(m)
    assert processed is not None
    assert processed.classification.label == Label.RESOURCE


# ------------------------------------------------------- multi-part syllabus
def test_syllabus_accepts_a_single_string(tmp_path):
    path = tmp_path / "syllabus.json"
    path.write_text(json.dumps({"semesters": [{
        "id": "sem5", "category": "S5",
        "subjects": [{"key": "cn", "channel": "cn", "syllabus": "Unit 1 - OSI"}]}]}))
    entry = load_syllabus(path).find("cn")
    assert entry.syllabus_parts == ["Unit 1 - OSI"]
    assert entry.syllabus_text == "Unit 1 - OSI"


def test_syllabus_accepts_a_list_of_parts(tmp_path):
    """Exam channels pin one message per subject rather than one wall of text."""
    path = tmp_path / "syllabus.json"
    path.write_text(json.dumps({"semesters": [{
        "id": "sem5", "category": "S5", "subjects": [],
        "exams": [{"key": None, "name": "Mid Sem 1", "channel": "midsem-1",
                   "syllabus": ["scope for CN", "scope for DMT", "scope for ML"]}]}]}))
    entry = load_syllabus(path).find("midsem-1")
    assert len(entry.syllabus_parts) == 3
    assert entry.syllabus_text == "scope for CN"


def test_empty_syllabus_yields_no_parts(tmp_path):
    path = tmp_path / "syllabus.json"
    path.write_text(json.dumps({"semesters": [{
        "id": "sem5", "category": "S5",
        "subjects": [{"key": "cn", "channel": "cn"}]}]}))
    assert load_syllabus(path).find("cn").syllabus_parts == []


def test_every_pinned_part_fits_in_a_discord_message():
    """Discord rejects anything over 2000 characters, and converting to an
    attachment would lose the text entirely."""
    from pathlib import Path as _P
    real = _P(__file__).resolve().parent.parent / "data" / "syllabus.json"
    if not real.exists():
        pytest.skip("no syllabus.json in this checkout")
    for entry in load_syllabus(real).all_entries():
        for i, part in enumerate(entry.syllabus_parts):
            assert len(part) + 3 < 1900, f"{entry.channel} part {i} is too long"
