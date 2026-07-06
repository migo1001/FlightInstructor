# Flight Procedure Evaluator for Microsoft Flight Simulator

## 1. Project Goal

The goal of this project is to build an external application for Microsoft Flight Simulator 2020, and later possibly Microsoft Flight Simulator 2024, that monitors the behavior of a virtual pilot from cold start to complete shutdown.

The application evaluates whether the pilot follows aircraft procedures, flight rules, safety principles, and good aircraft-management practices.

The product is not a simple checklist application. It is a post-flight and optionally real-time evaluator that behaves more like a virtual instructor or examiner.

The core idea is:

```text
Start with 100 points.
Detect reliable procedural, safety, and aircraft-care mistakes.
Apply maluses only when the evidence is strong.
Generate a detailed debrief explaining every lost point.
Keep history so the user can track improvement over time.
```

The first target aircraft is the default Cessna 172 in MSFS 2020.

The long-term goal is to support multiple aircraft through reusable global rules and aircraft-specific rule profiles.

---

## 2. Design Philosophy

### 2.1 Evidence-Based Scoring

The application must avoid unfair penalties.

A user must feel:

```text
I deserved that penalty.
```

Not:

```text
The app misunderstood the simulator.
```

Therefore:

```text
No reliable data = no penalty.
Ambiguous situation = warning or note only.
Optional procedure = ignored unless strict mode enables it.
Unsupported aircraft feature = ignored.
```

The project must prefer missing a minor mistake over creating false penalties.

### 2.2 Conservative Rule Enforcement

Every rule should have a confidence level.

Suggested categories:

| Reliability class | Meaning | Action |
|---|---|---|
| Reliable | Data is exposed and rule is clear | Can apply malus |
| Probable | Data is probably correct but context matters | Small malus or warning |
| Ambiguous | Optional SOP, unclear context, or weak data | Debrief note only |
| Unsupported | Required data unavailable | Ignore |

### 2.3 Context Matters

The same pilot action may be correct or incorrect depending on context.

Examples:

```text
45° bank at 5,000 ft during maneuvering: probably acceptable.
45° bank at 300 ft AGL on final: dangerous.
Landing light off during cruise: probably fine.
Landing light off during takeoff: procedural issue.
Full-rich mixture at low altitude: normal.
Full-rich mixture during long high-altitude cruise: maybe inefficient, but not always a strong penalty.
```

Rules must be phase-aware and aircraft-aware.

### 2.4 Do Not Penalize Optional or Poorly Simulated Items

Checks should be ignored if they are:

- optional,
- not reliably simulated,
- aircraft-specific but unsupported,
- dependent on procedures that vary between operators,
- impossible to detect confidently,
- only visual walkaround items not exposed by simulator data.

Examples likely to be ignored in early versions:

- departure briefing,
- passenger briefing,
- seat belts,
- paperwork,
- ATIS listening, unless a reliable radio/ATC model is added,
- exact heading indicator alignment if unreliable,
- subtle cockpit flow ordering if the simulator does not expose it cleanly.

### 2.5 Score Is Useful, Debrief Is More Useful

The score gives a measurable result, but the real value is the debrief.

The report should explain:

- what happened,
- when it happened,
- why it mattered,
- how severe it was,
- what evidence was used,
- what the pilot should have done instead.

Example:

```text
14:03:22 - Taxi speed reached 33 kt for 8 seconds.
Limit: 20 kt normal taxi, 30 kt serious threshold.
Penalty: -10.
Comment: Taxi speed was excessive. This would be unsafe near ramps, crossings, or other aircraft.
```

---

## 3. Product Modes

The application should eventually support several modes.

### 3.1 Examiner Mode

Default mode.

- No pop-ups during flight.
- No interruptions.
- All analysis is presented after shutdown.
- Best for immersion and serious simmers.

### 3.2 Instructor Mode

Optional mode.

- Provides short real-time feedback.
- Uses professional, concise messages.
- Avoids jokes and repeated nagging.

Examples:

```text
Taxi speed.
Check oil pressure.
Landing light.
Sink rate.
Go around.
```

### 3.3 Student Mode

Optional mode.

- More explanatory.
- Gives more context.
- Suitable for beginners.

Example:

```text
Your taxi speed is 28 kt. Recommended maximum is about 20 kt.
```

### 3.4 Strict Examiner Mode

Optional mode.

