import os
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Cement Mill Advisory System",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =========================================================
# FILE PATHS
# =========================================================
SOUND_LOOKUP_PATH = "sound_envelope.csv"
AMP_LOOKUP_PATH = "amp_envelope.csv"
FEED_HISTORY_PATH = "feed_advisory_history.csv"
SEPARATOR_HISTORY_PATH = "separator_advisory_history.csv"

# =========================================================
# SESSION STATE
# =========================================================
def initialize_session_state():
    defaults = {
        "feed_cat": 0,
        "total_tph": 120.0,
        "mill_sound": 70.0,
        "be_amp": 55.0,
        "sep_cat": 0,
        "current_blaine": 360.0,
        "current_rpm": 700.0,
        "demo_simulation_mode": False,
        "demo_scenario": "Scenario 1 - Increase RPM / Fuller Mill",
        "simulated_response": None,
        "applied_simulation": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


initialize_session_state()

# =========================================================
# LOAD LOOKUPS
# =========================================================
@st.cache_data
def load_lookup_tables():
    sound_envelope = pd.read_csv(SOUND_LOOKUP_PATH)
    amp_envelope = pd.read_csv(AMP_LOOKUP_PATH)

    sound_envelope["cement_category"] = pd.to_numeric(
        sound_envelope["cement_category"], errors="coerce"
    ).astype(int)
    amp_envelope["cement_category"] = pd.to_numeric(
        amp_envelope["cement_category"], errors="coerce"
    ).astype(int)

    sound_envelope["feed_bin"] = sound_envelope["feed_bin"].astype(str)
    amp_envelope["feed_bin"] = amp_envelope["feed_bin"].astype(str)

    sound_lookup = sound_envelope.set_index(
        ["cement_category", "feed_bin"]
    ).to_dict(orient="index")

    amp_lookup = amp_envelope.set_index(
        ["cement_category", "feed_bin"]
    ).to_dict(orient="index")

    return sound_lookup, amp_lookup, sound_envelope, amp_envelope


sound_lookup, amp_lookup, sound_envelope_df, amp_envelope_df = load_lookup_tables()

# =========================================================
# CONFIG
# =========================================================
CATEGORY_MAP = {
    0: "PPC",
    1: "OPC",
}

BLAINE_TARGETS = {
    0: {"name": "PPC", "target": 370, "range": "390-400"},
    1: {"name": "OPC", "target": 290, "range": "290-300"},
}

FEED_BIN_START = 100
FEED_BIN_END = 140
FEED_BIN_STEP = 2

DEMO_SCENARIOS = {
    "Scenario 1 - Increase RPM / Fuller Mill": {
        "required_interpretation": "Blaine below target",
        "trigger": "Increase separator RPM",
        "narrative": "As separator RPM increases, circulating load rises, the mill starts filling up, mill sound falls, and bucket elevator load rises.",
        "demo_input_caption": "Suggested target Blaine is midpoint of the target range",
        "mill_sound_before": 70.0,
        "mill_sound_after": 65.0,
        "be_amp_before": 52.0,
        "be_amp_after": 55.0,
        "default_interpretation": "Expected fuller mill condition",
        "fallback_recommendation": "Reduce feed by 1-3 TPH",
        "header_note": "Scenario 1 is ON: Separator RPM increase simulates Mill to be filling more so Mill Sound will decrease and BE Load will increase, then the next feed recommendation is expected to reduce feed.",
    },
    "Scenario 2 - Decrease RPM / Lighter Mill": {
        "required_interpretation": "Blaine above target",
        "trigger": "Reduce separator RPM",
        "narrative": "As separator RPM decreases, circulating load eases, mill sound rises, and bucket elevator load drops, indicating room to raise feed.",
        "demo_input_caption": "Suggested target Blaine is midpoint of the target range",
        "mill_sound_before": 75.0,
        "mill_sound_after": 85.0,
        "be_amp_before": 55.0,
        "be_amp_after": 48.0,
        "default_interpretation": "Expected lighter mill condition",
        "fallback_recommendation": "Increase feed by 1-3 TPH",
        "header_note": "Scenario 2 is ON: Separator RPM decrease simulates Mill filling to be lighter so MillSound will increase and BE Load will decrease, then the next feed recommendation is expected to increase feed.",
    },
}

# =========================================================
# STYLES
# =========================================================
st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.6rem;
            padding-bottom: 2rem;
            max-width: 1250px;
        }

        .main-title {
            font-size: 2.8rem;
            font-weight: 800;
            margin-bottom: 0.2rem;
        }

        .sub-title {
            color: #9aa4b2;
            font-size: 1rem;
            margin-bottom: 1.5rem;
        }

        .section-card {
            background: linear-gradient(135deg, rgba(20,25,35,0.95), rgba(10,14,22,0.95));
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 18px;
            padding: 20px 22px;
            margin-bottom: 18px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.18);
        }

        .metric-card {
            background: linear-gradient(135deg, rgba(25,31,44,1), rgba(16,20,29,1));
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 16px;
            padding: 16px 18px;
            margin-bottom: 10px;
        }

        .metric-label {
            color: #9aa4b2;
            font-size: 0.9rem;
            margin-bottom: 4px;
        }

        .metric-value {
            font-size: 1.25rem;
            font-weight: 700;
        }

        .result-success {
            background: linear-gradient(90deg, rgba(18,97,53,0.95), rgba(20,76,49,0.95));
            border-left: 6px solid #1db954;
            padding: 16px 18px;
            border-radius: 14px;
            margin-top: 12px;
            margin-bottom: 14px;
            font-size: 1.1rem;
            font-weight: 700;
        }

        .result-warning {
            background: linear-gradient(90deg, rgba(130,89,18,0.95), rgba(86,61,12,0.95));
            border-left: 6px solid #ffb020;
            padding: 14px 16px;
            border-radius: 12px;
            margin-top: 10px;
            margin-bottom: 12px;
        }

        .result-danger {
            background: linear-gradient(90deg, rgba(117,33,33,0.95), rgba(79,22,22,0.95));
            border-left: 6px solid #ff5a5a;
            padding: 16px 18px;
            border-radius: 14px;
            margin-top: 12px;
            margin-bottom: 14px;
            font-size: 1.1rem;
            font-weight: 700;
        }

        .sim-box {
            background: linear-gradient(135deg, rgba(24,37,63,0.98), rgba(13,21,38,0.98));
            border: 1px solid rgba(91,155,213,0.35);
            border-radius: 16px;
            padding: 18px 20px;
            margin-top: 16px;
            margin-bottom: 16px;
            box-shadow: 0 10px 28px rgba(0,0,0,0.16);
        }

        .sim-title {
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 8px;
            color: #cfe6ff;
        }

        .next-step-box {
            background: linear-gradient(90deg, rgba(18,97,53,0.95), rgba(20,76,49,0.95));
            border-left: 6px solid #1db954;
            padding: 16px 18px;
            border-radius: 14px;
            margin-top: 14px;
            margin-bottom: 14px;
            font-size: 1.05rem;
            font-weight: 700;
        }

        .small-note {
            color: #9aa4b2;
            font-size: 0.9rem;
        }

        div[data-testid="stDataFrame"] {
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 12px;
            overflow: hidden;
        }

        div[data-testid="stMetric"] {
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.05);
            padding: 8px 12px;
            border-radius: 12px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# HELPERS
