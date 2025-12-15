import os
import pandas as pd
import streamlit as st

# ---------- Basic page setup ----------

st.set_page_config(
    page_title="Property Matcher",
    layout="wide",
)

# ---------- File paths ----------

UNITS_FILE = "units.csv"
NOTICES_FILE = "notices.csv"
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


def get_selected_row(df: pd.DataFrame, label: str):
    if df.empty:
        st.info(f"No records found in {label}.")
        return None

    selection_col = "__row_index__"
    df_display = df.copy()
    df_display[selection_col] = range(len(df_display))

    st.dataframe(df_display.drop(columns=[selection_col]), use_container_width=True)

    row_options = list(range(len(df)))
    selected_idx = st.selectbox(
        f"Select a {label[:-1].lower()} to edit",
        options=["(None)"] + row_options,
        format_func=lambda x: "None" if x == "(None)" else f"Row {x}",
        key=f"{label}_row_select",
    )

    if selected_idx == "(None)":
        return None

    return int(selected_idx)


def show_record_form(df: pd.DataFrame, selected_idx: int, original_index: int, tab_name: str, file_path: str):
    st.markdown("---")
    st.subheader(f"{tab_name} details")

    columns = df.columns.tolist()

    default_values = {}
    if original_index is not None:
        row = df.loc[original_index]
        for col in columns:
            default_values[col] = row[col]
    else:
        for col in columns:
            default_values[col] = ""

    with st.form(f"{tab_name}_form", clear_on_submit=False):
        updated_values = {}
        col_left, col_right = st.columns(2)

        for i, col in enumerate(columns):
            target_col = col_left if i % 2 == 0 else col_right
            with target_col:
                updated_values[col] = st.text_input(
                    label=col,
                    value="" if pd.isna(default_values[col]) else str(default_values[col]),
                    key=f"{tab_name}_{col}_input"
                )

        col_a, col_b, col_c = st.columns([1, 1, 3])
        with col_a:
            add_submitted = st.form_submit_button("Add new", type="primary")
        with col_b:
            update_submitted = st.form_submit_button("Update selected")
        with col_c:
            delete_submitted = st.form_submit_button("Delete selected")

    # ADD
    if add_submitted:
        new_row = {col: updated_values[col] for col in columns}
        df_new = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_csv(df_new, file_path)
        st.success(f"New record added to {tab_name}.")
        st.rerun()

    # UPDATE
    if update_submitted:
        if original_index is None:
            st.warning("Please select a row to update.")
        else:
            df_new = df.copy()
            for col in columns:
                df_new.at[original_index, col] = updated_values[col]
            save_csv(df_new, file_path)
            st.success(f"{tab_name} record updated.")
            st.rerun()

    # DELETE
    if delete_submitted:
        if original_index is None:
            st.warning("Please select a row to delete.")
        else:
            df_new = df.drop(index=original_index).reset_index(drop=True)
            save_csv(df_new, file_path)
            st.success(f"{tab_name} record deleted.")
            st.rerun()


# ---------- Matching logic with Matched/Available ----------

def run_matching_logic(units_df: pd.DataFrame, notices_df: pd.DataFrame, waitlist_df: pd.DataFrame) -> pd.DataFrame:

    # Ensure Matched column exists
    if "Matched" not in units_df.columns:
        units_df["Matched"] = "Available"

    # Only match units that are Available
    units_df = units_df[units_df["Matched"].astype(str) == "Available"]

    if units_df.empty or waitlist_df.empty:
        return pd.DataFrame()

    # Simple placeholder matching logic
    units_df = units_df.copy()
    waitlist_df = waitlist_df.copy()

    units_df["key"] = 1
    waitlist_df["key"] = 1
    matched = pd.merge(units_df, waitlist_df, on="key", suffixes=("_unit", "_applicant")).drop(columns=["key"])

    if matched.empty:
        return matched

    matched["score"] = 1
    matched["match_status"] = "Pending"

    # Mark matched units
    matched_units = matched["Unit_unit"].astype(str).unique().tolist()

    full_units_df = load_csv(UNITS_FILE)
    full_units_df.loc[
        full_units_df["Unit"].astype(str).isin(matched_units),
        "Matched"
    ] = "Matched"

    save_csv(full_units_df, UNITS_FILE)

    return matched


