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

SPREADSHEET_ID = (
    "1R7ioNIYj7iAK3kN21WWlrxy9J9qEdRM9GOebCnUQNpI"
)

ACD_WORKSHEET_NAME = "ACD_Data"
PRODUCTIVITY_WORKSHEET_NAME = "Agent_Productivity"


# ============================================================
# ACD SOURCE COLUMNS
# ============================================================

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


ACD_GOOGLE_COLUMNS = EXPECTED_COLUMNS + [
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
# PRODUCTIVITY SOURCE COLUMNS
# ============================================================

PRODUCTIVITY_COLUMNS = [
    "User ID",
    "Username",
    "Session ID",
    "Login Time",
    "Logout Time",
    "Total Login Duration",
    "Campaign ID",
    "Campaign Name",
    "Ready History ID",
    "Ready Start Time",
    "Ready End Time",
    "Break End Time",
    "Break Reason",
    "Ready Duration",
    "Break Duration",
    "Auto Call On/Off History ID",
    "Auto Call-On Start Time",
    "Auto Call-On End Time",
    "Auto Call-Off End Time",
    "Auto Call-On Duration",
    "Auto Call-Off Duration",
]


PRODUCTIVITY_GOOGLE_COLUMNS = (
    PRODUCTIVITY_COLUMNS
    + ["Upload Date"]
)


# ============================================================
# CUSTOM CSS / COLOUR CODING
# ============================================================

st.markdown(
    """
    <style>

    /* Main background */
    .stApp {
        background: #f6f8fb;
    }

    /* Main title */
    h1 {
        color: #172033;
        font-weight: 700;
    }

    /* Section headings */
    h2, h3 {
        color: #233044;
    }

    /* Tabs */
    button[data-baseweb="tab"] {
        font-weight: 650;
        font-size: 16px;
    }

    /* Metric cards */
    div[data-testid="stMetric"] {
        background: white;
        border-radius: 12px;
        padding: 18px 18px 15px 18px;
        border: 1px solid #e4e9f0;
        box-shadow: 0 2px 8px rgba(31, 41, 55, 0.06);
    }

    div[data-testid="stMetricLabel"] {
        font-weight: 650;
    }

    div[data-testid="stMetricValue"] {
        font-weight: 750;
    }

    /* Expanders */
    div[data-testid="stExpander"] {
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        background: white;
    }

    /* Dataframes */
    div[data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #e3e8ef;
    }

    /* Filter area */
    .filter-box {
        background: white;
        border: 1px solid #e3e8ef;
        border-radius: 12px;
        padding: 8px 14px 12px 14px;
        margin-bottom: 10px;
    }

    /* Informational banner */
    .info-banner {
        background: #eef6ff;
        border-left: 5px solid #2f80ed;
        padding: 10px 14px;
        border-radius: 6px;
        margin: 8px 0 14px 0;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# TITLE
# ============================================================

st.title(
    "📞 ACD Time & Agent Performance"
)

st.caption(
    "ACD call performance and agent productivity tracking."
)


# ============================================================
# GOOGLE SHEETS
# ============================================================

@st.cache_resource
def get_google_client():

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = (
        Credentials.from_service_account_info(
            st.secrets[
                "gcp_service_account"
            ],
            scopes=scopes
        )
    )

    return gspread.authorize(
        credentials
    )


@st.cache_resource
def get_acd_worksheet():

    client = get_google_client()

    spreadsheet = client.open_by_key(
        SPREADSHEET_ID
    )

    try:

        worksheet = spreadsheet.worksheet(
            ACD_WORKSHEET_NAME
        )

    except gspread.WorksheetNotFound:

        worksheet = spreadsheet.add_worksheet(
            title=ACD_WORKSHEET_NAME,
            rows=1000,
            cols=len(
                ACD_GOOGLE_COLUMNS
            )
        )

        worksheet.update(
            "A1",
            [ACD_GOOGLE_COLUMNS]
        )

    return worksheet


@st.cache_resource
def get_productivity_worksheet():

    client = get_google_client()

    spreadsheet = client.open_by_key(
        SPREADSHEET_ID
    )

    try:

        worksheet = spreadsheet.worksheet(
            PRODUCTIVITY_WORKSHEET_NAME
        )

    except gspread.WorksheetNotFound:

        worksheet = spreadsheet.add_worksheet(
            title=PRODUCTIVITY_WORKSHEET_NAME,
            rows=1000,
            cols=len(
                PRODUCTIVITY_GOOGLE_COLUMNS
            )
        )

        worksheet.update(
            "A1",
            [PRODUCTIVITY_GOOGLE_COLUMNS]
        )

    return worksheet


# ============================================================
# COMMON HELPERS
# ============================================================

def clean_text_columns(df):

    df = df.copy()

    for column in df.columns:

        df[column] = (
            df[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    return df


def duration_to_seconds(value):

    if pd.isna(value):
        return 0

    value = str(value).strip()

    if value == "":
        return 0

    try:

        parts = value.split(":")

        if len(parts) == 3:

            return int(
                int(parts[0]) * 3600
                + int(parts[1]) * 60
                + float(parts[2])
            )

        if len(parts) == 2:

            return int(
                int(parts[0]) * 60
                + float(parts[1])
            )

        return int(float(value))

    except Exception:

        return 0


def seconds_to_hhmmss(seconds):

    if pd.isna(seconds):
        return "00:00:00"

    seconds = max(
        0,
        int(round(float(seconds)))
    )

    hours = seconds // 3600

    minutes = (
        seconds % 3600
    ) // 60

    secs = seconds % 60

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{secs:02d}"
    )


def format_average_seconds(value):

    if pd.isna(value):
        return "00:00:00"

    return seconds_to_hhmmss(
        value
    )


def filter_display_value(value):

    if pd.isna(value):
        return "(Blank)"

    value = str(value).strip()

    if value == "":
        return "(Blank)"

    return value


# ============================================================
# TABLE STYLING HELPERS
# ============================================================

def style_acd_table(df):

    styler = df.style

    if "Calls" in df.columns:

        styler = styler.background_gradient(
            subset=["Calls"],
            cmap="Blues"
        )

    for column in [
        "Average AHT",
        "Average ASA",
        "Average ACW",
    ]:

        if column in df.columns:

            styler = styler.set_properties(
                subset=[column],
                **{
                    "background-color": "#f2f7ff",
                    "font-weight": "600"
                }
            )

    return styler


def style_productivity_table(df):

    styler = df.style

    duration_columns = [
        "Login",
        "Active / Ready",
        "Break",
        "Call-On",
        "Call-Off",
        "Unaccounted",
        "Login Duration",
    ]

    for column in duration_columns:

        if column in df.columns:

            styler = styler.set_properties(
                subset=[column],
                **{
                    "font-weight": "600"
                }
            )

    percentage_columns = [
        "Ready %",
        "Break %",
        "Call-On % of Ready",
        "Call-On % of Login",
    ]

    for column in percentage_columns:

        if column in df.columns:

            styler = styler.background_gradient(
                subset=[column],
                cmap="RdYlGn"
            )

    return styler


# ============================================================
# ACD HELPERS
# ============================================================

def normalise_agent_names(df):

    df = df.copy()

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
# PROCESS ACD CSV
# ============================================================

def process_acd_data(df):

    df = clean_text_columns(
        df
    )

    df["Call ID"] = (
        df["Call ID"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df = df[
        df["Call ID"] != ""
    ].copy()

    df = df.drop_duplicates(
        subset=["Call ID"],
        keep="first"
    )

    df = normalise_agent_names(
        df
    )

    df["Parsed Call Time"] = (
        pd.to_datetime(
            df["Call Time"],
            dayfirst=True,
            errors="coerce"
        )
    )

    df["Call Date"] = (
        df["Parsed Call Time"]
        .dt.strftime("%Y-%m-%d")
        .fillna("")
    )

    df["Call Time Only"] = (
        df["Parsed Call Time"]
        .dt.strftime("%H:%M:%S")
        .fillna("")
    )

    df["Talk Seconds"] = (
        df["User Talk Time"]
        .apply(duration_to_seconds)
    )

    df["Hold Seconds"] = (
        df["User Hold Duration"]
        .apply(duration_to_seconds)
    )

    df["ACW Seconds"] = (
        df["ACW Duration"]
        .apply(duration_to_seconds)
    )

    df["ASA Seconds"] = (
        df["Total Wait Time"]
        .apply(duration_to_seconds)
    )

    df["AHT Seconds"] = (
        df["Talk Seconds"]
        + df["Hold Seconds"]
        + df["ACW Seconds"]
    )

    df["AHT"] = (
        df["AHT Seconds"]
        .apply(seconds_to_hhmmss)
    )

    df["ASA"] = (
        df["ASA Seconds"]
        .apply(seconds_to_hhmmss)
    )

    df["ACW"] = (
        df["ACW Seconds"]
        .apply(seconds_to_hhmmss)
    )

    df["Upload Date"] = (
        datetime.now().strftime(
            "%d-%m-%Y %H:%M:%S"
        )
    )

    df = df.drop(
        columns=[
            "Parsed Call Time",
            "Talk Seconds",
            "Hold Seconds",
        ],
        errors="ignore"
    )

    for column in ACD_GOOGLE_COLUMNS:

        if column not in df.columns:
            df[column] = ""

    return df[
        ACD_GOOGLE_COLUMNS
    ]


# ============================================================
# LOAD ACD HISTORY
# ============================================================

@st.cache_data(ttl=60)
def load_acd_history():

    worksheet = get_acd_worksheet()

    records = worksheet.get_all_records()

    if not records:

        return pd.DataFrame(
            columns=ACD_GOOGLE_COLUMNS
        )

    df = pd.DataFrame(records)

    for column in ACD_GOOGLE_COLUMNS:

        if column not in df.columns:
            df[column] = ""

    df = df[
        ACD_GOOGLE_COLUMNS
    ]

    df = clean_text_columns(
        df
    )

    df = normalise_agent_names(
        df
    )

    df["Parsed Call Time"] = (
        pd.to_datetime(
            df["Call Time"],
            dayfirst=True,
            errors="coerce"
        )
    )

    df["Call Date"] = (
        df["Parsed Call Time"]
        .dt.date
    )

    df["Call Time Only"] = (
        df["Parsed Call Time"]
        .dt.time
    )

    df["Talk Seconds"] = (
        df["User Talk Time"]
        .apply(duration_to_seconds)
    )

    df["Hold Seconds"] = (
        df["User Hold Duration"]
        .apply(duration_to_seconds)
    )

    df["ACW Seconds"] = (
        df["ACW Duration"]
        .apply(duration_to_seconds)
    )

    df["ASA Seconds"] = (
        df["Total Wait Time"]
        .apply(duration_to_seconds)
    )

    df["AHT Seconds"] = (
        df["Talk Seconds"]
        + df["Hold Seconds"]
        + df["ACW Seconds"]
    )

    df["AHT"] = (
        df["AHT Seconds"]
        .apply(seconds_to_hhmmss)
    )

    df["ASA"] = (
        df["ASA Seconds"]
        .apply(seconds_to_hhmmss)
    )

    df["ACW"] = (
        df["ACW Seconds"]
        .apply(seconds_to_hhmmss)
    )

    return df


# ============================================================
# PRODUCTIVITY PARSING
# ============================================================

def parse_productivity_datetime(
    series
):

    return pd.to_datetime(
        series,
        dayfirst=True,
        errors="coerce"
    )


def normalise_productivity_data(
    df
):

    df = clean_text_columns(
        df
    )

    datetime_columns = [
        "Login Time",
        "Logout Time",
        "Ready Start Time",
        "Ready End Time",
        "Break End Time",
        "Auto Call-On Start Time",
        "Auto Call-On End Time",
        "Auto Call-Off End Time",
    ]

    for column in datetime_columns:

        if column in df.columns:

            df[
                f"Parsed {column}"
            ] = parse_productivity_datetime(
                df[column]
            )

    df["Username"] = (
        df["Username"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df.loc[
        df["Username"].eq(""),
        "Username"
    ] = "Unknown Agent"

    df["Productivity Date"] = (
        df[
            "Parsed Login Time"
        ]
        .dt.date
    )

    df["Login Seconds"] = (
        df["Total Login Duration"]
        .apply(duration_to_seconds)
    )

    df["Ready Seconds"] = (
        df["Ready Duration"]
        .apply(duration_to_seconds)
    )

    df["Break Seconds"] = (
        df["Break Duration"]
        .apply(duration_to_seconds)
    )

    df["Call On Seconds"] = (
        df[
            "Auto Call-On Duration"
        ]
        .apply(duration_to_seconds)
    )

    df["Call Off Seconds"] = (
        df[
            "Auto Call-Off Duration"
        ]
        .apply(duration_to_seconds)
    )

    return df


def process_productivity_upload(
    df
):

    df = clean_text_columns(
        df
    )

    for column in PRODUCTIVITY_COLUMNS:

        if column not in df.columns:
            df[column] = ""

    df = df[
        PRODUCTIVITY_COLUMNS
    ]

    df = normalise_productivity_data(
        df
    )

    df["Upload Date"] = (
        datetime.now().strftime(
            "%d-%m-%Y %H:%M:%S"
        )
    )

    temporary_columns = [
        column
        for column in df.columns
        if column.startswith(
            "Parsed "
        )
        or column in [
            "Productivity Date",
            "Login Seconds",
            "Ready Seconds",
            "Break Seconds",
            "Call On Seconds",
            "Call Off Seconds",
        ]
    ]

    df = df.drop(
        columns=temporary_columns,
        errors="ignore"
    )

    for column in PRODUCTIVITY_GOOGLE_COLUMNS:

        if column not in df.columns:
            df[column] = ""

    return df[
        PRODUCTIVITY_GOOGLE_COLUMNS
    ]


# ============================================================
# PRODUCTIVITY DUPLICATE KEY
# ============================================================

def productivity_row_key(
    row
):

    session_id = str(
        row.get(
            "Session ID",
            ""
        )
    ).strip()

    ready_id = str(
        row.get(
            "Ready History ID",
            ""
        )
    ).strip()

    auto_id = str(
        row.get(
            "Auto Call On/Off History ID",
            ""
        )
    ).strip()

    if (
        session_id
        and ready_id
        and auto_id
    ):

        return (
            f"{session_id}|"
            f"{ready_id}|"
            f"{auto_id}"
        )

    values = [
        str(
            row.get(
                column,
                ""
            )
        ).strip()
        for column in PRODUCTIVITY_COLUMNS
    ]

    return (
        "ROW|"
        + "|".join(values)
    )


# ============================================================
# LOAD PRODUCTIVITY HISTORY
# ============================================================

@st.cache_data(ttl=60)
def load_productivity_history():

    worksheet = (
        get_productivity_worksheet()
    )

    records = (
        worksheet.get_all_records()
    )

    if not records:

        return pd.DataFrame(
            columns=PRODUCTIVITY_GOOGLE_COLUMNS
        )

    df = pd.DataFrame(
        records
    )

    for column in PRODUCTIVITY_GOOGLE_COLUMNS:

        if column not in df.columns:
            df[column] = ""

    df = df[
        PRODUCTIVITY_GOOGLE_COLUMNS
    ]

    return clean_text_columns(
        df
    )


# ============================================================
# SESSION SUMMARY
# ============================================================

def build_session_summary(
    df
):

    if df.empty:

        return pd.DataFrame()

    records = []

    grouped = (
        df
        .groupby(
            [
                "Username",
                "Session ID"
            ],
            dropna=False
        )
    )

    for (
        (agent, session_id),
        group
    ) in grouped:

        # ----------------------------------------------------
        # LOGIN / LOGOUT
        # ----------------------------------------------------

        login_times = (
            group[
                "Parsed Login Time"
            ]
            .dropna()
        )

        logout_times = (
            group[
                "Parsed Logout Time"
            ]
            .dropna()
        )

        if not login_times.empty:

            login_time = (
                login_times.min()
            )

        else:

            login_time = pd.NaT

        if not logout_times.empty:

            logout_time = (
                logout_times.max()
            )

        else:

            logout_time = pd.NaT

        # ----------------------------------------------------
        # Login duration
        # ----------------------------------------------------

        if (
            pd.notna(login_time)
            and pd.notna(logout_time)
        ):

            login_seconds = (
                logout_time
                - login_time
            ).total_seconds()

        else:

            login_seconds = (
                group[
                    "Total Login Duration"
                ]
                .apply(
                    duration_to_seconds
                )
                .max()
            )

        login_seconds = max(
            0,
            login_seconds
        )

        # ----------------------------------------------------
        # READY
        #
        # One Ready History ID = one ready event
        # ----------------------------------------------------

        ready_rows = (
            group[
                [
                    "Ready History ID",
                    "Ready Duration",
                ]
            ]
            .drop_duplicates(
                subset=[
                    "Ready History ID"
                ]
            )
        )

        ready_seconds = (
            ready_rows[
                "Ready Duration"
            ]
            .apply(
                duration_to_seconds
            )
            .sum()
        )

        # ----------------------------------------------------
        # BREAK
        #
        # One Break value per Ready History ID
        # ----------------------------------------------------

        break_rows = (
            group[
                [
                    "Ready History ID",
                    "Break Duration",
                ]
            ]
            .drop_duplicates(
                subset=[
                    "Ready History ID"
                ]
            )
        )

        break_seconds = (
            break_rows[
                "Break Duration"
            ]
            .apply(
                duration_to_seconds
            )
            .sum()
        )

        # ----------------------------------------------------
        # AUTO CALL
        #
        # One value per Auto Call History ID
        # ----------------------------------------------------

        call_rows = (
            group[
                [
                    "Auto Call On/Off History ID",
                    "Auto Call-On Duration",
                    "Auto Call-Off Duration",
                ]
            ]
            .drop_duplicates(
                subset=[
                    "Auto Call On/Off History ID"
                ]
            )
        )

        call_on_seconds = (
            call_rows[
                "Auto Call-On Duration"
            ]
            .apply(
                duration_to_seconds
            )
            .sum()
        )

        call_off_seconds = (
            call_rows[
                "Auto Call-Off Duration"
            ]
            .apply(
                duration_to_seconds
            )
            .sum()
        )

        # ----------------------------------------------------
        # RECONCILIATION
        #
        # Login = Ready + Break + Unaccounted
        #
        # Call-On/Call-Off are states WITHIN Ready.
        # They are therefore NOT subtracted separately.
        # ----------------------------------------------------

        unaccounted_seconds = max(
            login_seconds
            - ready_seconds
            - break_seconds,
            0
        )

        productivity_date = (
            login_time.date()
            if pd.notna(login_time)
            else None
        )

        campaign_values = (
            group[
                "Campaign Name"
            ]
            .replace(
                "",
                np.nan
            )
            .dropna()
        )

        campaign_name = (
            campaign_values.iloc[0]
            if not campaign_values.empty
            else ""
        )

        records.append(
            {
                "Date": productivity_date,
                "Agent": agent,
                "Session ID": session_id,
                "Login": login_time,
                "Logout": logout_time,
                "Login Seconds": login_seconds,
                "Ready Seconds": ready_seconds,
                "Break Seconds": break_seconds,
                "Call On Seconds": call_on_seconds,
                "Call Off Seconds": call_off_seconds,
                "Unaccounted Seconds": unaccounted_seconds,
                "Campaign Name": campaign_name,
            }
        )

    return pd.DataFrame(
        records
    )


# ============================================================
# AGENT-DAY SUMMARY
#
# STEP 1:
# Calculate the actual day for every agent.
#
# STEP 2:
# If an agent had multiple sessions in one day, those sessions
# form the complete day.
#
# STEP 3:
# This table contains the ACTUAL agent-day values.
#
# Later, dashboard totals/KPIs are AVERAGED across these days.
# ============================================================

def build_agent_day_numeric(
    df
):

    session_df = (
        build_session_summary(
            df
        )
    )

    if session_df.empty:

        return pd.DataFrame()

    daily = (
        session_df
        .groupby(
            [
                "Date",
                "Agent"
            ],
            dropna=False
        )
        .agg(
            Sessions=(
                "Session ID",
                "nunique"
            ),
            Login_Seconds=(
                "Login Seconds",
                "sum"
            ),
            Ready_Seconds=(
                "Ready Seconds",
                "sum"
            ),
            Break_Seconds=(
                "Break Seconds",
                "sum"
            ),
            Call_On_Seconds=(
                "Call On Seconds",
                "sum"
            ),
            Call_Off_Seconds=(
                "Call Off Seconds",
                "sum"
            ),
            Unaccounted_Seconds=(
                "Unaccounted Seconds",
                "sum"
            ),
        )
        .reset_index()
    )

    daily["Ready %"] = np.where(
        daily["Login_Seconds"] > 0,
        (
            daily["Ready_Seconds"]
            / daily["Login_Seconds"]
            * 100
        ),
        0
    )

    daily["Break %"] = np.where(
        daily["Login_Seconds"] > 0,
        (
            daily["Break_Seconds"]
            / daily["Login_Seconds"]
            * 100
        ),
        0
    )

    daily["Call-On % of Ready"] = np.where(
        daily["Ready_Seconds"] > 0,
        (
            daily["Call_On_Seconds"]
            / daily["Ready_Seconds"]
            * 100
        ),
        0
    )

    daily["Call-On % of Login"] = np.where(
        daily["Login_Seconds"] > 0,
        (
            daily["Call_On_Seconds"]
            / daily["Login_Seconds"]
            * 100
        ),
        0
    )

    return daily


def build_agent_day_display(
    numeric_df
):

    if numeric_df.empty:

        return pd.DataFrame()

    df = numeric_df.copy()

    df["Date"] = (
        pd.to_datetime(
            df["Date"],
            errors="coerce"
        )
        .dt.strftime(
            "%d-%m-%Y"
        )
    )

    df["Login"] = (
        df["Login_Seconds"]
        .apply(
            seconds_to_hhmmss
        )
    )

    df["Active / Ready"] = (
        df["Ready_Seconds"]
        .apply(
            seconds_to_hhmmss
        )
    )

    df["Break"] = (
        df["Break_Seconds"]
        .apply(
            seconds_to_hhmmss
        )
    )

    df["Call-On"] = (
        df["Call_On_Seconds"]
        .apply(
            seconds_to_hhmmss
        )
    )

    df["Call-Off"] = (
        df["Call_Off_Seconds"]
        .apply(
            seconds_to_hhmmss
        )
    )

    df["Unaccounted"] = (
        df["Unaccounted_Seconds"]
        .apply(
            seconds_to_hhmmss
        )
    )

    result = df[
        [
            "Date",
            "Agent",
            "Sessions",
            "Login",
            "Active / Ready",
            "Break",
            "Call-On",
            "Call-Off",
            "Unaccounted",
            "Ready %",
            "Break %",
            "Call-On % of Ready",
            "Call-On % of Login",
        ]
    ].copy()

    result["Ready %"] = (
        result["Ready %"]
        .map(
            lambda x:
            f"{x:.1f}%"
        )
    )

    result["Break %"] = (
        result["Break %"]
        .map(
            lambda x:
            f"{x:.1f}%"
        )
    )

    result["Call-On % of Ready"] = (
        result[
            "Call-On % of Ready"
        ]
        .map(
            lambda x:
            f"{x:.1f}%"
        )
    )

    result["Call-On % of Login"] = (
        result[
            "Call-On % of Login"
        ]
        .map(
            lambda x:
            f"{x:.1f}%"
        )
    )

    return result


# ============================================================
# DAILY AVERAGE SUMMARY
#
# One row per DATE.
# Every time metric = AVERAGE ACROSS AGENTS on that date.
# ============================================================

def build_daily_average_summary(
    numeric_df
):

    if numeric_df.empty:

        return pd.DataFrame()

    daily = (
        numeric_df
        .groupby(
            "Date",
            dropna=False
        )
        .agg(
            Agents=(
                "Agent",
                "nunique"
            ),
            Avg_Login=(
                "Login_Seconds",
                "mean"
            ),
            Avg_Ready=(
                "Ready_Seconds",
                "mean"
            ),
            Avg_Break=(
                "Break_Seconds",
                "mean"
            ),
            Avg_Call_On=(
                "Call_On_Seconds",
                "mean"
            ),
            Avg_Call_Off=(
                "Call_Off_Seconds",
                "mean"
            ),
            Avg_Unaccounted=(
                "Unaccounted_Seconds",
                "mean"
            ),
            Avg_Ready_Pct=(
                "Ready %",
                "mean"
            ),
            Avg_Break_Pct=(
                "Break %",
                "mean"
            ),
            Avg_Call_On_Ready_Pct=(
                "Call-On % of Ready",
                "mean"
            ),
            Avg_Call_On_Login_Pct=(
                "Call-On % of Login",
                "mean"
            ),
        )
        .reset_index()
    )

    daily["Date"] = (
        pd.to_datetime(
            daily["Date"],
            errors="coerce"
        )
        .dt.strftime(
            "%d-%m-%Y"
        )
    )

    daily["Average Login"] = (
        daily["Avg_Login"]
        .apply(
            seconds_to_hhmmss
        )
    )

    daily["Average Active / Ready"] = (
        daily["Avg_Ready"]
        .apply(
            seconds_to_hhmmss
        )
    )

    daily["Average Break"] = (
        daily["Avg_Break"]
        .apply(
            seconds_to_hhmmss
        )
    )

    daily["Average Call-On"] = (
        daily["Avg_Call_On"]
        .apply(
            seconds_to_hhmmss
        )
    )

    daily["Average Call-Off"] = (
        daily["Avg_Call_Off"]
        .apply(
            seconds_to_hhmmss
        )
    )

    daily["Average Unaccounted"] = (
        daily["Avg_Unaccounted"]
        .apply(
            seconds_to_hhmmss
        )
    )

    daily["Ready %"] = (
        daily["Avg_Ready_Pct"]
        .map(
            lambda x:
            f"{x:.1f}%"
        )
    )

    daily["Break %"] = (
        daily["Avg_Break_Pct"]
        .map(
            lambda x:
            f"{x:.1f}%"
        )
    )

    daily["Call-On % of Ready"] = (
        daily[
            "Avg_Call_On_Ready_Pct"
        ]
        .map(
            lambda x:
            f"{x:.1f}%"
        )
    )

    daily["Call-On % of Login"] = (
        daily[
            "Avg_Call_On_Login_Pct"
        ]
        .map(
            lambda x:
            f"{x:.1f}%"
        )
    )

    return daily[
        [
            "Date",
            "Agents",
            "Average Login",
            "Average Active / Ready",
            "Average Break",
            "Average Call-On",
            "Average Call-Off",
            "Average Unaccounted",
            "Ready %",
            "Break %",
            "Call-On % of Ready",
            "Call-On % of Login",
        ]
    ]


# ============================================================
# BREAK SUMMARY
# ============================================================

def build_break_summary(
    df
):

    if df.empty:

        return pd.DataFrame()

    break_df = df.copy()

    break_df["Break Seconds"] = (
        break_df[
            "Break Duration"
        ]
        .apply(
            duration_to_seconds
        )
    )

    break_df = (
        break_df[
            [
                "Username",
                "Ready History ID",
                "Break Reason",
                "Break Seconds",
                "Parsed Login Time",
            ]
        ]
        .drop_duplicates(
            subset=[
                "Ready History ID"
            ]
        )
    )

    break_df = break_df[
        break_df[
            "Break Seconds"
        ] > 0
    ].copy()

    if break_df.empty:

        return pd.DataFrame()

    break_df[
        "Break Reason"
    ] = (
        break_df[
            "Break Reason"
        ]
        .apply(
            filter_display_value
        )
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Break summary now uses AVERAGE break duration per
    # break-reason/agent combination.
    # --------------------------------------------------------

    summary = (
        break_df
        .groupby(
            [
                "Username",
                "Break Reason"
            ],
            dropna=False
        )
        .agg(
            Breaks=(
                "Ready History ID",
                "nunique"
            ),
            Average_Break_Seconds=(
                "Break Seconds",
                "mean"
            )
        )
        .reset_index()
    )

    summary["Average Break"] = (
        summary[
            "Average_Break_Seconds"
        ]
        .apply(
            seconds_to_hhmmss
        )
    )

    summary = summary.rename(
        columns={
            "Username": "Agent"
        }
    )

    return summary[
        [
            "Agent",
            "Break Reason",
            "Breaks",
            "Average Break",
        ]
    ].sort_values(
        [
            "Agent",
            "Breaks"
        ],
        ascending=[
            True,
            False
        ]
    )


# ============================================================
# FULL AGENT TIMELINE
# ============================================================

def build_agent_timeline(
    df,
    agent
):

    if df.empty:

        return pd.DataFrame()

    agent_df = df[
        df["Username"].eq(agent)
    ].copy()

    if agent_df.empty:

        return pd.DataFrame()

    timeline_rows = []

    # --------------------------------------------------------
    # LOGIN / LOGOUT
    # --------------------------------------------------------

    for session_id, group in (
        agent_df
        .groupby(
            "Session ID",
            dropna=False
        )
    ):

        login_times = (
            group[
                "Parsed Login Time"
            ]
            .dropna()
        )

        logout_times = (
            group[
                "Parsed Logout Time"
            ]
            .dropna()
        )

        if not login_times.empty:

            value = login_times.min()

            timeline_rows.append(
                {
                    "Session ID": session_id,
                    "Start": value,
                    "End": value,
                    "Activity": "LOGIN",
                    "Reason": "",
                }
            )

        if not logout_times.empty:

            value = logout_times.max()

            timeline_rows.append(
                {
                    "Session ID": session_id,
                    "Start": value,
                    "End": value,
                    "Activity": "LOGOUT",
                    "Reason": "",
                }
            )

    # --------------------------------------------------------
    # READY
    # --------------------------------------------------------

    ready_df = (
        agent_df[
            [
                "Session ID",
                "Ready History ID",
                "Parsed Ready Start Time",
                "Parsed Ready End Time",
            ]
        ]
        .drop_duplicates(
            subset=[
                "Ready History ID"
            ]
        )
    )

    for _, row in (
        ready_df.iterrows()
    ):

        start = row[
            "Parsed Ready Start Time"
        ]

        end = row[
            "Parsed Ready End Time"
        ]

        if (
            pd.notna(start)
            and pd.notna(end)
            and end >= start
        ):

            timeline_rows.append(
                {
                    "Session ID": row[
                        "Session ID"
                    ],
                    "Start": start,
                    "End": end,
                    "Activity": "READY / ACTIVE",
                    "Reason": "",
                }
            )

    # --------------------------------------------------------
    # BREAK
    # --------------------------------------------------------

    break_df = (
        agent_df[
            [
                "Session ID",
                "Ready History ID",
                "Parsed Ready End Time",
                "Parsed Break End Time",
                "Break Reason",
                "Break Duration",
            ]
        ]
        .drop_duplicates(
            subset=[
                "Ready History ID"
            ]
        )
    )

    for _, row in (
        break_df.iterrows()
    ):

        start = row[
            "Parsed Ready End Time"
        ]

        end = row[
            "Parsed Break End Time"
        ]

        seconds = duration_to_seconds(
            row[
                "Break Duration"
            ]
        )

        if (
            pd.notna(start)
            and pd.notna(end)
            and end >= start
            and seconds > 0
        ):

            timeline_rows.append(
                {
                    "Session ID": row[
                        "Session ID"
                    ],
                    "Start": start,
                    "End": end,
                    "Activity": "BREAK",
                    "Reason": filter_display_value(
                        row[
                            "Break Reason"
                        ]
                    ),
                }
            )

    # --------------------------------------------------------
    # AUTO CALL ON / OFF
    # --------------------------------------------------------

    call_df = (
        agent_df[
            [
                "Session ID",
                "Auto Call On/Off History ID",
                "Parsed Auto Call-On Start Time",
                "Parsed Auto Call-On End Time",
                "Parsed Auto Call-Off End Time",
            ]
        ]
        .drop_duplicates(
            subset=[
                "Auto Call On/Off History ID"
            ]
        )
    )

    for _, row in (
        call_df.iterrows()
    ):

        session_id = row[
            "Session ID"
        ]

        on_start = row[
            "Parsed Auto Call-On Start Time"
        ]

        on_end = row[
            "Parsed Auto Call-On End Time"
        ]

        off_end = row[
            "Parsed Auto Call-Off End Time"
        ]

        if (
            pd.notna(on_start)
            and pd.notna(on_end)
            and on_end > on_start
        ):

            timeline_rows.append(
                {
                    "Session ID": session_id,
                    "Start": on_start,
                    "End": on_end,
                    "Activity": "CALL-ON",
                    "Reason": "",
                }
            )

        if (
            pd.notna(on_end)
            and pd.notna(off_end)
            and off_end > on_end
        ):

            timeline_rows.append(
                {
                    "Session ID": session_id,
                    "Start": on_end,
                    "End": off_end,
                    "Activity": "CALL-OFF",
                    "Reason": "",
                }
            )

    if not timeline_rows:

        return pd.DataFrame()

    timeline = pd.DataFrame(
        timeline_rows
    )

    timeline = timeline.sort_values(
        [
            "Start",
            "End"
        ]
    )

    timeline["Duration Seconds"] = (
        timeline["End"]
        - timeline["Start"]
    ).dt.total_seconds()

    timeline["Duration Seconds"] = (
        timeline[
            "Duration Seconds"
        ]
        .fillna(0)
        .clip(
            lower=0
        )
    )

    timeline["Duration"] = (
        timeline[
            "Duration Seconds"
        ]
        .apply(
            seconds_to_hhmmss
        )
    )

    timeline["Date"] = (
        timeline["Start"]
        .dt.strftime(
            "%d-%m-%Y"
        )
    )

    timeline["Start Time"] = (
        timeline["Start"]
        .dt.strftime(
            "%H:%M:%S"
        )
    )

    timeline["End Time"] = (
        timeline["End"]
        .dt.strftime(
            "%H:%M:%S"
        )
    )

    return timeline[
        [
            "Date",
            "Session ID",
            "Start Time",
            "End Time",
            "Activity",
            "Reason",
            "Duration",
        ]
    ]


# ============================================================
# APP TABS
# ============================================================

acd_tab, productivity_tab = st.tabs(
    [
        "📞 ACD Performance",
        "👥 Agent Productivity",
    ]
)


# ################################################################
# TAB 1 — ACD PERFORMANCE
# ################################################################

with acd_tab:

    # ============================================================
    # UPLOAD
    # ============================================================

    with st.expander(
        "📤 Upload ACD Report",
        expanded=False
    ):

        uploaded_file = st.file_uploader(
            "Upload ACD Call Details CSV",
            type=["csv"],
            key="acd_upload",
            help=(
                "Upload the fixed-format ACD "
                "call-detail CSV."
            )
        )

        if uploaded_file is not None:

            if st.button(
                "⬆️ Import ACD Report",
                type="primary",
                key="import_acd"
            ):

                try:

                    with st.spinner(
                        "Importing ACD report..."
                    ):

                        uploaded_df = pd.read_csv(
                            uploaded_file,
                            dtype=str,
                            keep_default_na=False
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
                                "The uploaded CSV is missing "
                                "required columns."
                            )

                            for column in missing_columns:

                                st.write(
                                    f"- {column}"
                                )

                        else:

                            uploaded_df = (
                                uploaded_df[
                                    EXPECTED_COLUMNS
                                ]
                                .copy()
                            )

                            processed_df = (
                                process_acd_data(
                                    uploaded_df
                                )
                            )

                            worksheet = (
                                get_acd_worksheet()
                            )

                            existing_call_ids = set(
                                worksheet.col_values(
                                    6
                                )[1:]
                            )

                            existing_call_ids = {
                                str(x).strip()
                                for x in existing_call_ids
                                if str(x).strip()
                            }

                            new_df = (
                                processed_df[
                                    ~processed_df[
                                        "Call ID"
                                    ].isin(
                                        existing_call_ids
                                    )
                                ]
                                .copy()
                            )

                            duplicate_count = (
                                len(processed_df)
                                - len(new_df)
                            )

                            if not new_df.empty:

                                worksheet.append_rows(
                                    new_df
                                    .fillna("")
                                    .astype(str)
                                    .values
                                    .tolist(),
                                    value_input_option=(
                                        "USER_ENTERED"
                                    )
                                )

                                st.success(
                                    f"ACD upload complete — "
                                    f"**{len(new_df):,} new calls** added."
                                )

                                if duplicate_count:

                                    st.info(
                                        f"{duplicate_count:,} "
                                        "duplicate/existing Call IDs "
                                        "were skipped."
                                    )

                                load_acd_history.clear()

                            else:

                                st.info(
                                    "No new ACD calls were added."
                                )

                except Exception as e:

                    st.error(
                        f"Error importing ACD report: {e}"
                    )

    # ============================================================
    # LOAD ACD
    # ============================================================

    try:

        acd_df = load_acd_history()

    except Exception as e:

        st.error(
            f"Unable to load ACD history: {e}"
        )

        st.stop()

    if acd_df.empty:

        st.info(
            "No ACD data is available yet. "
            "Upload an ACD CSV report above."
        )

    else:

        acd_df = normalise_agent_names(
            acd_df
        )

        acd_df["Parsed Call Time"] = (
            pd.to_datetime(
                acd_df["Call Time"],
                dayfirst=True,
                errors="coerce"
            )
        )

        acd_df["Call Date"] = (
            acd_df["Parsed Call Time"]
            .dt.date
        )

        acd_df["Call Time Only"] = (
            acd_df["Parsed Call Time"]
            .dt.time
        )

        # ========================================================
        # FILTERS
        # ========================================================

        st.subheader(
            "🔎 Dashboard Filters"
        )

        f1, f2, f3, f4 = st.columns(4)

        valid_dates = (
            acd_df[
                "Call Date"
            ]
            .dropna()
        )

        if not valid_dates.empty:

            min_date = valid_dates.min()
            max_date = valid_dates.max()

        else:

            min_date = date.today()
            max_date = date.today()

        with f1:

            selected_dates = st.date_input(
                "📅 Date",
                value=(
                    min_date,
                    max_date
                ),
                min_value=min_date,
                max_value=max_date,
                format="DD-MM-YYYY",
                key="acd_date_filter"
            )

        with f2:

            selected_time_range = st.slider(
                "🕐 Time",
                min_value=time(0, 0),
                max_value=time(23, 59),
                value=(
                    time(0, 0),
                    time(23, 59)
                ),
                format="HH:mm",
                key="acd_time_filter"
            )

        queue_values = sorted(
            {
                filter_display_value(x)
                for x in acd_df[
                    "Queue Name"
                ]
            }
        )

        with f3:

            selected_queues = st.multiselect(
                "📥 Queue Name",
                queue_values,
                default=queue_values,
                key="acd_queue_filter"
            )

        disposition_values = sorted(
            {
                filter_display_value(x)
                for x in acd_df[
                    "User Disposition Code"
                ]
            }
        )

        with f4:

            selected_dispositions = st.multiselect(
                "🏷️ User Disposition Code",
                disposition_values,
                default=disposition_values,
                key="acd_disposition_filter"
            )

        # ========================================================
        # DATE RANGE
        # ========================================================

        if isinstance(
            selected_dates,
            tuple
        ) and len(selected_dates) >= 2:

            filter_start_date = (
                selected_dates[0]
            )

            filter_end_date = (
                selected_dates[1]
            )

        elif isinstance(
            selected_dates,
            tuple
        ) and len(selected_dates) == 1:

            filter_start_date = (
                selected_dates[0]
            )

            filter_end_date = (
                selected_dates[0]
            )

        else:

            filter_start_date = selected_dates
            filter_end_date = selected_dates

        # ========================================================
        # APPLY FILTERS
        # ========================================================

        filtered_acd = acd_df.copy()

        filtered_acd = filtered_acd[
            filtered_acd[
                "Call Date"
            ].notna()
        ]

        filtered_acd = filtered_acd[
            (
                filtered_acd[
                    "Call Date"
                ]
                >= filter_start_date
            )
            &
            (
                filtered_acd[
                    "Call Date"
                ]
                <= filter_end_date
            )
        ]

        start_time = (
            selected_time_range[0]
        )

        end_time = (
            selected_time_range[1]
        )

        if start_time <= end_time:

            filtered_acd = filtered_acd[
                (
                    filtered_acd[
                        "Call Time Only"
                    ]
                    >= start_time
                )
                &
                (
                    filtered_acd[
                        "Call Time Only"
                    ]
                    <= end_time
                )
            ]

        else:

            filtered_acd = filtered_acd[
                (
                    filtered_acd[
                        "Call Time Only"
                    ]
                    >= start_time
                )
                |
                (
                    filtered_acd[
                        "Call Time Only"
                    ]
                    <= end_time
                )
            ]

        if selected_queues:

            queue_mask = (
                filtered_acd[
                    "Queue Name"
                ]
                .apply(
                    filter_display_value
                )
                .isin(
                    selected_queues
                )
            )

            filtered_acd = (
                filtered_acd[
                    queue_mask
                ]
            )

        if selected_dispositions:

            disposition_mask = (
                filtered_acd[
                    "User Disposition Code"
                ]
                .apply(
                    filter_display_value
                )
                .isin(
                    selected_dispositions
                )
            )

            filtered_acd = (
                filtered_acd[
                    disposition_mask
                ]
            )

        # ========================================================
        # ACD KPIs
        # ========================================================

        total_calls = (
            filtered_acd[
                "Call ID"
            ].nunique()
        )

        if not filtered_acd.empty:

            avg_aht = (
                filtered_acd[
                    "AHT Seconds"
                ].mean()
            )

            avg_asa = (
                filtered_acd[
                    "ASA Seconds"
                ].mean()
            )

            avg_acw = (
                filtered_acd[
                    "ACW Seconds"
                ].mean()
            )

        else:

            avg_aht = 0
            avg_asa = 0
            avg_acw = 0

        st.caption(
            f"Showing **{total_calls:,} calls** "
            f"from **{filter_start_date.strftime('%d-%m-%Y')}** "
            f"to **{filter_end_date.strftime('%d-%m-%Y')}**."
        )

        # ========================================================
        # ACD KPI CARDS
        # ========================================================

        k1, k2, k3, k4 = st.columns(4)

        with k1:

            st.metric(
                "📞 Calls",
                f"{total_calls:,}",
                help=(
                    "Unique calls based on Call ID.\n\n"
                    "Blank agents are included as "
                    "'Call Dropped'."
                )
            )

        with k2:

            st.metric(
                "⏱️ Average AHT",
                format_average_seconds(
                    avg_aht
                ),
                help=(
                    "Average Handling Time.\n\n"
                    "User Talk Time + "
                    "User Hold Duration + "
                    "ACW Duration."
                )
            )

        with k3:

            st.metric(
                "⚡ Average ASA",
                format_average_seconds(
                    avg_asa
                ),
                help=(
                    "Average Speed of Answer.\n\n"
                    "Average of Total Wait Time."
                )
            )

        with k4:

            st.metric(
                "📝 Average ACW",
                format_average_seconds(
                    avg_acw
                ),
                help=(
                    "Average After Call Work.\n\n"
                    "Average of ACW Duration."
                )
            )

        if not filtered_acd.empty:

            # ====================================================
            # AGENT PERFORMANCE
            # ====================================================

            st.markdown("---")

            st.subheader(
                "👤 Agent Performance"
            )

            agent_summary = (
                filtered_acd
                .groupby(
                    "Username",
                    dropna=False
                )
                .agg(
                    Calls=(
                        "Call ID",
                        "nunique"
                    ),
                    Avg_AHT_Seconds=(
                        "AHT Seconds",
                        "mean"
                    ),
                    Avg_ASA_Seconds=(
                        "ASA Seconds",
                        "mean"
                    ),
                    Avg_ACW_Seconds=(
                        "ACW Seconds",
                        "mean"
                    ),
                )
                .reset_index()
                .rename(
                    columns={
                        "Username": "Agent"
                    }
                )
            )

            agent_summary[
                "Average AHT"
            ] = (
                agent_summary[
                    "Avg_AHT_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            agent_summary[
                "Average ASA"
            ] = (
                agent_summary[
                    "Avg_ASA_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            agent_summary[
                "Average ACW"
            ] = (
                agent_summary[
                    "Avg_ACW_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            agent_summary = (
                agent_summary[
                    [
                        "Agent",
                        "Calls",
                        "Average AHT",
                        "Average ASA",
                        "Average ACW",
                    ]
                ]
                .sort_values(
                    "Calls",
                    ascending=False
                )
            )

            st.dataframe(
                style_acd_table(
                    agent_summary
                ),
                use_container_width=True,
                hide_index=True
            )

            # ====================================================
            # DAILY PERFORMANCE
            # ====================================================

            st.markdown("---")

            st.subheader(
                "📅 Daily Performance"
            )

            daily_summary = (
                filtered_acd
                .groupby(
                    "Call Date"
                )
                .agg(
                    Calls=(
                        "Call ID",
                        "nunique"
                    ),
                    Avg_AHT_Seconds=(
                        "AHT Seconds",
                        "mean"
                    ),
                    Avg_ASA_Seconds=(
                        "ASA Seconds",
                        "mean"
                    ),
                    Avg_ACW_Seconds=(
                        "ACW Seconds",
                        "mean"
                    ),
                )
                .reset_index()
            )

            daily_summary[
                "Average AHT"
            ] = (
                daily_summary[
                    "Avg_AHT_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            daily_summary[
                "Average ASA"
            ] = (
                daily_summary[
                    "Avg_ASA_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            daily_summary[
                "Average ACW"
            ] = (
                daily_summary[
                    "Avg_ACW_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            daily_summary[
                "Call Date"
            ] = (
                pd.to_datetime(
                    daily_summary[
                        "Call Date"
                    ],
                    errors="coerce"
                )
                .dt.strftime(
                    "%d-%m-%Y"
                )
            )

            daily_summary = (
                daily_summary[
                    [
                        "Call Date",
                        "Calls",
                        "Average AHT",
                        "Average ASA",
                        "Average ACW",
                    ]
                ]
            )

            st.dataframe(
                style_acd_table(
                    daily_summary
                ),
                use_container_width=True,
                hide_index=True
            )

            # ====================================================
            # HOURLY
            # ====================================================

            st.markdown("---")

            st.subheader(
                "🕐 Hourly Call Distribution"
            )

            hourly = filtered_acd.copy()

            hourly["Hour"] = (
                hourly[
                    "Parsed Call Time"
                ]
                .dt.hour
            )

            hourly_summary = (
                hourly
                .groupby(
                    "Hour"
                )
                .agg(
                    Calls=(
                        "Call ID",
                        "nunique"
                    ),
                    Avg_AHT_Seconds=(
                        "AHT Seconds",
                        "mean"
                    ),
                    Avg_ASA_Seconds=(
                        "ASA Seconds",
                        "mean"
                    ),
                    Avg_ACW_Seconds=(
                        "ACW Seconds",
                        "mean"
                    ),
                )
                .reset_index()
            )

            hourly_summary["Time"] = (
                hourly_summary[
                    "Hour"
                ]
                .apply(
                    lambda x:
                    f"{int(x):02d}:00"
                )
            )

            hourly_summary[
                "Average AHT"
            ] = (
                hourly_summary[
                    "Avg_AHT_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            hourly_summary[
                "Average ASA"
            ] = (
                hourly_summary[
                    "Avg_ASA_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            hourly_summary[
                "Average ACW"
            ] = (
                hourly_summary[
                    "Avg_ACW_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            hourly_summary = (
                hourly_summary[
                    [
                        "Time",
                        "Calls",
                        "Average AHT",
                        "Average ASA",
                        "Average ACW",
                    ]
                ]
            )

            st.dataframe(
                style_acd_table(
                    hourly_summary
                ),
                use_container_width=True,
                hide_index=True
            )

            # ====================================================
            # DETAIL
            # ====================================================

            st.markdown("---")

            st.subheader(
                "📋 Detailed Call Records"
            )

            display_df = (
                filtered_acd.copy()
            )

            display_df[
                "Call Date"
            ] = (
                pd.to_datetime(
                    display_df[
                        "Call Date"
                    ],
                    errors="coerce"
                )
                .dt.strftime(
                    "%d-%m-%Y"
                )
            )

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
                c
                for c in detail_columns
                if c in display_df.columns
            ]

            detail_display = (
                display_df[
                    detail_columns
                ]
                .rename(
                    columns={
                        "Username": "Agent"
                    }
                )
            )

            st.dataframe(
                detail_display,
                use_container_width=True,
                hide_index=True,
                height=500
            )

            # ====================================================
            # EXPORT
            # ====================================================

            st.markdown("---")

            st.subheader(
                "⬇️ Export"
            )

            download_df = (
                filtered_acd.copy()
            )

            download_df[
                "Call Date"
            ] = (
                pd.to_datetime(
                    download_df[
                        "Call Date"
                    ],
                    errors="coerce"
                )
                .dt.strftime(
                    "%d-%m-%Y"
                )
            )

            download_df = (
                download_df
                .drop(
                    columns=[
                        "Parsed Call Time",
                        "Talk Seconds",
                        "Hold Seconds",
                    ],
                    errors="ignore"
                )
            )

            st.download_button(
                "📥 Download Filtered Calls CSV",
                data=(
                    download_df
                    .to_csv(
                        index=False
                    )
                    .encode("utf-8")
                ),
                file_name=(
                    "ACD_Filtered_"
                    f"{filter_start_date.strftime('%d-%m-%Y')}_"
                    "to_"
                    f"{filter_end_date.strftime('%d-%m-%Y')}.csv"
                ),
                mime="text/csv",
                key="acd_download"
            )

        else:

            st.warning(
                "No ACD calls match the selected filters."
            )


# ################################################################
# TAB 2 — AGENT PRODUCTIVITY
# ################################################################

with productivity_tab:

    st.header(
        "👥 Agent Productivity"
    )

    st.caption(
        "Average daily agent productivity based on Login, "
        "Active/Ready, Break and Auto Call-On activity."
    )

    # ============================================================
    # UPLOAD
    # ============================================================

    with st.expander(
        "📤 Upload Daily Agent Productivity CSV",
        expanded=True
    ):

        productivity_file = st.file_uploader(
            "Upload Agent Productivity CSV",
            type=["csv"],
            key="productivity_upload"
        )

        if productivity_file is not None:

            if st.button(
                "⬆️ Import Productivity Report",
                type="primary",
                key="import_productivity"
            ):

                try:

                    with st.spinner(
                        "Importing productivity report..."
                    ):

                        upload_df = pd.read_csv(
                            productivity_file,
                            dtype=str,
                            keep_default_na=False
                        )

                        upload_df.columns = (
                            upload_df.columns
                            .astype(str)
                            .str.strip()
                        )

                        missing_columns = [
                            column
                            for column in PRODUCTIVITY_COLUMNS
                            if column not in upload_df.columns
                        ]

                        if missing_columns:

                            st.error(
                                "The productivity CSV is missing "
                                "required columns."
                            )

                            for column in missing_columns:

                                st.write(
                                    f"- {column}"
                                )

                        else:

                            upload_df = (
                                upload_df[
                                    PRODUCTIVITY_COLUMNS
                                ]
                                .copy()
                            )

                            processed = (
                                process_productivity_upload(
                                    upload_df
                                )
                            )

                            worksheet = (
                                get_productivity_worksheet()
                            )

                            existing_records = (
                                worksheet.get_all_records()
                            )

                            existing_keys = set()

                            for row in (
                                existing_records
                            ):

                                existing_keys.add(
                                    productivity_row_key(
                                        row
                                    )
                                )

                            new_rows = []

                            for _, row in (
                                processed.iterrows()
                            ):

                                row_dict = (
                                    row.to_dict()
                                )

                                key = (
                                    productivity_row_key(
                                        row_dict
                                    )
                                )

                                if key not in existing_keys:

                                    new_rows.append(
                                        row.tolist()
                                    )

                                    existing_keys.add(
                                        key
                                    )

                            if new_rows:

                                worksheet.append_rows(
                                    [
                                        [
                                            ""
                                            if pd.isna(v)
                                            else str(v)
                                            for v in row
                                        ]
                                        for row in new_rows
                                    ],
                                    value_input_option=(
                                        "USER_ENTERED"
                                    )
                                )

                                skipped = (
                                    len(processed)
                                    - len(new_rows)
                                )

                                st.success(
                                    f"Productivity upload complete — "
                                    f"**{len(new_rows):,} new records** added."
                                )

                                if skipped:

                                    st.info(
                                        f"{skipped:,} existing/duplicate "
                                        "records were skipped."
                                    )

                                load_productivity_history.clear()

                            else:

                                st.info(
                                    "No new productivity records were added."
                                )

                except Exception as e:

                    st.error(
                        f"Error importing productivity report: {e}"
                    )

    # ============================================================
    # LOAD PRODUCTIVITY
    # ============================================================

    try:

        productivity_df = (
            load_productivity_history()
        )

    except Exception as e:

        st.error(
            f"Unable to load productivity history: {e}"
        )

        st.stop()

    if productivity_df.empty:

        st.info(
            "No productivity data is available yet. "
            "Upload the daily productivity CSV above."
        )

    else:

        productivity_df = (
            normalise_productivity_data(
                productivity_df
            )
        )

        # ========================================================
        # FILTERS
        # ========================================================

        st.markdown("---")

        st.subheader(
            "🔎 Productivity Filters"
        )

        p1, p2, p3, p4 = st.columns(4)

        valid_dates = (
            productivity_df[
                "Productivity Date"
            ]
            .dropna()
        )

        if not valid_dates.empty:

            productivity_min_date = (
                valid_dates.min()
            )

            productivity_max_date = (
                valid_dates.max()
            )

        else:

            productivity_min_date = date.today()
            productivity_max_date = date.today()

        with p1:

            productivity_dates = st.date_input(
                "📅 Date",
                value=(
                    productivity_min_date,
                    productivity_max_date
                ),
                min_value=productivity_min_date,
                max_value=productivity_max_date,
                format="DD-MM-YYYY",
                key="productivity_date_filter"
            )

        agents = sorted(
            [
                str(x)
                for x in productivity_df[
                    "Username"
                ]
                .dropna()
                .unique()
                if str(x).strip()
            ]
        )

        with p2:

            selected_agents = st.multiselect(
                "👤 Agent",
                agents,
                default=agents,
                key="productivity_agent_filter"
            )

        campaigns = sorted(
            {
                filter_display_value(x)
                for x in productivity_df[
                    "Campaign Name"
                ]
            }
        )

        with p3:

            selected_campaigns = st.multiselect(
                "📣 Campaign",
                campaigns,
                default=campaigns,
                key="productivity_campaign_filter"
            )

        break_reasons = sorted(
            {
                filter_display_value(x)
                for x in productivity_df[
                    "Break Reason"
                ]
            }
        )

        with p4:

            selected_break_reasons = st.multiselect(
                "☕ Break Reason",
                break_reasons,
                default=break_reasons,
                key="productivity_break_filter"
            )

        # ========================================================
        # DATE RANGE
        # ========================================================

        if isinstance(
            productivity_dates,
            tuple
        ) and len(productivity_dates) >= 2:

            productivity_start_date = (
                productivity_dates[0]
            )

            productivity_end_date = (
                productivity_dates[1]
            )

        elif isinstance(
            productivity_dates,
            tuple
        ) and len(productivity_dates) == 1:

            productivity_start_date = (
                productivity_dates[0]
            )

            productivity_end_date = (
                productivity_dates[0]
            )

        else:

            productivity_start_date = (
                productivity_dates
            )

            productivity_end_date = (
                productivity_dates
            )

        # ========================================================
        # APPLY FILTERS
        # ========================================================

        filtered_productivity = (
            productivity_df.copy()
        )

        filtered_productivity = (
            filtered_productivity[
                filtered_productivity[
                    "Productivity Date"
                ].notna()
            ]
        )

        filtered_productivity = (
            filtered_productivity[
                (
                    filtered_productivity[
                        "Productivity Date"
                    ]
                    >= productivity_start_date
                )
                &
                (
                    filtered_productivity[
                        "Productivity Date"
                    ]
                    <= productivity_end_date
                )
            ]
        )

        if selected_agents:

            filtered_productivity = (
                filtered_productivity[
                    filtered_productivity[
                        "Username"
                    ].isin(
                        selected_agents
                    )
                ]
            )

        if selected_campaigns:

            campaign_mask = (
                filtered_productivity[
                    "Campaign Name"
                ]
                .apply(
                    filter_display_value
                )
                .isin(
                    selected_campaigns
                )
            )

            filtered_productivity = (
                filtered_productivity[
                    campaign_mask
                ]
            )

        if selected_break_reasons:

            break_mask = (
                filtered_productivity[
                    "Break Reason"
                ]
                .apply(
                    filter_display_value
                )
                .isin(
                    selected_break_reasons
                )
            )

            filtered_productivity = (
                filtered_productivity[
                    break_mask
                ]
            )

        # ========================================================
        # BUILD ACTUAL AGENT-DAY DATA
        # ========================================================

        agent_day_numeric = (
            build_agent_day_numeric(
                filtered_productivity
            )
        )

        if agent_day_numeric.empty:

            st.warning(
                "No productivity records match "
                "the selected filters."
            )

        else:

            # ====================================================
            # IMPORTANT:
            # ALL TOP-LEVEL PRODUCTIVITY KPIs ARE AVERAGES.
            #
            # They are averages of agent-day values.
            # ====================================================

            average_login = (
                agent_day_numeric[
                    "Login_Seconds"
                ].mean()
            )

            average_ready = (
                agent_day_numeric[
                    "Ready_Seconds"
                ].mean()
            )

            average_break = (
                agent_day_numeric[
                    "Break_Seconds"
                ].mean()
            )

            average_call_on = (
                agent_day_numeric[
                    "Call_On_Seconds"
                ].mean()
            )

            average_call_off = (
                agent_day_numeric[
                    "Call_Off_Seconds"
                ].mean()
            )

            average_unaccounted = (
                agent_day_numeric[
                    "Unaccounted_Seconds"
                ].mean()
            )

            average_ready_pct = (
                agent_day_numeric[
                    "Ready %"
                ].mean()
            )

            average_break_pct = (
                agent_day_numeric[
                    "Break %"
                ].mean()
            )

            average_call_on_ready_pct = (
                agent_day_numeric[
                    "Call-On % of Ready"
                ].mean()
            )

            average_call_on_login_pct = (
                agent_day_numeric[
                    "Call-On % of Login"
                ].mean()
            )

            unique_agents = (
                agent_day_numeric[
                    "Agent"
                ].nunique()
            )

            unique_days = (
                agent_day_numeric[
                    "Date"
                ].nunique()
            )

            st.caption(
                f"Average values are calculated per "
                f"**agent-day** across "
                f"**{unique_agents} agents** and "
                f"**{unique_days} day(s)**."
            )

            # ====================================================
            # PRIMARY PRODUCTIVITY KPIs
            # ====================================================

            st.markdown("---")

            st.subheader(
                "📊 Average Productivity"
            )

            pk1, pk2, pk3, pk4 = st.columns(4)

            with pk1:

                st.metric(
                    "🔐 Avg Login",
                    seconds_to_hhmmss(
                        average_login
                    ),
                    help=(
                        "Average login duration per "
                        "agent-day.\n\n"
                        "Calculated from each agent's "
                        "Login Time → Logout Time."
                    )
                )

            with pk2:

                st.metric(
                    "🟢 Avg Active / Ready",
                    seconds_to_hhmmss(
                        average_ready
                    ),
                    help=(
                        "Average Ready/Active time "
                        "per agent-day.\n\n"
                        "Based on Ready Duration."
                    )
                )

            with pk3:

                st.metric(
                    "📞 Avg Call-On",
                    seconds_to_hhmmss(
                        average_call_on
                    ),
                    help=(
                        "Average Auto Call-On duration "
                        "per agent-day.\n\n"
                        "Based on Auto Call-On Duration."
                    )
                )

            with pk4:

                st.metric(
                    "☕ Avg Break",
                    seconds_to_hhmmss(
                        average_break
                    ),
                    help=(
                        "Average recorded break time "
                        "per agent-day."
                    )
                )

            # ====================================================
            # SECOND KPI ROW
            # ====================================================

            pk5, pk6, pk7, pk8 = st.columns(4)

            with pk5:

                st.metric(
                    "📊 Avg Ready %",
                    f"{average_ready_pct:.1f}%",
                    help=(
                        "Average Ready/Active utilisation "
                        "per agent-day.\n\n"
                        "Ready Time ÷ Login Time."
                    )
                )

            with pk6:

                st.metric(
                    "📞 Avg Call-On % of Ready",
                    f"{average_call_on_ready_pct:.1f}%",
                    help=(
                        "Average percentage of Ready time "
                        "spent in Auto Call-On."
                    )
                )

            with pk7:

                st.metric(
                    "📞 Avg Call-On % of Login",
                    f"{average_call_on_login_pct:.1f}%",
                    help=(
                        "Average Auto Call-On time as a "
                        "percentage of login time."
                    )
                )

            with pk8:

                st.metric(
                    "❓ Avg Unaccounted",
                    seconds_to_hhmmss(
                        average_unaccounted
                    ),
                    help=(
                        "Average logged-in time per agent-day "
                        "not accounted for by Ready/Active "
                        "or Break.\n\n"
                        "Login − Ready − Break."
                    )
                )

            # ====================================================
            # AGENT-DAY TABLE
            # ====================================================

            st.markdown("---")

            st.subheader(
                "👤 Agent Daily Productivity"
            )

            st.caption(
                "Each row represents the actual reconstructed "
                "day of one agent. Where multiple sessions "
                "occurred on the same day, they are combined "
                "to represent the complete day."
            )

            agent_day_display = (
                build_agent_day_display(
                    agent_day_numeric
                )
            )

            st.dataframe(
                style_productivity_table(
                    agent_day_display
                ),
                use_container_width=True,
                hide_index=True
            )

            # ====================================================
            # DAILY AVERAGES
            # ====================================================

            st.markdown("---")

            st.subheader(
                "📅 Daily Average Productivity"
            )

            st.caption(
                "Each date shows the average time per agent "
                "for that day — not the combined time of all agents."
            )

            daily_average = (
                build_daily_average_summary(
                    agent_day_numeric
                )
            )

            st.dataframe(
                style_productivity_table(
                    daily_average
                ),
                use_container_width=True,
                hide_index=True
            )

            # ====================================================
            # BREAK ANALYSIS
            # ====================================================

            st.markdown("---")

            st.subheader(
                "☕ Break Analysis"
            )

            break_summary = (
                build_break_summary(
                    filtered_productivity
                )
            )

            if break_summary.empty:

                st.info(
                    "No recorded breaks match "
                    "the selected filters."
                )

            else:

                st.dataframe(
                    break_summary,
                    use_container_width=True,
                    hide_index=True
                )

            # ====================================================
            # SESSION SUMMARY
            # ====================================================

            st.markdown("---")

            st.subheader(
                "🔐 Session Detail"
            )

            session_summary = (
                build_session_summary(
                    filtered_productivity
                )
            )

            if session_summary.empty:

                st.info(
                    "No sessions match the selected filters."
                )

            else:

                session_display = (
                    session_summary.copy()
                )

                session_display[
                    "Login"
                ] = (
                    session_display[
                        "Login"
                    ]
                    .apply(
                        lambda x:
                        x.strftime(
                            "%d-%m-%Y %H:%M:%S"
                        )
                        if pd.notna(x)
                        else ""
                    )
                )

                session_display[
                    "Logout"
                ] = (
                    session_display[
                        "Logout"
                    ]
                    .apply(
                        lambda x:
                        x.strftime(
                            "%d-%m-%Y %H:%M:%S"
                        )
                        if pd.notna(x)
                        else ""
                    )
                )

                session_display[
                    "Login Duration"
                ] = (
                    session_display[
                        "Login Seconds"
                    ]
                    .apply(
                        seconds_to_hhmmss
                    )
                )

                session_display[
                    "Active / Ready"
                ] = (
                    session_display[
                        "Ready Seconds"
                    ]
                    .apply(
                        seconds_to_hhmmss
                    )
                )

                session_display[
                    "Break"
                ] = (
                    session_display[
                        "Break Seconds"
                    ]
                    .apply(
                        seconds_to_hhmmss
                    )
                )

                session_display[
                    "Call-On"
                ] = (
                    session_display[
                        "Call On Seconds"
                    ]
                    .apply(
                        seconds_to_hhmmss
                    )
                )

                session_display[
                    "Call-Off"
                ] = (
                    session_display[
                        "Call Off Seconds"
                    ]
                    .apply(
                        seconds_to_hhmmss
                    )
                )

                session_display[
                    "Unaccounted"
                ] = (
                    session_display[
                        "Unaccounted Seconds"
                    ]
                    .apply(
                        seconds_to_hhmmss
                    )
                )

                session_display = (
                    session_display[
                        [
                            "Date",
                            "Agent",
                            "Session ID",
                            "Campaign Name",
                            "Login",
                            "Logout",
                            "Login Duration",
                            "Active / Ready",
                            "Break",
                            "Call-On",
                            "Call-Off",
                            "Unaccounted",
                        ]
                    ]
                )

                session_display[
                    "Date"
                ] = (
                    pd.to_datetime(
                        session_display[
                            "Date"
                        ],
                        errors="coerce"
                    )
                    .dt.strftime(
                        "%d-%m-%Y"
                    )
                )

                st.dataframe(
                    session_display,
                    use_container_width=True,
                    hide_index=True
                )

            # ====================================================
            # FULL-DAY TIMELINE
            # ====================================================

            st.markdown("---")

            st.subheader(
                "🕐 Full-Day Agent Timeline"
            )

            available_agents = sorted(
                filtered_productivity[
                    "Username"
                ]
                .dropna()
                .unique()
                .tolist()
            )

            if available_agents:

                timeline_agent = (
                    st.selectbox(
                        "Select an agent",
                        available_agents,
                        key="timeline_agent"
                    )
                )

                timeline = (
                    build_agent_timeline(
                        filtered_productivity,
                        timeline_agent
                    )
                )

                if timeline.empty:

                    st.info(
                        "No timeline events are available "
                        "for this agent."
                    )

                else:

                    st.dataframe(
                        timeline,
                        use_container_width=True,
                        hide_index=True,
                        height=500
                    )

            # ====================================================
            # RAW RECORDS
            # ====================================================

            st.markdown("---")

            with st.expander(
                "📄 View Uploaded Productivity Records",
                expanded=False
            ):

                raw_display = (
                    filtered_productivity.copy()
                )

                raw_display = (
                    raw_display.drop(
                        columns=[
                            "Login Seconds",
                            "Ready Seconds",
                            "Break Seconds",
                            "Call On Seconds",
                            "Call Off Seconds",
                            "Parsed Login Time",
                            "Parsed Logout Time",
                            "Parsed Ready Start Time",
                            "Parsed Ready End Time",
                            "Parsed Break End Time",
                            "Parsed Auto Call-On Start Time",
                            "Parsed Auto Call-On End Time",
                            "Parsed Auto Call-Off End Time",
                        ],
                        errors="ignore"
                    )
                )

                st.dataframe(
                    raw_display,
                    use_container_width=True,
                    hide_index=True,
                    height=500
                )

            # ====================================================
            # EXPORT — AGENT DAY
            # ====================================================

            st.markdown("---")

            st.subheader(
                "⬇️ Productivity Export"
            )

            export_df = (
                agent_day_numeric.copy()
            )

            export_df["Date"] = (
                pd.to_datetime(
                    export_df["Date"],
                    errors="coerce"
                )
                .dt.strftime(
                    "%d-%m-%Y"
                )
            )

            export_df["Login"] = (
                export_df[
                    "Login_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            export_df["Active / Ready"] = (
                export_df[
                    "Ready_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            export_df["Break"] = (
                export_df[
                    "Break_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            export_df["Call-On"] = (
                export_df[
                    "Call_On_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            export_df["Call-Off"] = (
                export_df[
                    "Call_Off_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            export_df["Unaccounted"] = (
                export_df[
                    "Unaccounted_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            export_df = export_df[
                [
                    "Date",
                    "Agent",
                    "Sessions",
                    "Login",
                    "Active / Ready",
                    "Break",
                    "Call-On",
                    "Call-Off",
                    "Unaccounted",
                    "Ready %",
                    "Break %",
                    "Call-On % of Ready",
                    "Call-On % of Login",
                ]
            ]

            # Numeric percentages
            export_df[
                "Ready %"
            ] = (
                export_df[
                    "Ready %"
                ]
                .round(2)
            )

            export_df[
                "Break %"
            ] = (
                export_df[
                    "Break %"
                ]
                .round(2)
            )

            export_df[
                "Call-On % of Ready"
            ] = (
                export_df[
                    "Call-On % of Ready"
                ]
                .round(2)
            )

            export_df[
                "Call-On % of Login"
            ] = (
                export_df[
                    "Call-On % of Login"
                ]
                .round(2)
            )

            st.download_button(
                "📥 Download Agent Productivity CSV",
                data=(
                    export_df
                    .to_csv(
                        index=False
                    )
                    .encode(
                        "utf-8"
                    )
                ),
                file_name=(
                    "Agent_Productivity_"
                    f"{productivity_start_date.strftime('%d-%m-%Y')}_"
                    "to_"
                    f"{productivity_end_date.strftime('%d-%m-%Y')}.csv"
                ),
                mime="text/csv",
                key="productivity_download"
            )

            # ====================================================
            # FOOTER
            # ====================================================

            st.markdown("---")

            st.caption(
                f"Historical productivity records: "
                f"{len(productivity_df):,} | "
                f"Filtered source records: "
                f"{len(filtered_productivity):,} | "
                f"Agent-days: "
                f"{len(agent_day_numeric):,}"
            )
