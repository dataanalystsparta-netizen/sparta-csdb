
import streamlit as st
import pandas as pd
import numpy as np
import gspread

from google.oauth2.service_account import Credentials
from datetime import datetime, date, time


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="ACD Time & Agent Performance",
    page_icon="📞",
    layout="wide"
)


# ============================================================
# CONSTANTS
# ============================================================

SPREADSHEET_ID = "1R7ioNIYj7iAK3kN21WWlrxy9J9qEdRM9GOebCnUQNpI"

WORKSHEET_NAME = "ACD_Data"


SOURCE_COLUMNS = [
    "#",
    "Campaign Name",
    "Phone",
    "DNIS",
    "Call Type",
    "Call ID",
    "Answered/Hungup",
    "Call Time",
    "Queue ID",
    "Queue Name",
    "Wait Time at ACD",
    "Total Wait Time",
    "Hangup Details",
    "Customer Hold Duration",
    "Actual Channel",
    "Username",
    "User ID",
    "User Setup Time",
    "User Ringing Time",
    "User Talk Time",
    "User Hold Duration",
    "Cumulative User Talk Time",
    "ACW Duration",
    "User Disposition Code",
    "Call Notes",
]


EXTRA_COLUMNS = [
    "Call Date",
    "Call Time Only",
    "AHT Seconds",
    "AHT",
    "ASA Seconds",
    "ASA",
    "ACW Seconds",
    "ACW",
    "Upload Date",
]


ALL_COLUMNS = SOURCE_COLUMNS + EXTRA_COLUMNS


# ============================================================
# GOOGLE SHEETS CONNECTION
# ============================================================

@st.cache_resource
def get_gspread_client():

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )

    return gspread.authorize(credentials)


@st.cache_resource
def get_worksheet():

    client = get_gspread_client()

    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    try:
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

    except gspread.WorksheetNotFound:

        worksheet = spreadsheet.add_worksheet(
            title=WORKSHEET_NAME,
            rows=1000,
            cols=len(ALL_COLUMNS)
        )

        worksheet.append_row(
            ALL_COLUMNS,
            value_input_option="USER_ENTERED"
        )

    return worksheet


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def clean_string(value):

    if pd.isna(value):
        return ""

    return str(value).strip()


def duration_to_seconds(value):

    if pd.isna(value):
        return 0

    value = str(value).strip()

    if not value:
        return 0

    try:

        parts = value.split(":")

        if len(parts) == 3:

            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])

            return int(hours * 3600 + minutes * 60 + seconds)

        elif len(parts) == 2:

            minutes = int(parts[0])
            seconds = float(parts[1])

            return int(minutes * 60 + seconds)

        else:

            return 0

    except Exception:

        return 0


def seconds_to_hhmmss(seconds):

    if pd.isna(seconds):
        return "00:00:00"

    seconds = max(0, int(round(seconds)))

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_average_seconds(seconds):

    if pd.isna(seconds):
        return "00:00:00"

    return seconds_to_hhmmss(seconds)


def normalize_agent_name(value):

    value = clean_string(value)

    if not value:
        return "Call Dropped"

    return value


# ============================================================
# PROCESS UPLOADED CSV
# ============================================================

