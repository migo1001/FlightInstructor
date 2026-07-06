from flight_instructor.score_card import ScoreCard
from flight_instructor.score_cap import ScoreCap
from flight_instructor.score_category import ScoreCategory
from flight_instructor.violation import Violation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _v(malus, category=ScoreCategory.PROCEDURES, timestamp=0.0, description="test violation", **evidence):
    """Build a Violation with minimal boilerplate."""
    return Violation(category=category, malus=malus, description=description, timestamp=timestamp, **evidence)


def _cap(max_score, timestamp=0.0, reason="test cap"):
    """Build a ScoreCap with minimal boilerplate."""
    return ScoreCap(max_score=max_score, reason=reason, timestamp=timestamp)


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------

class TestInitialState:
    def test_score_starts_at_100(self):
        assert ScoreCard().score() == 100

    def test_raw_score_starts_at_100(self):
        assert ScoreCard().raw_score() == 100

    def test_all_category_scores_start_at_100(self):
        card = ScoreCard()
        for category in ScoreCategory:
            assert card.category_score(category) == 100

    def test_no_violations_recorded(self):
        assert ScoreCard().violations() == []

    def test_no_active_caps(self):
        assert ScoreCard().active_caps() == []


# ---------------------------------------------------------------------------
# Maluses
# ---------------------------------------------------------------------------

class TestMaluses:
    def test_single_violation_reduces_score(self):
        card = ScoreCard()
        card.add_violation(_v(malus=10))
        assert card.score() == 90

    def test_multiple_violations_accumulate(self):
        card = ScoreCard()
        card.add_violation(_v(malus=5))
        card.add_violation(_v(malus=8))
        card.add_violation(_v(malus=3))
        assert card.score() == 84

    def test_score_cannot_go_below_zero(self):
        card = ScoreCard()
        card.add_violation(_v(malus=150))
        assert card.score() == 0

    def test_raw_score_also_floors_at_zero(self):
        card = ScoreCard()
        card.add_violation(_v(malus=150))
        assert card.raw_score() == 0

    def test_score_from_description_example(self):
        """Reproduce the worked example from the design document."""
        card = ScoreCard()
        card.add_violation(_v(malus=5, description="Forgot landing light"))
        card.add_violation(_v(malus=4, description="Taxi speed excessive"))
        card.add_violation(_v(malus=25, description="Approach sink rate 2000 fpm"))
        card.add_violation(_v(malus=20, description="Bank angle 45 deg on final"))
        assert card.raw_score() == 46


# ---------------------------------------------------------------------------
# Score caps
# ---------------------------------------------------------------------------

class TestScoreCaps:
    def test_cap_limits_final_score_when_raw_is_above_cap(self):
        card = ScoreCard()
        card.add_cap(_cap(max_score=65))
        card.add_violation(_v(malus=5))
        # raw = 95, cap = 65 → final = 65
        assert card.score() == 65

    def test_cap_has_no_effect_when_raw_is_already_below_cap(self):
        card = ScoreCard()
        card.add_cap(_cap(max_score=65))
        card.add_violation(_v(malus=50))
        # raw = 50, cap = 65 → final = 50
        assert card.score() == 50

    def test_most_restrictive_cap_of_several_applies(self):
        card = ScoreCard()
        card.add_cap(_cap(max_score=70, reason="serious deviation"))
        card.add_cap(_cap(max_score=50, reason="critical violation"))
        # raw = 100, caps = [70, 50] → final = 50
        assert card.score() == 50

    def test_raw_score_is_never_affected_by_caps(self):
        card = ScoreCard()
        card.add_cap(_cap(max_score=65))
        card.add_violation(_v(malus=5))
        assert card.raw_score() == 95
        assert card.score() == 65

    def test_caps_do_not_affect_category_scores(self):
        card = ScoreCard()
        card.add_cap(_cap(max_score=30))
        card.add_violation(_v(malus=5, category=ScoreCategory.SAFETY))
        assert card.category_score(ScoreCategory.SAFETY) == 95
        assert card.score() == 30

    def test_fatal_cap_at_zero_results_in_zero_score(self):
        card = ScoreCard()
        card.add_cap(_cap(max_score=0, reason="crash"))
        assert card.score() == 0

    def test_cap_with_no_violations_still_limits_score(self):
        card = ScoreCard()
        card.add_cap(_cap(max_score=65))
        # raw = 100, cap = 65 → final = 65
        assert card.score() == 65

    def test_description_example_with_cap(self):
        """Cap at 65 on a raw score of 46 — cap has no additional effect."""
        card = ScoreCard()
        card.add_violation(_v(malus=5))
        card.add_violation(_v(malus=4))
        card.add_violation(_v(malus=25))
        card.add_violation(_v(malus=20))
        card.add_cap(_cap(max_score=65, reason="Unstable approach continued below 500 ft"))
        # raw = 46, cap = 65 → final = 46 (raw already below cap)
        assert card.raw_score() == 46
        assert card.score() == 46


# ---------------------------------------------------------------------------
# Active caps reporting
# ---------------------------------------------------------------------------