- Silent during flight.
- Applies stricter SOP rules.
- Critical mistakes may cap the score or fail the flight.

---

## 4. High-Level Architecture

The application is external to MSFS and connects through SimConnect.

The chosen implementation language is Python.

Lua is used for global and aircraft-specific scoring rules.

```text
MSFS 2020
    ↓
SimConnect
    ↓
Python telemetry collector
    ↓
Python normalization layer
    ↓
Python state model
    ↓
Python event detector
    ↓
Lua global rules
    ↓
Lua aircraft-specific rules
    ↓
Python scoring/reporting engine
    ↓
SQLite database
    ↓
FastAPI/browser UI
```

### 4.1 Python Responsibilities

Python handles:

- SimConnect connection,
- telemetry polling,
- data normalization,
- aircraft state model,
- phase detection,
- event detection,
- rule execution environment,
- Lua sandbox integration,
- database storage,
- history,
- report generation,
- browser UI,
- packaging as a Windows executable.

### 4.2 Lua Responsibilities

Lua handles:

- global scoring rules,
- aircraft-specific scoring rules,
- procedural maluses,
- safety maluses,
- aircraft-care maluses,
- score caps,
- report comments,
- optional instructor messages.

Lua should not directly handle:

- SimConnect,
- raw simulator polling,
- database access,
- UI,
- file system writes,
- networking,
- application lifecycle.

Lua is a rules language, not the application framework.

---

## 5. Python and Lua Split

### 5.1 Core Principle

Lua should consume clean facts, not raw SimVars.

Bad:

```lua
if simvar("LIGHT BEACON") == 0 and simvar("GROUND VELOCITY") > 1 then
    apply_malus(-8)
end
```

Good:

```lua
if phase == TAXI and lights.beacon == OFF then
    procedures:malus(8)
    report:add("Beacon lights are off during taxi.")
end
```

Even better:

```lua
if phase == TAXI and not runup.completed then
    procedures:malus(15)
    report:add("Taxi began before run-up was completed.")
end
```

Python does the ugly work:

```text
Raw SimVars → normalized state → derived facts → events → Lua rules
```

Lua stays readable and aircraft-focused.

### 5.2 Exposed Lua State Model

Lua rules should see a structured state object.

Example conceptual model:

```lua
phase = TAXI

aircraft.type = "C172"
aircraft.profile = "default_c172"

engine.running = true
engine.rpm = 950
engine.oil_pressure = NORMAL
engine.oil_temperature = COLD
engine.cht = NORMAL

lights.beacon = ON
lights.taxi = OFF
lights.landing = OFF
lights.nav = ON
lights.strobe = OFF

position.on_ground = true
position.on_runway = false
position.in_parking_area = false
position.ground_speed = 8

controls.flaps = 0
controls.trim_takeoff_ok = true

runup.completed = false
weather.is_night = false
weather.imc_probability = LOW
```

### 5.3 Lua Rule Style

A readable rule might look like:

```lua
rule "Beacon during taxi"

if phase == TAXI and lights.beacon == OFF then
    procedures:malus(8)
    report:add("Beacon lights are off during taxi.")
end
```

For more complex checks:

```lua
rule "Dangerous final approach"

if phase == APPROACH
   and position.agl < 500
   and flight.vertical_speed_fpm < -1000
   and attitude.bank_degrees > 30 then
    safety:malus(25)
    score:cap(65)
    report:add("Unstable approach continued below 500 ft AGL. Go-around recommended.")
end
```

### 5.4 Rule Execution Model

The system should avoid running every rule blindly at high frequency if possible.

Preferred model:

```text
Telemetry sample received
    ↓
State updated
    ↓
Events generated if something meaningful changed
    ↓
Only relevant rules executed
```

Examples of events:

```text
EVENT_SESSION_STARTED
EVENT_ENGINE_STARTED
EVENT_TAXI_STARTED
EVENT_ENTERED_RUNWAY
EVENT_TAKEOFF_ROLL_STARTED
EVENT_ROTATED
EVENT_LIFTOFF
EVENT_CLIMB_STARTED
EVENT_CRUISE_STARTED
EVENT_DESCENT_STARTED
EVENT_APPROACH_STARTED
EVENT_TOUCHDOWN
EVENT_TAXI_IN_STARTED
EVENT_ENGINE_STOPPED
EVENT_SESSION_ENDED
```

