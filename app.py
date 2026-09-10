
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
    page_icon="📞",
    layout="wide"
)


# ============================================================
# CONFIGURATION
# ============================================================

SPREADSHEET_ID = "1R7ioNIYj7iAK3kN21WWlrxy9J9qEdRM9GOebCnUQNpI"

WORKSHEET_NAME = "ACD_Data"


# ============================================================
# SOURCE COLUMNS
# ============================================================

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

def duration_to_seconds(value):
    """
    Convert HH:MM:SS duration into seconds.

    Examples:
        00:00:10 -> 10
        00:02:35 -> 155
        01:05:10 -> 3910
    """

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
            seconds = int(float(parts[2]))

            return hours * 3600 + minutes * 60 + seconds

        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = int(float(parts[1]))

            return minutes * 60 + seconds

        return float(value)

    except Exception:
        return 0


def seconds_to_hhmmss(seconds):
    """
    Convert seconds into HH:MM:SS.
    """

    if pd.isna(seconds):
        return "00:00:00"

    try:
        seconds = int(round(float(seconds)))
    except Exception:
        return "00:00:00"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_average_seconds(seconds):
    """
    Format an average duration as HH:MM:SS.
    """

    if pd.isna(seconds):
        return "00:00:00"

    return seconds_to_hhmmss(seconds)


def clean_dataframe_strings(df):
    """
    Clean whitespace from string columns.
    """

    df = df.copy()

    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = (
                df[col]
                .fillna("")
                .astype(str)
                .str.strip()
            )

    return df


