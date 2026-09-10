
import streamlit as st
import pandas as pd
import numpy as np
import gspread

from datetime import datetime, date, time, timedelta
from google.oauth2.service_account import Credentials


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

CALCULATED_COLUMNS = [
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

ALL_COLUMNS = SOURCE_COLUMNS + CALCULATED_COLUMNS


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_string(value):
    """Convert a value to a clean string."""
    if pd.isna(value):
        return ""

    value = str(value).strip()

    if value.lower() in ["nan", "none", "null"]:
        return ""

    return value


def duration_to_seconds(value):
    """
    Convert HH:MM:SS duration to seconds.
    Also handles numeric values safely.
    """
    if pd.isna(value):
        return 0

    value = str(value).strip()

    if not value:
        return 0

    # HH:MM:SS
    if ":" in value:
        try:
            parts = value.split(":")

            if len(parts) == 3:
                hours = int(float(parts[0]))
                minutes = int(float(parts[1]))
                seconds = float(parts[2])

                return int(hours * 3600 + minutes * 60 + seconds)

            elif len(parts) == 2:
                minutes = int(float(parts[0]))
                seconds = float(parts[1])

                return int(minutes * 60 + seconds)

        except Exception:
            return 0

    # Numeric fallback
    try:
        return int(float(value))
    except Exception:
        return 0


def seconds_to_timedelta(seconds):
    """Convert seconds into a pandas Timedelta."""
    try:
        return pd.to_timedelta(float(seconds), unit="s")
    except Exception:
        return pd.Timedelta(seconds=0)


def format_seconds(seconds):
    """Format seconds as HH:MM:SS."""
    if pd.isna(seconds):
        return "00:00:00"

    try:
        seconds = int(round(float(seconds)))
    except Exception:
        return "00:00:00"

    if seconds < 0:
        seconds = 0

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_average_seconds(seconds):
    """Format average seconds as HH:MM:SS."""
    return format_seconds(seconds)


def get_google_client():
    """Create authenticated Google Sheets client."""

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=scopes,
    )

    return gspread.authorize(credentials)


def get_worksheet():
    """Open spreadsheet and get/create ACD_Data worksheet."""

    client = get_google_client()

    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    try:
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

    except gspread.WorksheetNotFound:

        worksheet = spreadsheet.add_worksheet(
            title=WORKSHEET_NAME,
            rows=1000,
            cols=len(ALL_COLUMNS),
        )

        worksheet.append_row(
            ALL_COLUMNS,
            value_input_option="USER_ENTERED"
        )

    return worksheet


@st.cache_data(ttl=60)
def load_historical_data():
    """Load all historical ACD data from Google Sheets."""

    worksheet = get_worksheet()

    records = worksheet.get_all_records()

    if not records:
        return pd.DataFrame(columns=ALL_COLUMNS)

    df = pd.DataFrame(records)

    # Make sure all expected columns exist
    for column in ALL_COLUMNS:
        if column not in df.columns:
            df[column] = ""

    return df[ALL_COLUMNS]