Rules may be event-driven, phase-driven, or continuous.

---

## 6. Data Sources

### 6.1 SimConnect

The application retrieves data through SimConnect.

Expected data includes:

- latitude,
- longitude,
- altitude,
- altitude above ground,
- ground speed,
- indicated airspeed,
- vertical speed,
- pitch,
- bank,
- heading,
- on-ground status,
- engine RPM,
- oil pressure,
- oil temperature,
- CHT if available,
- fuel quantity,
- fuel selector state,
- mixture,
- throttle,
- flaps,
- elevator trim,
- parking brake,
- wheel brakes,
- beacon light,
- nav light,
- taxi light,
- landing light,
- strobe light,
- transponder state if available,
- pitot heat,
- outside air temperature,
- pressure,
- weather/visibility where available.

### 6.2 Airport and Runway Data

The app should eventually determine whether the aircraft is:

- on a runway,
- on a taxiway,
- in a parking/ramp/gate area,
- near a hold-short line,
- taking off from a valid runway,
- shutting down in a valid parking area.

This may require:

- MSFS facility data,
- runway geometry,
- taxi parking data,
- external navigation or airport databases,
- derived geometry calculations.

### 6.3 Airspace Data

Controlled airspace detection is desirable but not part of the first MVP.

Long-term checks could include:

- Class C or above violations,
- prohibited/restricted airspace,
- VFR into controlled airspace without required configuration,
- VFR into IMC,
- altitude restrictions.

This requires a reliable airspace database. SimConnect alone is not expected to provide a simple `current_airspace_class` variable.

---

## 7. Scoring Model

### 7.1 Overall Score

The flight starts at 100.

Penalties subtract points.

Score caps may limit the maximum possible score after serious or critical violations.

Example:

```text
Base score: 100

Forgot landing light: -5
Taxi speed excessive: -4
Approach sink rate 2,000 ft/min: -25
Bank angle 45° on final: -20

Raw score: 46

Safety cap: unstable approach continued below 500 ft = max 65

Final score: 46
```

### 7.2 Score Categories

Use separate category scores.

Suggested categories:

```text
Procedures
Safety
Aircraft handling
Aircraft care
Navigation / airspace
ATC compliance, optional later
```

Example report:

```text
Overall: 86

Procedures: 92
Safety: 78
Aircraft handling: 84
Aircraft care: 95
Navigation: 88
```

### 7.3 Severity Classes

Suggested severity classes:

| Severity | Penalty range |
|---|---:|
| Minor | -1 to -3 |
| Moderate | -4 to -8 |
| Serious | -10 to -20 |
| Critical | -25 to -50 or score cap |
| Fatal | score 0 |

### 7.4 Score Caps

Some mistakes should cap the maximum score.

Examples:

```text
Crash: final score = 0
Takeoff from taxiway: max score 60
Takeoff with no oil pressure: max score 50
Fuel selector wrong during takeoff: max score 60
Unstable approach continued below 500 ft: max score 65
Runway overrun: max score 50
Shutdown on active runway: max score 60
```

Without caps, a pilot could perform many minor procedures correctly and still receive an acceptable score after a dangerous event. That would be wrong.

### 7.5 Time-Based Penalties

Some issues should accumulate over time instead of triggering instantly.

Examples:

```text
CHT high for 30 seconds: note only
CHT high for 10 minutes: -5
CHT very high for 20 minutes: -15
```

This applies to:

- engine temperature,
- oil temperature,
- excessive RPM,
- fuel reserve,
- brake abuse,
- pitot heat in icing-risk conditions,
- VFR in IMC,
- overspeed.

---

## 8. Database and History

Use SQLite for the first version.

Store:

- flight sessions,
- aircraft profile used,
- profile version,
- simulator version if available,
- start time,
- end time,
- departure airport if detected,
- arrival airport if detected,
- raw telemetry, possibly compressed or sampled,
- events,
- rule violations,
- warnings,
- notes,
- score categories,
- final score,
- score caps,
- report text.

Important: store the aircraft profile version and rule version.

If the rules change later, old scores should remain reproducible.

### 8.1 Suggested Stored Objects

```text
FlightSession
TelemetrySample
DetectedEvent
RuleEvaluation
Violation
ScoreCategory
ScoreCap
AircraftProfile
RulePackVersion
```

### 8.2 Telemetry Retention

Raw telemetry can become large.