# =========================================================
def assign_feed_bin(total_tph, start=FEED_BIN_START, end=FEED_BIN_END, step=FEED_BIN_STEP):
    if total_tph < start or total_tph >= end:
        return None
    bin_start = start + int((total_tph - start) // step) * step
    bin_end = bin_start + step
    return f"{int(bin_start)}-{int(bin_end)}"


def get_status(value, q25, q75, low_label, mid_label, high_label):
    if value < q25:
        return low_label
    elif value > q75:
        return high_label
    return mid_label


def classify_row(cement_category, feed_bin, mill_sound, be_amp):
    key = (cement_category, feed_bin)
    sound_ref = sound_lookup.get(key)
    amp_ref = amp_lookup.get(key)

    if sound_ref is None or amp_ref is None:
        return None

    sound_status = get_status(
        mill_sound,
        sound_ref["q25"],
        sound_ref["q75"],
        low_label="underloaded",
        mid_label="stable",
        high_label="overloaded",
    )

    amp_status = get_status(
        be_amp,
        amp_ref["q25"],
        amp_ref["q75"],
        low_label="low_load",
        mid_label="stable",
        high_label="high_load",
    )

    return sound_status, amp_status, sound_ref, amp_ref


decision_matrix = {
    ("underloaded", "low_load"): {
        "interpretation": "Underload",
        "action": "increase",
        "bias": 1,
    },
    ("underloaded", "stable"): {
        "interpretation": "Mild underload",
        "action": "increase",
        "bias": 0,
    },
    ("underloaded", "high_load"): {
        "interpretation": "Conflicting condition",
        "action": "increase",
        "bias": -1,
    },
    ("stable", "low_load"): {
        "interpretation": "Low utilization",
        "action": "increase",
        "bias": 0,
    },
    ("stable", "stable"): {
        "interpretation": "Optimal",
        "action": "maintain",
        "bias": 0,
    },
    ("stable", "high_load"): {
        "interpretation": "Overload tendency",
        "action": "reduce",
        "bias": 0,
    },
    ("overloaded", "low_load"): {
        "interpretation": "Conflicting condition",
        "action": "reduce",
        "bias": -1,
    },
    ("overloaded", "stable"): {
        "interpretation": "Overloaded",
        "action": "reduce",
        "bias": 0,
    },
    ("overloaded", "high_load"): {
        "interpretation": "Severe overload",
        "action": "reduce",
        "bias": 1,
    },
}


def compute_severity(value, q25, q75):
    band_width = max(q75 - q25, 0.1)
    if value < q25:
        return (q25 - value) / band_width
    elif value > q75:
        return (value - q75) / band_width
    return 0


def map_severity_level(deviation):
    if deviation < 0.5:
        return 1
    elif deviation < 1.0:
        return 2
    return 3


def get_feed_advisory(cement_category, total_tph, mill_sound, be_amp):
    if cement_category not in [0, 1]:
        return {"error": "Invalid cement category."}
    if total_tph <= 0 or mill_sound <= 0 or be_amp <= 0:
        return {"error": "All inputs must be greater than zero."}

    # =========================================
    # HARD SAFETY LIMITS (SME RULES)
    # =========================================
    if mill_sound >= 95:
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cement_category": cement_category,
            "product_name": CATEGORY_MAP.get(cement_category, str(cement_category)),
            "total_feed_tph": round(float(total_tph), 2),
            "feed_bin": "N/A",
            "mill_sound_pct": round(float(mill_sound), 2),
            "be_amp": round(float(be_amp), 2),
            "sound_status": "critical_overload",
            "amp_status": "critical_overload",
            "interpretation": "Severe choke risk",
            "tph_change": -5,
            "recommendation": "Reduce feed by 5 TPH immediately",
            "reason": "Mill pholaphone indicates severe choke condition (>95%). Immediate unloading required.",
            "caution": "Critical condition — take action immediately.",
            "sound_q25": None,
            "sound_median": None,
            "sound_q75": None,
            "amp_q25": None,
            "amp_median": None,
            "amp_q75": None,
        }

    elif mill_sound >= 87:
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cement_category": cement_category,
            "product_name": CATEGORY_MAP.get(cement_category, str(cement_category)),
            "total_feed_tph": round(float(total_tph), 2),
            "feed_bin": "N/A",
            "mill_sound_pct": round(float(mill_sound), 2),
            "be_amp": round(float(be_amp), 2),
            "sound_status": "high_load",
            "amp_status": "high_load",
            "interpretation": "Choke tendency",
            "tph_change": -3,
            "recommendation": "Reduce feed by 3 TPH",
            "reason": "Mill pholaphone above safe operating range (>87%). Preventive unloading recommended.",
            "caution": "Monitor closely — risk of choking if trend continues.",
            "sound_q25": None,
            "sound_median": None,
            "sound_q75": None,
            "amp_q25": None,
            "amp_median": None,
            "amp_q75": None,
        }



    feed_bin = assign_feed_bin(total_tph)
    if feed_bin is None:
        return {"error": f"Feed outside configured range {FEED_BIN_START}-{FEED_BIN_END} TPH."}

    classified = classify_row(cement_category, feed_bin, mill_sound, be_amp)
    if classified is None:
        return {"error": f"No lookup available for category={cement_category}, feed_bin={feed_bin}"}

    sound_status, amp_status, sound_ref, amp_ref = classified
    decision = decision_matrix[(sound_status, amp_status)]

    interpretation = decision["interpretation"]
    action = decision["action"]
    bias = decision["bias"]

    if action == "maintain":
        tph_change = 0
    else:
        deviation = compute_severity(mill_sound, sound_ref["q25"], sound_ref["q75"])
        base_level = map_severity_level(deviation)
        final_level = max(1, min(3, base_level + bias))
        tph_change = final_level if action == "increase" else -final_level

    if tph_change > 0:
        recommendation = f"Increase feed by {tph_change} TPH"
    elif tph_change < 0:
        recommendation = f"Reduce feed by {abs(tph_change)} TPH"
    else:
        recommendation = "Maintain current feed"

    reason = (
        f"Mill sound is '{sound_status}' and bucket elevator load condition is "
        f"'{amp_status}' for feed bin {feed_bin}."
    )

    caution = ""
    if interpretation == "Conflicting condition":
        caution = "Check bucket elevator load or separator condition before making a large feed correction."

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cement_category": cement_category,
        "product_name": CATEGORY_MAP.get(cement_category, str(cement_category)),
        "total_feed_tph": round(float(total_tph), 2),
        "feed_bin": feed_bin,
        "mill_sound_pct": round(float(mill_sound), 2),
        "be_amp": round(float(be_amp), 2),
        "sound_status": sound_status,
        "amp_status": amp_status,
        "interpretation": interpretation,
        "tph_change": tph_change,
        "recommendation": recommendation,
        "reason": reason,
        "caution": caution,
        "sound_q25": round(float(sound_ref["q25"]), 2),
        "sound_median": round(float(sound_ref["median"]), 2),
        "sound_q75": round(float(sound_ref["q75"]), 2),
        "amp_q25": round(float(amp_ref["q25"]), 2),
        "amp_median": round(float(amp_ref["median"]), 2),
        "amp_q75": round(float(amp_ref["q75"]), 2),
    }