def process_uploaded_csv(uploaded_file):

    df = pd.read_csv(
        uploaded_file,
        dtype=str,
        keep_default_na=False
    )

    # --------------------------------------------------------
    # Validate columns
    # --------------------------------------------------------

    missing_columns = [
        column
        for column in SOURCE_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:

        st.error(
            "The uploaded CSV is missing these required columns:\n\n"
            + "\n".join(f"- {x}" for x in missing_columns)
        )

        return None

    # --------------------------------------------------------
    # Keep only expected source columns
    # --------------------------------------------------------

    df = df[SOURCE_COLUMNS].copy()

    # --------------------------------------------------------
    # Clean strings
    # --------------------------------------------------------

    for column in SOURCE_COLUMNS:

        df[column] = df[column].map(clean_string)

    # --------------------------------------------------------
    # Remove blank Call IDs
    # --------------------------------------------------------

    df = df[df["Call ID"] != ""].copy()

    # --------------------------------------------------------
    # Deduplicate within upload
    # --------------------------------------------------------

    df = df.drop_duplicates(
        subset=["Call ID"],
        keep="first"
    ).copy()

    # --------------------------------------------------------
    # Parse Call Time
    # --------------------------------------------------------

    df["Parsed Call Time"] = pd.to_datetime(
        df["Call Time"],
        dayfirst=True,
        errors="coerce"
    )

    # --------------------------------------------------------
    # Agent blank -> Call Dropped
    # --------------------------------------------------------

    df["Username"] = df["Username"].apply(
        normalize_agent_name
    )

    # --------------------------------------------------------
    # Date
    # --------------------------------------------------------

    df["Call Date"] = df["Parsed Call Time"].dt.strftime(
        "%Y-%m-%d"
    )

    # --------------------------------------------------------
    # Time
    # --------------------------------------------------------

    df["Call Time Only"] = df["Parsed Call Time"].dt.strftime(
        "%H:%M:%S"
    )

    # --------------------------------------------------------
    # Duration conversions
    # --------------------------------------------------------

    df["Talk Seconds"] = df["User Talk Time"].apply(
        duration_to_seconds
    )

    df["Hold Seconds"] = df["User Hold Duration"].apply(
        duration_to_seconds
    )

    df["ACW Seconds"] = df["ACW Duration"].apply(
        duration_to_seconds
    )

    df["ASA Seconds"] = df["Total Wait Time"].apply(
        duration_to_seconds
    )

    # --------------------------------------------------------
    # AHT
    #
    # AHT =
    # User Talk Time
    # + User Hold Duration
    # + ACW Duration
    # --------------------------------------------------------

    df["AHT Seconds"] = (
        df["Talk Seconds"]
        + df["Hold Seconds"]
        + df["ACW Seconds"]
    )

    df["AHT"] = df["AHT Seconds"].apply(
        seconds_to_hhmmss
    )

    # --------------------------------------------------------
    # ASA
    #
    # ASA = Total Wait Time
    # --------------------------------------------------------

    df["ASA"] = df["ASA Seconds"].apply(
        seconds_to_hhmmss
    )

    # --------------------------------------------------------
    # ACW
    # --------------------------------------------------------

    df["ACW"] = df["ACW Seconds"].apply(
        seconds_to_hhmmss
    )

    # --------------------------------------------------------
    # Upload date
    # --------------------------------------------------------

    df["Upload Date"] = datetime.now().strftime(
        "%Y-%m-%d"
    )

    # --------------------------------------------------------
    # Remove helper columns
    # --------------------------------------------------------

    df = df.drop(
        columns=[
            "Parsed Call Time",
            "Talk Seconds",
            "Hold Seconds",
        ],
        errors="ignore"
    )

    # --------------------------------------------------------
    # Make sure exact Google Sheet column order
    # --------------------------------------------------------

    for column in ALL_COLUMNS:

        if column not in df.columns:

            df[column] = ""

    df = df[ALL_COLUMNS]

    return df


# ============================================================
# GET EXISTING CALL IDS
# ============================================================

def get_existing_call_ids(worksheet):

    try:

        # Call ID is column F
        values = worksheet.col_values(6)

        if not values:
            return set()

        return set(
            str(value).strip()
            for value in values[1:]
            if str(value).strip()
        )

    except Exception:

        return set()


# ============================================================
# APPEND NEW DATA
# ============================================================

def append_new_records(df):

    worksheet = get_worksheet()

    existing_call_ids = get_existing_call_ids(
        worksheet
    )

    new_df = df[
        ~df["Call ID"].isin(existing_call_ids)
    ].copy()

    if new_df.empty:

        return 0

    rows = new_df.fillna("").astype(str).values.tolist()

    worksheet.append_rows(
        rows,
        value_input_option="USER_ENTERED"
    )

    return len(rows)


# ============================================================
# LOAD HISTORICAL DATA
# ============================================================

@st.cache_data(ttl=60)
def load_historical_data():

    worksheet = get_worksheet()

    records = worksheet.get_all_records()

    if not records:

        return pd.DataFrame(
            columns=ALL_COLUMNS
        )

    df = pd.DataFrame(records)

    # Make sure expected columns exist
    for column in ALL_COLUMNS:

        if column not in df.columns:

            df[column] = ""

    df = df[ALL_COLUMNS].copy()

    # --------------------------------------------------------
    # Normalize agent names
    # --------------------------------------------------------

    df["Username"] = df["Username"].apply(
        normalize_agent_name
    )

    # --------------------------------------------------------
    # Parse date/time
    # --------------------------------------------------------

    df["Parsed Call Time"] = pd.to_datetime(
        df["Call Time"],
        dayfirst=True,
        errors="coerce"
    )

    # If Call Time could not be parsed, try Call Date
    invalid_time = df["Parsed Call Time"].isna()

    if invalid_time.any():

        fallback_dates = pd.to_datetime(
            df.loc[invalid_time, "Call Date"],
            errors="coerce"
        )

        df.loc[
            invalid_time,
            "Parsed Call Time"
        ] = fallback_dates

    # --------------------------------------------------------
    # Ensure Call Date is a proper date
    # --------------------------------------------------------

    df["Call Date Parsed"] = (
        df["Parsed Call Time"].dt.date
    )

    # --------------------------------------------------------
    # Ensure time
    # --------------------------------------------------------

    df["Call Time Parsed"] = (
        df["Parsed Call Time"].dt.time
    )

    return df


# ============================================================
# SIDEBAR / UPLOAD
# ============================================================

st.title("📞 ACD Time & Agent Performance")

st.caption(
    "ACD call performance dashboard with historical Google Sheets storage."
)


# ============================================================
# TOP FILTERS
# ============================================================

st.markdown("### 🔎 Dashboard Filters")


df = load_historical_data()


if df.empty:

    st.info(
        "No historical data is currently available. "
        "Upload an ACD CSV below to begin."
    )

    min_available_date = date.today()
    max_available_date = date.today()

else:

    valid_dates = df["Call Date Parsed"].dropna()

    if valid_dates.empty:

        min_available_date = date.today()
        max_available_date = date.today()

    else:

        min_available_date = min(valid_dates)
        max_available_date = max(valid_dates)


# ------------------------------------------------------------
# Date filter
# ------------------------------------------------------------

filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)


