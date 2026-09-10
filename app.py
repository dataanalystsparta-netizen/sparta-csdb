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

GOOGLE_COLUMNS = EXPECTED_COLUMNS + [
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


# ============================================================
# TITLE
# ============================================================

st.title("📞 ACD Time & Agent Performance")
st.caption(
    "Upload ACD call-detail reports, maintain historical data in Google Sheets, "
    "and analyse AHT, ASA and ACW by agent, date, time and queue."
)


# ============================================================
# GOOGLE SHEETS CONNECTION
# ============================================================

@st.cache_resource
def get_google_client():

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

    client = get_google_client()

    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    try:
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

    except gspread.WorksheetNotFound:

        worksheet = spreadsheet.add_worksheet(
            title=WORKSHEET_NAME,
            rows=1000,
            cols=len(GOOGLE_COLUMNS)
        )

        worksheet.update(
            "A1",
            [GOOGLE_COLUMNS]
        )

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
            seconds = float(parts[2])

            return int(
                hours * 3600 +
                minutes * 60 +
                seconds
            )

        elif len(parts) == 2:

            minutes = int(parts[0])
            seconds = float(parts[1])

            return int(
                minutes * 60 +
                seconds
            )

        else:

            return int(float(value))

    except Exception:

        return 0


def seconds_to_hhmmss(seconds):

    if pd.isna(seconds):
        return "00:00:00"

    seconds = int(round(float(seconds)))

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_average_seconds(value):

    if pd.isna(value):
        return "00:00:00"

    return seconds_to_hhmmss(value)


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text_columns(df):

    for column in df.columns:

        df[column] = (
            df[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    return df


# ============================================================
# NORMALISE AGENT NAME
# ============================================================

def normalise_agent_names(df):

    if "Username" not in df.columns:
        return df

    df["Username"] = (
        df["Username"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df.loc[
        df["Username"].eq(""),
        "Username"
    ] = "Call Dropped"

    return df


# ============================================================
# PROCESS ACD DATA
# ============================================================

def process_acd_data(df):

    df = df.copy()

    df = clean_text_columns(df)

    # --------------------------------------------------------
    # Call ID
    # --------------------------------------------------------

    df["Call ID"] = (
        df["Call ID"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df = df[df["Call ID"] != ""].copy()

    # One row per Call ID within upload
    df = df.drop_duplicates(
        subset=["Call ID"],
        keep="first"
    )

    # --------------------------------------------------------
    # Agent
    # --------------------------------------------------------

    df = normalise_agent_names(df)

    # --------------------------------------------------------
    # Call Time
    # --------------------------------------------------------

    df["Parsed Call Time"] = pd.to_datetime(
        df["Call Time"],
        dayfirst=True,
        errors="coerce"
    )

    df["Call Date"] = df["Parsed Call Time"].dt.date

    df["Call Time Only"] = (
        df["Parsed Call Time"].dt.time
    )

    # --------------------------------------------------------
    # Durations
    # --------------------------------------------------------

    df["Talk Seconds"] = df[
        "User Talk Time"
    ].apply(duration_to_seconds)

    df["Hold Seconds"] = df[
        "User Hold Duration"
    ].apply(duration_to_seconds)

    df["ACW Seconds"] = df[
        "ACW Duration"
    ].apply(duration_to_seconds)

    df["ASA Seconds"] = df[
        "Total Wait Time"
    ].apply(duration_to_seconds)

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
    # Display durations
    # --------------------------------------------------------

    df["AHT"] = df[
        "AHT Seconds"
    ].apply(seconds_to_hhmmss)

    df["ASA"] = df[
        "ASA Seconds"
    ].apply(seconds_to_hhmmss)

    df["ACW"] = df[
        "ACW Seconds"
    ].apply(seconds_to_hhmmss)

    # --------------------------------------------------------
    # Upload date
    # --------------------------------------------------------

    df["Upload Date"] = datetime.now().strftime(
        "%d-%m-%Y %H:%M:%S"
    )

    # Remove temporary calculation columns
    df = df.drop(
        columns=[
            "Parsed Call Time",
            "Talk Seconds",
            "Hold Seconds",
        ],
        errors="ignore"
    )

    # Make sure final columns are exactly in Google order
    for column in GOOGLE_COLUMNS:

        if column not in df.columns:
            df[column] = ""

    df = df[GOOGLE_COLUMNS]

    return df


# ============================================================
# LOAD HISTORICAL DATA
# ============================================================

@st.cache_data(ttl=60)
def load_historical_data():

    worksheet = get_worksheet()

    records = worksheet.get_all_records()

    if not records:

        return pd.DataFrame(columns=GOOGLE_COLUMNS)

    df = pd.DataFrame(records)

    # Ensure expected columns exist
    for column in GOOGLE_COLUMNS:

        if column not in df.columns:
            df[column] = ""

    df = df[GOOGLE_COLUMNS]

    df = clean_text_columns(df)

    # --------------------------------------------------------
    # Fix blank agent names in existing historical data
    # --------------------------------------------------------

    df = normalise_agent_names(df)

    # --------------------------------------------------------
    # Parse date/time
    # --------------------------------------------------------

    df["Parsed Call Time"] = pd.to_datetime(
        df["Call Time"],
        dayfirst=True,
        errors="coerce"
    )

    df["Call Date"] = df["Parsed Call Time"].dt.date

    df["Call Time Only"] = (
        df["Parsed Call Time"].dt.time
    )

    # --------------------------------------------------------
    # Recalculate KPI seconds
    #
    # This also protects against older rows that may not
    # have had the calculated fields populated correctly.
    # --------------------------------------------------------

    df["Talk Seconds"] = df[
        "User Talk Time"
    ].apply(duration_to_seconds)

    df["Hold Seconds"] = df[
        "User Hold Duration"
    ].apply(duration_to_seconds)

    df["ACW Seconds"] = df[
        "ACW Duration"
    ].apply(duration_to_seconds)

    df["ASA Seconds"] = df[
        "Total Wait Time"
    ].apply(duration_to_seconds)

    df["AHT Seconds"] = (
        df["Talk Seconds"]
        + df["Hold Seconds"]
        + df["ACW Seconds"]
    )

    df["AHT"] = df[
        "AHT Seconds"
    ].apply(seconds_to_hhmmss)

    df["ASA"] = df[
        "ASA Seconds"
    ].apply(seconds_to_hhmmss)

    df["ACW"] = df[
        "ACW Seconds"
    ].apply(seconds_to_hhmmss)

    return df


# ============================================================
# UPLOAD SECTION
# ============================================================

st.subheader("📤 Upload ACD Report")

uploaded_file = st.file_uploader(
    "Upload ACD Call Details CSV",
    type=["csv"],
    help="Upload the fixed-format ACD call-detail CSV report."
)


if uploaded_file is not None:

    try:

        uploaded_df = pd.read_csv(
            uploaded_file,
            dtype=str
        )

        uploaded_df.columns = (
            uploaded_df.columns
            .astype(str)
            .str.strip()
        )

        missing_columns = [
            column
            for column in EXPECTED_COLUMNS
            if column not in uploaded_df.columns
        ]

        if missing_columns:

            st.error(
                "The uploaded CSV is missing required columns:\n\n"
                + "\n".join(
                    f"- {column}"
                    for column in missing_columns
                )
            )

        else:

            uploaded_df = uploaded_df[
                EXPECTED_COLUMNS
            ].copy()

            processed_df = process_acd_data(
                uploaded_df
            )

            worksheet = get_worksheet()

            # ------------------------------------------------
            # Existing Call IDs
            # Call ID is column F = column 6
            # ------------------------------------------------

            existing_call_ids = set(
                worksheet.col_values(6)[1:]
            )

            existing_call_ids = {
                str(x).strip()
                for x in existing_call_ids
                if str(x).strip()
            }

            processed_call_ids = set(
                processed_df["Call ID"]
                .astype(str)
                .str.strip()
            )

            new_df = processed_df[
                ~processed_df["Call ID"].isin(
                    existing_call_ids
                )
            ].copy()

            duplicate_count = (
                len(processed_df)
                - len(new_df)
            )

            # ------------------------------------------------
            # Append new rows
            # ------------------------------------------------

            if len(new_df) > 0:

                rows_to_append = (
                    new_df
                    .fillna("")
                    .astype(str)
                    .values
                    .tolist()
                )

                worksheet.append_rows(
                    rows_to_append,
                    value_input_option="USER_ENTERED"
                )

                st.success(
                    f"Upload complete — {len(new_df):,} new "
                    f"calls added to Google Sheets."
                )

                if duplicate_count > 0:

                    st.info(
                        f"{duplicate_count:,} duplicate/existing "
                        f"Call ID(s) were skipped."
                    )

                # Clear cached historical data
                load_historical_data.clear()

            else:

                st.info(
                    "No new calls were added. "
                    "All uploaded Call IDs already exist."
                )

    except Exception as e:

        st.error(
            f"Error processing upload: {e}"
        )


# ============================================================
# LOAD DATA
# ============================================================

try:

    df = load_historical_data()

except Exception as e:

    st.error(
        f"Unable to load Google Sheets data: {e}"
    )

    st.stop()


if df.empty:

    st.info(
        "No ACD data is available yet. "
        "Upload an ACD CSV report above."
    )

    st.stop()


# ============================================================
# ENSURE DATE/TIME DATA IS CORRECT
# ============================================================

df["Parsed Call Time"] = pd.to_datetime(
    df["Call Time"],
    dayfirst=True,
    errors="coerce"
)

df["Call Date"] = (
    df["Parsed Call Time"]
    .dt.date
)

df["Call Time Only"] = (
    df["Parsed Call Time"]
    .dt.time
)

df = normalise_agent_names(df)


# ============================================================
# TOP-LEVEL FILTERS
# ============================================================

st.markdown("---")

st.subheader("🔎 Dashboard Filters")

filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)


# ============================================================
# DATE FILTER
# ============================================================

valid_dates = df["Call Date"].dropna()

if len(valid_dates) > 0:

    min_date = valid_dates.min()
    max_date = valid_dates.max()

else:

    min_date = date.today()
    max_date = date.today()


with filter_col1:

    selected_dates = st.date_input(
        "📅 Date",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        format="DD-MM-YYYY",
        help="Filter all dashboard values by Call Date."
    )


# ============================================================
# TIME FILTER
# ============================================================

with filter_col2:

    selected_time_range = st.slider(
        "🕐 Time",
        min_value=time(0, 0),
        max_value=time(23, 59),
        value=(
            time(0, 0),
            time(23, 59)
        ),
        format="HH:mm",
        help="Filter all dashboard values by Call Time."
    )


# ============================================================
# QUEUE FILTER
# ============================================================

queue_values = sorted(
    [
        str(x).strip()
        for x in df["Queue Name"]
        .dropna()
        .unique()
        if str(x).strip()
    ]
)

with filter_col3:

    selected_queues = st.multiselect(
        "📥 Queue Name",
        options=queue_values,
        default=queue_values,
        help="Filter all dashboard values by Queue Name."
    )


# ============================================================
# DISPOSITION FILTER
# ============================================================

disposition_values = sorted(
    [
        str(x).strip()
        for x in df["User Disposition Code"]
        .dropna()
        .unique()
        if str(x).strip()
    ]
)

with filter_col4:

    selected_dispositions = st.multiselect(
        "🏷️ User Disposition Code",
        options=disposition_values,
        default=disposition_values,
        help=(
            "Filter all dashboard values by "
            "User Disposition Code."
        )
    )


# ============================================================
# HANDLE DATE INPUT
# ============================================================

if isinstance(selected_dates, tuple):

    if len(selected_dates) == 2:

        filter_start_date = selected_dates[0]
        filter_end_date = selected_dates[1]

    else:

        filter_start_date = selected_dates[0]
        filter_end_date = selected_dates[0]

else:

    filter_start_date = selected_dates
    filter_end_date = selected_dates


# ============================================================
# APPLY TOP-LEVEL FILTERS
#
# IMPORTANT:
# Everything below uses filtered_df.
# Therefore ALL dashboard values update together.
# ============================================================

filtered_df = df.copy()


# ------------------------------------------------------------
# Date
# ------------------------------------------------------------

filtered_df = filtered_df[
    filtered_df["Call Date"].notna()
]

filtered_df = filtered_df[
    (
        filtered_df["Call Date"]
        >= filter_start_date
    )
    &
    (
        filtered_df["Call Date"]
        <= filter_end_date
    )
]


# ------------------------------------------------------------
# Time
# ------------------------------------------------------------

start_time = selected_time_range[0]
end_time = selected_time_range[1]

if start_time <= end_time:

    filtered_df = filtered_df[
        (
            filtered_df["Call Time Only"]
            >= start_time
        )
        &
        (
            filtered_df["Call Time Only"]
            <= end_time
        )
    ]

else:

    # Supports overnight ranges such as 22:00 -> 06:00

    filtered_df = filtered_df[
        (
            filtered_df["Call Time Only"]
            >= start_time
        )
        |
        (
            filtered_df["Call Time Only"]
            <= end_time
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

else:

    filtered_df = filtered_df.iloc[0:0]


# ------------------------------------------------------------
# Disposition
# ------------------------------------------------------------

if selected_dispositions:

    filtered_df = filtered_df[
        filtered_df[
            "User Disposition Code"
        ].isin(selected_dispositions)
    ]

else:

    filtered_df = filtered_df.iloc[0:0]


# ============================================================
# FILTER SUMMARY
# ============================================================

st.caption(
    f"Showing {len(filtered_df):,} calls "
    f"from {filter_start_date.strftime('%d-%m-%Y')} "
    f"to {filter_end_date.strftime('%d-%m-%Y')} "
    f"between {start_time.strftime('%H:%M')} "
    f"and {end_time.strftime('%H:%M')}"
)


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
            "date/time/queue/disposition filters. "
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
# NO DATA AFTER FILTER
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
    .apply(seconds_to_hhmmss)
)

agent_summary["Average ASA"] = (
    agent_summary["Avg_ASA_Seconds"]
    .apply(seconds_to_hhmmss)
)

agent_summary["Average ACW"] = (
    agent_summary["Avg_ACW_Seconds"]
    .apply(seconds_to_hhmmss)
)


agent_summary = agent_summary[
    [
        "Username",
        "Calls",
        "Average AHT",
        "Average ASA",
        "Average ACW",
    ]
]


agent_summary = agent_summary.rename(
    columns={
        "Username": "Agent"
    }
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

st.markdown("---")

st.subheader("📅 Daily Performance")


daily_summary = (
    filtered_df
    .groupby("Call Date")
    .agg(
        Calls=("Call ID", "count"),
        Avg_AHT_Seconds=("AHT Seconds", "mean"),
        Avg_ASA_Seconds=("ASA Seconds", "mean"),
        Avg_ACW_Seconds=("ACW Seconds", "mean"),
    )
    .reset_index()
)


daily_summary["Average AHT"] = (
    daily_summary["Avg_AHT_Seconds"]
    .apply(seconds_to_hhmmss)
)

daily_summary["Average ASA"] = (
    daily_summary["Avg_ASA_Seconds"]
    .apply(seconds_to_hhmmss)
)

daily_summary["Average ACW"] = (
    daily_summary["Avg_ACW_Seconds"]
    .apply(seconds_to_hhmmss)
)


daily_summary = daily_summary[
    [
        "Call Date",
        "Calls",
        "Average AHT",
        "Average ASA",
        "Average ACW",
    ]
]


# ------------------------------------------------------------
# IMPORTANT:
# Display date as DD-MM-YYYY
# ------------------------------------------------------------

daily_summary["Call Date"] = (
    pd.to_datetime(
        daily_summary["Call Date"]
    )
    .dt.strftime("%d-%m-%Y")
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


hourly_df = filtered_df.copy()

hourly_df["Hour"] = (
    hourly_df["Parsed Call Time"]
    .dt.hour
)


hourly_summary = (
    hourly_df
    .groupby("Hour")
    .agg(
        Calls=("Call ID", "count"),
        Avg_AHT_Seconds=("AHT Seconds", "mean"),
        Avg_ASA_Seconds=("ASA Seconds", "mean"),
        Avg_ACW_Seconds=("ACW Seconds", "mean"),
    )
    .reset_index()
)


hourly_summary["Time"] = (
    hourly_summary["Hour"]
    .apply(
        lambda x: f"{int(x):02d}:00"
    )
)


hourly_summary["Average AHT"] = (
    hourly_summary["Avg_AHT_Seconds"]
    .apply(seconds_to_hhmmss)
)

hourly_summary["Average ASA"] = (
    hourly_summary["Avg_ASA_Seconds"]
    .apply(seconds_to_hhmmss)
)

hourly_summary["Average ACW"] = (
    hourly_summary["Avg_ACW_Seconds"]
    .apply(seconds_to_hhmmss)
)


hourly_summary = hourly_summary[
    [
        "Time",
        "Calls",
        "Average AHT",
        "Average ASA",
        "Average ACW",
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


display_df = filtered_df.copy()


# ------------------------------------------------------------
# Format Call Date
# ------------------------------------------------------------

display_df["Call Date"] = (
    pd.to_datetime(
        display_df["Call Date"],
        errors="coerce"
    )
    .dt.strftime("%d-%m-%Y")
)


# ------------------------------------------------------------
# Format Call Time
# ------------------------------------------------------------

display_df["Call Time Only"] = (
    display_df["Call Time Only"]
    .apply(
        lambda x:
        x.strftime("%H:%M:%S")
        if pd.notna(x)
        and hasattr(x, "strftime")
        else ""
    )
)


# ------------------------------------------------------------
# Select useful columns for display
# ------------------------------------------------------------

detail_columns = [
    "Call Date",
    "Call Time Only",
    "Campaign Name",
    "Phone",
    "Call Type",
    "Call ID",
    "Answered/Hungup",
    "Queue Name",
    "Username",
    "User Disposition Code",
    "User Talk Time",
    "User Hold Duration",
    "ACW Duration",
    "AHT",
    "ASA",
    "ACW",
    "Hangup Details",
    "Call Notes",
]


detail_columns = [
    column
    for column in detail_columns
    if column in display_df.columns
]


detail_display = display_df[
    detail_columns
].copy()


# Agent column label
detail_display = detail_display.rename(
    columns={
        "Username": "Agent"
    }
)


st.dataframe(
    detail_display,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# DOWNLOAD FILTERED DATA
# ============================================================

st.markdown("---")

st.subheader("⬇️ Export")


download_df = filtered_df.copy()


# ------------------------------------------------------------
# Make dates Excel/CSV friendly as DD-MM-YYYY
# ------------------------------------------------------------

download_df["Call Date"] = (
    pd.to_datetime(
        download_df["Call Date"],
        errors="coerce"
    )
    .dt.strftime("%d-%m-%Y")
)


download_df["Call Time Only"] = (
    download_df["Call Time Only"]
    .apply(
        lambda x:
        x.strftime("%H:%M:%S")
        if pd.notna(x)
        and hasattr(x, "strftime")
        else ""
    )
)


download_df = download_df.drop(
    columns=[
        "Parsed Call Time",
        "Talk Seconds",
        "Hold Seconds",
    ],
    errors="ignore"
)


csv_data = download_df.to_csv(
    index=False
).encode("utf-8")


st.download_button(
    label="📥 Download Filtered Calls CSV",
    data=csv_data,
    file_name=(
        f"ACD_Filtered_"
        f"{filter_start_date.strftime('%d-%m-%Y')}_"
        f"to_"
        f"{filter_end_date.strftime('%d-%m-%Y')}.csv"
    ),
    mime="text/csv"
)


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    f"Google Sheet: {SPREADSHEET_ID} | "
    f"Historical records: {len(df):,} | "
    f"Filtered records: {len(filtered_df):,}"
)
