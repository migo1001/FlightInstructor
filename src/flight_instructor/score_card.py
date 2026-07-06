class ScoreCard:
    """
    Tracks the score for a single flight session.

    The overall score starts at 100. Every violation subtracts its malus.
    Score caps place a ceiling on the final score — a pilot who continues an
    unstable approach cannot fully recover their score with procedural compliance.
    Category scores are calculated independently from the overall score and are
    not affected by caps.
    """

    BASE_SCORE = 100

    def __init__(self):
        """Initialise a clean score card for a new session."""
        self._violations = []
        self._caps = []

    def violations(self):
        """Return all recorded violations."""
        return list(self._violations)

    def add_violation(self, violation):
        """Record a penalty against the flight score."""
        self._violations.append(violation)

    def add_cap(self, cap):
        """Apply a ceiling to the overall score after a serious event."""
        self._caps.append(cap)

    def score(self):
        """Final overall score after all maluses and the most restrictive cap."""
        effective_cap = min(
            (c.max_score for c in self._caps),
            default=self.BASE_SCORE,
        )
        return min(self.raw_score(), effective_cap)

    def raw_score(self):
        """Overall score after maluses only, before caps are applied."""
        total_malus = sum(v.malus for v in self._violations)
        return max(0, self.BASE_SCORE - total_malus)

    def category_score(self, category):
        """
        Score for one category, calculated independently of all other categories
        and unaffected by caps.
        """
        total_malus = sum(v.malus for v in self._violations if v.category == category)
        return max(0, self.BASE_SCORE - total_malus)

    def active_caps(self):
        """
        Return caps that are actually limiting the score.

        A cap is active when its ceiling is strictly below the raw score,
        meaning it has reduced (or would reduce) the final score.
        """
        raw = self.raw_score()
        return [c for c in self._caps if c.max_score < raw]