with filter_col1:

    selected_dates = st.date_input(
        "📅 Date",
        value=(
            min_available_date,
            max_available_date
        ),
        min_value=min_available_date,
        max_value=max_available_date,
        format="DD-MM-YYYY"
    )


# Handle Streamlit single-date selection
if isinstance(selected_dates, tuple):

    if len(selected_dates) == 2:

        start_date = selected_dates[0]
        end_date = selected_dates[1]

    else:

        start_date = selected_dates[0]
        end_date = selected_dates[0]

else:

    start_date = selected_dates
    end_date = selected_dates


# ------------------------------------------------------------
# Time filter
# ------------------------------------------------------------

with filter_col2:

    selected_time_range = st.slider(
        "🕐 Time",
        min_value=time(0, 0),
        max_value=time(23, 59),
        value=(
            time(0, 0),
            time(23, 59)
        ),
        format="HH:mm"
    )


start_time = selected_time_range[0]
end_time = selected_time_range[1]


# ------------------------------------------------------------
# Queue filter
# ------------------------------------------------------------

with filter_col3:

    queue_options = sorted(
        [
            x for x in df["Queue Name"].dropna().unique()
            if str(x).strip()
        ]
    )

    selected_queues = st.multiselect(
        "📋 Queue Name",
        options=queue_options,
        default=queue_options
    )


# ------------------------------------------------------------
# Disposition filter
# ------------------------------------------------------------

with filter_col4:

    disposition_options = sorted(
        [
            x
            for x in df["User Disposition Code"].dropna().unique()
            if str(x).strip()
        ]
    )

    selected_dispositions = st.multiselect(
        "🏷️ User Disposition Code",
        options=disposition_options,
        default=disposition_options
    )


# ============================================================
# SECOND ROW OF FILTERS
# ============================================================

filter_col5, filter_col6, filter_col7, filter_col8 = st.columns(4)


with filter_col5:

    agent_options = sorted(
        [
            x
            for x in df["Username"].dropna().unique()
            if str(x).strip()
        ]
    )

    selected_agents = st.multiselect(
        "👤 Agent",
        options=agent_options,
        default=agent_options
    )


with filter_col6:

    campaign_options = sorted(
        [
            x
            for x in df["Campaign Name"].dropna().unique()
            if str(x).strip()
        ]
    )

    selected_campaigns = st.multiselect(
        "📢 Campaign",
        options=campaign_options,
        default=campaign_options
    )