def get_separator_advisory(cement_category, blaine, rpm):
    if cement_category not in [0, 1]:
        return {"error": "Invalid cement category."}
    if blaine <= 0 or rpm <= 0:
        return {"error": "Blaine and RPM must be greater than zero."}

    target = BLAINE_TARGETS[cement_category]
    target_blaine = target["target"]
    product_name = target["name"]

    blaine_gap_pct = ((target_blaine - blaine) / blaine) * 100
    suggested_rpm = rpm * (1 + blaine_gap_pct / 100)

    rpm_change = suggested_rpm

    if blaine_gap_pct > 0:
        interpretation = "Blaine below target"
        recommendation = f"New suggested separator RPM: {abs(suggested_rpm):.1f} RPM ({abs(blaine_gap_pct):.2f}%)"

    elif blaine_gap_pct < 0:
        interpretation = "Blaine above target"
        recommendation = f"New suggested separator RPM: {abs(suggested_rpm):.1f} RPM ({abs(blaine_gap_pct):.2f}%)"

    else:
        interpretation = "Blaine on target"
        recommendation = "Maintain current separator RPM"
    reason = (
        f"{product_name} target Blaine is {target_blaine}. "
        f"Current Blaine is {blaine:.2f}, so required correction is {blaine_gap_pct:.2f}%."
    )

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cement_category": cement_category,
        "product_name": product_name,
        "current_blaine": round(float(blaine), 2),
        "target_blaine": target_blaine,
        "blaine_gap_pct": round(float(blaine_gap_pct), 2),
        "current_rpm": round(float(rpm), 2),
        "suggested_rpm": round(float(suggested_rpm), 2),
        "interpretation": interpretation,
        "recommendation": recommendation,
        "reason": reason,
    }