class TestActiveCaps:
    def test_active_caps_returns_only_caps_that_limit_the_score(self):
        card = ScoreCard()
        limiting = _cap(max_score=65, reason="unstable approach")
        not_limiting = _cap(max_score=90, reason="minor issue")
        card.add_cap(limiting)
        card.add_cap(not_limiting)
        card.add_violation(_v(malus=5))
        # raw = 95; 65 < 95 → limiting; 90 < 95 → also limiting
        active = card.active_caps()
        assert limiting in active
        assert not_limiting in active

    def test_cap_is_not_active_when_raw_score_is_below_it(self):
        card = ScoreCard()
        cap = _cap(max_score=65)
        card.add_cap(cap)
        card.add_violation(_v(malus=50))
        # raw = 50, cap = 65 → cap not active
        assert cap not in card.active_caps()

    def test_no_active_caps_when_score_card_is_clean(self):
        card = ScoreCard()
        card.add_cap(_cap(max_score=65))
        # raw = 100, no violations but cap IS active (65 < 100)
        assert _cap(max_score=65) not in card.active_caps()

    def test_active_caps_returns_cap_objects_not_scores(self):
        card = ScoreCard()
        cap = _cap(max_score=65)
        card.add_cap(cap)
        card.add_violation(_v(malus=5))
        active = card.active_caps()
        assert len(active) == 1
        assert active[0].max_score == 65
        assert active[0].reason == "test cap"


# ---------------------------------------------------------------------------
# Category scores
# ---------------------------------------------------------------------------

class TestCategoryScores:
    def test_category_score_only_counts_its_own_violations(self):
        card = ScoreCard()
        card.add_violation(_v(malus=10, category=ScoreCategory.SAFETY))
        card.add_violation(_v(malus=15, category=ScoreCategory.PROCEDURES))
        assert card.category_score(ScoreCategory.SAFETY) == 90
        assert card.category_score(ScoreCategory.PROCEDURES) == 85

    def test_violation_does_not_affect_other_categories(self):
        card = ScoreCard()
        card.add_violation(_v(malus=20, category=ScoreCategory.SAFETY))
        assert card.category_score(ScoreCategory.PROCEDURES) == 100
        assert card.category_score(ScoreCategory.AIRCRAFT_CARE) == 100
        assert card.category_score(ScoreCategory.AIRCRAFT_HANDLING) == 100
        assert card.category_score(ScoreCategory.NAVIGATION) == 100

    def test_category_score_cannot_go_below_zero(self):
        card = ScoreCard()
        card.add_violation(_v(malus=200, category=ScoreCategory.SAFETY))
        assert card.category_score(ScoreCategory.SAFETY) == 0

    def test_multiple_violations_in_same_category_accumulate(self):
        card = ScoreCard()
        card.add_violation(_v(malus=8, category=ScoreCategory.SAFETY))
        card.add_violation(_v(malus=12, category=ScoreCategory.SAFETY))
        assert card.category_score(ScoreCategory.SAFETY) == 80

    def test_overall_score_includes_all_categories(self):
        """Overall score is not an average of category scores — all maluses sum."""
        card = ScoreCard()
        card.add_violation(_v(malus=10, category=ScoreCategory.SAFETY))
        card.add_violation(_v(malus=10, category=ScoreCategory.PROCEDURES))
        assert card.score() == 80
        assert card.category_score(ScoreCategory.SAFETY) == 90
        assert card.category_score(ScoreCategory.PROCEDURES) == 90


# ---------------------------------------------------------------------------
# Violation recording
# ---------------------------------------------------------------------------

class TestViolationRecording:
    def test_violations_are_stored(self):
        card = ScoreCard()
        v = _v(malus=5)
        card.add_violation(v)
        assert v in card.violations()

    def test_violations_preserved_in_insertion_order(self):
        card = ScoreCard()
        v1 = _v(malus=5, timestamp=1.0)
        v2 = _v(malus=8, timestamp=2.0)
        v3 = _v(malus=3, timestamp=3.0)
        card.add_violation(v1)
        card.add_violation(v2)
        card.add_violation(v3)
        assert card.violations() == [v1, v2, v3]

    def test_violation_evidence_is_accessible(self):
        card = ScoreCard()
        v = Violation(
            category=ScoreCategory.SAFETY,
            malus=10,
            description="Taxi speed 33 kt for 8 seconds. Limit: 20 kt.",
            timestamp=14.0,
            max_speed_kt=33.0,
            duration_seconds=8.0,
        )
        card.add_violation(v)
        assert card.violations()[0].evidence["max_speed_kt"] == 33.0
        assert card.violations()[0].evidence["duration_seconds"] == 8.0

    def test_violation_severity_is_preserved(self):
        from flight_instructor.severity import Severity
        card = ScoreCard()
        v = Violation(
            category=ScoreCategory.SAFETY,
            malus=25,
            description="Dangerous bank angle on final",
            timestamp=60.0,
            severity=Severity.CRITICAL,
        )
        card.add_violation(v)
        assert card.violations()[0].severity == Severity.CRITICAL
