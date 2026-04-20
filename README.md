# SA Calculator Logic — Engine as a Service

A modular, data-agnostic Python engine that reproduces the full calculation logic of the Electric Mirror **Sales Aid Calculator (v0.94)** — extracted and refactored from the original Excel workbook.

---

## What This Is

The original Sales Aid Calc is an Excel tool that determines whether a given LED strip + driver combination is valid for a specific fixture length. This repo contains:

| File | Purpose |
|------|---------|
| `sa_calc_engine.py` | Core Python engine (class-based, no Excel dependency) |
| `reference_data.json` | LED strip and Driver reference tables (JSON) |
| `reference_schema.json` | JSON Schema for validating / extending reference tables |
| `app_test.py` | Interactive Streamlit test UI |
| `driver_reference.csv` | Raw driver data (source reference) |
| `led_reference.csv` | Raw LED data (source reference) |
| `product_reference.csv` | Raw product data (source reference) |

---

## Quick Start

### 1. Install dependencies
```bash
pip install streamlit
```

### 2. Run the interactive test UI
```bash
python -m streamlit run app_test.py
```
Opens at **http://localhost:8501**

### 3. Use the engine directly in Python
```python
from sa_calc_engine import SACalcEngine, CalcInputs

engine = SACalcEngine.from_json("reference_data.json")

result = engine.calculate(CalcInputs(
    fixture_length_in=60,
    num_strips=1,
    num_drivers=1,
    product_line="GEN4",
    voltage_config="STANDARD",
    dimming_style="D2",
    driver_key="79314 - SMARTS",
    strip_type="STANDARD",
    led_style_key="SO",
))

print(result.state_label)      # [VALID]
print(result.total_system_w)   # ~W
print(result.initial_lumens)   # ~lm
```

---

## Inputs (Orange Cells from Excel)

| Cell | Field | Type | Description |
|------|-------|------|-------------|
| C3 | `fixture_length_in` | `float` | Fixture length in inches |
| C4 | `num_strips` | `int` | Number of LED strips |
| C5 | `num_drivers` | `int` | Number of drivers |
| C6 | `product_line` | `enum` | GEN4 / RAD4 / JS2.3/JS3 / JS2 / LEGACY |
| C7 | `voltage_config` | `enum` | STANDARD / 230V / 277V |
| C8 | `dimming_style` | `enum` | AVA / D2 / D4 / D4 DT8 / DM / KEEN / NON-DIMMING |
| C9 | `driver_key` | `enum` | Must match a key in `reference_data.json → drivers` |
| C10 | `strip_type` | `enum` | STANDARD or DIM TO WARM |
| C11 | `led_style_key` | `enum` | Must match a key in `reference_data.json → led_strips` |
| C12 | `button_correction_manual` | `int` | Added watts from feature table (Button=1W, Clock=2W, etc.) |

---

## Calculation Logic (Measured Path)

```
length_mm   = MROUND(fixture_in × 25.4, segment_mm)     ← snaps to cut point
actual_m    = length_mm / 1000
segment_cnt = length_mm / segment_mm

measured_wm = interpolate(wm_curve, actual_m)            ← linear interp of measured data
req_w_strip = measured_wm × actual_m

buffer      = driver_rated_w × 0.15                      ← 15% headroom
button_w    = 1 (if AVA/KEEN) + manual_added_watts
buffered_w  = (buffer × ratio × multiplier) + req_w + button_w
total_w     = buffered_w × (num_strips / num_drivers)

VALID  ←→  total_w < driver_rated_w  AND  actual_m ≤ max_run_m
```

---

## Validation Gate

| Check | Cell | Condition | Result |
|-------|------|-----------|--------|
| Driver in reference | GY2 | `driver_key` exists in JSON | FAIL if missing |
| Strip type valid | GZ2 | `strip_type` in {STANDARD, DIM TO WARM} | FAIL if invalid |
| LED style in reference | HA2 | `led_style_key` exists in JSON | FAIL if missing |
| **Wattage over limit** | **HC2** | `total_system_w >= driver_rated_w` | **FAIL (RED)** |
| Length over max | HD2 | `actual_length_m > max_run_m` | FAIL |
| **Master state** | **HE2** | Any of above is TRUE | **RED / GREEN** |

---

## Updating Reference Data

To add new LED strips or Drivers, edit `reference_data.json` — no code changes required.

```json
"led_strips": {
  "NEW XLE": {
    "em_number": "85000",
    "max_run_m": 5,
    "segment_mm": 50,
    "lumens_per_inch": 90.0,
    "wm_curve": {
      "0.25": 25.0, "0.5": 24.5, "1": 23.8, "2": 21.0,
      "3": 19.0, "4": 17.0, "5": 15.5
    }
  }
}
```

See `reference_schema.json` for the full field specification.

---

## Project Structure

```
SA-Calculator-Logic/
├── sa_calc_engine.py      # Core engine — CalcInputs, CalcOutputs, SACalcEngine
├── app_test.py            # Streamlit interactive UI
├── reference_data.json    # LED + Driver reference tables
├── reference_schema.json  # JSON Schema for reference_data.json
├── driver_reference.csv   # Raw source data
├── led_reference.csv      # Raw source data
├── product_reference.csv  # Raw source data
└── README.md
```