def prepare_uploaded_data(uploaded_file):
    """Read and prepare uploaded ACD CSV."""

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
        raise ValueError(
            "The uploaded CSV is missing these columns:\n\n"
            + "\n".join(missing_columns)
        )

    # Keep only expected source columns
    df = df[SOURCE_COLUMNS].copy()

    # Clean all strings
    for column in SOURCE_COLUMNS:
        df[column] = df[column].apply(clean_string)

    # --------------------------------------------------------
    # Call ID is required
    # --------------------------------------------------------

    df = df[df["Call ID"] != ""].copy()

    # Remove duplicate Call IDs inside uploaded file
    df = df.drop_duplicates(
        subset=["Call ID"],
        keep="first"
    )

    # --------------------------------------------------------
    # Parse Call Time
    # --------------------------------------------------------

    df["Parsed Call Time"] = pd.to_datetime(
        df["Call Time"],
        dayfirst=True,
        errors="coerce"
    )

    df = df[df["Parsed Call Time"].notna()].copy()

    # --------------------------------------------------------
    # BLANK AGENTS -> CALL DROPPED
    # --------------------------------------------------------

    df["Username"] = df["Username"].apply(clean_string)

    df["Username"] = df["Username"].replace(
        "",
        "Call Dropped"
    )

    # --------------------------------------------------------
    # Duration calculations
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

    # --------------------------------------------------------
    # Display date/time
    # --------------------------------------------------------

    df["Call Date"] = (
        df["Parsed Call Time"]
        .dt.strftime("%d-%m-%Y")
    )

    df["Call Time Only"] = (
        df["Parsed Call Time"]
        .dt.strftime("%H:%M:%S")
    )

    # --------------------------------------------------------
    # Display duration columns
    # --------------------------------------------------------

    df["AHT"] = df["AHT Seconds"].apply(
        format_seconds
    )

    df["ASA"] = df["ASA Seconds"].apply(
        format_seconds
    )

    df["ACW"] = df["ACW Seconds"].apply(
        format_seconds
    )

    df["Upload Date"] = datetime.now().strftime(
        "%d-%m-%Y"
    )

    # --------------------------------------------------------
    # Remove temporary calculation columns
    # --------------------------------------------------------

    df = df.drop(
        columns=[
            "Parsed Call Time",
            "Talk Seconds",
            "Hold Seconds",
        ],
        errors="ignore"
    )

    # Ensure exact column order
    df = df[ALL_COLUMNS]

    return df


def append_new_records(uploaded_df):
    """
    Append only Call IDs which do not already exist
    in Google Sheets.
    """

    worksheet = get_worksheet()

    # --------------------------------------------------------
    # Get existing Call IDs
    #
    # Call ID is column F = column 6
    # --------------------------------------------------------

    try:
        existing_call_ids = set(
            clean_string(x)
            for x in worksheet.col_values(6)[1:]
        )
    except Exception:
        existing_call_ids = set()

    # --------------------------------------------------------
    # Find genuinely new records
    # --------------------------------------------------------

    new_df = uploaded_df[
        ~uploaded_df["Call ID"].isin(existing_call_ids)
    ].copy()

    if new_df.empty:
        return 0

    # --------------------------------------------------------
    # Append to Google Sheets
    # --------------------------------------------------------

    rows = new_df.astype(str).values.tolist()

    worksheet.append_rows(
        rows,
        value_input_option="USER_ENTERED"
    )

    # Clear cache so dashboard immediately sees new data
    load_historical_data.clear()

    return len(new_df)


# ============================================================
# TITLE
# ============================================================

st.title("📞 ACD Time & Agent Performance")

st.caption(
    "Historical ACD performance dashboard powered by Google Sheets"
)


# ============================================================
# CSV UPLOAD
# ============================================================

with st.expander("📤 Upload ACD Call Details CSV", expanded=False):

    uploaded_file = st.file_uploader(
        "Upload the ACD Call Details CSV",
        type=["csv"],
        key="acd_csv_upload"
    )

    if uploaded_file is not None:

        if st.button(
            "⬆️ Upload & Save",
            type="primary"
        ):

            try:

                with st.spinner(
                    "Reading and processing ACD data..."
                ):

                    uploaded_df = prepare_uploaded_data(
                        uploaded_file
                    )

                    added_count = append_new_records(
                        uploaded_df
                    )

                if added_count == 0:

                    st.info(
                        "No new calls found. "
                        "All Call IDs from this file already exist."
                    )

                else:

                    st.success(
                        f"{added_count:,} new calls added to Google Sheets."
                    )

                    st.rerun()

            except Exception as e:

                st.error(
                    f"Upload failed: {e}"
                )


# ============================================================
# LOAD HISTORICAL DATA
# ============================================================

try:

    df = load_historical_data()

except Exception as e:

    st.error(
        "Unable to load data from Google Sheets."
    )

    st.exception(e)

    st.stop()


if df.empty:

    st.info(
        "No ACD data is currently available. "
        "Upload an ACD Call Details CSV to begin."
    )

    st.stop()


# ============================================================
# NORMALISE HISTORICAL DATA
# ============================================================

# ------------------------------------------------------------
# Blank agents -> Call Dropped
# ------------------------------------------------------------