def replace_blank_agents(df):
    """
    Replace blank Username values with 'Call Dropped'.
    """

    df = df.copy()

    if "Username" in df.columns:

        df["Username"] = (
            df["Username"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        blank_mask = (
            df["Username"].eq("")
            | df["Username"].str.lower().isin(
                ["nan", "none", "null", "na", "n/a"]
            )
        )

        df.loc[blank_mask, "Username"] = "Call Dropped"

    return df


def prepare_uploaded_data(df):
    """
    Prepare a newly uploaded ACD CSV.
    """

    df = df.copy()

    # --------------------------------------------------------
    # Clean strings
    # --------------------------------------------------------

    df = clean_dataframe_strings(df)

    # --------------------------------------------------------
    # Replace blank agents
    # --------------------------------------------------------

    df = replace_blank_agents(df)

    # --------------------------------------------------------
    # Remove rows without Call ID
    # --------------------------------------------------------

    df["Call ID"] = (
        df["Call ID"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df = df[df["Call ID"] != ""].copy()

    # --------------------------------------------------------
    # Deduplicate within upload
    # --------------------------------------------------------

    df = df.drop_duplicates(
        subset=["Call ID"],
        keep="last"
    ).copy()

    # --------------------------------------------------------
    # Parse Call Time
    # --------------------------------------------------------

    df["Call Time Parsed"] = pd.to_datetime(
        df["Call Time"],
        dayfirst=True,
        errors="coerce"
    )

    # --------------------------------------------------------
    # Date and time fields
    # --------------------------------------------------------

    df["Call Date"] = df["Call Time Parsed"].dt.strftime(
        "%d-%m-%Y"
    )

    df["Call Time Only"] = df["Call Time Parsed"].dt.strftime(
        "%H:%M:%S"
    )

    # --------------------------------------------------------
    # Duration calculations
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # KPI calculations
    #
    # AHT = User Talk Time
    #     + User Hold Duration
    #     + ACW Duration
    #
    # ASA = Total Wait Time
    #
    # ACW = ACW Duration
    # --------------------------------------------------------

    df["AHT Seconds"] = (
        talk_seconds
        + hold_seconds
        + acw_seconds
    )

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

    # --------------------------------------------------------
    # Upload date
    # --------------------------------------------------------

    df["Upload Date"] = datetime.now().strftime(
        "%d-%m-%Y"
    )

    # --------------------------------------------------------
    # Remove temporary parsed column
    # --------------------------------------------------------

    df.drop(
        columns=["Call Time Parsed"],
        inplace=True,
        errors="ignore"
    )

    # --------------------------------------------------------
    # Make sure all expected columns exist
    # --------------------------------------------------------

    for col in ALL_COLUMNS:

        if col not in df.columns:
            df[col] = ""

    # --------------------------------------------------------
    # Keep exact column order
    # --------------------------------------------------------

    df = df[ALL_COLUMNS].copy()

    return df


def parse_historical_dataframe(df):
    """
    Prepare historical Google Sheet data for dashboard use.
    """

    df = df.copy()

    if df.empty:
        return df

    df = clean_dataframe_strings(df)

    # --------------------------------------------------------
    # Blank agent -> Call Dropped
    # --------------------------------------------------------

    df = replace_blank_agents(df)

    # --------------------------------------------------------
    # Parse Call Date
    #
    # Historical Google Sheet may contain:
    # 2026-09-01
    # 2026-09-01 00:00:00
    # 01-09-2026
    # etc.
    # --------------------------------------------------------

    if "Call Date" in df.columns:

        df["_CallDateParsed"] = pd.to_datetime(
            df["Call Date"],
            dayfirst=True,
            errors="coerce"
        )

    else:

        df["_CallDateParsed"] = pd.NaT

    # --------------------------------------------------------
    # Parse Call Time
    # --------------------------------------------------------

    if "Call Time" in df.columns:

        call_time_parsed = pd.to_datetime(
            df["Call Time"],
            dayfirst=True,
            errors="coerce"
        )

        # If Call Date could not be parsed from the calculated
        # field, use Call Time as the source.
        df["_CallDateParsed"] = df["_CallDateParsed"].fillna(
            call_time_parsed.dt.normalize()
        )

        # Time only from Call Time
        df["_TimeParsed"] = call_time_parsed.dt.time

    else:

        df["_TimeParsed"] = pd.NaT

    # --------------------------------------------------------
    # Format Call Date for display
    # --------------------------------------------------------

    df["Call Date"] = df["_CallDateParsed"].dt.strftime(
        "%d-%m-%Y"
    )

    # --------------------------------------------------------
    # Ensure Call Time Only exists
    # --------------------------------------------------------

    if "Call Time Only" not in df.columns:

        df["Call Time Only"] = ""

    # Fill missing Call Time Only from Call Time
    missing_time = (
        df["Call Time Only"].fillna("").astype(str).str.strip()
        == ""
    )

    if "Call Time" in df.columns:

        formatted_times = pd.to_datetime(
            df["Call Time"],
            dayfirst=True,
            errors="coerce"
        ).dt.strftime("%H:%M:%S")

        df.loc[missing_time, "Call Time Only"] = (
            formatted_times.loc[missing_time]
        )

    # --------------------------------------------------------
    # Convert KPI seconds columns to numeric
    # --------------------------------------------------------

    for col in [
        "AHT Seconds",
        "ASA Seconds",
        "ACW Seconds"
    ]:

        if col in df.columns:

            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            ).fillna(0)

    # --------------------------------------------------------
    # If calculated seconds are missing, recalculate
    # --------------------------------------------------------

    if "AHT Seconds" not in df.columns:
        df["AHT Seconds"] = 0

    if "ASA Seconds" not in df.columns:
        df["ASA Seconds"] = 0

    if "ACW Seconds" not in df.columns:
        df["ACW Seconds"] = 0

    # --------------------------------------------------------
    # Recalculate missing / zero KPI values from source data
    # --------------------------------------------------------

    if "User Talk Time" in df.columns:
        talk = df["User Talk Time"].apply(
            duration_to_seconds
        )
    else:
        talk = pd.Series(
            0,
            index=df.index
        )

    if "User Hold Duration" in df.columns:
        hold = df["User Hold Duration"].apply(
            duration_to_seconds
        )
    else:
        hold = pd.Series(
            0,
            index=df.index
        )

    if "ACW Duration" in df.columns:
        acw = df["ACW Duration"].apply(
            duration_to_seconds
        )
    else:
        acw = pd.Series(
            0,
            index=df.index
        )

    if "Total Wait Time" in df.columns:
        asa = df["Total Wait Time"].apply(
            duration_to_seconds
        )
    else:
        asa = pd.Series(
            0,
            index=df.index
        )

    # Calculate directly to ensure historical data is correct.
    df["AHT Seconds"] = talk + hold + acw
    df["ASA Seconds"] = asa
    df["ACW Seconds"] = acw

    df["AHT"] = df["AHT Seconds"].apply(
        seconds_to_hhmmss
    )

    df["ASA"] = df["ASA Seconds"].apply(
        seconds_to_hhmmss
    )

    df["ACW"] = df["ACW Seconds"].apply(
        seconds_to_hhmmss
    )

    return df


# ============================================================
# GOOGLE SHEETS CONNECTION
# ============================================================

@st.cache_resource
def get_google_sheet():

    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )

    client = gspread.authorize(credentials)

    spreadsheet = client.open_by_key(
        SPREADSHEET_ID
    )

    try:

        worksheet = spreadsheet.worksheet(
            WORKSHEET_NAME
        )

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
# LOAD HISTORICAL DATA
# ============================================================

@st.cache_data(ttl=60)
def load_historical_data():

    worksheet = get_google_sheet()

    records = worksheet.get_all_records()

    if not records:
        return pd.DataFrame(
            columns=ALL_COLUMNS
        )

    df = pd.DataFrame(records)

    # Make sure expected columns exist
    for col in ALL_COLUMNS:

        if col not in df.columns:
            df[col] = ""

    df = df[ALL_COLUMNS].copy()

    df = parse_historical_dataframe(
        df
    )

    return df


# ============================================================
# APPEND NEW DATA
# ============================================================

def append_new_data(uploaded_df):

    worksheet = get_google_sheet()

    # --------------------------------------------------------
    # Existing Call IDs
    # --------------------------------------------------------

    try:

        existing_call_ids = worksheet.col_values(6)

        existing_call_ids = set(
            str(x).strip()
            for x in existing_call_ids[1:]
            if str(x).strip()
        )

    except Exception:

        existing_call_ids = set()

    # --------------------------------------------------------
    # Find new calls only
    # --------------------------------------------------------

    new_df = uploaded_df[
        ~uploaded_df["Call ID"].isin(
            existing_call_ids
        )
    ].copy()

    if new_df.empty:

        return 0

    # --------------------------------------------------------
    # Append to Google Sheet
    # --------------------------------------------------------

    rows = new_df[
        ALL_COLUMNS
    ].fillna("").astype(str).values.tolist()

    worksheet.append_rows(
        rows,
        value_input_option="USER_ENTERED"
    )

    return len(new_df)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("⚙️ Filters")

st.sidebar.markdown(
    "Use the filters below to refine the dashboard."
)


# ============================================================
# LOAD DATA
# ============================================================

try:

    historical_df = load_historical_data()

except Exception as e:

    st.error(
        f"Unable to connect to Google Sheets.\n\n{e}"
    )

    st.stop()


# ============================================================
# CSV UPLOAD
# ============================================================

st.sidebar.markdown("---")

st.sidebar.subheader("📤 Upload ACD CSV")

uploaded_file = st.sidebar.file_uploader(
    "Upload ACD Call Details CSV",
    type=["csv"]
)


if uploaded_file is not None:

    try:

        uploaded_raw = pd.read_csv(
            uploaded_file,
            dtype=str
        )

        # ----------------------------------------------------
        # Validate source columns
        # ----------------------------------------------------

        missing_columns = [
            col
            for col in SOURCE_COLUMNS
            if col not in uploaded_raw.columns
        ]

        if missing_columns:

            st.error(
                "The uploaded CSV is missing these "
                f"required columns:\n\n"
                + "\n".join(
                    f"- {col}"
                    for col in missing_columns
                )
            )

        else:

            prepared_upload = prepare_uploaded_data(
                uploaded_raw
            )

            # ------------------------------------------------
            # Append only new Call IDs
            # ------------------------------------------------

            with st.spinner(
                "Checking Google Sheets and uploading new calls..."
            ):

                added_count = append_new_data(
                    prepared_upload
                )

            # ------------------------------------------------
            # Refresh cached historical data
            # ------------------------------------------------

            load_historical_data.clear()

            historical_df = load_historical_data()

            if added_count > 0:

                st.success(
                    f"Successfully added {added_count:,} "
                    f"new call record(s) to Google Sheets."
                )

            else:

                st.info(
                    "No new calls found. "
                    "All uploaded Call IDs already exist."
                )

    except Exception as e:

        st.error(
            f"Error processing uploaded CSV:\n\n{e}"
        )


# ============================================================
# MAIN TITLE
# ============================================================

st.title("📞 ACD Time & Agent Performance")

st.caption(
    "ACD call performance dashboard using historical "
    "Google Sheets data."
)


# ============================================================
# TOP DATE + TIME FILTER
# ============================================================

st.markdown("### 📅 Dashboard Date & Time Filter")

# ------------------------------------------------------------
# Determine available dates
# ------------------------------------------------------------

if not historical_df.empty:

    valid_dates = historical_df[
        "_CallDateParsed"
    ].dropna()

else:

    valid_dates = pd.Series(
        dtype="datetime64[ns]"
    )


if len(valid_dates) > 0:

    min_available_date = (
        valid_dates.min().date()
    )

    max_available_date = (
        valid_dates.max().date()
    )

else:

    min_available_date = date.today()
    max_available_date = date.today()


date_col1, date_col2, time_col1, time_col2 = st.columns(4)


with date_col1:

    start_date = st.date_input(
        "From Date",
        value=min_available_date,
        min_value=min_available_date,
        max_value=max_available_date,
        format="DD-MM-YYYY",
        key="top_start_date"
    )


with date_col2:

    end_date = st.date_input(
        "To Date",
        value=max_available_date,
        min_value=min_available_date,
        max_value=max_available_date,
        format="DD-MM-YYYY",
        key="top_end_date"
    )


with time_col1:

    start_time = st.time_input(
        "From Time",
        value=time(0, 0),
        key="top_start_time"
    )


with time_col2:

    end_time = st.time_input(
        "To Time",
        value=time(23, 59, 59),
        key="top_end_time"
    )


# ------------------------------------------------------------
# Fix reversed date selection
# ------------------------------------------------------------

if start_date > end_date:

    st.warning(
        "From Date cannot be later than To Date."
    )

    st.stop()


# ============================================================
# APPLY DATE + TIME FILTER FIRST
# ============================================================

filtered_df = historical_df.copy()


if not filtered_df.empty:

    # --------------------------------------------------------
    # Date filter
    # --------------------------------------------------------

    date_mask = (
        (filtered_df["_CallDateParsed"].dt.date >= start_date)
        &
        (filtered_df["_CallDateParsed"].dt.date <= end_date)
    )

    filtered_df = filtered_df[
        date_mask
    ].copy()

    # --------------------------------------------------------
    # Time filter
    #
    # Supports normal ranges:
    # 09:00 -> 18:00
    #
    # Also supports overnight:
    # 22:00 -> 06:00
    # --------------------------------------------------------

    if "_TimeParsed" in filtered_df.columns:

        def time_to_seconds(t):
            if pd.isna(t):
                return np.nan

            return (
                t.hour * 3600
                + t.minute * 60
                + t.second
            )

        filtered_df["_TimeSeconds"] = (
            filtered_df["_TimeParsed"]
            .apply(time_to_seconds)
        )

        start_seconds = (
            start_time.hour * 3600
            + start_time.minute * 60
            + start_time.second
        )

        end_seconds = (
            end_time.hour * 3600
            + end_time.minute * 60
            + end_time.second
        )

        if start_seconds <= end_seconds:

            time_mask = (
                (filtered_df["_TimeSeconds"] >= start_seconds)
                &
                (filtered_df["_TimeSeconds"] <= end_seconds)
            )

        else:

            # Overnight range
            time_mask = (
                (filtered_df["_TimeSeconds"] >= start_seconds)
                |
                (filtered_df["_TimeSeconds"] <= end_seconds)
            )

        filtered_df = filtered_df[
            time_mask
        ].copy()


# ============================================================
# SIDEBAR SECONDARY FILTERS
# ============================================================

st.sidebar.markdown("---")

# ------------------------------------------------------------
# Agent
# ------------------------------------------------------------

if not historical_df.empty:

    agent_values = sorted(
        historical_df["Username"]
        .fillna("Call Dropped")
        .replace("", "Call Dropped")
        .unique()
        .tolist()
    )

else:

    agent_values = []


selected_agents = st.sidebar.multiselect(
    "👤 Agent",
    options=agent_values,
    default=[]
)


# ------------------------------------------------------------
# Campaign
# ------------------------------------------------------------

if not historical_df.empty:

    campaign_values = sorted(
        historical_df["Campaign Name"]
        .fillna("")
        .astype(str)
        .replace("", "Unknown")
        .unique()
        .tolist()
    )

else:

    campaign_values = []


selected_campaigns = st.sidebar.multiselect(
    "📣 Campaign",
    options=campaign_values,
    default=[]
)


# ------------------------------------------------------------
# Queue
# ------------------------------------------------------------

if not historical_df.empty:

    queue_values = sorted(
        historical_df["Queue Name"]
        .fillna("")
        .astype(str)
        .replace("", "Unknown")
        .unique()
        .tolist()
    )

else:

    queue_values = []


selected_queues = st.sidebar.multiselect(
    "📋 Queue",
    options=queue_values,
    default=[]
)


# ------------------------------------------------------------
# Disposition
# ------------------------------------------------------------

if not historical_df.empty:

    disposition_values = sorted(
        historical_df[
            "User Disposition Code"
        ]
        .fillna("")
        .astype(str)
        .replace("", "Unknown")
        .unique()
        .tolist()
    )

else:

    disposition_values = []


selected_dispositions = st.sidebar.multiselect(
    "🏷️ Disposition",
    options=disposition_values,
    default=[]
)


# ============================================================
# APPLY SIDEBAR FILTERS
# ============================================================

# ------------------------------------------------------------
# Agent
# ------------------------------------------------------------

if selected_agents:

    filtered_df = filtered_df[
        filtered_df["Username"].isin(
            selected_agents
        )
    ].copy()


# ------------------------------------------------------------
# Campaign
# ------------------------------------------------------------

if selected_campaigns:

    filtered_df = filtered_df[
        filtered_df["Campaign Name"]
        .replace("", "Unknown")
        .isin(selected_campaigns)
    ].copy()


# ------------------------------------------------------------
# Queue
# ------------------------------------------------------------

if selected_queues:

    filtered_df = filtered_df[
        filtered_df["Queue Name"]
        .replace("", "Unknown")
        .isin(selected_queues)
    ].copy()


# ------------------------------------------------------------
# Disposition
# ------------------------------------------------------------

if selected_dispositions:

    filtered_df = filtered_df[
        filtered_df["User Disposition Code"]
        .replace("", "Unknown")
        .isin(selected_dispositions)
    ].copy()


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

st.markdown("### 📊 Key Performance Indicators")

col1, col2, col3, col4 = st.columns(4)


with col1:

    st.metric(
        "📞 Calls",
        f"{total_calls:,}",
        help=(
            "Total number of unique calls in the "
            "selected date/time/agent filters.\n\n"
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
    f"Showing {len(filtered_df):,} call(s) "
    f"from {start_date.strftime('%d-%m-%Y')} "
    f"to {end_date.strftime('%d-%m-%Y')} "
    f"| {start_time.strftime('%H:%M:%S')} "
    f"to {end_time.strftime('%H:%M:%S')}"
)


# ============================================================
# AGENT PERFORMANCE
# ============================================================

st.markdown("---")
st.subheader("👤 Agent Performance")


if not filtered_df.empty:

    agent_performance = (
        filtered_df
        .groupby("Username", dropna=False)
        .agg(
            Calls=("Call ID", "count"),
            Average_AHT=("AHT Seconds", "mean"),
            Average_ASA=("ASA Seconds", "mean"),
            Average_ACW=("ACW Seconds", "mean"),
        )
        .reset_index()
    )

    agent_performance.rename(
        columns={
            "Username": "Agent",
            "Average_AHT": "Average AHT",
            "Average_ASA": "Average ASA",
            "Average_ACW": "Average ACW",
        },
        inplace=True
    )

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

    st.info(
        "No agent performance data for the selected filters."
    )


# ============================================================
# DAILY PERFORMANCE
# ============================================================

st.markdown("---")
st.subheader("📅 Daily Performance")


if not filtered_df.empty:

    daily_performance = (
        filtered_df
        .groupby(
            "_CallDateParsed",
            dropna=False
        )
        .agg(
            Calls=("Call ID", "count"),
            Average_AHT=("AHT Seconds", "mean"),
            Average_ASA=("ASA Seconds", "mean"),
            Average_ACW=("ACW Seconds", "mean"),
        )
        .reset_index()
    )

    daily_performance.rename(
        columns={
            "_CallDateParsed": "Date",
            "Average_AHT": "Average AHT",
            "Average_ASA": "Average ASA",
            "Average_ACW": "Average ACW",
        },
        inplace=True
    )

    # --------------------------------------------------------
    # dd-mm-yyyy
    # --------------------------------------------------------

    daily_performance["Date"] = (
        pd.to_datetime(
            daily_performance["Date"],
            errors="coerce"
        )
        .dt.strftime("%d-%m-%Y")
    )

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

    st.info(
        "No daily performance data for the selected filters."
    )


# ============================================================
# HOURLY CALL DISTRIBUTION
# ============================================================

st.markdown("---")
st.subheader("🕐 Hourly Call Distribution")


if not filtered_df.empty:

    hourly_df = filtered_df.copy()

    hourly_df["Hour"] = (
        pd.to_datetime(
            hourly_df["Call Time"],
            dayfirst=True,
            errors="coerce"
        )
        .dt.hour
    )

    hourly_distribution = (
        hourly_df
        .dropna(subset=["Hour"])
        .groupby("Hour")
        .size()
        .reset_index(name="Calls")
    )

    hourly_distribution["Hour"] = (
        hourly_distribution["Hour"]
        .apply(
            lambda x: f"{int(x):02d}:00"
        )
    )

    st.dataframe(
        hourly_distribution,
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

st.markdown("---")
st.subheader("📋 Detailed Call Records")


if not filtered_df.empty:

    display_columns = [
        "Call ID",
        "Campaign Name",
        "Phone",
        "Call Type",
        "Answered/Hungup",
        "Call Date",
        "Call Time Only",
        "Queue Name",
        "Username",
        "User Disposition Code",
        "AHT",
        "ASA",
        "ACW",
        "Hangup Details",
        "Call Notes",
    ]

    display_columns = [
        col
        for col in display_columns
        if col in filtered_df.columns
    ]

    detailed_df = filtered_df[
        display_columns
    ].copy()

    # --------------------------------------------------------
    # Make absolutely sure dates display as dd-mm-yyyy
    # --------------------------------------------------------

    if "Call Date" in detailed_df.columns:

        detailed_df["Call Date"] = (
            pd.to_datetime(
                detailed_df["Call Date"],
                dayfirst=True,
                errors="coerce"
            )
            .dt.strftime("%d-%m-%Y")
        )

    # --------------------------------------------------------
    # Blank agents -> Call Dropped
    # --------------------------------------------------------

    if "Username" in detailed_df.columns:

        detailed_df["Username"] = (
            detailed_df["Username"]
            .fillna("")
            .replace("", "Call Dropped")
        )

    st.dataframe(
        detailed_df,
        use_container_width=True,
        hide_index=True
    )

    # --------------------------------------------------------
    # Download filtered records
    # --------------------------------------------------------

    csv_data = detailed_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        label="⬇️ Download Filtered Calls CSV",
        data=csv_data,
        file_name=(
            f"ACD_filtered_"
            f"{start_date.strftime('%d-%m-%Y')}_"
            f"{end_date.strftime('%d-%m-%Y')}.csv"
        ),
        mime="text/csv"
    )

else:

    st.info(
        "No call records match the selected filters."
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    f"Google Sheet: {SPREADSHEET_ID} "
    f"| Historical records: {len(historical_df):,}"
)