# ------------------------------------------------------------
# Upload section
# ------------------------------------------------------------

with filter_col7:

    uploaded_file = st.file_uploader(
        "📤 Upload ACD CSV",
        type=["csv"]
    )


with filter_col8:

    st.write("")
    st.write("")

    if st.button(
        "🔄 Refresh Data",
        use_container_width=True
    ):

        st.cache_data.clear()

        st.rerun()


# ============================================================
# PROCESS UPLOAD
# ============================================================

if uploaded_file is not None:

    file_signature = (
        uploaded_file.name,
        uploaded_file.size
    )

    if (
        "last_uploaded_file" not in st.session_state
        or st.session_state.last_uploaded_file
        != file_signature
    ):

        with st.spinner(
            "Processing ACD CSV..."
        ):

            uploaded_df = process_uploaded_csv(
                uploaded_file
            )

            if uploaded_df is not None:

                try:

                    added_count = append_new_records(
                        uploaded_df
                    )

                    st.session_state.last_uploaded_file = (
                        file_signature
                    )

                    st.cache_data.clear()

                    if added_count > 0:

                        st.success(
                            f"✅ {added_count:,} new call records "
                            f"added to Google Sheets."
                        )

                    else:

                        st.info(
                            "ℹ️ No new records found. "
                            "All Call IDs already exist."
                        )

                    # Reload data after upload
                    df = load_historical_data()

                except Exception as e:

                    st.error(
                        "Unable to save the uploaded data "
                        f"to Google Sheets.\n\n{e}"
                    )


# ============================================================
# APPLY ALL TOP FILTERS
# ============================================================

filtered_df = df.copy()


if not filtered_df.empty:

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    filtered_df = filtered_df[
        filtered_df["Call Date Parsed"].notna()
    ].copy()

    filtered_df = filtered_df[
        (
            filtered_df["Call Date Parsed"] >= start_date
        )
        &
        (
            filtered_df["Call Date Parsed"] <= end_date
        )
    ].copy()

    # --------------------------------------------------------
    # TIME
    # --------------------------------------------------------

    def time_in_range(t):

        if pd.isna(t):

            return False

        if isinstance(t, datetime):

            t = t.time()

        if not isinstance(t, time):

            return False

        # Normal range
        if start_time <= end_time:

            return (
                start_time
                <= t
                <= end_time
            )

        # Overnight range, e.g. 22:00 -> 06:00
        return (
            t >= start_time
            or t <= end_time
        )


    filtered_df = filtered_df[
        filtered_df["Call Time Parsed"].apply(
            time_in_range
        )
    ].copy()

    # --------------------------------------------------------
    # QUEUE
    # --------------------------------------------------------

    if selected_queues:

        filtered_df = filtered_df[
            filtered_df["Queue Name"].isin(
                selected_queues
            )
        ].copy()

    else:

        filtered_df = filtered_df.iloc[0:0].copy()

    # --------------------------------------------------------
    # USER DISPOSITION
    # --------------------------------------------------------

    if selected_dispositions:

        filtered_df = filtered_df[
            filtered_df[
                "User Disposition Code"
            ].isin(selected_dispositions)
        ].copy()

    else:

        filtered_df = filtered_df.iloc[0:0].copy()

    # --------------------------------------------------------
    # AGENT
    # --------------------------------------------------------

    if selected_agents:

        filtered_df = filtered_df[
            filtered_df["Username"].isin(
                selected_agents
            )
        ].copy()

    else:

        filtered_df = filtered_df.iloc[0:0].copy()

    # --------------------------------------------------------
    # CAMPAIGN
    # --------------------------------------------------------

    if selected_campaigns:

        filtered_df = filtered_df[
            filtered_df["Campaign Name"].isin(
                selected_campaigns
            )
        ].copy()

    else:

        filtered_df = filtered_df.iloc[0:0].copy()


# ============================================================
# KPI CALCULATIONS
# ============================================================

total_calls = len(filtered_df)