df["Username"] = (
    df["Username"]
    .fillna("")
    .astype(str)
    .str.strip()
)

df["Username"] = df["Username"].replace(
    "",
    "Call Dropped"
)

# ------------------------------------------------------------
# Parse actual Call Time
# ------------------------------------------------------------

df["Parsed Call Time"] = pd.to_datetime(
    df["Call Time"],
    dayfirst=True,
    errors="coerce"
)

# ------------------------------------------------------------
# If historical Call Date exists, use actual datetime
# ------------------------------------------------------------

df["Actual Date"] = (
    df["Parsed Call Time"].dt.date
)

df["Actual Time"] = (
    df["Parsed Call Time"].dt.time
)

# ------------------------------------------------------------
# Recalculate numerical KPI columns safely
# ------------------------------------------------------------

df["AHT Seconds"] = pd.to_numeric(
    df["AHT Seconds"],
    errors="coerce"
).fillna(0)

df["ASA Seconds"] = pd.to_numeric(
    df["ASA Seconds"],
    errors="coerce"
).fillna(0)

df["ACW Seconds"] = pd.to_numeric(
    df["ACW Seconds"],
    errors="coerce"
).fillna(0)


# ============================================================
# TOP GLOBAL FILTERS
# ============================================================

st.markdown("---")

st.subheader("🔎 Dashboard Filters")

# ------------------------------------------------------------
# Available dates
# ------------------------------------------------------------

valid_dates = df["Actual Date"].dropna()

if valid_dates.empty:

    min_date = date.today()
    max_date = date.today()

else:

    min_date = valid_dates.min()
    max_date = valid_dates.max()


# ------------------------------------------------------------
# DATE FILTER
# ------------------------------------------------------------

filter_col1, filter_col2 = st.columns(2)

with filter_col1:

    start_date = st.date_input(
        "📅 Start Date",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
        format="DD-MM-YYYY",
        key="global_start_date"
    )

with filter_col2:

    end_date = st.date_input(
        "📅 End Date",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
        format="DD-MM-YYYY",
        key="global_end_date"
    )


# ------------------------------------------------------------
# TIME FILTER
# ------------------------------------------------------------

time_col1, time_col2 = st.columns(2)

with time_col1:

    start_time = st.time_input(
        "🕐 Start Time",
        value=time(0, 0),
        key="global_start_time"
    )

with time_col2:

    end_time = st.time_input(
        "🕐 End Time",
        value=time(23, 59, 59),
        key="global_end_time"
    )


# ------------------------------------------------------------
# QUEUE + DISPOSITION FILTER
# ------------------------------------------------------------

queue_col, disposition_col = st.columns(2)

# ------------------------------------------------------------
# Queue
# ------------------------------------------------------------

queue_values = sorted(
    [
        x for x in
        df["Queue Name"]
        .fillna("")
        .astype(str)
        .str.strip()
        .unique()
        if x
    ]
)

with queue_col:

    selected_queues = st.multiselect(
        "📥 Queue Name",
        options=queue_values,
        default=queue_values,
        key="global_queue_filter"
    )


# ------------------------------------------------------------
# User disposition
# ------------------------------------------------------------

disposition_values = sorted(
    [
        x for x in
        df["User Disposition Code"]
        .fillna("")
        .astype(str)
        .str.strip()
        .unique()
        if x
    ]
)

with disposition_col:

    selected_dispositions = st.multiselect(
        "🏷️ User Disposition Code",
        options=disposition_values,
        default=disposition_values,
        key="global_disposition_filter"
    )


# ============================================================
# APPLY GLOBAL FILTERS
# ============================================================

filtered_df = df.copy()


# ------------------------------------------------------------
# Date filtering
# ------------------------------------------------------------

if start_date > end_date:

    st.error(
        "Start Date cannot be after End Date."
    )

    st.stop()


filtered_df = filtered_df[
    (
        filtered_df["Actual Date"] >= start_date
    )
    &
    (
        filtered_df["Actual Date"] <= end_date
    )
].copy()


# ------------------------------------------------------------
# Time filtering
# ------------------------------------------------------------

