import unittest

import helpers  # noqa: F401

from evidence_aware_crypto_call_recognition.reading import read_sentence
from evidence_aware_crypto_call_recognition.segment import quoted_ranges, split_sentences


def read(text):
    return read_sentence(split_sentences(text)[0])


class Segmentation(unittest.TestCase):
    def test_apostrophes_are_not_quotes(self):
        self.assertEqual(quoted_ranges("Today's view is someone else's, not mine."), [])

    def test_single_quoted_speech_is_found(self):
        line = "A sketch: 'I am loading $ABCD now.' That line is a joke."
        ((start, end),) = quoted_ranges(line)
        self.assertEqual(line[start:end], "'I am loading $ABCD now.'")

    def test_decimals_do_not_end_a_sentence(self):
        sentences = split_sentences("If $ABCD closes above 0.55, I will buy it. Until then I wait.")
        self.assertEqual(len(sentences), 2)
        self.assertTrue(sentences[0].text.endswith("buy it."))

    def test_sentence_ending_inside_a_quote_keeps_the_quote_whole(self):
        sentences = split_sentences("He said: 'Start $ABCD now.' I disagree.")
        self.assertEqual([s.text for s in sentences], ["He said: 'Start $ABCD now.'", "I disagree."])

    def test_offsets_point_into_the_source(self):
        text = "First line.\n\n  Second paragraph here."
        for sentence in split_sentences(text):
            self.assertEqual(text[sentence.start:sentence.end], sentence.text)
        self.assertEqual([s.paragraph for s in split_sentences(text)], [0, 1])


class Operations(unittest.TestCase):
    def op(self, text, asset):
        return read(text).operations[asset][0]

    def test_explicit_entry(self):
        self.assertEqual(self.op("I am opening a fresh position in $ABCD today.", "$ABCD"), "ENTRY")

    def test_team_subject_counts_as_author_voice(self):
        self.assertEqual(self.op("This week our desk is accumulating $ABCD.", "$ABCD"), "ENTRY")

    def test_quoted_entry_is_not_the_authors(self):
        reading = read("My impression of a promoter: 'I am loading $ABCD now!'")
        self.assertEqual(reading.operations, {})
        self.assertEqual(reading.quoted_assets, ["$ABCD"])

    def test_short_cover_is_not_a_long_entry(self):
        self.assertEqual(self.op("I am closing the old $ABCD short here.", "$ABCD"), "COVER")
        self.assertEqual(self.op("Covered the $ABCD short this afternoon.", "$ABCD"), "COVER")

    def test_opening_a_short_is_not_an_entry(self):
        self.assertEqual(self.op("Opening a short on $ABCD at 3.40.", "$ABCD"), "SHORT")

    def test_taking_profit_is_an_exit(self):
        self.assertEqual(self.op("I am taking profits on $ABCD here.", "$ABCD"), "EXIT")

    def test_negated_entry_is_a_disclaimer(self):
        reading = read("I am not initiating a long position in $ABCD.")
        self.assertNotEqual(reading.operations["$ABCD"][0], "ENTRY")
        self.assertIn("DISCLAIMER", reading.flags)

    def test_conditional_entry_is_set_aside(self):
        reading = read("If $ABCD closes a daily candle above 0.55, I will buy it.")
        self.assertEqual(reading.set_aside, "CONDITIONAL")
        self.assertNotEqual(reading.operations["$ABCD"][0], "ENTRY")

    def test_undated_purchase_is_separate_from_dated_past(self):
        self.assertEqual(self.op("I bought some $ABCD.", "$ABCD"), "UNDATED_PURCHASE")
        self.assertEqual(self.op("Last summer I acquired $ABCD.", "$ABCD"), "PAST")

    def test_same_day_purchase_claim_is_an_entry(self):
        reading = read("I just bought $ABCD this morning.")
        self.assertEqual(reading.operations["$ABCD"], ("ENTRY", "purchase_claim"))

    def test_entry_beats_holding_in_one_sentence(self):
        self.assertEqual(self.op("Still holding $ABCD and adding more today.", "$ABCD"), "ENTRY")

    def test_rotation_keeps_assets_apart(self):
        reading = read("I am selling $AAAA and buying $BBBB today.")
        self.assertEqual(reading.operations["$AAAA"][0], "EXIT")
        self.assertEqual(reading.operations["$BBBB"][0], "ENTRY")

    def test_genuine_question_is_not_an_entry(self):
        reading = read("Should I start a $ABCD position today?")
        self.assertEqual(reading.set_aside, "QUESTION")

    def test_boilerplate_does_not_disclaim(self):
        self.assertNotIn("DISCLAIMER", read("Adding $ABCD here, not financial advice.").flags)

    def test_contrast_with_another_speaker_is_not_a_disclaimer(self):
        reading = read("That is my own current recommendation, not the announcement writer's instruction.")
        self.assertNotIn("DISCLAIMER", reading.flags)


if __name__ == "__main__":
    unittest.main()