if total_calls > 0:

    avg_aht = pd.to_numeric(
        filtered_df["AHT Seconds"],
        errors="coerce"
    ).mean()

    avg_asa = pd.to_numeric(
        filtered_df["ASA Seconds"],
        errors="coerce"
    ).mean()

    avg_acw = pd.to_numeric(
        filtered_df["ACW Seconds"],
        errors="coerce"
    ).mean()

else:

    avg_aht = 0
    avg_asa = 0
    avg_acw = 0


# ============================================================
# KPI CARDS
# ============================================================

st.markdown("---")


col1, col2, col3, col4 = st.columns(4)


with col1:

    st.metric(
        "📞 Calls",
        f"{total_calls:,}",
        help=(
            "Total number of unique calls in the "
            "selected filters.\n\n"
            "Unique Call ID is used to identify each call."
        )
    )


with col2:

    st.metric(
        "⏱️ Average AHT",
        format_average_seconds(avg_aht),
        help=(
            "Average Handling Time (AHT)\n\n"
            "Calculated from the ACD report columns:\n"
            "• User Talk Time\n"
            "• User Hold Duration\n"
            "• ACW Duration\n\n"
            "Formula:\n"
            "AHT = User Talk Time + User Hold Duration "
            "+ ACW Duration"
        )
    )


with col3:

    st.metric(
        "⚡ Average ASA",
        format_average_seconds(avg_asa),
        help=(
            "Average Speed of Answer (ASA)\n\n"
            "Calculated directly from the ACD report column:\n"
            "• Total Wait Time\n\n"
            "Formula:\n"
            "ASA = Average of Total Wait Time"
        )
    )


with col4:

    st.metric(
        "📝 Average ACW",
        format_average_seconds(avg_acw),
        help=(
            "Average After Call Work (ACW)\n\n"
            "Calculated directly from the ACD report column:\n"
            "• ACW Duration\n\n"
            "Formula:\n"
            "ACW = Average of ACW Duration"
        )
    )


# ============================================================
# FILTER SUMMARY
# ============================================================

st.caption(
    f"Showing {total_calls:,} calls | "
    f"{start_date.strftime('%d-%m-%Y')} to "
    f"{end_date.strftime('%d-%m-%Y')} | "
    f"{start_time.strftime('%H:%M')}–"
    f"{end_time.strftime('%H:%M')}"
)


# ============================================================
# AGENT PERFORMANCE
# ============================================================

st.markdown("## 👤 Agent Performance")


if filtered_df.empty:

    st.info(
        "No calls match the selected filters."
    )