def build_demo_simulation(sep_result, current_feed_tph, scenario_name):
    scenario = DEMO_SCENARIOS.get(
        scenario_name,
        DEMO_SCENARIOS["Scenario 1 - Increase RPM / Fuller Mill"],
    )

    if sep_result.get("interpretation") != scenario["required_interpretation"]:
        return None

    simulated_mill_sound = scenario["mill_sound_after"]
    simulated_be_amp = scenario["be_amp_after"]
    feed_bin = assign_feed_bin(current_feed_tph)

    predicted_feed_recommendation = scenario["fallback_recommendation"]
    predicted_interpretation = scenario["default_interpretation"]

    if feed_bin is not None:
        feed_preview = get_feed_advisory(
            sep_result["cement_category"],
            current_feed_tph,
            simulated_mill_sound,
            simulated_be_amp,
        )
        if "error" not in feed_preview:
            predicted_feed_recommendation = feed_preview["recommendation"]
            predicted_interpretation = feed_preview["interpretation"]

    return {
        "source": "separator_demo_mode",
        "scenario_name": scenario_name,
        "trigger": scenario["trigger"],
        "narrative": scenario["narrative"],
        "product_name": sep_result["product_name"],
        "cement_category": sep_result["cement_category"],
        "separator_rpm_before": sep_result["current_rpm"],
        "separator_rpm_after": sep_result["suggested_rpm"],
        "mill_sound_before": scenario["mill_sound_before"],
        "mill_sound_after": simulated_mill_sound,
        "be_amp_before": scenario["be_amp_before"],
        "be_amp_after": simulated_be_amp,
        "feed_tph_for_demo": current_feed_tph,
        "predicted_feed_recommendation": predicted_feed_recommendation,
        "predicted_feed_interpretation": predicted_interpretation,
    }


