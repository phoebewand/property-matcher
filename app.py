import os
import pandas as pd
import streamlit as st

# ---------- Basic page setup ----------
st.set_page_config(page_title="Property Matcher", layout="wide")

# ---------- File paths ----------
UNITS_FILE = "units.csv"
WAITLIST_FILE = "waitlist.csv"
MATCHES_FILE = "matches.csv"

# ---------- Utility functions ----------
@st.cache_data
def load_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
    return df

def save_csv(df: pd.DataFrame, path: str):
    df.to_csv(path, index=False)
    load_csv.clear()

def global_search_filter(df: pd.DataFrame, search_query: str) -> pd.DataFrame:
    if not search_query or df.empty:
        return df
    mask = pd.Series([False] * len(df))
    for col in df.columns:
        mask = mask | df[col].astype(str).str.contains(search_query, case=False, na=False)
    return df[mask]

# ---------- Matching logic ----------
def run_matching_logic(units_df: pd.DataFrame, waitlist_df: pd.DataFrame, priorities: list) -> pd.DataFrame:

    # Only include units with Ready Date
    units_df = units_df[units_df["Ready Date"].astype(str).str.strip() != ""]
    if units_df.empty or waitlist_df.empty:
        return pd.DataFrame()

    matches = []

    # Priority weights: 100, 10, 1
    priority_weights = {
        priorities[i]: 10 ** (len(priorities) - i - 1)
        for i in range(len(priorities))
    }

    # Floor Plan preference weights
    fp_weights = {
        "Floor Plan 1": 100,
        "Floor Plan 2": 50,
        "Floor Plan 3": 25
    }

    for _, applicant in waitlist_df.iterrows():
        best_score = -1
        best_unit = None

        for _, unit in units_df.iterrows():
            score = 0

            for field in priorities:

                # ---------- Floor Plan (special logic) ----------
                if field == "Floor Plan":
                    if unit["Floor Plan"] == applicant["Floor Plan 1"]:
                        score += fp_weights["Floor Plan 1"] * priority_weights[field]
                    elif unit["Floor Plan"] == applicant["Floor Plan 2"]:
                        score += fp_weights["Floor Plan 2"] * priority_weights[field]
                    elif unit["Floor Plan"] == applicant["Floor Plan 3"]:
                        score += fp_weights["Floor Plan 3"] * priority_weights[field]

                # ---------- Floor ----------
                elif field == "Floor":
                    if str(unit["Floor"]).strip() == str(applicant["Floor"]).strip():
                        score += priority_weights[field]

                # ---------- Direction ----------
                elif field == "Direction":
                    if unit["Direction"] == applicant["Direction"]:
                        score += priority_weights[field]

            if score > best_score:
                best_score = score
                best_unit = unit

        if best_unit is not None:
            matches.append({
                "Applicant": applicant["Applicant"],
                "Unit": best_unit["Unit"],
                "Score": best_score,
                "Floor Plan Match": best_unit["Floor Plan"],
                "Ready Date": best_unit["Ready Date"]
            })

    return pd.DataFrame(matches)

# ---------- Main UI ----------
st.title("Property Matcher")
st.markdown("<span style='color:#2CB1A1; font-weight:600;'>Internal matching dashboard</span>", unsafe_allow_html=True)

tabs = st.tabs(["Units", "Notices", "Waitlist", "Matches", "Run Matching"])

# ---------- Units Tab ----------
with tabs[0]:
    st.subheader("Units")
    units_df = load_csv(UNITS_FILE)
    edited_df = st.data_editor(units_df, use_container_width=True, num_rows="dynamic")
    if st.button("Save Units", type="primary"):
        save_csv(edited_df, UNITS_FILE)
        st.success("Units updated successfully.")
        st.rerun()

# ---------- Notices Tab ----------
with tabs[1]:
    st.subheader("Notices")
    units_df = load_csv(UNITS_FILE)
    notices_df = units_df[
    units_df["Ready Date"].fillna("").astype(str).str.strip() != ""
]
    notices_df = notices_df[["Unit", "Ready Date"]]
    search_query = st.text_input("Search", "", key="notices_search")
    notices_filtered = global_search_filter(notices_df, search_query)
    st.dataframe(notices_filtered, use_container_width=True)

# ---------- Waitlist Tab ----------
with tabs[2]:
    st.subheader("Waitlist")

    waitlist_df = load_csv(WAITLIST_FILE)

    edited_waitlist = st.data_editor(
        waitlist_df,
        use_container_width=True,
        num_rows="dynamic"
    )

    if st.button("Save Waitlist", type="primary"):
        save_csv(edited_waitlist, WAITLIST_FILE)
        st.success("Waitlist updated successfully.")
        st.rerun()

# ---------- Matches Tab ----------
with tabs[3]:
    st.subheader("Matches")
    matches_df = load_csv(MATCHES_FILE)
    search_query = st.text_input("Search", "", key="matches_search")
    matches_filtered = global_search_filter(matches_df, search_query)
    st.dataframe(matches_filtered, use_container_width=True)

# ---------- Run Matching Tab ----------
with tabs[4]:
    st.subheader("Run Matching")

    st.write("Choose your matching priorities:")

    priorities = st.multiselect(
        "Select and order priorities",
        options=["Floor Plan", "Floor", "Direction"],
        default=["Floor Plan", "Floor", "Direction"]
    )

    run_button = st.button("Run Matching", type="primary")

    if run_button:
        units_df = load_csv(UNITS_FILE)
        waitlist_df = load_csv(WAITLIST_FILE)

        if units_df.empty:
            st.warning("Units data is empty.")
        elif waitlist_df.empty:
            st.warning("Waitlist is empty.")
        else:
            matches_df = run_matching_logic(units_df, waitlist_df, priorities)
            save_csv(matches_df, MATCHES_FILE)
            st.success("Matching completed.")
            st.dataframe(matches_df, use_container_width=True)