if start_time <= end_time:

    filtered_df = filtered_df[
        (
            filtered_df["Actual Time"] >= start_time
        )
        &
        (
            filtered_df["Actual Time"] <= end_time
        )
    ].copy()

else:

    # Overnight time range
    # Example: 22:00 -> 06:00

    filtered_df = filtered_df[
        (
            filtered_df["Actual Time"] >= start_time
        )
        |
        (
            filtered_df["Actual Time"] <= end_time
        )
    ].copy()


# ------------------------------------------------------------
# Queue filtering
# ------------------------------------------------------------

if queue_values:

    if selected_queues:

        filtered_df = filtered_df[
            filtered_df["Queue Name"]
            .fillna("")
            .astype(str)
            .str.strip()
            .isin(selected_queues)
        ].copy()

    else:

        filtered_df = filtered_df.iloc[0:0].copy()


# ------------------------------------------------------------
# Disposition filtering
# ------------------------------------------------------------

if disposition_values:

    if selected_dispositions:

        filtered_df = filtered_df[
            filtered_df["User Disposition Code"]
            .fillna("")
            .astype(str)
            .str.strip()
            .isin(selected_dispositions)
        ].copy()

    else:

        filtered_df = filtered_df.iloc[0:0].copy()


# ------------------------------------------------------------
# Filter summary
# ------------------------------------------------------------

st.caption(
    f"Showing {len(filtered_df):,} calls "
    f"from {start_date.strftime('%d-%m-%Y')} "
    f"to {end_date.strftime('%d-%m-%Y')} "
    f"between {start_time.strftime('%H:%M:%S')} "
    f"and {end_time.strftime('%H:%M:%S')}"
)


# ============================================================
# KPI CALCULATIONS
# ============================================================

total_calls = len(filtered_df)

if total_calls > 0:

    avg_aht = filtered_df["AHT Seconds"].mean()
    avg_asa = filtered_df["ASA Seconds"].mean()
    avg_acw = filtered_df["ACW Seconds"].mean()

else:

    avg_aht = 0
    avg_asa = 0
    avg_acw = 0


# ============================================================
# KPI CARDS
# ============================================================

col1, col2, col3, col4 = st.columns(4)


