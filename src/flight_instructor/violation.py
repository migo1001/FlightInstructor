class Violation:
    """
    A single scoring penalty recorded during a flight.

    The malus is a positive integer representing points deducted from the score.
    Evidence kwargs carry the raw data that justified the penalty — used in
    the debrief report to explain exactly what happened and when.
    """

    def __init__(self, category, malus, description, timestamp, severity=None, **evidence):
        """
        Create a violation.

        category    — ScoreCategory this penalty belongs to
        malus       — points to deduct (positive integer)
        description — human-readable explanation for the debrief
        timestamp   — session time in seconds when the violation was detected
        severity    — optional Severity enum value for reporting
        evidence    — arbitrary keyword arguments stored as context data
        """
        self.category = category
        self.malus = malus
        self.description = description
        self.timestamp = timestamp
        self.severity = severity
        self.evidence = evidence

    def __repr__(self):
        return f"Violation({self.category.value}, -{self.malus}, t={self.timestamp:.1f})"