def append_to_csv(file_path, row_dict):
    row_df = pd.DataFrame([row_dict])
    if os.path.exists(file_path):
        row_df.to_csv(file_path, mode="a", header=False, index=False)
    else:
        row_df.to_csv(file_path, index=False)


def read_history(file_path):
    if os.path.exists(file_path):
        return pd.read_csv(file_path)
    return pd.DataFrame()


def render_input_label(label, range_text):
    st.markdown(
        f"""
        <div style="margin-bottom: 0.35rem;">
            <div style="font-weight: 600; font-size: 0.96rem;">{label}</div>
            <div class="small-note">Range: {range_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(label, value):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def apply_simulation_to_feed():
    sim = st.session_state.get("simulated_response")
    if not sim:
        return
    st.session_state.feed_cat = sim["cement_category"]
    st.session_state.total_tph = float(sim["feed_tph_for_demo"])
    st.session_state.mill_sound = float(sim["mill_sound_after"])
    st.session_state.be_amp = float(sim["be_amp_after"])
    st.session_state.applied_simulation = True


# =========================================================
# HEADER
# =========================================================
st.markdown('<div class="main-title">Cement Mill AI Advisory System</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Physics Based Process Stabilization AI advisory system for feed and separator control</div>',
    unsafe_allow_html=True,
)

sim_col, note_col = st.columns([1.1, 2.4])
with sim_col:
    demo_mode = st.toggle(
        "Demo Simulation Mode",
        value=st.session_state.demo_simulation_mode,
        help="When enabled, separator advisory can generate a linked plant-response demo for feed advisory.",
    )
    st.session_state.demo_simulation_mode = demo_mode
with note_col:
    if demo_mode:
        st.radio(
            "Demo Scenario",
            options=list(DEMO_SCENARIOS.keys()),
            horizontal=True,
            key="demo_scenario",
        )
        st.info(DEMO_SCENARIOS[st.session_state.demo_scenario]["header_note"])
    else:
        st.caption("Turn on Demo Simulation Mode to show linked cause-and-effect behavior between separator and feed control.")


tab1, tab2 = st.tabs(["Feed Advisory", "Separator Advisory"])

# =========================================================
# FEED TAB
# =========================================================
with tab1:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Feed Optimization")

    if st.session_state.get("applied_simulation"):
        st.markdown(
            '<div class="result-success">Demo simulation values are loaded in this tab. Run Feed Recommendation to show the downstream effect.</div>',
            unsafe_allow_html=True,
        )

    c1, c2 = st.columns(2)

    with c1:
        feed_cat = st.selectbox(
            "Cement Category",
            options=[0, 1],
            format_func=lambda x: f"{x} - {CATEGORY_MAP.get(x, x)}",
            key="feed_cat",
        )
        render_input_label("Total Feed (TPH)", "100-140")
        total_tph = st.number_input(
            "Total Feed (TPH)",
            min_value=float(FEED_BIN_START),
            max_value=float(FEED_BIN_END),
            value=float(st.session_state.total_tph),
            step=1.0,
            key="total_tph",
            label_visibility="collapsed",
        )
        render_input_label("Mill Sound (%)", "50-90")
        mill_sound = st.number_input(
            "Mill Sound (%)",
            min_value=0.01,
            max_value=150.0,
            value=float(st.session_state.mill_sound),
            step=1.0,
            key="mill_sound",
            label_visibility="collapsed",
        )

    with c2:
        render_input_label("Bucket Elevator AMP", "45-75")
        be_amp = st.number_input(
            "Bucket Elevator AMP",
            min_value=0.01,
            max_value=150.0,
            value=float(st.session_state.be_amp),
            step=1.0,
            key="be_amp",
            label_visibility="collapsed",
        )

        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("Advisory uses sound as loading signal and BE load as confirmation signal.")

    run_feed = st.button("Get Feed Recommendation", use_container_width=False)

    if run_feed:
        feed_result = get_feed_advisory(feed_cat, total_tph, mill_sound, be_amp)

        if "error" in feed_result:
            st.markdown(
                f'<div class="result-danger">{feed_result["error"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            append_to_csv(FEED_HISTORY_PATH, feed_result)

            st.markdown(
                f'<div class="result-success">{feed_result["recommendation"]}</div>',
                unsafe_allow_html=True,
            )

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                render_metric_card("Interpretation", feed_result["interpretation"])
            with m2:
                render_metric_card("Feed Bin", feed_result["feed_bin"])
            with m3:
                render_metric_card("Mill Sound Status", feed_result["sound_status"])
            with m4:
                render_metric_card("BE Load Status", feed_result["amp_status"])

            st.write(f"**Reason:** {feed_result['reason']}")
            if feed_result["caution"]:
                st.markdown(
                    f'<div class="result-warning">{feed_result["caution"]}</div>',
                    unsafe_allow_html=True,
                )

            with st.expander("Show lookup details used in decision"):
                d1, d2 = st.columns(2)
                with d1:
                    st.write("**Mill Sound Envelope**")
                    st.write(
                        {
                            "Q25": feed_result["sound_q25"],
                            "Median": feed_result["sound_median"],
                            "Q75": feed_result["sound_q75"],
                        }
                    )
                with d2:
                    st.write("**BE AMP Envelope**")
                    st.write(
                        {
                            "Q25": feed_result["amp_q25"],
                            "Median": feed_result["amp_median"],
                            "Q75": feed_result["amp_q75"],
                        }
                    )

    st.markdown("---")
    st.markdown("### Historical Combinations")

    feed_history = read_history(FEED_HISTORY_PATH)
    if not feed_history.empty:
        display_cols = [
            "timestamp",
            "product_name",
            "total_feed_tph",
            "feed_bin",
            "mill_sound_pct",
            "be_amp",
            "interpretation",
            "recommendation",
        ]
        display_cols = [c for c in display_cols if c in feed_history.columns]

        st.dataframe(
            feed_history[display_cols].sort_values("timestamp", ascending=False),
            use_container_width=True,
            height=320,
        )

        st.download_button(
            label="Download Feed History CSV",
            data=feed_history.to_csv(index=False).encode("utf-8"),
            file_name="feed_advisory_history.csv",
            mime="text/csv",
        )
    else:
        st.info("No feed advisory history saved yet.")

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# SEPARATOR TAB
# =========================================================
with tab2:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Fineness Control")

    c1, c2 = st.columns(2)

    with c1:
        sep_cat = st.selectbox(
            "Cement Category",
            options=[0, 1],
            format_func=lambda x: f"{x} - {CATEGORY_MAP.get(x, x)}",
            key="sep_cat",
        )
        render_input_label("Current Blaine(m2/kg)", "(250-450)")
        current_blaine = st.number_input(
            "Current Blaine",
            min_value=1.0,
            max_value=1000.0,
            value=float(st.session_state.current_blaine),
            step=1.0,
            key="current_blaine",
            label_visibility="collapsed",
        )

        selected_target = BLAINE_TARGETS[sep_cat]
        st.markdown(
            f'<div class="small-note"><b>Target Blaine Range in m2/kg:</b> {selected_target["name"]} = {selected_target["range"]}</div>',
            unsafe_allow_html=True,
        )

    with c2:
        render_input_label("Separator Drive Speed (RPM)", "500-950")
        current_rpm = st.number_input(
            "Separator Drive Speed (RPM)",
            min_value=1.0,
            max_value=2000.0,
            value=float(st.session_state.current_rpm),
            step=1.0,
            key="current_rpm",
            label_visibility="collapsed",
        )

    if demo_mode:
        st.caption(DEMO_SCENARIOS[st.session_state.demo_scenario]["demo_input_caption"])

    run_sep = st.button("Get Separator Recommendation", use_container_width=False)

    if run_sep:
        sep_result = get_separator_advisory(sep_cat, current_blaine, current_rpm)

        if "error" in sep_result:
            st.markdown(
                f'<div class="result-danger">{sep_result["error"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            append_to_csv(SEPARATOR_HISTORY_PATH, sep_result)

            st.markdown(
                f'<div class="result-success">{sep_result["recommendation"]}</div>',
                unsafe_allow_html=True,
            )

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                render_metric_card("Product", sep_result["product_name"])
            with m2:
                render_metric_card("Target Blaine", sep_result["target_blaine"])
            with m3:
                render_metric_card("Blaine Gap (%)", sep_result["blaine_gap_pct"])
            with m4:
                render_metric_card("Suggested RPM", sep_result["suggested_rpm"])

            st.write(f"**Interpretation:** {sep_result['interpretation']}")
            st.write(f"**Reason:** {sep_result['reason']}")

            if demo_mode:
                sim_result = build_demo_simulation(
                    sep_result,
                    st.session_state.total_tph,
                    st.session_state.demo_scenario,
                )
                st.session_state.simulated_response = sim_result
                st.session_state.applied_simulation = False

                if sim_result is not None:
                    st.markdown(
                        f"""
                        <div class="sim-box">
                            <div class="sim-title">Simulated Plant Response</div>
                            <div>{sim_result['narrative']}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    rpm_delta = sim_result["separator_rpm_after"] - sim_result["separator_rpm_before"]
                    be_delta = sim_result["be_amp_after"] - sim_result["be_amp_before"]
                    sound_delta = sim_result["mill_sound_after"] - sim_result["mill_sound_before"]

                    s1, s2, s3 = st.columns(3)

                    with s1:
                        st.metric(
                            "Mill Sound (%)",
                            f"{sim_result['mill_sound_before']:.1f} → {sim_result['mill_sound_after']:.1f}",
                            delta=f"{sound_delta:.1f}",
                        )

                    with s2:
                        st.metric(
                            "BE Load (AMP)",
                            f"{sim_result['be_amp_before']:.1f} → {sim_result['be_amp_after']:.1f}",
                            delta=f"{be_delta:.1f}",
                        )

                    with s3:
                        st.metric(
                            "Separator RPM",
                            f"{sim_result['separator_rpm_before']:.1f} → {sim_result['separator_rpm_after']:.1f}",
                            delta=f"{rpm_delta:.1f}",
                        )
                    st.write(f"**Expected feed-side interpretation:** {sim_result['predicted_feed_interpretation']}")
                    st.markdown(
                        f'<div class="next-step-box">Expected next feed recommendation within 15min: {sim_result["predicted_feed_recommendation"]}</div>',
                        unsafe_allow_html=True,
                    )

                    st.button(
                        "Use Simulated Response in Feed Advisory",
                        on_click=apply_simulation_to_feed,
                        use_container_width=False,
                    )
                else:
                    if st.session_state.demo_scenario == "Scenario 1 - Increase RPM / Fuller Mill":
                        st.info("Scenario 1 runs when Blaine is below target, so the separator recommendation becomes an RPM increase.")
                    else:
                        st.info("Scenario 2 runs when Blaine is above target, so the separator recommendation becomes an RPM decrease.")

    st.markdown("---")
    st.markdown("### Historical Combinations")

    sep_history = read_history(SEPARATOR_HISTORY_PATH)
    if not sep_history.empty:
        display_cols = [
            "timestamp",
            "product_name",
            "current_blaine",
            "target_blaine",
            "blaine_gap_pct",
            "current_rpm",
            "suggested_rpm",
            "recommendation",
        ]
        display_cols = [c for c in display_cols if c in sep_history.columns]

        st.dataframe(
            sep_history[display_cols].sort_values("timestamp", ascending=False),
            use_container_width=True,
            height=320,
        )

        st.download_button(
            label="Download Separator History CSV",
            data=sep_history.to_csv(index=False).encode("utf-8"),
            file_name="separator_advisory_history.csv",
            mime="text/csv",
        )
    else:
        st.info("No separator advisory history saved yet.")

    st.markdown('</div>', unsafe_allow_html=True)
