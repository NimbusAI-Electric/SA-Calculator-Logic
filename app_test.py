"""
SA Calc Engine — Interactive Streamlit Test App
================================================
Mirrors the orange-cell UX of the Excel calculator.
Run with:  python -m streamlit run app_test.py
"""
import sys
import json
from pathlib import Path

import streamlit as st

# ── Import engine from same directory ──────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from sa_calc_engine import SACalcEngine, CalcInputs

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SA Calc Engine — Test UI",
    page_icon="💡",
    layout="wide",
)

# ── Load engine ─────────────────────────────────────────────────────────────
def load_engine():
    return SACalcEngine.from_json(Path(__file__).parent / "reference_data.json")

engine = load_engine()

# ── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .stApp { background: #0f1117; }

    /* Orange input section */
    .input-section {
        background: linear-gradient(135deg, #1a1208 0%, #261a06 100%);
        border: 2px solid #ff8c00;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1rem;
    }
    .input-section h3 {
        color: #ff8c00;
        font-size: 0.85rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin: 0 0 0.8rem 0;
    }

    /* VALID state */
    .state-valid {
        background: linear-gradient(135deg, #0a2a0a, #0f3d0f);
        border: 2px solid #22c55e;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        text-align: center;
    }
    .state-valid .state-label {
        font-size: 1.8rem;
        font-weight: 700;
        color: #22c55e;
        letter-spacing: 0.05em;
    }

    /* INVALID state */
    .state-invalid {
        background: linear-gradient(135deg, #2a0a0a, #3d0f0f);
        border: 2px solid #ef4444;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        text-align: center;
    }
    .state-invalid .state-label {
        font-size: 1.8rem;
        font-weight: 700;
        color: #ef4444;
        letter-spacing: 0.05em;
    }

    /* Metric cards */
    .metric-card {
        background: #1c1f2e;
        border: 1px solid #2a2d3e;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.6rem;
    }
    .metric-card .label {
        font-size: 0.7rem;
        color: #6b7280;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-bottom: 0.2rem;
    }
    .metric-card .ref {
        font-size: 0.65rem;
        color: #374151;
        font-family: monospace;
        float: right;
        margin-top: 2px;
    }
    .metric-card .value {
        font-size: 1.3rem;
        font-weight: 700;
        color: #f9fafb;
    }
    .metric-card .unit {
        font-size: 0.75rem;
        color: #9ca3af;
        margin-left: 0.3rem;
    }

    /* Warn cards */
    .warn-card {
        background: #2d1b1b;
        border-left: 4px solid #ef4444;
        border-radius: 0 8px 8px 0;
        padding: 0.7rem 1rem;
        margin-bottom: 0.5rem;
        color: #fca5a5;
        font-size: 0.85rem;
    }

    /* Section header */
    .section-header {
        font-size: 0.7rem;
        font-weight: 700;
        color: #4b5563;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        border-bottom: 1px solid #1f2937;
        padding-bottom: 0.4rem;
        margin: 1.2rem 0 0.8rem 0;
    }

    /* Streamlit overrides */
    div[data-testid="stSelectbox"] label,
    div[data-testid="stNumberInput"] label { color: #d1d5db !important; font-size: 0.8rem !important; }
    div[data-testid="stSelectbox"] select,
    div[data-testid="stNumberInput"] input { background: #1c1f2e !important; color: #f9fafb !important; border-color: #374151 !important; }

    .title-bar {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        margin-bottom: 1.5rem;
    }
    .title-bar h1 {
        font-size: 1.4rem;
        font-weight: 700;
        color: #f9fafb;
        margin: 0;
    }
    .title-bar .version {
        font-size: 0.7rem;
        color: #6b7280;
        background: #1c1f2e;
        padding: 0.2rem 0.6rem;
        border-radius: 4px;
        border: 1px solid #374151;
    }

    /* Progress bar for wattage */
    .watt-bar-container {
        background: #1c1f2e;
        border-radius: 8px;
        height: 12px;
        margin: 0.4rem 0;
        overflow: hidden;
        border: 1px solid #2a2d3e;
    }
    .watt-bar-fill-ok   { height: 100%; border-radius: 8px; background: linear-gradient(90deg, #22c55e, #16a34a); }
    .watt-bar-fill-warn { height: 100%; border-radius: 8px; background: linear-gradient(90deg, #f59e0b, #d97706); }
    .watt-bar-fill-fail { height: 100%; border-radius: 8px; background: linear-gradient(90deg, #ef4444, #dc2626); }
</style>
""", unsafe_allow_html=True)

# ── Title ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="title-bar">
  <span style="font-size:2rem">💡</span>
  <h1>SA Calc Engine</h1>
  <span class="version">v1.0.0 — Measured Path</span>
</div>
""", unsafe_allow_html=True)

# ── Layout: left inputs | right results ─────────────────────────────────────
left, right = st.columns([1, 1.4], gap="large")

# ── LEFT: Orange Input Section ──────────────────────────────────────────────
with left:
    st.markdown('<div class="input-section"><h3>🟠 Orange Inputs</h3>', unsafe_allow_html=True)

    # Row 1
    c1, c2 = st.columns(2)
    fixture_length = c1.number_input(
        "Fixture Length (in) — C3", min_value=1.0, max_value=500.0,
        value=110.0, step=1.0, format="%.1f"
    )
    num_strips = c2.number_input(
        "Number of Strips — C4", min_value=1, max_value=10, value=2, step=1
    )

    # Row 2
    c3, c4 = st.columns(2)
    num_drivers = c3.number_input(
        "Number of Drivers — C5", min_value=1, max_value=10, value=1, step=1
    )
    product_line = c4.selectbox(
        "Product Line — C6", engine.valid_product_lines(), index=0
    )

    # Row 3
    c5, c6 = st.columns(2)
    voltage_config = c5.selectbox(
        "Voltage — C7", engine.valid_voltage_configs(), index=0
    )
    dimming_style = c6.selectbox(
        "Dimming Style — C8", engine.valid_dimming_styles(), index=3  # D2
    )

    # Row 4
    driver_options = engine.valid_drivers()
    default_driver_idx = driver_options.index("79314 - SMARTS") if "79314 - SMARTS" in driver_options else 0
    driver_key = st.selectbox(
        "Driver — C9", driver_options, index=default_driver_idx
    )

    # Row 5
    c7, c8 = st.columns(2)
    strip_type = c7.selectbox(
        "Strip Type — C10", engine.valid_strip_types(), index=0
    )
    led_options = engine.valid_led_styles()
    default_led_idx = led_options.index("LHE") if "LHE" in led_options else 0
    led_style = c8.selectbox(
        "LED Style — C11", led_options, index=default_led_idx
    )

    # Added Watts — matches Excel C12 "ADDED WATTS (SEE FEATURE TABLE)"
    added_watts = st.number_input(
        "Added Watts (see feature table) — C12",
        min_value=0, max_value=100, value=0, step=1,
        help="Extra wattage for features like Button (+1W), Clock (+2W), etc. Enter the sum of all applicable feature watts."
    )

    st.markdown("</div>", unsafe_allow_html=True)

    # Show driver & LED quick info
    drv = engine.drivers.get(driver_key)
    led = engine.led_strips.get(led_style)

    if drv and led:
        ic1, ic2 = st.columns(2)
        ic1.markdown(f"""
        <div class="metric-card">
          <div class="label">Driver Rated Power <span class="ref">GH3</span></div>
          <div class="value">{drv.power_w:.0f}<span class="unit">W</span></div>
          <div style="font-size:0.7rem;color:#6b7280;margin-top:0.3rem">{drv.dimming_style} · {drv.mfr_pn}</div>
        </div>
        """, unsafe_allow_html=True)
        ic2.markdown(f"""
        <div class="metric-card">
          <div class="label">Strip Segment Pitch <span class="ref">FX3</span></div>
          <div class="value">{led.segment_mm}<span class="unit">mm</span></div>
          <div style="font-size:0.7rem;color:#6b7280;margin-top:0.3rem">{led.lumens_per_inch:.1f} lm/in · max {led.max_run_m}m run</div>
        </div>
        """, unsafe_allow_html=True)

# ── RIGHT: Results ───────────────────────────────────────────────────────────
with right:
    inp = CalcInputs(
        fixture_length_in=fixture_length,
        num_strips=int(num_strips),
        num_drivers=int(num_drivers),
        product_line=product_line,
        voltage_config=voltage_config,
        dimming_style=dimming_style,
        driver_key=driver_key,
        strip_type=strip_type,
        led_style_key=led_style,
        button_correction_manual=int(added_watts),
    )
    result = engine.calculate(inp)

    # ── State Banner ────────────────────────────────────────────────────────
    if result.state_is_invalid:
        st.markdown(f"""
        <div class="state-invalid">
          <div class="state-label">🔴 INVALID</div>
          <div style="font-size:0.8rem;color:#fca5a5;margin-top:0.4rem">Configuration has errors — see details below</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="state-valid">
          <div class="state-label">🟢 VALID</div>
          <div style="font-size:0.8rem;color:#86efac;margin-top:0.4rem">All checks passed — configuration is safe to spec</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Wattage load bar ───────────────────────────────────────────────────
    if result.driver_rated_w > 0:
        pct = min(result.total_system_w / result.driver_rated_w, 1.0)
        pct_display = min(pct * 100, 100)
        bar_class = "watt-bar-fill-ok" if pct < 0.75 else ("watt-bar-fill-warn" if pct < 1.0 else "watt-bar-fill-fail")
        safe_limit = result.driver_rated_w * 0.85
        st.markdown(f"""
        <div style="margin-top:1rem">
          <div style="display:flex;justify-content:space-between;font-size:0.7rem;color:#6b7280;margin-bottom:0.3rem">
            <span>Driver Load: {result.total_system_w:.1f}W / {result.driver_rated_w:.0f}W rated</span>
            <span>{pct_display:.0f}% · safe ceiling {safe_limit:.0f}W (85%)</span>
          </div>
          <div class="watt-bar-container"><div class="{bar_class}" style="width:{pct_display:.1f}%"></div></div>
        </div>
        """, unsafe_allow_html=True)

    # ── Power Requirements ─────────────────────────────────────────────────
    st.markdown('<div class="section-header">Power Requirements (Before Additional Tech Features)</div>', unsafe_allow_html=True)
    sep = result.voltage_separator
    vlo = int(result.voltage_lower)
    vhi = int(result.voltage_upper)
    st.markdown(f"""
    <div class="metric-card" style="padding:0.8rem 1.2rem">
      <div style="display:flex;align-items:center;gap:2rem;flex-wrap:wrap">
        <div>
          <div class="label">Voltage</div>
          <div class="value" style="font-size:1.1rem">{vlo} <span style="color:#6b7280;font-size:0.9rem">{sep}</span> {vhi}<span class="unit">V</span></div>
        </div>
        <div style="width:1px;height:2rem;background:#2a2d3e"></div>
        <div>
          <div class="label">Amps</div>
          <div class="value" style="font-size:1.1rem">{result.amps_lower:.2f} <span style="color:#6b7280;font-size:0.9rem">{sep}</span> {result.amps_upper:.2f}<span class="unit">A</span></div>
        </div>
        <div style="width:1px;height:2rem;background:#2a2d3e"></div>
        <div>
          <div class="label">Input Power</div>
          <div class="value" style="font-size:1.1rem">{result.input_power_w:.1f}<span class="unit">W</span></div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── LED Specification ──────────────────────────────────────────────────
    st.markdown('<div class="section-header">LED Specification</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="metric-card" style="padding:0.9rem 1.2rem">
      <table style="width:100%;border-collapse:collapse;font-size:0.82rem">
        <tr><td style="color:#6b7280;padding:0.25rem 0.5rem 0.25rem 0;width:40%">LED TYPE</td>
            <td style="color:#f9fafb;font-weight:600">{result.led_type}</td></tr>
        <tr><td style="color:#6b7280;padding:0.25rem 0.5rem 0.25rem 0">LENGTH (IN)</td>
            <td style="color:#f9fafb;font-weight:600">{result.length_display}</td></tr>
        <tr><td style="color:#6b7280;padding:0.25rem 0.5rem 0.25rem 0">WATTAGE (W)</td>
            <td style="color:#f9fafb;font-weight:600">{round(result.measured_total_w)}</td></tr>
        <tr><td style="color:#6b7280;padding:0.25rem 0.5rem 0.25rem 0">CALCULATED L70 LIFESPAN (HRS)</td>
            <td style="color:#f9fafb;font-weight:600">{result.l70_hours:,}</td></tr>
        <tr><td style="color:#6b7280;padding:0.25rem 0.5rem 0.25rem 0">CCT (K)</td>
            <td style="color:#f9fafb;font-weight:600">{result.color_temp}</td></tr>
        <tr><td style="color:#6b7280;padding:0.25rem 0.5rem 0.25rem 0">TOTAL INITIAL LUMENS</td>
            <td style="color:#f9fafb;font-weight:600">{result.initial_lumens:,} <span style="color:#6b7280;font-weight:400">@ {result.lumens_per_ft:.0f} LM/FT</span></td></tr>
        <tr><td style="color:#6b7280;padding:0.25rem 0.5rem 0.25rem 0">CRI</td>
            <td style="color:#f9fafb;font-weight:600">{result.cri}</td></tr>
      </table>
    </div>
    """, unsafe_allow_html=True)

    # ── Geometry ───────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Geometry</div>', unsafe_allow_html=True)
    gc1, gc2, gc3 = st.columns(3)
    gc1.markdown(f"""
    <div class="metric-card">
      <div class="label">Actual Length <span class="ref">GA2</span></div>
      <div class="value">{result.actual_length_in:.2f}<span class="unit">in</span></div>
    </div>""", unsafe_allow_html=True)
    gc2.markdown(f"""
    <div class="metric-card">
      <div class="label">Actual Length <span class="ref">GB2</span></div>
      <div class="value">{result.actual_length_m:.3f}<span class="unit">m</span></div>
    </div>""", unsafe_allow_html=True)
    gc3.markdown(f"""
    <div class="metric-card">
      <div class="label">Segment Count <span class="ref">GC2</span></div>
      <div class="value">{result.segment_count}<span class="unit">segs</span></div>
    </div>""", unsafe_allow_html=True)

    # ── Measured Path ──────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Measured Path (Interpolated)</div>', unsafe_allow_html=True)
    mp1, mp2, mp3 = st.columns(3)
    mp1.markdown(f"""
    <div class="metric-card">
      <div class="label">Measured W/m <span class="ref">GG2</span></div>
      <div class="value">{result.measured_wm:.3f}<span class="unit">W/m</span></div>
    </div>""", unsafe_allow_html=True)
    mp2.markdown(f"""
    <div class="metric-card">
      <div class="label">Req. W/Strip <span class="ref">GL2</span></div>
      <div class="value">{result.required_w_per_strip:.2f}<span class="unit">W</span></div>
    </div>""", unsafe_allow_html=True)
    mp3.markdown(f"""
    <div class="metric-card">
      <div class="label">Initial Lumens <span class="ref">GT2</span></div>
      <div class="value">{result.initial_lumens:,}<span class="unit">lm</span></div>
    </div>""", unsafe_allow_html=True)

    # ── Power Calc ─────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Power Calculation</div>', unsafe_allow_html=True)
    pw1, pw2, pw3, pw4 = st.columns(4)
    pw1.markdown(f"""
    <div class="metric-card">
      <div class="label">Headroom (15%) <span class="ref">GJ2</span></div>
      <div class="value">{result.buffered_headroom_w:.2f}<span class="unit">W</span></div>
    </div>""", unsafe_allow_html=True)
    pw2.markdown(f"""
    <div class="metric-card">
      <div class="label">Btn Correction <span class="ref">GN2</span></div>
      <div class="value">+{result.button_correction_w}<span class="unit">W</span></div>
    </div>""", unsafe_allow_html=True)
    pw3.markdown(f"""
    <div class="metric-card">
      <div class="label">Buffered W/Driver <span class="ref">GO2</span></div>
      <div class="value">{result.buffered_w_per_driver:.2f}<span class="unit">W</span></div>
    </div>""", unsafe_allow_html=True)

    total_color = "#ef4444" if result.bad_driver_wattage else "#22c55e"
    pw4.markdown(f"""
    <div class="metric-card" style="border-color:{total_color}40">
      <div class="label">Total System W <span class="ref">C19</span></div>
      <div class="value" style="color:{total_color}">{result.total_system_w:.2f}<span class="unit" style="color:{total_color}">W</span></div>
    </div>""", unsafe_allow_html=True)

    # ── Validation Checks ──────────────────────────────────────────────────
    st.markdown('<div class="section-header">Validation Gate (HE2)</div>', unsafe_allow_html=True)

    def check_row(label, cell_ref, passed: bool, detail: str = ""):
        icon = "✅" if passed else "❌"
        color = "#22c55e" if passed else "#ef4444"
        bg = "#0f2a0f" if passed else "#2a0f0f"
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:0.8rem;background:{bg};
             border-radius:8px;padding:0.5rem 0.8rem;margin-bottom:0.4rem;
             border:1px solid {color}30">
          <span style="font-size:1rem">{icon}</span>
          <div style="flex:1">
            <span style="color:{color};font-weight:600;font-size:0.85rem">{label}</span>
            <span style="color:#374151;font-size:0.7rem;margin-left:0.5rem;font-family:monospace">{cell_ref}</span>
          </div>
          <span style="color:#9ca3af;font-size:0.75rem">{detail}</span>
        </div>
        """, unsafe_allow_html=True)

    check_row("Driver in reference", "GY2",
              not result.bad_inputs or driver_key in engine.drivers,
              f"{driver_key[:35]}")
    check_row("Strip type valid", "GZ2",
              strip_type in engine.valid_strip_types(),
              strip_type)
    check_row("LED style in reference", "HA2",
              led_style in engine.led_strips,
              led_style)
    check_row("Length within max run", "HD2",
              not result.bad_length,
              f"{result.actual_length_m:.3f}m vs {led.max_run_m}m max" if led else "")
    check_row("Wattage within driver limit", "HC2",
              not result.bad_driver_wattage,
              f"{result.total_system_w:.1f}W vs {result.driver_rated_w:.0f}W rated")

    # Error messages
    if result.validation_messages:
        st.markdown('<div class="section-header">Failure Details</div>', unsafe_allow_html=True)
        for msg in result.validation_messages:
            st.markdown(f'<div class="warn-card">{msg}</div>', unsafe_allow_html=True)

    # ── W/m curve visualisation ──────────────────────────────────────────
    if led and led.wm_curve:
        st.markdown('<div class="section-header">W/m Curve — ' + led_style + '</div>', unsafe_allow_html=True)
        curve_pts = sorted([(l, w) for l, w in led.wm_curve.items() if w is not None])
        if curve_pts:
            import pandas as pd
            df = pd.DataFrame(curve_pts, columns=["Length (m)", "W/m"])
            chart_data = df.set_index("Length (m)")

            # Highlight the current operating point
            op_point = pd.DataFrame(
                [[result.actual_length_m, result.measured_wm]],
                columns=["Length (m)", "W/m"]
            ).set_index("Length (m)")

            st.line_chart(chart_data, color="#ff8c00", height=180)
            st.caption(f"Operating point: {result.actual_length_m:.3f}m -> {result.measured_wm:.3f} W/m")