else:

    agent_summary = (
        filtered_df
        .groupby("Username", dropna=False)
        .agg(
            Calls=("Call ID", "nunique"),
            Avg_AHT=("AHT Seconds", "mean"),
            Avg_ASA=("ASA Seconds", "mean"),
            Avg_ACW=("ACW Seconds", "mean"),
        )
        .reset_index()
    )

    agent_summary = agent_summary.rename(
        columns={
            "Username": "Agent",
            "Avg_AHT": "Average AHT",
            "Avg_ASA": "Average ASA",
            "Avg_ACW": "Average ACW",
        }
    )

    agent_summary["Average AHT"] = (
        agent_summary["Average AHT"]
        .apply(seconds_to_hhmmss)
    )

    agent_summary["Average ASA"] = (
        agent_summary["Average ASA"]
        .apply(seconds_to_hhmmss)
    )

    agent_summary["Average ACW"] = (
        agent_summary["Average ACW"]
        .apply(seconds_to_hhmmss)
    )

    agent_summary = agent_summary.sort_values(
        "Calls",
        ascending=False
    )

    st.dataframe(
        agent_summary,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# DAILY PERFORMANCE
# ============================================================

st.markdown("## 📅 Daily Performance")


if filtered_df.empty:

    st.info(
        "No daily data available for the selected filters."
    )

else:

    daily_summary = (
        filtered_df
        .groupby(
            "Call Date Parsed",
            dropna=False
        )
        .agg(
            Calls=("Call ID", "nunique"),
            Avg_AHT=("AHT Seconds", "mean"),
            Avg_ASA=("ASA Seconds", "mean"),
            Avg_ACW=("ACW Seconds", "mean"),
        )
        .reset_index()
    )

    daily_summary = daily_summary.rename(
        columns={
            "Call Date Parsed": "Date",
            "Avg_AHT": "Average AHT",
            "Avg_ASA": "Average ASA",
            "Avg_ACW": "Average ACW",
        }
    )

    # IMPORTANT:
    # Display DD-MM-YYYY rather than timestamp
    daily_summary["Date"] = (
        pd.to_datetime(
            daily_summary["Date"]
        ).dt.strftime("%d-%m-%Y")
    )

    daily_summary["Average AHT"] = (
        daily_summary["Average AHT"]
        .apply(seconds_to_hhmmss)
    )

    daily_summary["Average ASA"] = (
        daily_summary["Average ASA"]
        .apply(seconds_to_hhmmss)
    )

    daily_summary["Average ACW"] = (
        daily_summary["Average ACW"]
        .apply(seconds_to_hhmmss)
    )

    st.dataframe(
        daily_summary,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# HOURLY CALL DISTRIBUTION
# ============================================================

st.markdown("## 🕐 Hourly Call Distribution")


if filtered_df.empty:

    st.info(
        "No hourly data available for the selected filters."
    )

else:

    hourly_df = filtered_df.copy()

    hourly_df["Hour"] = (
        pd.to_datetime(
            hourly_df["Parsed Call Time"],
            errors="coerce"
        ).dt.hour
    )

    hourly_summary = (
        hourly_df
        .groupby("Hour")
        .agg(
            Calls=("Call ID", "nunique")
        )
        .reset_index()
    )

    hourly_summary["Hour"] = (
        hourly_summary["Hour"]
        .apply(
            lambda x:
            f"{int(x):02d}:00"
        )
    )

    st.dataframe(
        hourly_summary,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# DETAILED CALL RECORDS
# ============================================================

st.markdown("## 📋 Detailed Call Records")


if filtered_df.empty:

    st.info(
        "No detailed records available for the selected filters."
    )

else:

    display_columns = [
        "Call Date Parsed",
        "Call Time Only",
        "Campaign Name",
        "Phone",
        "Call Type",
        "Call ID",
        "Answered/Hungup",
        "Queue Name",
        "Username",
        "User ID",
        "User Talk Time",
        "User Hold Duration",
        "ACW Duration",
        "Total Wait Time",
        "AHT",
        "ASA",
        "ACW",
        "User Disposition Code",
        "Hangup Details",
        "Call Notes",
    ]

    detail_df = filtered_df[
        [
            column
            for column in display_columns
            if column in filtered_df.columns
        ]
    ].copy()

    # --------------------------------------------------------
    # Format date
    # --------------------------------------------------------

    if "Call Date Parsed" in detail_df.columns:

        detail_df["Call Date"] = (
            pd.to_datetime(
                detail_df["Call Date Parsed"]
            ).dt.strftime(
                "%d-%m-%Y"
            )
        )

        detail_df = detail_df.drop(
            columns=["Call Date Parsed"]
        )

    # --------------------------------------------------------
    # Reorder Call Date
    # --------------------------------------------------------

    if "Call Date" in detail_df.columns:

        columns = list(
            detail_df.columns
        )

        columns.remove("Call Date")

        detail_df.insert(
            0,
            "Call Date",
            detail_df.pop("Call Date")
        )

    st.dataframe(
        detail_df,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# DOWNLOAD
# ============================================================

st.markdown("## ⬇️ Export")


if not filtered_df.empty:

    export_df = filtered_df.copy()

    # --------------------------------------------------------
    # Format date for export
    # --------------------------------------------------------

    export_df["Call Date"] = (
        pd.to_datetime(
            export_df["Call Date Parsed"],
            errors="coerce"
        ).dt.strftime(
            "%d-%m-%Y"
        )
    )

    # Remove internal helper columns
    export_df = export_df.drop(
        columns=[
            "Parsed Call Time",
            "Call Date Parsed",
            "Call Time Parsed",
        ],
        errors="ignore"
    )

    csv_data = export_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        label="📥 Download Filtered Calls CSV",
        data=csv_data,
        file_name=(
            "ACD_Filtered_"
            f"{start_date.strftime('%d-%m-%Y')}_"
            f"{end_date.strftime('%d-%m-%Y')}.csv"
        ),
        mime="text/csv",
        use_container_width=False
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

historical_count = len(df)

st.caption(
    f"Historical records: {historical_count:,} | "
    f"Google Sheet: {SPREADSHEET_ID}"
)
