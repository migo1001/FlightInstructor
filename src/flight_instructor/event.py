class Event:
    """
    A discrete flight event captured at a specific moment in the session.

    The data dict carries event-specific context — for example, LIFTOFF carries
    the indicated airspeed at the moment of rotation. Most events carry no data.
    """

    def __init__(self, event_type, timestamp, **data):
        """Create an event of the given type at the given timestamp."""
        self.event_type = event_type
        self.timestamp = timestamp
        self.data = data

    def __repr__(self):
        return f"Event({self.event_type.value}, t={self.timestamp:.2f}, data={self.data})"