with col1:

    st.metric(
        "📞 Calls",
        f"{total_calls:,}",
        help=(
            "Total number of unique calls in the selected "
            "date/time/queue/disposition filters. "
            "Blank agent names are counted as 'Call Dropped'. "
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
            "AHT = User Talk Time + User Hold Duration + "
            "ACW Duration"
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
# NO RESULTS CHECK
# ============================================================

if filtered_df.empty:

    st.warning(
        "No calls match the selected filters."
    )

    st.stop()


# ============================================================
# AGENT PERFORMANCE
# ============================================================

st.markdown("---")

st.subheader("👤 Agent Performance")


agent_summary = (
    filtered_df
    .groupby("Username", dropna=False)
    .agg(
        Calls=("Call ID", "count"),
        Avg_AHT_Seconds=("AHT Seconds", "mean"),
        Avg_ASA_Seconds=("ASA Seconds", "mean"),
        Avg_ACW_Seconds=("ACW Seconds", "mean"),
    )
    .reset_index()
)


agent_summary["Average AHT"] = (
    agent_summary["Avg_AHT_Seconds"]
    .apply(format_seconds)
)

agent_summary["Average ASA"] = (
    agent_summary["Avg_ASA_Seconds"]
    .apply(format_seconds)
)

agent_summary["Average ACW"] = (
    agent_summary["Avg_ACW_Seconds"]
    .apply(format_seconds)
)


agent_summary = agent_summary[
    [
        "Username",
        "Calls",
        "Average AHT",
        "Average ASA",
        "Average ACW",
    ]
].rename(
    columns={
        "Username": "Agent"
    }
)


# Sort Call Dropped to the bottom
agent_summary["_sort"] = (
    agent_summary["Agent"]
    .eq("Call Dropped")
    .astype(int)
)

agent_summary = (
    agent_summary
    .sort_values(
        ["_sort", "Calls"],
        ascending=[True, False]
    )
    .drop(columns="_sort")
)


st.dataframe(
    agent_summary,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# DAILY PERFORMANCE
# ============================================================

st.markdown("---")

st.subheader("📅 Daily Performance")


daily_summary = (
    filtered_df
    .groupby("Actual Date")
    .agg(
        Calls=("Call ID", "count"),
        Avg_AHT_Seconds=("AHT Seconds", "mean"),
        Avg_ASA_Seconds=("ASA Seconds", "mean"),
        Avg_ACW_Seconds=("ACW Seconds", "mean"),
    )
    .reset_index()
)


daily_summary["Date"] = pd.to_datetime(
    daily_summary["Actual Date"]
).dt.strftime("%d-%m-%Y")


daily_summary["Average AHT"] = (
    daily_summary["Avg_AHT_Seconds"]
    .apply(format_seconds)
)

daily_summary["Average ASA"] = (
    daily_summary["Avg_ASA_Seconds"]
    .apply(format_seconds)
)

daily_summary["Average ACW"] = (
    daily_summary["Avg_ACW_Seconds"]
    .apply(format_seconds)
)


daily_summary = daily_summary[
    [
        "Date",
        "Calls",
        "Average AHT",
        "Average ASA",
        "Average ACW",
    ]
]


daily_summary = daily_summary.sort_values(
    "Date",
    key=lambda x: pd.to_datetime(
        x,
        format="%d-%m-%Y"
    )
)


st.dataframe(
    daily_summary,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# HOURLY CALL DISTRIBUTION
# ============================================================

st.markdown("---")

st.subheader("🕐 Hourly Call Distribution")


filtered_df["Hour"] = (
    filtered_df["Parsed Call Time"]
    .dt.hour
)


hourly_summary = (
    filtered_df
    .groupby("Hour")
    .size()
    .reset_index(name="Calls")
)


# Include all 24 hours
all_hours = pd.DataFrame(
    {
        "Hour": range(24)
    }
)


hourly_summary = all_hours.merge(
    hourly_summary,
    on="Hour",
    how="left"
)


hourly_summary["Calls"] = (
    hourly_summary["Calls"]
    .fillna(0)
    .astype(int)
)


hourly_summary["Time"] = (
    hourly_summary["Hour"]
    .apply(
        lambda x: f"{x:02d}:00 - {x:02d}:59"
    )
)


hourly_summary = hourly_summary[
    [
        "Time",
        "Calls"
    ]
]


st.dataframe(
    hourly_summary,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# DETAILED CALL RECORDS
# ============================================================

st.markdown("---")

st.subheader("📋 Detailed Call Records")


detail_columns = [
    "Call Date",
    "Call Time Only",
    "Call ID",
    "Phone",
    "Campaign Name",
    "Queue Name",
    "Username",
    "User Disposition Code",
    "Answered/Hungup",
    "AHT",
    "ASA",
    "ACW",
    "Hangup Details",
]


detail_df = filtered_df.copy()


# Recreate display date/time explicitly
detail_df["Call Date"] = (
    detail_df["Parsed Call Time"]
    .dt.strftime("%d-%m-%Y")
)

detail_df["Call Time Only"] = (
    detail_df["Parsed Call Time"]
    .dt.strftime("%H:%M:%S")
)


# Ensure all columns exist
available_detail_columns = [
    column
    for column in detail_columns
    if column in detail_df.columns
]


detail_df = detail_df[
    available_detail_columns
].copy()


st.dataframe(
    detail_df,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# DOWNLOAD FILTERED DATA
# ============================================================

st.markdown("---")

st.subheader("⬇️ Export")


csv_data = detail_df.to_csv(
    index=False
).encode("utf-8")


st.download_button(
    label="📥 Download Filtered Calls CSV",
    data=csv_data,
    file_name=(
        f"ACD_Filtered_"
        f"{start_date.strftime('%d-%m-%Y')}_"
        f"{end_date.strftime('%d-%m-%Y')}.csv"
    ),
    mime="text/csv"
)


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    f"Google Sheet: {SPREADSHEET_ID} "
    f"| Historical records: {len(df):,} "
    f"| Filtered records: {len(filtered_df):,}"
)
