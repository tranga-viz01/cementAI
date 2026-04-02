import os
from datetime import datetime

import numpy as np
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
    0: {"name": "PPC", "target": 395},
    1: {"name": "OPC", "target": 295},
}

FEED_BIN_START = 100
FEED_BIN_END = 140
FEED_BIN_STEP = 2

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

        .small-note {
            color: #9aa4b2;
            font-size: 0.9rem;
        }

        div[data-testid="stDataFrame"] {
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 12px;
            overflow: hidden;
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
        low_label="overloaded",
        mid_label="stable",
        high_label="underloaded",
    )

    amp_status = get_status(
        be_amp,
        amp_ref["q25"],
        amp_ref["q75"],
        low_label="low_circulation",
        mid_label="stable",
        high_label="high_circulation",
    )

    return sound_status, amp_status, sound_ref, amp_ref


decision_matrix = {
    ("underloaded", "low_circulation"): {
        "interpretation": "Underload",
        "action": "increase",
        "bias": 1,
    },
    ("underloaded", "stable"): {
        "interpretation": "Mild underload",
        "action": "increase",
        "bias": 0,
    },
    ("underloaded", "high_circulation"): {
        "interpretation": "Conflicting condition",
        "action": "increase",
        "bias": -1,
    },
    ("stable", "low_circulation"): {
        "interpretation": "Low utilization",
        "action": "increase",
        "bias": 0,
    },
    ("stable", "stable"): {
        "interpretation": "Optimal",
        "action": "maintain",
        "bias": 0,
    },
    ("stable", "high_circulation"): {
        "interpretation": "Overload tendency",
        "action": "reduce",
        "bias": 0,
    },
    ("overloaded", "low_circulation"): {
        "interpretation": "Conflicting condition",
        "action": "reduce",
        "bias": -1,
    },
    ("overloaded", "stable"): {
        "interpretation": "Overloaded",
        "action": "reduce",
        "bias": 0,
    },
    ("overloaded", "high_circulation"): {
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
        f"Mill sound is '{sound_status}' and bucket elevator condition is "
        f"'{amp_status}' for feed bin {feed_bin}."
    )

    caution = ""
    if interpretation == "Conflicting condition":
        caution = "Check circulation or separator condition before making a large feed correction."

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

    if blaine_gap_pct > 0:
        interpretation = "Blaine below target"
        recommendation = f"Increase separator RPM by {abs(blaine_gap_pct):.2f}%"
    elif blaine_gap_pct < 0:
        interpretation = "Blaine above target"
        recommendation = f"Reduce separator RPM by {abs(blaine_gap_pct):.2f}%"
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


# =========================================================
# HEADER
# =========================================================
st.markdown('<div class="main-title">Cement Mill AI Advisory System</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Physics Based Process Stabilization AI advisory system for feed and separator control</div>',
    unsafe_allow_html=True,
)

tab1, tab2 = st.tabs(["Feed Advisory", "Separator Advisory"])

# =========================================================
# FEED TAB
# =========================================================
with tab1:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Feed Optimization")

    c1, c2 = st.columns(2)

    with c1:
        feed_cat = st.selectbox(
            "Cement Category",
            options=[0, 1],
            format_func=lambda x: f"{x} - {CATEGORY_MAP.get(x, x)}",
            key="feed_cat",
        )
        total_tph = st.number_input(
            "Total Feed (TPH)",
            min_value=float(FEED_BIN_START),
            max_value=float(FEED_BIN_END),
            value=120.0,
            step=1.0,
        )
        mill_sound = st.number_input(
            "Mill Sound (%)",
            min_value=0.01,
            max_value=150.0,
            value=70.0,
            step=1.0,
        )

    with c2:
        be_amp = st.number_input(
            "Bucket Elevator AMP",
            min_value=0.01,
            max_value=150.0,
            value=55.0,
            step=1.0,
        )

        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("Advisory uses sound as loading signal and BE amp as circulation confirmation signal.")

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
                render_metric_card("Sound Status", feed_result["sound_status"])
            with m4:
                render_metric_card("AMP Status", feed_result["amp_status"])

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
        current_blaine = st.number_input(
            "Current Blaine",
            min_value=1.0,
            max_value=1000.0,
            value=360.0,
            step=1.0,
        )

    with c2:
        current_rpm = st.number_input(
            "Current Separator RPM",
            min_value=1.0,
            max_value=2000.0,
            value=700.0,
            step=1.0,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("Advisory uses target Blaine midpoint and proportional RPM correction.")

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