import streamlit as st
import pandas as pd
import numpy as np
import gspread

from datetime import datetime, date, time
from google.oauth2.service_account import Credentials


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="ACD Time & Agent Performance",
    page_icon="⏱️",
    layout="wide"
)


# ============================================================
# CONFIGURATION
# ============================================================

SPREADSHEET_ID = "1R7ioNIYj7iAK3kN21WWlrxy9J9qEdRM9GOebCnUQNpI"

WORKSHEET_NAME = "ACD_Data"

EXPECTED_COLUMNS = [
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

ALL_COLUMNS = EXPECTED_COLUMNS + EXTRA_COLUMNS


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
        scopes=scopes,
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

        worksheet.update(
            "A1",
            [ALL_COLUMNS]
        )

    return worksheet


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_string(value):
    """
    Convert a value into a clean string.
    """
    if pd.isna(value):
        return ""

    return str(value).strip()


def replace_blank_agents(df):
    """
    Replace blank / missing Username values with Call Dropped.
    """

    if "Username" not in df.columns:
        return df

    df["Username"] = (
        df["Username"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df.loc[
        df["Username"].isin(["", "nan", "None", "NaN"]),
        "Username"
    ] = "Call Dropped"

    return df


def duration_to_seconds(value):
    """
    Convert HH:MM:SS duration into seconds.

    Handles:
    - HH:MM:SS
    - MM:SS
    - numeric values
    - blank values
    """

    if pd.isna(value):
        return 0.0

    value = str(value).strip()

    if not value:
        return 0.0

    # Numeric value
    try:
        if ":" not in value:
            return float(value)
    except Exception:
        pass

    parts = value.split(":")

    try:
        parts = [float(x) for x in parts]

        if len(parts) == 3:
            hours, minutes, seconds = parts
            return (
                hours * 3600
                + minutes * 60
                + seconds
            )

        elif len(parts) == 2:
            minutes, seconds = parts
            return (
                minutes * 60
                + seconds
            )

        elif len(parts) == 1:
            return parts[0]

    except Exception:
        return 0.0

    return 0.0


def seconds_to_hhmmss(seconds):
    """
    Convert seconds to HH:MM:SS.
    """

    if pd.isna(seconds):
        return "00:00:00"

    try:
        seconds = max(0, float(seconds))
    except Exception:
        return "00:00:00"

    total_seconds = int(round(seconds))

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_average_seconds(seconds):
    """
    Format average duration as HH:MM:SS.
    """

    if pd.isna(seconds):
        return "00:00:00"

    return seconds_to_hhmmss(seconds)


def prepare_uploaded_data(df):
    """
    Prepare a newly uploaded ACD CSV.
    """

    # --------------------------------------------------------
    # Ensure expected columns exist
    # --------------------------------------------------------

    missing_columns = [
        col for col in EXPECTED_COLUMNS
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "The uploaded CSV is missing these required columns:\n\n"
            + "\n".join(f"- {x}" for x in missing_columns)
        )

    # Keep only the expected source columns
    df = df[EXPECTED_COLUMNS].copy()

    # --------------------------------------------------------
    # Clean strings
    # --------------------------------------------------------

    for col in df.columns:
        df[col] = df[col].apply(clean_string)

    # --------------------------------------------------------
    # Remove rows without Call ID
    # --------------------------------------------------------

    df = df[
        df["Call ID"].astype(str).str.strip() != ""
    ].copy()

    # --------------------------------------------------------
    # Remove duplicate Call IDs within upload
    # --------------------------------------------------------

    df = df.drop_duplicates(
        subset=["Call ID"],
        keep="first"
    )

    # --------------------------------------------------------
    # Replace blank agents
    # --------------------------------------------------------

    df = replace_blank_agents(df)

    # --------------------------------------------------------
    # Parse Call Time
    # --------------------------------------------------------

    df["Parsed Call Time"] = pd.to_datetime(
        df["Call Time"],
        dayfirst=True,
        errors="coerce"
    )

    # --------------------------------------------------------
    # Call Date
    # --------------------------------------------------------

    df["Call Date"] = df["Parsed Call Time"].dt.date

    # --------------------------------------------------------
    # Call Time Only
    # --------------------------------------------------------

    df["Call Time Only"] = df["Parsed Call Time"].dt.strftime(
        "%H:%M:%S"
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
    # AHT = User Talk Time
    #     + User Hold Duration
    #     + ACW Duration
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
    #
    # ACW = ACW Duration
    # --------------------------------------------------------

    df["ACW"] = df["ACW Seconds"].apply(
        seconds_to_hhmmss
    )

    # --------------------------------------------------------
    # Upload date
    # --------------------------------------------------------

    df["Upload Date"] = date.today().strftime(
        "%d-%m-%Y"
    )

    # --------------------------------------------------------
    # Remove temporary columns
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
    # Reorder columns
    # --------------------------------------------------------

    df = df[ALL_COLUMNS]

    return df


# ============================================================
# LOAD HISTORICAL DATA
# ============================================================

@st.cache_data(ttl=60)
def load_historical_data():
    worksheet = get_worksheet()

    records = worksheet.get_all_records()

    if not records:
        return pd.DataFrame(columns=ALL_COLUMNS)

    df = pd.DataFrame(records)

    # --------------------------------------------------------
    # Ensure all columns exist
    # --------------------------------------------------------

    for col in ALL_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[ALL_COLUMNS]

    # --------------------------------------------------------
    # Replace blank agents
    # --------------------------------------------------------

    df = replace_blank_agents(df)

    # --------------------------------------------------------
    # Parse Call Date
    # --------------------------------------------------------

    df["Call Date"] = pd.to_datetime(
        df["Call Date"],
        dayfirst=True,
        errors="coerce"
    ).dt.date

    # --------------------------------------------------------
    # Parse Call Time
    # --------------------------------------------------------

    parsed_call_time = pd.to_datetime(
        df["Call Time"],
        dayfirst=True,
        errors="coerce"
    )

    # If Call Time Only exists, use it where possible
    if "Call Time Only" in df.columns:

        time_only = pd.to_datetime(
            df["Call Time Only"],
            format="%H:%M:%S",
            errors="coerce"
        )

        missing_time = parsed_call_time.isna()

        # We don't overwrite a valid full Call Time.
        # This simply ensures the column exists correctly.
        if missing_time.any():
            pass

    # --------------------------------------------------------
    # Convert metric seconds back to numeric
    # --------------------------------------------------------

    for col in [
        "AHT Seconds",
        "ASA Seconds",
        "ACW Seconds",
    ]:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        ).fillna(0)

    # --------------------------------------------------------
    # If historical calculated values are missing,
    # recalculate them from source columns.
    # --------------------------------------------------------

    missing_aht = (
        df["AHT Seconds"].isna()
        | (df["AHT Seconds"] == 0)
    )

    talk_seconds = df["User Talk Time"].apply(
        duration_to_seconds
    )

    hold_seconds = df["User Hold Duration"].apply(
        duration_to_seconds
    )

    acw_seconds = df["ACW Duration"].apply(
        duration_to_seconds
    )

    asa_seconds = df["Total Wait Time"].apply(
        duration_to_seconds
    )

    calculated_aht = (
        talk_seconds
        + hold_seconds
        + acw_seconds
    )

    df.loc[
        missing_aht,
        "AHT Seconds"
    ] = calculated_aht[missing_aht]

    df["AHT"] = df["AHT Seconds"].apply(
        seconds_to_hhmmss
    )

    df["ASA Seconds"] = asa_seconds

    df["ASA"] = df["ASA Seconds"].apply(
        seconds_to_hhmmss
    )

    df["ACW Seconds"] = acw_seconds

    df["ACW"] = df["ACW Seconds"].apply(
        seconds_to_hhmmss
    )

    return df


# ============================================================
# APPEND NEW DATA TO GOOGLE SHEETS
# ============================================================

def append_new_records(df):
    worksheet = get_worksheet()

    # --------------------------------------------------------
    # Existing Call IDs
    # Call ID is column F = column 6
    # --------------------------------------------------------

    existing_ids = worksheet.col_values(6)

    existing_ids = {
        str(x).strip()
        for x in existing_ids
        if str(x).strip()
    }

    # --------------------------------------------------------
    # Filter only new calls
    # --------------------------------------------------------

    new_df = df[
        ~df["Call ID"].astype(str).str.strip().isin(
            existing_ids
        )
    ].copy()

    if new_df.empty:
        return 0

    # --------------------------------------------------------
    # Ensure blank agents are fixed before writing
    # --------------------------------------------------------

    new_df = replace_blank_agents(new_df)

    # --------------------------------------------------------
    # Convert dates to strings suitable for Sheets
    # --------------------------------------------------------

    if "Call Date" in new_df.columns:

        new_df["Call Date"] = pd.to_datetime(
            new_df["Call Date"],
            errors="coerce"
        ).dt.strftime(
            "%d-%m-%Y"
        )

        new_df["Call Date"] = new_df[
            "Call Date"
        ].fillna("")

    # --------------------------------------------------------
    # Convert everything to string
    # --------------------------------------------------------

    values = []

    for _, row in new_df.iterrows():

        row_values = []

        for col in ALL_COLUMNS:

            value = row.get(col, "")

            if pd.isna(value):
                value = ""

            row_values.append(str(value))

        values.append(row_values)

    # --------------------------------------------------------
    # Append
    # --------------------------------------------------------

    worksheet.append_rows(
        values,
        value_input_option="USER_ENTERED"
    )

    # Clear cached historical data
    load_historical_data.clear()

    return len(values)


# ============================================================
# TITLE
# ============================================================

st.title("⏱️ ACD Time & Agent Performance")

st.caption(
    "Upload ACD call-detail reports to build a historical "
    "agent performance dashboard."
)


# ============================================================
# SIDEBAR — UPLOAD
# ============================================================

st.sidebar.header("📤 Upload ACD Report")

uploaded_file = st.sidebar.file_uploader(
    "Upload CSV",
    type=["csv"],
    help="Upload the fixed-format ACD Call Details CSV."
)


if uploaded_file is not None:

    if st.sidebar.button(
        "⬆️ Upload & Process",
        use_container_width=True
    ):

        try:

            with st.spinner(
                "Processing ACD report..."
            ):

                uploaded_df = pd.read_csv(
                    uploaded_file,
                    dtype=str,
                    keep_default_na=False
                )

                processed_df = prepare_uploaded_data(
                    uploaded_df
                )

                added = append_new_records(
                    processed_df
                )

            if added > 0:

                st.sidebar.success(
                    f"Added {added:,} new calls."
                )

            else:

                st.sidebar.info(
                    "No new calls found. "
                    "All Call IDs already exist."
                )

        except Exception as e:

            st.sidebar.error(
                f"Upload failed:\n\n{e}"
            )


# ============================================================
# LOAD DATA
# ============================================================

try:

    df = load_historical_data()

except Exception as e:

    st.error(
        "Unable to load data from Google Sheets."
    )

    st.exception(e)

    st.stop()


# ============================================================
# NO DATA
# ============================================================

if df.empty:

    st.info(
        "No ACD data is available yet. "
        "Upload your first ACD CSV from the sidebar."
    )

    st.stop()


# ============================================================
# DATA CLEANUP
# ============================================================

# ------------------------------------------------------------
# Blank agents → Call Dropped
# ------------------------------------------------------------

df = replace_blank_agents(df)


# ------------------------------------------------------------
# Ensure Call Date is a date
# ------------------------------------------------------------

df["Call Date"] = pd.to_datetime(
    df["Call Date"],
    dayfirst=True,
    errors="coerce"
).dt.date


# ------------------------------------------------------------
# Make sure calculated columns are numeric
# ------------------------------------------------------------

for col in [
    "AHT Seconds",
    "ASA Seconds",
    "ACW Seconds",
]:

    df[col] = pd.to_numeric(
        df[col],
        errors="coerce"
    ).fillna(0)


# ============================================================
# SIDEBAR — FILTERS
# ============================================================

st.sidebar.header("🔎 Filters")


# ------------------------------------------------------------
# DATE FILTER
# ------------------------------------------------------------

valid_dates = df["Call Date"].dropna()

if not valid_dates.empty:

    min_date = valid_dates.min()
    max_date = valid_dates.max()

    date_range = st.sidebar.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        format="DD-MM-YYYY"
    )

else:

    date_range = (
        date.today(),
        date.today()
    )


# ------------------------------------------------------------
# TIME FILTER
# ------------------------------------------------------------

st.sidebar.subheader("Time of Day")

start_time = st.sidebar.time_input(
    "From",
    value=time(0, 0)
)

end_time = st.sidebar.time_input(
    "To",
    value=time(23, 59, 59)
)


# ------------------------------------------------------------
# AGENT FILTER
# ------------------------------------------------------------

agents = sorted(
    df["Username"]
    .dropna()
    .astype(str)
    .unique()
)

selected_agents = st.sidebar.multiselect(
    "Agent",
    options=agents,
    default=[]
)


# ------------------------------------------------------------
# CAMPAIGN FILTER
# ------------------------------------------------------------

campaigns = sorted(
    df["Campaign Name"]
    .dropna()
    .astype(str)
    .unique()
)

selected_campaigns = st.sidebar.multiselect(
    "Campaign",
    options=campaigns,
    default=[]
)


# ------------------------------------------------------------
# QUEUE FILTER
# ------------------------------------------------------------

queues = sorted(
    df["Queue Name"]
    .dropna()
    .astype(str)
    .unique()
)

selected_queues = st.sidebar.multiselect(
    "Queue",
    options=queues,
    default=[]
)


# ------------------------------------------------------------
# DISPOSITION FILTER
# ------------------------------------------------------------

dispositions = sorted(
    df["User Disposition Code"]
    .dropna()
    .astype(str)
    .unique()
)

selected_dispositions = st.sidebar.multiselect(
    "Disposition",
    options=dispositions,
    default=[]
)


# ============================================================
# APPLY FILTERS
# ============================================================

filtered_df = df.copy()


# ------------------------------------------------------------
# Date range
# ------------------------------------------------------------

if isinstance(date_range, tuple) and len(date_range) == 2:

    selected_start_date = date_range[0]
    selected_end_date = date_range[1]

    filtered_df = filtered_df[
        (
            filtered_df["Call Date"]
            >= selected_start_date
        )
        &
        (
            filtered_df["Call Date"]
            <= selected_end_date
        )
    ]


# ------------------------------------------------------------
# Time of day
# ------------------------------------------------------------

def extract_time(value):

    parsed = pd.to_datetime(
        value,
        dayfirst=True,
        errors="coerce"
    )

    if pd.isna(parsed):
        return None

    return parsed.time()


filtered_df["_Time"] = filtered_df[
    "Call Time"
].apply(extract_time)


if start_time <= end_time:

    filtered_df = filtered_df[
        (
            filtered_df["_Time"] >= start_time
        )
        &
        (
            filtered_df["_Time"] <= end_time
        )
    ]

else:

    # Overnight range, e.g. 22:00 → 06:00

    filtered_df = filtered_df[
        (
            filtered_df["_Time"] >= start_time
        )
        |
        (
            filtered_df["_Time"] <= end_time
        )
    ]


# ------------------------------------------------------------
# Agent
# ------------------------------------------------------------

if selected_agents:

    filtered_df = filtered_df[
        filtered_df["Username"].isin(
            selected_agents
        )
    ]


# ------------------------------------------------------------
# Campaign
# ------------------------------------------------------------

if selected_campaigns:

    filtered_df = filtered_df[
        filtered_df["Campaign Name"].isin(
            selected_campaigns
        )
    ]


# ------------------------------------------------------------
# Queue
# ------------------------------------------------------------

if selected_queues:

    filtered_df = filtered_df[
        filtered_df["Queue Name"].isin(
            selected_queues
        )
    ]


# ------------------------------------------------------------
# Disposition
# ------------------------------------------------------------

if selected_dispositions:

    filtered_df = filtered_df[
        filtered_df[
            "User Disposition Code"
        ].isin(selected_dispositions)
    ]


# ============================================================
# KPI CALCULATIONS
# ============================================================

total_calls = len(filtered_df)

if total_calls > 0:

    avg_aht = filtered_df[
        "AHT Seconds"
    ].mean()

    avg_asa = filtered_df[
        "ASA Seconds"
    ].mean()

    avg_acw = filtered_df[
        "ACW Seconds"
    ].mean()

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
            "date/time/agent filters.\n\n"
            "Call ID is used to identify each call."
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
# AGENT PERFORMANCE
# ============================================================

st.subheader("👤 Agent Performance")


if not filtered_df.empty:

    agent_performance = (
        filtered_df
        .groupby("Username", dropna=False)
        .agg(
            Calls=("Call ID", "count"),
            Avg_AHT=("AHT Seconds", "mean"),
            Avg_ASA=("ASA Seconds", "mean"),
            Avg_ACW=("ACW Seconds", "mean"),
        )
        .reset_index()
    )

    agent_performance = agent_performance.rename(
        columns={
            "Username": "Agent",
            "Avg_AHT": "Average AHT",
            "Avg_ASA": "Average ASA",
            "Avg_ACW": "Average ACW",
        }
    )

    # --------------------------------------------------------
    # Ensure blank agent names are never displayed
    # --------------------------------------------------------

    agent_performance["Agent"] = (
        agent_performance["Agent"]
        .fillna("Call Dropped")
        .replace("", "Call Dropped")
    )

    # --------------------------------------------------------
    # Format duration columns
    # --------------------------------------------------------

    agent_performance["Average AHT"] = (
        agent_performance["Average AHT"]
        .apply(format_average_seconds)
    )

    agent_performance["Average ASA"] = (
        agent_performance["Average ASA"]
        .apply(format_average_seconds)
    )

    agent_performance["Average ACW"] = (
        agent_performance["Average ACW"]
        .apply(format_average_seconds)
    )

    agent_performance = agent_performance.sort_values(
        "Calls",
        ascending=False
    )

    st.dataframe(
        agent_performance,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info("No agent data for the selected filters.")


# ============================================================
# DAILY PERFORMANCE
# ============================================================

st.subheader("📅 Daily Performance")


if not filtered_df.empty:

    daily_performance = (
        filtered_df
        .groupby("Call Date")
        .agg(
            Calls=("Call ID", "count"),
            Avg_AHT=("AHT Seconds", "mean"),
            Avg_ASA=("ASA Seconds", "mean"),
            Avg_ACW=("ACW Seconds", "mean"),
        )
        .reset_index()
    )

    daily_performance = daily_performance.rename(
        columns={
            "Call Date": "Date",
            "Avg_AHT": "Average AHT",
            "Avg_ASA": "Average ASA",
            "Avg_ACW": "Average ACW",
        }
    )

    # --------------------------------------------------------
    # Sort by actual date first
    # --------------------------------------------------------

    daily_performance = daily_performance.sort_values(
        "Date"
    )

    # --------------------------------------------------------
    # Display date as DD-MM-YYYY
    # --------------------------------------------------------

    daily_performance["Date"] = pd.to_datetime(
        daily_performance["Date"],
        errors="coerce"
    ).dt.strftime(
        "%d-%m-%Y"
    )

    # --------------------------------------------------------
    # Format duration columns
    # --------------------------------------------------------

    daily_performance["Average AHT"] = (
        daily_performance["Average AHT"]
        .apply(format_average_seconds)
    )

    daily_performance["Average ASA"] = (
        daily_performance["Average ASA"]
        .apply(format_average_seconds)
    )

    daily_performance["Average ACW"] = (
        daily_performance["Average ACW"]
        .apply(format_average_seconds)
    )

    st.dataframe(
        daily_performance,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info("No daily data for the selected filters.")


# ============================================================
# HOURLY CALL DISTRIBUTION
# ============================================================

st.subheader("🕐 Hourly Call Distribution")


if not filtered_df.empty:

    hourly_df = filtered_df.copy()

    parsed_times = pd.to_datetime(
        hourly_df["Call Time"],
        dayfirst=True,
        errors="coerce"
    )

    hourly_df["Hour"] = (
        parsed_times.dt.hour
    )

    hourly_performance = (
        hourly_df
        .dropna(subset=["Hour"])
        .groupby("Hour")
        .agg(
            Calls=("Call ID", "count"),
            Average_AHT=("AHT Seconds", "mean"),
            Average_ASA=("ASA Seconds", "mean"),
            Average_ACW=("ACW Seconds", "mean"),
        )
        .reset_index()
    )

    hourly_performance["Hour"] = (
        hourly_performance["Hour"]
        .astype(int)
        .apply(lambda x: f"{x:02d}:00")
    )

    hourly_performance["Average_AHT"] = (
        hourly_performance["Average_AHT"]
        .apply(format_average_seconds)
    )

    hourly_performance["Average_ASA"] = (
        hourly_performance["Average_ASA"]
        .apply(format_average_seconds)
    )

    hourly_performance["Average_ACW"] = (
        hourly_performance["Average_ACW"]
        .apply(format_average_seconds)
    )

    hourly_performance = hourly_performance.rename(
        columns={
            "Hour": "Hour",
            "Average_AHT": "Average AHT",
            "Average_ASA": "Average ASA",
            "Average_ACW": "Average ACW",
        }
    )

    st.dataframe(
        hourly_performance,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "No hourly data for the selected filters."
    )


# ============================================================
# DETAILED CALL RECORDS
# ============================================================

st.subheader("📋 Detailed Call Records")


if not filtered_df.empty:

    detail_df = filtered_df.copy()

    # --------------------------------------------------------
    # Sort chronologically
    # --------------------------------------------------------

    detail_df["_SortDate"] = pd.to_datetime(
        detail_df["Call Time"],
        dayfirst=True,
        errors="coerce"
    )

    detail_df = detail_df.sort_values(
        "_SortDate",
        ascending=False
    )

    # --------------------------------------------------------
    # Display date/time in friendly format
    # --------------------------------------------------------

    detail_df["Call Date"] = pd.to_datetime(
        detail_df["Call Date"],
        errors="coerce"
    ).dt.strftime(
        "%d-%m-%Y"
    )

    # --------------------------------------------------------
    # Replace blank agents
    # --------------------------------------------------------

    detail_df = replace_blank_agents(
        detail_df
    )

    # --------------------------------------------------------
    # Remove internal helper
    # --------------------------------------------------------

    detail_df = detail_df.drop(
        columns=[
            "_Time",
            "_SortDate",
        ],
        errors="ignore"
    )

    # --------------------------------------------------------
    # Select useful display columns
    # --------------------------------------------------------

    display_columns = [
        "Call Date",
        "Call Time",
        "Campaign Name",
        "Phone",
        "Call Type",
        "Call ID",
        "Answered/Hungup",
        "Queue Name",
        "Total Wait Time",
        "Username",
        "User Talk Time",
        "User Hold Duration",
        "ACW Duration",
        "AHT",
        "ASA",
        "ACW",
        "User Disposition Code",
        "Call Notes",
    ]

    display_columns = [
        col
        for col in display_columns
        if col in detail_df.columns
    ]

    display_df = detail_df[
        display_columns
    ].copy()

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=500
    )

else:

    st.info(
        "No call records for the selected filters."
    )


# ============================================================
# DOWNLOAD FILTERED DATA
# ============================================================

st.subheader("⬇️ Export")


if not filtered_df.empty:

    export_df = filtered_df.copy()

    export_df = export_df.drop(
        columns=[
            "_Time",
        ],
        errors="ignore"
    )

    # --------------------------------------------------------
    # Date format for export
    # --------------------------------------------------------

    export_df["Call Date"] = pd.to_datetime(
        export_df["Call Date"],
        errors="coerce"
    ).dt.strftime(
        "%d-%m-%Y"
    )

    # --------------------------------------------------------
    # Blank agents
    # --------------------------------------------------------

    export_df = replace_blank_agents(
        export_df
    )

    csv_data = export_df.to_csv(
        index=False
    ).encode(
        "utf-8-sig"
    )

    st.download_button(
        label="📥 Download Filtered Calls CSV",
        data=csv_data,
        file_name=(
            "ACD_Filtered_Calls_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        ),
        mime="text/csv",
        use_container_width=False
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    f"Google Sheet: {SPREADSHEET_ID}"
)

st.caption(
    f"Historical records loaded: {len(df):,}"
)
