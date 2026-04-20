"""
SA Calc Engine — v1.0.0
========================
Python class-based engine that faithfully reproduces the logic of
Sales Aid Calc v0.94.xlsx (Electric Mirror internal tool).

Design Goals
------------
• Data-agnostic: ingests LED/Driver specs via JSON (see reference_data.json)
• Measured-path only: uses the interpolated W/m curve, NOT advertised max W/m
• Validation-aware: reproduces the Red/Green pass-fail state (HE2 cell)
• Scaling: correctly applies Number_of_Strips and Number_of_Drivers inputs

Cell Reference Legend (from original workbook)
-----------------------------------------------
C3  = fixture_length_in        (input)
C4  = num_strips               (input)
C5  = num_drivers              (input)
C8  = dimming_style            (input → GN2 button correction)
C9  = driver_key               (input → GH3 lookup)
C11 = led_style_key            (input → FX3/FY3/FZ3/FW3 lookup)
C12 = button_correction_manual (input, usually 0)

GA2 = actual_length_in         MROUND(C3*25.4, FX3) / 25.4
GB2 = actual_length_m          MROUND(C3*25.4, FX3) / 1000
GC2 = segment_count            FIXED((GB2*1000)/FX3, 1)
GD3 = wm_lower                 W/m at lower bracket bound (VLOOKUP on LED ref)
GE3 = wm_upper                 W/m at upper bracket bound
GF2 = remainder                fractional position within bracket
GG2 = measured_wm              GD3 + (GE3-GD3)*GF2  [Interpolated]
GH3 = driver_rated_w           Lookup driver power (W)
GI2 = DRIVER_BUFFER_PCT        0.15 (15%)
GJ2 = buffered_headroom_w      GH3 * GI2
GK2 = per_strip_ratio          C5 / C4
GL2 = required_w_per_strip     GG2 * GB2
GM2 = buffer_multiplier        ((GL2*C4)/C5) / (GH3 - GJ2)
GN2 = button_correction_w      1 if dimming_style in {AVA, KEEN}, else 0
GO2 = buffered_w_per_driver    (GJ2*GK2*GM2) + GL2 + GN2
C19 = total_system_w           GO2 * (C4/C5)
GT2 = initial_lumens           FIXED(actual_length_in * lumens_per_inch * num_strips, 0)

HC2 = bad_driver_wattage       C19 >= GH3 (required exceeds driver rated)
HD2 = bad_length               GB2 > max_run_m
HB2 = bad_input                any dropdown invalid
HE2 = bad_calc (FAIL state)    HC2 OR HD2 OR HB2 OR any IFNA error
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DRIVER_BUFFER_PCT: float = 0.15          # GI2 — 15% driver headroom
BUTTON_CORRECTION_STYLES: set[str] = {"AVA", "KEEN"}   # dimming styles that add +1W


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class LEDStrip:
    """Physical and photometric properties of one LED strip type."""
    name: str
    em_number: str
    roll_length: str
    max_run_m: float
    color_temp: str
    lumens_per_inch: float
    lumens_per_ft: float
    lumens_per_m: float
    efficiency_lm_w: float
    nominal_wm: float
    max_wm: float
    segment_mm: float        # FX3 — controls length snapping
    pcb_width_mm: float
    l70_hours: int
    cri: str
    led_type: str            # Human-readable product description
    wm_curve: dict[float, Optional[float]]   # {length_m: W/m}
    lux_curve: dict[float, Optional[float]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, name: str, d: dict) -> "LEDStrip":
        raw_wm = d.get("wm_curve", {})
        raw_lux = d.get("lux_curve", {})
        return cls(
            name=name,
            em_number=d["em_number"],
            roll_length=d.get("roll_length", ""),
            max_run_m=float(d["max_run_m"]),
            color_temp=d.get("color_temp", ""),
            lumens_per_inch=float(d["lumens_per_inch"]),
            lumens_per_ft=float(d.get("lumens_per_ft", 0)),
            lumens_per_m=float(d.get("lumens_per_m", 0)),
            efficiency_lm_w=float(d.get("efficiency_lm_w", 0)),
            nominal_wm=float(d.get("nominal_wm", 0)),
            max_wm=float(d.get("max_wm", 0)),
            segment_mm=float(d["segment_mm"]),
            pcb_width_mm=float(d.get("pcb_width_mm", 0)),
            l70_hours=int(d.get("l70_hours", 0)),
            cri=d.get("cri", ""),
            led_type=d.get("led_type", "Replaceable Flex Strips"),
            wm_curve={float(k): (float(v) if v is not None else None)
                      for k, v in raw_wm.items()},
            lux_curve={float(k): (float(v) if v is not None else None)
                       for k, v in raw_lux.items()},
        )


@dataclass
class Driver:
    """Electrical ratings and compatibility flags for one driver."""
    name: str
    dimming_style: str
    mfr_pn: str
    power_factor: float
    efficiency: float
    power_w: float           # GH3 — rated output watts (key validation threshold)
    current_a: float
    input_lower_v: float
    input_separator: str
    input_upper_v: float
    em_use_note: str
    retired: bool
    compatible_lines: dict[str, bool]

    @classmethod
    def from_dict(cls, name: str, d: dict) -> "Driver":
        return cls(
            name=name,
            dimming_style=d.get("dimming_style", ""),
            mfr_pn=d.get("mfr_pn", ""),
            power_factor=float(d.get("power_factor", 1)),
            efficiency=float(d.get("efficiency", 1)),
            power_w=float(d["power_w"]),
            current_a=float(d.get("current_a", 0)),
            input_lower_v=float(d.get("input_lower_v", 0)),
            input_separator=d.get("input_separator", "-"),
            input_upper_v=float(d.get("input_upper_v", 0)),
            em_use_note=d.get("em_use_note", ""),
            retired=bool(d.get("retired", False)),
            compatible_lines=d.get("compatible_lines", {}),
        )


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

@dataclass
class CalcInputs:
    """
    All orange-cell user inputs for one calculation.
    
    Inputs correspond to:
        C3  = fixture_length_in
        C4  = num_strips
        C5  = num_drivers
        C6  = product_line
        C7  = voltage_config
        C8  = dimming_style
        C9  = driver_key     (must match a key in the drivers dict)
        C10 = strip_type     ("STANDARD" or "DIM TO WARM")
        C11 = led_style_key  (must match a key in led_strips dict)
        C12 = button_correction_manual (0 normally, 1 for manual override)
    """
    fixture_length_in: float          # C3
    num_strips: int                   # C4
    num_drivers: int                  # C5
    product_line: str                 # C6
    voltage_config: str               # C7
    dimming_style: str                # C8
    driver_key: str                   # C9
    strip_type: str                   # C10
    led_style_key: str                # C11
    button_correction_manual: int = 0 # C12


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

@dataclass
class CalcOutputs:
    """All computed results from a single engine run."""

    # --- Geometry ---
    actual_length_in: float     # GA2 / C14
    actual_length_m: float      # GB2 / C15
    segment_count: float        # GC2 / C16
    segment_mm: float           # FX3

    # --- Interpolation ---
    measured_wm: float          # GG2 / C23

    # --- Power ---
    required_w_per_strip: float # GL2
    driver_rated_w: float       # GH3
    buffered_headroom_w: float  # GJ2
    per_strip_driver_ratio: float
    buffer_multiplier: float    # GM2
    button_correction_w: int    # GN2 + C12
    buffered_w_per_driver: float  # GO2
    total_system_w: float       # C19 — buffered W/driver × (strips/drivers): VALID check value
    measured_total_w: float     # GL2 × C4 — actual measured strip draw: used for LED Spec WATTAGE + Amps

    # --- Power Requirements (before tech features) ---
    input_power_w: float        # total_system_w / driver_efficiency
    voltage_lower: float        # driver input lower voltage
    voltage_upper: float        # driver input upper voltage
    voltage_separator: str      # "OR" or "-"
    amps_lower: float           # input_power_w / (voltage_lower * power_factor)
    amps_upper: float           # input_power_w / (voltage_upper * power_factor)

    # --- Lumens ---
    initial_lumens: int         # GT2
    lumens_per_ft: float        # from LED reference

    # --- LED Specification ---
    led_type: str               # human-readable strip description
    l70_hours: int              # lifespan hours
    color_temp: str             # CCT string
    cri: str                    # CRI rating
    num_strips: int             # C4 (echoed for display)

    # --- Validation ---
    bad_driver_wattage: bool
    bad_length: bool
    bad_inputs: bool
    state_is_invalid: bool

    # --- Diagnostics ---
    validation_messages: list[str] = field(default_factory=list)

    @property
    def state_label(self) -> str:
        return "INVALID" if self.state_is_invalid else "VALID"

    @property
    def length_display(self) -> str:
        """e.g. '2X 109' for 2 strips at 109.15in"""
        return f"{self.num_strips}X {self.actual_length_in:.0f}"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class SACalcEngine:
    """
    Data-agnostic SA Calc engine.
    
    Usage
    -----
    engine = SACalcEngine.from_json("reference_data.json")
    inputs = CalcInputs(
        fixture_length_in=110,
        num_strips=2,
        num_drivers=1,
        product_line="GEN4",
        voltage_config="STANDARD",
        dimming_style="D2",
        driver_key="79314 - SMARTS",
        strip_type="STANDARD",
        led_style_key="LHE",
    )
    result = engine.calculate(inputs)
    print(result.state_label, result.total_system_w, "W")
    """

    def __init__(self, led_strips: dict[str, LEDStrip], drivers: dict[str, Driver]) -> None:
        self.led_strips = led_strips
        self.drivers = drivers

    # -- Factories --

    @classmethod
    def from_json(cls, path: str | Path) -> "SACalcEngine":
        """Load reference data from a JSON file matching reference_data.json schema."""
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)

        led_strips = {
            name: LEDStrip.from_dict(name, spec)
            for name, spec in data.get("led_strips", {}).items()
        }
        drivers = {
            name: Driver.from_dict(name, spec)
            for name, spec in data.get("drivers", {}).items()
        }
        return cls(led_strips=led_strips, drivers=drivers)

    @classmethod
    def from_dict(cls, data: dict) -> "SACalcEngine":
        """Load from an already-parsed dict (e.g., API ingestion)."""
        led_strips = {n: LEDStrip.from_dict(n, s) for n, s in data.get("led_strips", {}).items()}
        drivers    = {n: Driver.from_dict(n, s)    for n, s in data.get("drivers",    {}).items()}
        return cls(led_strips=led_strips, drivers=drivers)

    # -- Helpers --

    @staticmethod
    def _mround(value: float, multiple: float) -> float:
        """Excel MROUND: round `value` to nearest `multiple`."""
        if multiple == 0:
            return value
        return round(value / multiple) * multiple

    def _interpolate_wm(self, strip: LEDStrip, length_m: float) -> float:
        """
        Linear interpolation of W/m from the strip's wm_curve.
        
        Replicates cells GD2/GE2/GF2/GG2:
          - Find the two bracketing measured lengths in the curve
          - Interpolate fractionally between them
        
        Special cases (matching Excel brackets):
          0 < L < 0.25 : below first point → use 0.25m value
          L = 0        : return 0 (no strip)
          L > max key  : clamp to last available value
        """
        curve = strip.wm_curve
        # Collect only non-null data points, sorted
        points: list[tuple[float, float]] = sorted(
            [(l, w) for l, w in curve.items() if w is not None],
            key=lambda x: x[0]
        )

        if not points:
            return 0.0
        if length_m <= 0:
            return 0.0
        if length_m <= points[0][0]:
            return points[0][1]
        if length_m >= points[-1][0]:
            return points[-1][1]

        # Find surrounding bracket
        for i in range(len(points) - 1):
            l_lo, w_lo = points[i]
            l_hi, w_hi = points[i + 1]
            if l_lo <= length_m <= l_hi:
                # Fractional position within bracket (GF2 logic)
                remainder = (length_m - l_lo) / (l_hi - l_lo)
                return w_lo + (w_hi - w_lo) * remainder

        return points[-1][1]  # fallback

    # -- Input Validation --

    def _validate_inputs(self, inp: CalcInputs) -> tuple[bool, list[str]]:
        """
        Replicate GY2 / GZ2 / HA2 / HB2:
        Check that the three keyed inputs exist in the reference tables.
        Returns (any_invalid: bool, messages: list[str])
        """
        messages = []
        invalid = False

        if inp.driver_key not in self.drivers:
            messages.append(f"Driver '{inp.driver_key}' not found in Driver Reference (GY2=FALSE)")
            invalid = True

        valid_strip_types = {"STANDARD", "DIM TO WARM"}
        if inp.strip_type not in valid_strip_types:
            messages.append(f"Strip type '{inp.strip_type}' not in valid list (GZ2=FALSE)")
            invalid = True

        if inp.led_style_key not in self.led_strips:
            messages.append(f"LED style '{inp.led_style_key}' not found in LED Reference (HA2=FALSE)")
            invalid = True

        return invalid, messages

    # -- Core Calculation --

    def calculate(self, inp: CalcInputs) -> CalcOutputs:
        """
        Run the full measured-path calculation.
        """
        messages: list[str] = []

        # ---------------------------------------------------------------
        # Step 1: Validate dropdown inputs (GY2/GZ2/HA2 → HB2)
        # ---------------------------------------------------------------
        bad_inputs, input_msgs = self._validate_inputs(inp)
        messages.extend(input_msgs)

        # Early exit: if core lookups would fail, return invalid state
        if inp.led_style_key not in self.led_strips or inp.driver_key not in self.drivers:
            # We can't compute anything meaningful — return sentinel
            return CalcOutputs(
                actual_length_in=0, actual_length_m=0, segment_count=0,
                segment_mm=0, measured_wm=0, required_w_per_strip=0,
                driver_rated_w=0, buffered_headroom_w=0,
                per_strip_driver_ratio=0, buffer_multiplier=0,
                button_correction_w=0, buffered_w_per_driver=0,
                total_system_w=0, initial_lumens=0,
                bad_driver_wattage=False, bad_length=False,
                bad_inputs=True, state_is_invalid=True,
                validation_messages=messages,
            )

        strip  = self.led_strips[inp.led_style_key]
        driver = self.drivers[inp.driver_key]

        # ---------------------------------------------------------------
        # Step 2: Unit conversion & length snapping
        # GA2 = MROUND(C3*25.4, FX3) / 25.4   → actual length in inches
        # GB2 = MROUND(C3*25.4, FX3) / 1000   → actual length in meters
        # GC2 = FIXED((GB2*1000)/FX3, 1)       → segment count
        # ---------------------------------------------------------------
        seg_mm = strip.segment_mm                                    # FX3
        length_mm_raw = inp.fixture_length_in * 25.4                 # C3 × 25.4
        length_mm_snapped = self._mround(length_mm_raw, seg_mm)      # MROUND()

        actual_length_in = length_mm_snapped / 25.4                  # GA2
        actual_length_m  = length_mm_snapped / 1000                  # GB2
        segment_count    = round((length_mm_snapped / seg_mm), 1)    # GC2

        # ---------------------------------------------------------------
        # Step 3: W/m interpolation from the measured curve
        # GG2 = GD3 + (GE3 - GD3) * GF2
        # ---------------------------------------------------------------
        measured_wm = self._interpolate_wm(strip, actual_length_m)   # GG2

        # ---------------------------------------------------------------
        # Step 4: Driver lookup
        # GH3 = driver rated watts
        # ---------------------------------------------------------------
        driver_rated_w = driver.power_w                               # GH3

        # ---------------------------------------------------------------
        # Step 5: Power calculations
        # GL2 = GG2 * GB2                         (Required W per strip)
        # GI2 = 0.15                              (buffer constant)
        # GJ2 = GH3 * GI2                         (Buffered headroom W)
        # GK2 = C5 / C4                           (per-strip driver ratio)
        # GN2 = 1 if dimming_style in {AVA,KEEN}  (button correction)
        # GM2 = ((GL2*C4)/C5) / (GH3 - GJ2)      (buffer multiplier)
        # GO2 = (GJ2*GK2*GM2) + GL2 + GN2        (buffered W per driver)
        # C19 = GO2 * (C4/C5)                     (total system W)
        # ---------------------------------------------------------------
        required_w_per_strip   = measured_wm * actual_length_m                        # GL2
        buffered_headroom_w    = driver_rated_w * DRIVER_BUFFER_PCT                   # GJ2
        per_strip_ratio        = inp.num_drivers / inp.num_strips                     # GK2
        # GN2: auto button correction (+1W) for AVA/KEEN dimming styles
        auto_button_w          = 1 if inp.dimming_style in BUTTON_CORRECTION_STYLES else 0
        # C12: manual added watts from feature table (Button, Clock, etc.)
        button_correction_w    = auto_button_w + inp.button_correction_manual          # GN2 + C12

        denom = driver_rated_w - buffered_headroom_w
        if denom == 0:
            messages.append("Driver rated watts equals buffered headroom — division by zero avoided.")
            buffer_multiplier = 0.0
        else:
            buffer_multiplier = ((required_w_per_strip * inp.num_strips) / inp.num_drivers) / denom  # GM2

        buffered_w_per_driver = (
            (buffered_headroom_w * per_strip_ratio * buffer_multiplier)
            + required_w_per_strip
            + button_correction_w
        )  # GO2

        total_system_w = buffered_w_per_driver * (inp.num_strips / inp.num_drivers)   # C19

        # ---------------------------------------------------------------
        # Step 6: Power Requirements (input-side, BEFORE ADDITIONAL TECH FEATURES)
        # The Excel "WATTAGE (W)" and AMPS are based on the RAW MEASURED total
        # (GL2 × num_strips), NOT the buffered safety-check value (C19).
        # This matches the Excel label: "Power Requirements (before additional tech features)"
        #
        # measured_total_w = GL2 × C4  = required_w_per_strip * num_strips
        # input_power_w    = measured_total_w / driver_efficiency
        # amps             = input_power_w / (voltage × power_factor)
        # ---------------------------------------------------------------
        measured_total_w = required_w_per_strip * inp.num_strips          # GL2 × C4
        input_power_w    = measured_total_w / driver.efficiency if driver.efficiency > 0 else measured_total_w
        pf   = driver.power_factor if driver.power_factor > 0 else 1.0
        v_lo = driver.input_lower_v
        v_hi = driver.input_upper_v
        amps_lower = input_power_w / (v_lo * pf) if v_lo > 0 else 0.0
        amps_upper = input_power_w / (v_hi * pf) if v_hi > 0 else 0.0

        # ---------------------------------------------------------------
        # Step 7: Lumens
        # GT2 = FIXED(actual_length_in * lumens_per_inch * num_strips, 0)
        # ---------------------------------------------------------------
        initial_lumens = round(actual_length_in * strip.lumens_per_inch * inp.num_strips)

        # ---------------------------------------------------------------
        # Step 8: Validation gate (HC2 / HD2 / HE2)
        # ---------------------------------------------------------------
        bad_driver_wattage = total_system_w >= driver_rated_w
        bad_length         = actual_length_m > strip.max_run_m

        if bad_driver_wattage:
            messages.append(
                f"FAIL - Required wattage ({total_system_w:.1f}W) >= Driver rated ({driver_rated_w:.0f}W). "
                f"Reduce length, select a more efficient LED, or use a higher-watt driver."
            )
        if bad_length:
            messages.append(
                f"FAIL - Actual length ({actual_length_m:.3f}m) exceeds max run "
                f"({strip.max_run_m}m) for {strip.name}."
            )

        state_is_invalid = bad_driver_wattage or bad_length or bad_inputs

        return CalcOutputs(
            actual_length_in=actual_length_in,
            actual_length_m=actual_length_m,
            segment_count=segment_count,
            segment_mm=seg_mm,
            measured_wm=measured_wm,
            required_w_per_strip=required_w_per_strip,
            driver_rated_w=driver_rated_w,
            buffered_headroom_w=buffered_headroom_w,
            per_strip_driver_ratio=per_strip_ratio,
            buffer_multiplier=buffer_multiplier,
            button_correction_w=button_correction_w,
            buffered_w_per_driver=buffered_w_per_driver,
            total_system_w=total_system_w,
            measured_total_w=measured_total_w,
            input_power_w=input_power_w,
            voltage_lower=v_lo,
            voltage_upper=v_hi,
            voltage_separator=driver.input_separator,
            amps_lower=amps_lower,
            amps_upper=amps_upper,
            initial_lumens=initial_lumens,
            lumens_per_ft=strip.lumens_per_ft,
            led_type=strip.led_type,
            l70_hours=strip.l70_hours,
            color_temp=strip.color_temp,
            cri=strip.cri,
            num_strips=inp.num_strips,
            bad_driver_wattage=bad_driver_wattage,
            bad_length=bad_length,
            bad_inputs=bad_inputs,
            state_is_invalid=state_is_invalid,
            validation_messages=messages,
        )

    # -- Convenience methods --

    def valid_led_styles(self) -> list[str]:
        """Return dropdown options for LED Style (cell C11)."""
        return sorted(self.led_strips.keys())

    def valid_drivers(self, retired: bool = False) -> list[str]:
        """Return dropdown options for Driver (cell C9). Excludes retired by default."""
        return sorted(
            k for k, v in self.drivers.items()
            if (retired or not v.retired)
        )

    def valid_strip_types(self) -> list[str]:
        """Return dropdown options for Strip Type (cell C10)."""
        return ["STANDARD", "DIM TO WARM"]

    def valid_dimming_styles(self) -> list[str]:
        """Return dropdown options for Dimming Style (cell C8)."""
        styles = sorted({v.dimming_style for v in self.drivers.values() if not v.retired})
        return [s for s in styles if s != "Retired"]

    def valid_product_lines(self) -> list[str]:
        """Return dropdown options for Product Line (cell C6)."""
        return ["GEN4", "RAD4", "JS2.3/JS3", "JS2", "LEGACY"]

    def valid_voltage_configs(self) -> list[str]:
        """Return dropdown options for Voltage (cell C7)."""
        return ["STANDARD", "230V", "277V"]

    def get_input_space(self) -> dict:
        """
        Return the full valid input space (all dropdown constraints).
        Useful for API schema generation or UI population.
        """
        return {
            "fixture_length_in": {
                "type": "number", "unit": "inches",
                "description": "Fixture length (C3). Will be snapped to segment cut point."
            },
            "num_strips": {
                "type": "integer", "min": 1,
                "description": "Number of LED strips in the fixture (C4)."
            },
            "num_drivers": {
                "type": "integer", "min": 1,
                "description": "Number of drivers powering the strips (C5)."
            },
            "product_line": {
                "type": "enum", "options": self.valid_product_lines(),
                "description": "Mirror product line (C6)."
            },
            "voltage_config": {
                "type": "enum", "options": self.valid_voltage_configs(),
                "description": "Voltage configuration (C7)."
            },
            "dimming_style": {
                "type": "enum", "options": self.valid_dimming_styles(),
                "description": "Dimming protocol (C8)."
            },
            "driver_key": {
                "type": "enum", "options": self.valid_drivers(),
                "description": "Driver selection (C9). Must exactly match a key in driver reference."
            },
            "strip_type": {
                "type": "enum", "options": self.valid_strip_types(),
                "description": "Strip colour type (C10)."
            },
            "led_style_key": {
                "type": "enum", "options": self.valid_led_styles(),
                "description": "LED strip style (C11). Must exactly match a key in LED reference."
            },
            "button_correction_manual": {
                "type": "integer", "options": [0, 1], "default": 0,
                "description": "Manual button wattage override (C12). Usually 0."
            },
        }


# ---------------------------------------------------------------------------
# CLI / Demo
# ---------------------------------------------------------------------------

def _print_result(result: CalcOutputs, inputs: CalcInputs) -> None:
    w = 60
    state_str = "[INVALID]" if result.state_is_invalid else "[VALID]"
    print("=" * w)
    print(f"  SA CALC ENGINE - RESULT  {state_str}")
    print("=" * w)
    print(f"  INPUTS")
    print(f"    Fixture length      : {inputs.fixture_length_in} in")
    print(f"    Num strips          : {inputs.num_strips}")
    print(f"    Num drivers         : {inputs.num_drivers}")
    print(f"    LED style           : {inputs.led_style_key}")
    print(f"    Driver              : {inputs.driver_key}")
    print(f"    Dimming style       : {inputs.dimming_style}")
    print()
    print(f"  GEOMETRY")
    print(f"    Segment pitch       : {result.segment_mm} mm  (FX3)")
    print(f"    Actual length       : {result.actual_length_in:.2f} in  (GA2)")
    print(f"    Actual length       : {result.actual_length_m:.4f} m   (GB2)")
    print(f"    Segment count       : {result.segment_count}  (GC2)")
    print()
    print(f"  MEASURED PATH (INTERPOLATION)")
    print(f"    W/m at length       : {result.measured_wm:.3f} W/m  (GG2)")
    print()
    print(f"  POWER")
    print(f"    Required W/strip    : {result.required_w_per_strip:.3f} W  (GL2)")
    print(f"    Driver rated W      : {result.driver_rated_w:.1f} W  (GH3)")
    print(f"    15% headroom        : {result.buffered_headroom_w:.3f} W  (GJ2)")
    print(f"    Buffer multiplier   : {result.buffer_multiplier:.4f}  (GM2)")
    print(f"    Button correction   : +{result.button_correction_w} W  (GN2)")
    print(f"    Buffered W/driver   : {result.buffered_w_per_driver:.3f} W  (GO2)")
    print(f"    Total system W      : {result.total_system_w:.3f} W  (C19)")
    print()
    print(f"  LUMENS")
    print(f"    Initial lumens      : {result.initial_lumens:,}  (GT2)")
    print()
    print(f"  VALIDATION")
    print(f"    Bad driver wattage  : {result.bad_driver_wattage}  (HC2)")
    print(f"    Bad length          : {result.bad_length}  (HD2)")
    print(f"    Bad inputs          : {result.bad_inputs}  (HB2)")
    print(f"    FINAL STATE         : {state_str}  (HE2)")
    if result.validation_messages:
        print()
        print(f"  MESSAGES")
        for msg in result.validation_messages:
            print(f"    !! {msg}")
    print("=" * w)


if __name__ == "__main__":
    import sys

    # Locate reference data relative to this script
    script_dir = Path(__file__).parent
    ref_path = script_dir / "reference_data.json"

    if not ref_path.exists():
        print(f"ERROR: reference_data.json not found at {ref_path}")
        sys.exit(1)

    engine = SACalcEngine.from_json(ref_path)

    # --------------------------------------------------------
    # Demo 1 — Replicate the default Excel state (C3=110in, 2 strips, 1 driver)
    # --------------------------------------------------------
    demo_inputs = CalcInputs(
        fixture_length_in=110,
        num_strips=2,
        num_drivers=1,
        product_line="GEN4",
        voltage_config="STANDARD",
        dimming_style="D2",
        driver_key="79314 - SMARTS",
        strip_type="STANDARD",
        led_style_key="LHE",
    )

    result = engine.calculate(demo_inputs)
    _print_result(result, demo_inputs)

    print()
    print("Available LED Styles:")
    for s in engine.valid_led_styles():
        print(f"  {s}")

    print()
    print("Available Drivers (active):")
    for d in engine.valid_drivers():
        print(f"  {d}")