# ---------- Main UI ----------

st.title("Property Matcher")
st.markdown(
    "<span style='color:#2CB1A1; font-weight:600;'>Internal matching dashboard</span>",
    unsafe_allow_html=True,
)
st.write("Use the tabs below to manage units, notices, waitlist, and matches, then run matching when you're ready.")

tabs = st.tabs(["Units", "Notices", "Waitlist", "Matches", "Run Matching"])

# ---------- Units Tab ----------
with tabs[0]:
    st.subheader("Units")

    units_df = load_csv(UNITS_FILE)


    edited_df = st.data_editor(
        units_df,
        use_container_width=True,
        num_rows="dynamic"
    )

    if st.button("Save Changes", type="primary"):
        save_csv(edited_df, UNITS_FILE)
        st.success("Units updated successfully.")
        st.rerun()

# ---------- Notices Tab ----------
with tabs[1]:
    st.subheader("Notices")

    units_df = load_csv(UNITS_FILE)

    # Filter: Ready Date is not empty
    notices_df = units_df[
        units_df["Ready Date"].astype(str).str.strip() != ""
    ]

    # Only show Unit + Ready Date
    notices_df = notices_df[["Unit", "Ready Date"]]

    # Global search
    search_query = st.text_input("Global search", "", key="notices_global_search")
    notices_filtered = global_search_filter(notices_df, search_query)

    if notices_filtered.empty:
        st.info("No units with a Ready Date.")
    else:
        st.dataframe(notices_filtered, use_container_width=True)

# ---------- Waitlist Tab ----------

with tabs[2]:
    st.subheader("Waitlist")
    waitlist_df = load_csv(WAITLIST_FILE)

    search_query = st.text_input("Global search", "", key="waitlist_global_search")
    waitlist_filtered = global_search_filter(waitlist_df, search_query)

    selected_idx = get_selected_row(waitlist_filtered, label="Waitlist")

    if selected_idx is not None and not waitlist_filtered.empty:
        original_index = waitlist_filtered.index[selected_idx]
    else:
        original_index = None

    show_record_form(waitlist_df, selected_idx, original_index, tab_name="Waitlist", file_path=WAITLIST_FILE)

# ---------- Matches Tab ----------

with tabs[3]:
    st.subheader("Matches")
    matches_df = load_csv(MATCHES_FILE)

    search_query = st.text_input("Global search", "", key="matches_global_search")
    matches_filtered = global_search_filter(matches_df, search_query)

    if matches_filtered.empty:
        st.info("No matches found yet. Run matching from the 'Run Matching' tab.")
    else:
        st.dataframe(matches_filtered, use_container_width=True)

# ---------- Run Matching Tab ----------

with tabs[4]:
    st.subheader("Run Matching")

    st.write("Use this tab to run your matching logic based on current Units, Notices, and Waitlist data.")

    col1, col2 = st.columns([1, 3])
    with col1:
        run_button = st.button("Run Matching", type="primary")
    with col2:
        st.write("Click to generate matches and update the Matches table.")

    if run_button:
        units_df = load_csv(UNITS_FILE)
        notices_df = load_csv(NOTICES_FILE)
        waitlist_df = load_csv(WAITLIST_FILE)

        if units_df.empty:
            st.warning("Units data is empty. Please add units first.")
        elif waitlist_df.empty:
            st.warning("Waitlist data is empty. Please add applicants first.")
        else:
            matches_df = run_matching_logic(units_df, notices_df, waitlist_df)
            save_csv(matches_df, MATCHES_FILE)

            if matches_df.empty:
                st.warning("Matching completed, but no matches were produced.")
            else:
                st.success("Matching completed successfully.")
                st.dataframe(matches_df, use_container_width=True)