Possible approach:

```text
Always store events and violations.
Store low-frequency telemetry for charts.
Optionally store full telemetry for debug mode only.
```

---

## 9. Aircraft Profiles

### 9.1 Purpose

Aircraft profiles define how an aircraft should be interpreted and scored.

They include:

- aircraft name,
- supported simulator aircraft identifiers,
- required SimVars,
- optional SimVars,
- state normalization rules,
- phase thresholds,
- expected procedures,
- enabled/disabled global rules,
- aircraft-specific Lua rules,
- rule severity overrides,
- score weights,
- score caps,
- supported feature coverage.

### 9.2 Coverage

Each profile should report how much of the intended rule set is supported.

Example:

```text
Default C172:
Coverage: 98%

Fenix A320:
Coverage: 76%

PMDG 737:
Coverage: 71%
```

This avoids misleading users. If a plane does not expose a reliable variable, related checks should be disabled.

### 9.3 Global Rules vs Aircraft Rules

Use shared global rules for common concepts:

```text
taxi discipline
takeoff configuration
engine abuse
approach stability
landing quality
shutdown location
weather/light logic
airspace warnings
```

Aircraft-specific profiles adapt those rules:

```text
C172:
- fuel selector BOTH
- mixture rich for takeoff
- carb heat off for takeoff
- flaps 0 or 10 depending takeoff type
- CHT/oil limits

A320:
- packs/bleeds/APU logic
- flight directors
- autobrake
- spoilers armed
- managed/selected modes
- flap/slat config
- ECAM status
```

---

## 10. Flight Phases

The app must detect phases robustly.

Suggested phases:

```text
SESSION_START
COLD_AND_DARK
PREFLIGHT
ENGINE_START
POST_START
PRE_TAXI
TAXI_OUT
RUNUP
HOLD_SHORT
LINEUP
TAKEOFF_ROLL
ROTATION
INITIAL_CLIMB
CLIMB
CRUISE
DESCENT
APPROACH
FINAL
LANDING
ROLLOUT
TAXI_IN
PARKING
SHUTDOWN
SECURED
SESSION_END
```

Phase detection should be conservative.

Avoid changing phase based on a single noisy telemetry sample.

Use hysteresis and duration thresholds.

Example:

```text
Taxi starts only when:
- on ground,
- engine running,
- ground speed above threshold for several seconds,
- not on runway takeoff roll.
```

---

## 11. MVP Scope

### 11.1 First MVP

The first MVP should be deliberately small.

Target:

```text
MSFS 2020
Default Cessna 172
External Python app
Silent monitoring
Post-flight report
SQLite storage
No complex UI
No A320
No online accounts
No cloud sync
No installer at first
```

Flight scope:

```text
Cold start
Pre-taxi
Taxi
Run-up
Takeoff
Initial climb
```

Minimum features:

```text
Connect to MSFS
Read 10-20 reliable variables
Detect basic phases
Generate event log
Run Lua rules
Apply penalties
Produce final report
Store flight history
```

### 11.2 Variables for First MVP

Initial variables should include:

```text
latitude
longitude
altitude
AGL altitude
on ground
ground speed
indicated airspeed
vertical speed
pitch
bank
heading
engine RPM
oil pressure
oil temperature
parking brake
brakes
beacon light
taxi light
landing light
nav light
flaps
trim
fuel selector
mixture
throttle
```

### 11.3 First MVP Rules

Suggested first rules:

```text
Started from runway
Engine already running when cold-start expected
Parking brake not set during start
Beacon off before engine start
Fuel selector not BOTH
Mixture incorrect before start/takeoff
Excessive throttle before start
Starter abuse
Oil pressure not rising after start
Alternator off after start
Avionics timing issue, if reliable
Taxi light off while taxiing
Taxi speed too high
Power against brakes
Taxi before engine stabilized
Run-up not completed
Magneto check not completed, if detectable
Flaps wrong for takeoff
Trim outside takeoff range
Landing light off for takeoff
Takeoff from taxiway
Takeoff from runway mismatch
Takeoff power not reached
Airspeed not alive
Rotate too early
Rotate too late
Stall warning after liftoff, if available
Dangerous bank after liftoff
```

---

## 12. C172 Rule Inventory

### 12.1 Before Taxi / Cold Start

Potential checks:

```text
Started directly on runway
Not cold and dark when expected
Parking brake not set during start
Battery/master sequence issue
Beacon off before engine start
Fuel selector not BOTH
Fuel quantity too low
Mixture not rich before normal start
Throttle excessive before start
Starter abuse
Engine RPM spike after start
Oil pressure not rising after start
Alternator/generator left off after engine running
Avionics on before engine stable
Avionics still off before taxi
Transponder not ready before taxi, optional
Flaps incorrect for taxi/pre-takeoff
Elevator trim far outside takeoff range
Control movement check not observed
Taxi light off before movement
Nav lights off at night
Pitot heat off in icing-risk conditions
Taxi power applied with parking brake set
High throttle while brakes held
Taxi before RPM/oil pressure stable
Door/canopy open if exposed
High power with cold oil
Altimeter setting wrong if reliable
Spawned outside valid parking/ramp area
```

### 12.2 Taxi

Potential checks:

```text
Parking brake still set while moving
Taxi light off while taxiing
Beacon off while engine running
Navigation lights off at night
Taxi speed over normal threshold
Taxi speed over serious threshold
Excessive braking
Power against brakes
Excessive RPM while taxiing
High power before oil temperature acceptable
Sharp turns at excessive speed
Incorrect flaps for taxi/pre-takeoff profile
Trim far from takeoff setting
Mixture unsuitable for altitude, optional
Magnetos switched incorrectly
Alternator off
Fuel selector not BOTH
Pitot heat misuse depending on weather
Carb heat misuse if reliable
Taxi with low oil pressure
Taxi despite abnormal engine condition
No control check before runway
No instrument movement check, likely note only
No run-up before takeoff
No magneto check
No carb heat check
No idle check
No suction/vacuum check if reliable
No ammeter/alternator check if reliable
Doors/windows not secured if detectable
```

### 12.3 Takeoff

Potential checks:

```text
Run-up not completed
Magneto check not completed
Flight controls not checked
Elevator trim outside takeoff range
Wrong flap setting
Fuel selector not BOTH
Mixture not rich/suitable
Carb heat on during takeoff
Beacon off
Landing light off
Strobe off on runway if modeled
Pitot heat off in icing/cold moisture
Transponder not ALT/ON if reliable
Heading/runway mismatch
Takeoff roll not on runway
Rolling takeoff without line-up stop, optional
High RPM while brakes applied
Expected takeoff RPM not reached
Takeoff with insufficient power
Ignored rejected-takeoff condition
Airspeed not alive
Rotate too early
Rotate too late
Excessive pitch-up after rotation
Low climb speed
Very high climb speed
Stall warning after liftoff
Excessive bank below safe altitude
Turn too early
Poor runway tracking
Tailwind takeoff above threshold
Crosswind above aircraft/user threshold
Poor climb gradient
Flaps retracted too early
Landing light off too early, minor
CHT/oil temp excessive before takeoff
Cold engine abuse
Door/window open if detectable
Parking brake engaged during takeoff roll
Takeoff from taxiway
Takeoff from invalid surface
```

### 12.4 Cruise

Cruise should have fewer checks.

Potential checks:

```text
Excessive cruise RPM for sustained period
Mixture not leaned during long high-altitude cruise, note or small malus
CHT too high for sustained period
Oil temperature too high
Oil pressure abnormal
Fuel reserve becoming unsafe
Overspeed
Near-stall without reason
Excessive bank without reason
VFR into IMC if confidence high
Night lights misconfigured
Pitot heat off in icing-risk conditions
Route/altitude discipline if flight plan known
```

Cruise rules should be conservative and mostly time-based.

### 12.5 Approach

Potential checks:

```text
Unstable approach below 1000 ft AGL
Unstable approach below 500 ft AGL
Excessive sink rate
Excessive bank angle
Too fast on final
Too slow on final
Stall warning on final
Poor runway alignment
Large heading corrections close to ground
High descent rate with low power
Flaps not set for landing
Landing light off
Mixture not rich/suitable
Fuel selector not BOTH
Carb heat usage if applicable and reliable
Gear down for retractable aircraft, not C172 fixed gear
Pitot heat in icing-risk conditions
Failure to go around after unstable approach
Descending below safe altitude in IMC, later
VFR into IMC, later
```

### 12.6 Landing

Potential checks:

```text
Hard landing
Very hard landing
Bounce
Repeated bounce
Touchdown too fast
Touchdown too slow / near stall
Excessive vertical speed
Side-load / crab if available
Touchdown far from centerline
Touchdown too far down runway
Runway overrun
Runway excursion
Excessive braking
Flaps retracted immediately after touchdown, optional
Loss of directional control
Landing on taxiway
Landing off airport/runway
```

### 12.7 Taxi-In and Shutdown

Potential checks:

```text
Excessive taxi speed after landing
Taxi light not used
Landing light left on unnecessarily, optional
Strobe left on off runway, optional
Engine abuse after landing
Parking brake not set before shutdown
Shutdown before parking
Shutdown on taxiway
Shutdown on runway
Avionics not turned off before master, if reliable
Mixture cutoff/fuel shutdown not performed
Beacon off before engine fully stopped, optional
Master left on after shutdown
Battery drain after shutdown
Fuel selector not closed if profile requires
Lights left on
Aircraft not secured
```

---

## 13. Takeoff Speed Logic

Rotation/liftoff speed should be treated as a window, not a single exact value.

For a C172:

```text
Expected liftoff IAS: roughly 50-60 kt for normal takeoff
Warning zone: 45-50 kt or 60-70 kt
Bad zone: below 45 kt or above 70 kt
```

Do not over-penalize small deviations.

Weight affects stall and takeoff speed. Airport altitude affects takeoff distance and climb performance more than indicated rotation speed.

Suggested early logic:

```text
Detect IAS at liftoff.
Compare to aircraft-profile speed window.
Apply malus only outside broad tolerance.
```

Later enhancement:

```text
Read aircraft weight.
Adjust expected liftoff window slightly:
- light: 48-56 kt
- medium: 50-60 kt
- near max weight: 52-62 kt
```

Density altitude should mainly be used for:

```text
takeoff distance checks
climb performance checks
unsafe runway-length checks
```

Not for heavy-handed rotation-speed penalties.

---

## 14. Aircraft Abuse / Aircraft Care

The app should monitor whether the pilot treats the aircraft properly.

Aircraft-care scoring is separate from pure procedure scoring.

Examples:

```text
Excessive CHT
Excessive oil temperature
Low oil pressure ignored
Full power with cold engine
Starter abuse
High RPM immediately after cold start
Brake riding during taxi
High power against brakes
Flap overspeed
Gear overspeed, for retractable aircraft
Prop overspeed
Turbine hot start, for turbine aircraft
Battery left on after shutdown
```

Engine abuse should often be time-based.

Example:

```text
CHT normal: no penalty
CHT slightly high for 10 minutes: -5
CHT very high for 20 minutes: -15
Extreme overheat: score cap
```

The app could eventually provide an aircraft-care score:

```text
Flight score: 94
Aircraft care: 72

Issues:
- CHT exceeded recommended value for 18 minutes.
- Oil temperature remained high during climb.
- One flap overspeed.
- Heavy braking during taxi.
```

---

## 15. Airspace, Weather, VFR, and IFR

### 15.1 VFR / IFR

The app may detect whether a flight plan is VFR or IFR if the simulator exposes it.

However, legal VFR/IFR compliance is more complex.

The app should distinguish:

```text
Filed flight plan type
Actual flight conditions
Pilot behavior
Weather visibility/cloud condition
Airspace class
```

A pilot can fly IFR in VMC or VFR into IMC. The simulator does not automatically make that judgment for the app.

### 15.2 Night Detection

Night detection is feasible through:

```text
time
latitude
longitude
sun position
ambient light
```

Night can drive lighting rules.

Examples:

```text
Nav lights off at night: penalty
Landing light off during night takeoff: penalty
```

### 15.3 Cloud / IMC Detection

There may not be a perfect Boolean saying “inside cloud”.

Possible inference:

```text
visibility low
cloud layer at aircraft altitude
precipitation
outside visual conditions
weather API data
```

This should be treated probabilistically.

Early rule:

```text
VFR into probable IMC: warning or strict-mode penalty only.
```

### 15.4 Controlled Airspace

Class C or higher violations are desirable long-term but require an airspace database.

Possible checks:

```text
Entered Class C or above without proper mode/transponder/radio requirement
Entered prohibited/restricted area
Violated altitude ceiling/floor
VFR in controlled airspace without required conditions
```

This is not part of the first MVP.

---

## 16. User Interface

### 16.1 Initial UI

Avoid native Windows GUI at first.

Recommended:

