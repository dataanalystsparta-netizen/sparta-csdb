import streamlit as st
import pandas as pd
import numpy as np
import gspread

from google.oauth2.service_account import Credentials
from datetime import datetime, time, timedelta


# ============================================================
# CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="ACD Time & Agent Performance",
    page_icon="📞",
    layout="wide"
)

SPREADSHEET_ID = "1R7ioNIYj7iAK3kN21WWlrxy9J9qEdRM9GOebCnUQNpI"
WORKSHEET_NAME = "ACD_Data"


# ============================================================
# EXPECTED SOURCE COLUMNS
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


# ============================================================
# GOOGLE SHEETS
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
def get_spreadsheet():

    client = get_gspread_client()

    return client.open_by_key(SPREADSHEET_ID)


def get_or_create_worksheet():

    spreadsheet = get_spreadsheet()

    try:
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

    except gspread.WorksheetNotFound:

        worksheet = spreadsheet.add_worksheet(
            title=WORKSHEET_NAME,
            rows=1000,
            cols=40,
        )

        headers = SOURCE_COLUMNS + [
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

        worksheet.append_row(headers)

    return worksheet


# ============================================================
# DURATION HELPERS
# ============================================================

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
            seconds = int(float(parts[2]))

            return (
                hours * 3600
                + minutes * 60
                + seconds
            )

        if len(parts) == 2:

            minutes = int(parts[0])
            seconds = int(float(parts[1]))

            return minutes * 60 + seconds

    except Exception:
        pass

    return 0


def seconds_to_duration(seconds):

    if pd.isna(seconds):
        seconds = 0

    seconds = int(round(float(seconds)))

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


# ============================================================
# NORMALISE CSV
# ============================================================

def validate_columns(df):

    missing = [
        col for col in SOURCE_COLUMNS
        if col not in df.columns
    ]

    extra = [
        col for col in df.columns
        if col not in SOURCE_COLUMNS
    ]

    return missing, extra


def process_uploaded_file(uploaded_file):

    df = pd.read_csv(
        uploaded_file,
        dtype=str,
        keep_default_na=False
    )

    # --------------------------------------------------------
    # Validate structure
    # --------------------------------------------------------

    missing, extra = validate_columns(df)

    if missing:

        st.error("The uploaded file is missing required columns:")

        for col in missing:
            st.write(f"- {col}")

        return None

    # Keep exact source order
    df = df[SOURCE_COLUMNS].copy()

    # --------------------------------------------------------
    # Clean strings
    # --------------------------------------------------------

    for col in SOURCE_COLUMNS:

        df[col] = (
            df[col]
            .astype(str)
            .str.strip()
        )

    # --------------------------------------------------------
    # Call ID
    # --------------------------------------------------------

    df["Call ID"] = df["Call ID"].str.strip()

    # Remove completely blank Call IDs
    df = df[df["Call ID"] != ""].copy()

    # Remove duplicates inside the uploaded file
    df = df.drop_duplicates(
        subset=["Call ID"],
        keep="last"
    )

    # --------------------------------------------------------
    # Parse Call Time
    # --------------------------------------------------------

    df["Parsed Call Time"] = pd.to_datetime(
        df["Call Time"],
        errors="coerce",
        dayfirst=True
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
    # --------------------------------------------------------

    df["AHT Seconds"] = (
        df["Talk Seconds"]
        + df["Hold Seconds"]
        + df["ACW Seconds"]
    )

    # --------------------------------------------------------
    # Display fields
    # --------------------------------------------------------

    df["Call Date"] = df["Parsed Call Time"].apply(
        lambda x: x.strftime("%Y-%m-%d")
        if pd.notna(x)
        else ""
    )

    df["Call Time Only"] = df["Parsed Call Time"].apply(
        lambda x: x.strftime("%H:%M:%S")
        if pd.notna(x)
        else ""
    )

    df["AHT"] = df["AHT Seconds"].apply(
        seconds_to_duration
    )

    df["ASA"] = df["ASA Seconds"].apply(
        seconds_to_duration
    )

    df["ACW"] = df["ACW Seconds"].apply(
        seconds_to_duration
    )

    df["Upload Date"] = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    # --------------------------------------------------------
    # Final Google Sheet structure
    # --------------------------------------------------------

    output_columns = SOURCE_COLUMNS + [
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

    output = df[output_columns].copy()

    return output


# ============================================================
# EXISTING CALL IDS
# ============================================================

def get_existing_call_ids(worksheet):

    try:

        # Call ID is column F
        values = worksheet.col_values(6)

        if not values:
            return set()

        # First row is header
        return set(
            str(x).strip()
            for x in values[1:]
            if str(x).strip()
        )

    except Exception as e:

        st.error(
            f"Could not read existing Call IDs: {e}"
        )

        return set()


# ============================================================
# APPEND NEW RECORDS
# ============================================================

def append_records(worksheet, df):

    if df.empty:
        return 0

    existing_ids = get_existing_call_ids(
        worksheet
    )

    df = df[
        ~df["Call ID"].isin(existing_ids)
    ].copy()

    if df.empty:
        return 0

    # Convert NaN to blank
    df = df.replace(
        [np.nan, np.inf, -np.inf],
        ""
    )

    values = df.astype(str).values.tolist()

    worksheet.append_rows(
        values,
        value_input_option="USER_ENTERED"
    )

    return len(values)


# ============================================================
# LOAD GOOGLE SHEET DATA
# ============================================================

@st.cache_data(ttl=60)
def load_sheet_data():

    worksheet = get_or_create_worksheet()

    records = worksheet.get_all_records()

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    return df


# ============================================================
# PREPARE DASHBOARD DATA
# ============================================================

def prepare_dashboard_data(df):

    if df.empty:
        return df

    df = df.copy()

    df["Call Date Parsed"] = pd.to_datetime(
        df["Call Date"],
        errors="coerce"
    )

    df["Call Time Parsed"] = pd.to_datetime(
        df["Call Time Only"],
        format="%H:%M:%S",
        errors="coerce"
    )

    # Numeric fields
    for col in [
        "AHT Seconds",
        "ASA Seconds",
        "ACW Seconds",
    ]:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        ).fillna(0)

    # Hour
    df["Hour"] = (
        df["Call Time Parsed"]
        .dt.hour
    )

    return df


# ============================================================
# FORMAT SECONDS
# ============================================================

def format_average_seconds(seconds):

    if pd.isna(seconds):
        return "00:00:00"

    return seconds_to_duration(
        round(seconds)
    )


# ============================================================
# SIDEBAR FILTERS
# ============================================================

def show_filters(df):

    st.sidebar.header("🔎 Filters")

    filtered = df.copy()

    # --------------------------------------------------------
    # Date
    # --------------------------------------------------------

    valid_dates = df[
        "Call Date Parsed"
    ].dropna()

    if not valid_dates.empty:

        min_date = valid_dates.min().date()
        max_date = valid_dates.max().date()

        date_range = st.sidebar.date_input(
            "Call Date",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )

        if isinstance(date_range, tuple) and len(date_range) == 2:

            start_date, end_date = date_range

            filtered = filtered[
                (
                    filtered["Call Date Parsed"].dt.date
                    >= start_date
                )
                &
                (
                    filtered["Call Date Parsed"].dt.date
                    <= end_date
                )
            ]

    # --------------------------------------------------------
    # Time
    # --------------------------------------------------------

    st.sidebar.markdown("### 🕐 Time of Day")

    start_time = st.sidebar.time_input(
        "From",
        value=time(0, 0)
    )

    end_time = st.sidebar.time_input(
        "To",
        value=time(23, 59, 59)
    )

    if not filtered.empty:

        time_values = filtered[
            "Call Time Parsed"
        ].dt.time

        if start_time <= end_time:

            filtered = filtered[
                (
                    time_values >= start_time
                )
                &
                (
                    time_values <= end_time
                )
            ]

        else:

            # Overnight range, e.g. 22:00 → 02:00
            filtered = filtered[
                (
                    time_values >= start_time
                )
                |
                (
                    time_values <= end_time
                )
            ]

    # --------------------------------------------------------
    # Agent
    # --------------------------------------------------------

    agents = sorted(
        x for x in
        df["Username"].dropna().astype(str).unique()
        if x.strip()
    )

    selected_agents = st.sidebar.multiselect(
        "Agent",
        agents
    )

    if selected_agents:

        filtered = filtered[
            filtered["Username"].isin(
                selected_agents
            )
        ]

    # --------------------------------------------------------
    # Campaign
    # --------------------------------------------------------

    campaigns = sorted(
        x for x in
        df["Campaign Name"].dropna().astype(str).unique()
        if x.strip()
    )

    selected_campaigns = st.sidebar.multiselect(
        "Campaign",
        campaigns
    )

    if selected_campaigns:

        filtered = filtered[
            filtered["Campaign Name"].isin(
                selected_campaigns
            )
        ]

    # --------------------------------------------------------
    # Queue
    # --------------------------------------------------------

    queues = sorted(
        x for x in
        df["Queue Name"].dropna().astype(str).unique()
        if x.strip()
    )

    selected_queues = st.sidebar.multiselect(
        "Queue",
        queues
    )

    if selected_queues:

        filtered = filtered[
            filtered["Queue Name"].isin(
                selected_queues
            )
        ]

    # --------------------------------------------------------
    # Disposition
    # --------------------------------------------------------

    dispositions = sorted(
        x for x in
        df["User Disposition Code"]
        .dropna()
        .astype(str)
        .unique()
        if x.strip()
    )

    selected_dispositions = st.sidebar.multiselect(
        "Disposition",
        dispositions
    )

    if selected_dispositions:

        filtered = filtered[
            filtered[
                "User Disposition Code"
            ].isin(selected_dispositions)
        ]

    return filtered


# ============================================================
# MAIN
# ============================================================

st.title("📞 ACD Time & Agent Performance")

st.caption(
    "Historical ACD performance dashboard"
)


# ============================================================
# UPLOAD SECTION
# ============================================================

with st.expander(
    "📤 Upload ACD Report",
    expanded=True
):

    uploaded_file = st.file_uploader(
        "Upload the fixed-format ACD CSV report",
        type=["csv"],
        help=(
            "The CSV must contain the standard "
            "25 ACD report columns."
        )
    )

    if uploaded_file is not None:

        if st.button(
            "⬆️ Import Report",
            type="primary"
        ):

            with st.spinner(
                "Validating and importing..."
            ):

                try:

                    processed = process_uploaded_file(
                        uploaded_file
                    )

                    if processed is not None:

                        worksheet = (
                            get_or_create_worksheet()
                        )

                        before = len(processed)

                        added = append_records(
                            worksheet,
                            processed
                        )

                        skipped = before - added

                        load_sheet_data.clear()

                        st.success(
                            f"Import complete: "
                            f"**{added:,} new records** added."
                        )

                        if skipped > 0:

                            st.info(
                                f"**{skipped:,} duplicate "
                                f"records** were skipped "
                                f"using Call ID."
                            )

                        st.rerun()

                except Exception as e:

                    st.error(
                        f"Import failed: {e}"
                    )


# ============================================================
# LOAD DATA
# ============================================================

try:

    raw_df = load_sheet_data()

except Exception as e:

    st.error(
        "Unable to connect to Google Sheets."
    )

    st.exception(e)

    st.stop()


if raw_df.empty:

    st.info(
        "No ACD records are currently stored. "
        "Upload your first ACD CSV above."
    )

    st.stop()


df = prepare_dashboard_data(
    raw_df
)


# ============================================================
# FILTERS
# ============================================================

filtered_df = show_filters(df)


# ============================================================
# FILTER SUMMARY
# ============================================================

st.markdown(
    f"Showing **{len(filtered_df):,}** "
    f"of **{len(df):,}** historical calls"
)


# ============================================================
# KPI CALCULATIONS
# ============================================================

if filtered_df.empty:

    st.warning(
        "No records match the selected filters."
    )

    st.stop()


total_calls = filtered_df[
    "Call ID"
].nunique()

answered_calls = filtered_df[
    filtered_df["Answered/Hungup"]
    .astype(str)
    .str.lower()
    .str.contains("answer")
]["Call ID"].nunique()

avg_aht = filtered_df[
    "AHT Seconds"
].mean()

avg_asa = filtered_df[
    "ASA Seconds"
].mean()

avg_acw = filtered_df[
    "ACW Seconds"
].mean()

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
            "date/time/agent filters. "
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
# AGENT PERFORMANCE
# ============================================================

st.subheader("👤 Agent Performance")


agent_df = (
    filtered_df
    .groupby("Username", dropna=False)
    .agg(
        Calls=("Call ID", "nunique"),
        AHT_Seconds=("AHT Seconds", "mean"),
        ASA_Seconds=("ASA Seconds", "mean"),
        ACW_Seconds=("ACW Seconds", "mean"),
        Talk_Seconds=("Talk Seconds", "mean")
        if "Talk Seconds" in filtered_df.columns
        else ("AHT Seconds", "mean"),
    )
    .reset_index()
)

agent_df = agent_df.rename(
    columns={
        "Username": "Agent"
    }
)

agent_df["AHT"] = agent_df[
    "AHT_Seconds"
].apply(format_average_seconds)

agent_df["ASA"] = agent_df[
    "ASA_Seconds"
].apply(format_average_seconds)

agent_df["ACW"] = agent_df[
    "ACW_Seconds"
].apply(format_average_seconds)

display_agent_df = agent_df[
    [
        "Agent",
        "Calls",
        "AHT",
        "ASA",
        "ACW",
    ]
].sort_values(
    "Calls",
    ascending=False
)

st.dataframe(
    display_agent_df,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# DAILY PERFORMANCE
# ============================================================

st.subheader("📅 Daily Performance")


daily_df = (
    filtered_df
    .groupby("Call Date Parsed")
    .agg(
        Calls=("Call ID", "nunique"),
        AHT_Seconds=("AHT Seconds", "mean"),
        ASA_Seconds=("ASA Seconds", "mean"),
        ACW_Seconds=("ACW Seconds", "mean"),
    )
    .reset_index()
    .sort_values("Call Date Parsed")
)

daily_df["AHT"] = daily_df[
    "AHT_Seconds"
].apply(format_average_seconds)

daily_df["ASA"] = daily_df[
    "ASA_Seconds"
].apply(format_average_seconds)

daily_df["ACW"] = daily_df[
    "ACW_Seconds"
].apply(format_average_seconds)

display_daily = daily_df[
    [
        "Call Date Parsed",
        "Calls",
        "AHT",
        "ASA",
        "ACW",
    ]
].copy()

display_daily = display_daily.rename(
    columns={
        "Call Date Parsed": "Date"
    }
)

st.dataframe(
    display_daily,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# HOURLY PERFORMANCE
# ============================================================

st.subheader("🕐 Hourly Call Distribution")

hourly_df = (
    filtered_df
    .groupby("Hour")
    .agg(
        Calls=("Call ID", "nunique"),
        AHT_Seconds=("AHT Seconds", "mean"),
        ASA_Seconds=("ASA Seconds", "mean"),
        ACW_Seconds=("ACW Seconds", "mean"),
    )
    .reset_index()
)

hourly_df["Time"] = (
    hourly_df["Hour"]
    .apply(lambda x: f"{int(x):02d}:00")
)

hourly_display = hourly_df[
    [
        "Time",
        "Calls",
        "AHT_Seconds",
        "ASA_Seconds",
        "ACW_Seconds",
    ]
].copy()

hourly_display["AHT"] = hourly_display[
    "AHT_Seconds"
].apply(format_average_seconds)

hourly_display["ASA"] = hourly_display[
    "ASA_Seconds"
].apply(format_average_seconds)

hourly_display["ACW"] = hourly_display[
    "ACW_Seconds"
].apply(format_average_seconds)

hourly_display = hourly_display[
    [
        "Time",
        "Calls",
        "AHT",
        "ASA",
        "ACW",
    ]
]

st.dataframe(
    hourly_display,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# DETAILED CALL RECORDS
# ============================================================

st.subheader("📋 Call Details")

detail_columns = [
    "Call Date",
    "Call Time Only",
    "Username",
    "Campaign Name",
    "Queue Name",
    "Phone",
    "Call Type",
    "Answered/Hungup",
    "Total Wait Time",
    "User Talk Time",
    "User Hold Duration",
    "ACW Duration",
    "AHT",
    "ASA",
    "User Disposition Code",
    "Call ID",
]

detail_columns = [
    c for c in detail_columns
    if c in filtered_df.columns
]

details = filtered_df[
    detail_columns
].copy()

st.dataframe(
    details,
    use_container_width=True,
    hide_index=True,
    height=500
)


# ============================================================
# DOWNLOAD FILTERED DATA
# ============================================================

csv_data = details.to_csv(
    index=False
).encode("utf-8")

st.download_button(
    "⬇️ Download Filtered Calls",
    data=csv_data,
    file_name=(
        "ACD_filtered_calls_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
        + ".csv"
    ),
    mime="text/csv"
)


# ============================================================
# FOOTER
# ============================================================

st.caption(
    f"Google Sheet: {SPREADSHEET_ID}  •  "
    f"Historical records: {len(df):,}"
)
