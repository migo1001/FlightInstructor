from flight_instructor.score_cap import ScoreCap


class LuaScoreApi:
    """
    Exposes score-level operations to Lua (currently only cap()).

    Lua rules call `score.cap(70, "unstable approach")` to place a ceiling
    on the overall flight score.
    """

    def __init__(self, score_card):
        """Bind the score card that cap() will write to."""
        self._score_card = score_card
        self._timestamp = 0.0

    def set_timestamp(self, timestamp):
        """Update the timestamp used for caps recorded this frame."""
        self._timestamp = timestamp

    def set_score_card(self, score_card):
        """Swap in a new score card (called at the start of each evaluate())."""
        self._score_card = score_card

    def cap(self, max_score, reason):
        """Apply a score ceiling."""
        self._score_card.add_cap(ScoreCap(
            max_score=int(max_score),
            reason=str(reason),
            timestamp=self._timestamp,
        ))