```text
FastAPI backend
Local browser UI
SQLite database
Simple HTML/JS frontend
```

The browser UI should show:

```text
current connection status
current aircraft
current phase
current score
detected events
active warnings, if enabled
post-flight report
history
```

### 16.2 Post-Flight Debrief

The debrief should include:

```text
final score
score categories
phase scores
major violations
minor violations
warnings
notes
timeline
charts
evidence for each penalty
recommendations
```

Suggested report structure:

```text
Flight: C172 LFxx → LFyy
Duration: 1h12
Overall score: 86

Phase scores:
Cold start: 92
Taxi: 81
Takeoff: 90
Climb: 95
Cruise: 98
Approach: 72
Landing: 84
Shutdown: 90

Main issue:
Unstable approach continued below 500 ft AGL.

Detailed events:
14:03:22 - Taxi speed reached 33 kt for 8 seconds. -10
14:21:04 - Landing light off during takeoff. -5
15:08:12 - Sink rate exceeded 1,000 ft/min below 500 ft AGL. -15
```

---

## 17. Packaging

The user should not need to install Python.

Development uses Python, but release builds should be packaged as a Windows executable.

Possible tools:

```text
PyInstaller
Nuitka
cx_Freeze
```

Later, create a normal Windows installer using tools such as:

```text
Inno Setup
NSIS
```

User experience goal:

```text
Download
Install
Launch
Connect to MSFS
```

No manual Python installation. No `pip install`.

---

## 18. Development Order

Recommended order:

```text
1. Create project skeleton.
2. Connect to MSFS through Python SimConnect wrapper.
3. Read a minimal set of C172 variables.
4. Print live telemetry to console.
5. Add state normalization.
6. Add basic phase detection.
7. Add event generation.
8. Store session/events in SQLite.
9. Embed Lua.
10. Execute simple Lua rules.
11. Produce a plain text post-flight report.
12. Add simple browser UI.
13. Expand C172 pre-taxi/taxi/takeoff rules.
14. Add history view.
15. Add packaging.
```

Do not start with:

```text
A320 support
complex GUI
Lua for everything
cloud sync
online accounts
MSFS 2024-specific features
full ATC integration
airspace database
```

---

## 19. Major Risks

### 19.1 SimConnect Inconsistency

Different aircraft expose different data.

Default aircraft usually expose standard SimVars.

High-fidelity aircraft may use:

```text
L:Vars
custom events
custom SDKs
proprietary internal systems
```

The application must support aircraft-specific variable mappings.

### 19.2 False Positives

False penalties will damage trust.

Mitigation:

```text
confidence classes
evidence stored for every penalty
disabled rules when data missing
strict mode optional
conservative default rules
```

### 19.3 Phase Detection Errors

Incorrect phase detection can cause wrong penalties.

Mitigation:

```text
hysteresis
duration thresholds
event logs
debug UI
manual override later if needed
```

### 19.4 Performance

Python should be sufficient.

The application is not expected to be CPU-heavy.

Likely sample rates:

```text
1 Hz for slow values
5 Hz for normal state
10 Hz for takeoff/landing-sensitive values
```

The bottleneck is more likely SimConnect polling and data design, not Python speed.

### 19.5 Scope Creep

The project can easily expand into:

```text
full flight school simulator
ATC compliance checker
airspace database
A320 SOP examiner
maintenance simulator
career mode
online leaderboard
```

These are not first-version goals.

---

## 20. Naming Ideas

Possible project names:

```text
Flight Examiner
Virtual Flight Instructor
Flight Discipline
ProcedureCheck
Airmanship
Sim Debrief Examiner
```

Working name:

```text
Flight Procedure Evaluator
```

---

## 21. Final Project Summary

This project is an external Python application for MSFS 2020 that monitors flight telemetry through SimConnect, converts raw data into clean aircraft state and flight events, applies global and per-aircraft Lua rules, and generates evidence-based scoring and debriefs.

The application should be conservative, fair, configurable, and focused on improving pilot behavior.

First target:

```text
Default Cessna 172
MSFS 2020
Cold start to takeoff
Python telemetry/state/UI
Lua rules
SQLite history
Post-flight debrief
```

Long-term target:

```text
Multi-aircraft virtual examiner
Procedural scoring
Safety scoring
Aircraft-care scoring
Flight history
Configurable strictness
Optional instructor mode
```
