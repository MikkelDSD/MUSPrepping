import pytest

from musprepping import praise
from musprepping.db.schema import STRENGTHS

STRENGTH = {"key": "samarbejde", "label": "Samarbejde"}


def test_every_strength_has_phrases():
    assert {key for _, key, *_ in STRENGTHS} == set(praise.STRENGTH_PHRASES)


def test_uses_first_name_and_highlights():
    result = praise.generate_praise("Sofie Lindberg", [STRENGTH], [{"title": "Lancerede portalen."}], seed=1)
    assert "Sofie" in result["text"]
    assert "Lindberg" not in result["text"]
    assert "Lancerede portalen" in result["text"]
    assert "{" not in result["text"]  # no unfilled placeholders


def test_same_seed_same_text_and_variants_differ():
    texts = {praise.generate_praise("Ahmad", [STRENGTH], seed=s)["text"] for s in range(20)}
    assert praise.generate_praise("Ahmad", [STRENGTH], seed=3) == praise.generate_praise("Ahmad", [STRENGTH], seed=3)
    assert len(texts) > 1


@pytest.mark.parametrize("tone", list(praise.TONES))
def test_every_tone_opens_and_closes_in_that_tone(tone):
    result = praise.generate_praise("Mette", [STRENGTH], tone=tone, seed=5)
    assert result["tone"] == tone
    openers = [o.format(navn="Mette") for o in praise.TONES[tone]["openers"]]
    closers = [c.format(navn="Mette") for c in praise.TONES[tone]["closers"]]
    assert result["paragraphs"][0] in openers
    assert result["paragraphs"][-1] in closers


def test_unknown_tone_and_no_strengths_still_produce_warm_text():
    result = praise.generate_praise("Jonas", [], tone="ukendt", seed=2)
    assert result["tone"] == praise.DEFAULT_TONE
    assert result["paragraphs"][1] in praise.GENERIC_PHRASES


def test_conversation_questions():
    qs = praise.conversation_questions(count=5, seed=1)
    assert len(qs) == len(set(qs)) == 5
    assert qs == praise.conversation_questions(count=5, seed=1)
