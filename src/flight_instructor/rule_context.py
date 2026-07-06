class RuleContext:
    """
    Everything a rule needs to evaluate one telemetry frame.

    Passing a single context object keeps rule signatures stable as the
    system grows — adding aircraft profile, session metadata, or other
    context requires no signature changes to existing rules.
    """

    def __init__(self, state, phase, events, score_card, timestamp):
        """Bundle a single telemetry frame for rule evaluation."""
        self.state = state
        self.phase = phase
        self.events = events
        self.score_card = score_card
        self.timestamp = timestamp
