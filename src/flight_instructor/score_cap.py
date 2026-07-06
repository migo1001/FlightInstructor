class ScoreCap:
    """
    A ceiling applied to the overall score after a serious or critical violation.

    Caps are independent of maluses. A cap at 65 means the final score cannot
    exceed 65, regardless of how well the rest of the flight went. Multiple caps
    stack: the most restrictive one (lowest value) determines the ceiling.
    """

    def __init__(self, max_score, reason, timestamp):
        """
        Create a score cap.

        max_score — the highest score achievable after this cap is applied
        reason    — human-readable description for the debrief
        timestamp — session time in seconds when the cap was triggered
        """
        self.max_score = max_score
        self.reason = reason
        self.timestamp = timestamp

    def __repr__(self):
        return f"ScoreCap(max={self.max_score}, t={self.timestamp:.1f})"
