
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
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ============================================================
# CUSTOM STYLING
# ============================================================

st.markdown(
    """
    <style>

    /* --------------------------------------------------------
       GENERAL
       -------------------------------------------------------- */

    .main {
        padding-top: 1rem;
    }

    h1 {
        font-weight: 700;
    }

    h2, h3 {
        font-weight: 650;
    }

    /* --------------------------------------------------------
       TABS
       -------------------------------------------------------- */

    button[data-baseweb="tab"] {
        font-size: 16px;
        font-weight: 650;
        padding-left: 20px;
        padding-right: 20px;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        border-bottom-width: 3px;
    }

    /* --------------------------------------------------------
       KPI CARDS
       -------------------------------------------------------- */

    div[data-testid="stMetric"] {
        background: linear-gradient(
            135deg,
            rgba(245, 248, 252, 1),
            rgba(235, 241, 249, 1)
        );
        border-radius: 14px;
        padding: 16px 18px;
        border: 1px solid rgba(80, 100, 130, 0.15);
        box-shadow: 0 3px 10px rgba(0, 0, 0, 0.06);
        min-height: 105px;
    }

    div[data-testid="stMetric"] label {
        font-weight: 650;
    }

    div[data-testid="stMetricValue"] {
        font-weight: 750;
    }

    /* --------------------------------------------------------
       DATAFRAMES / TABLES
       -------------------------------------------------------- */

    div[data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
    }

    /* --------------------------------------------------------
       FILTER CONTAINERS
       -------------------------------------------------------- */

    div[data-testid="stExpander"] {
        border-radius: 12px;
    }

    /* --------------------------------------------------------
       INFO / WARNING / SUCCESS BOXES
       -------------------------------------------------------- */

    div[data-testid="stAlert"] {
        border-radius: 10px;
    }

    /* --------------------------------------------------------
       BUTTONS
       -------------------------------------------------------- */

    div.stButton > button {
        border-radius: 8px;
        font-weight: 650;
    }

    /* --------------------------------------------------------
       SECTION DIVIDERS
       -------------------------------------------------------- */

    hr {
        margin-top: 1rem;
        margin-bottom: 1rem;
    }

    /* --------------------------------------------------------
       SMALL CAPTION
       -------------------------------------------------------- */

    .dashboard-caption {
        font-size: 0.88rem;
        opacity: 0.75;
    }

    </style>
    """,
    unsafe_allow_html=True
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
# TITLE
# ============================================================

st.title(
    "📞 ACD Time & Agent Performance"
)

st.caption(
    "ACD call performance and agent productivity tracking."
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

    credentials = (
        Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=scopes
        )
    )

    return gspread.authorize(
        credentials
    )


# ============================================================
# ACD WORKSHEET
# ============================================================

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
            cols=len(ACD_GOOGLE_COLUMNS)
        )

        worksheet.update(
            "A1",
            [ACD_GOOGLE_COLUMNS]
        )

    return worksheet


# ============================================================
# PRODUCTIVITY WORKSHEET
# ============================================================

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

            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])

            return int(
                hours * 3600
                + minutes * 60
                + seconds
            )

        elif len(parts) == 2:

            minutes = int(parts[0])
            seconds = float(parts[1])

            return int(
                minutes * 60
                + seconds
            )

        return int(float(value))

    except Exception:

        return 0


def seconds_to_hhmmss(seconds):

    if pd.isna(seconds):
        return "00:00:00"

    seconds = int(
        round(float(seconds))
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


def filter_display_value(value):

    if pd.isna(value):
        return "(Blank)"

    value = str(value).strip()

    if value == "":
        return "(Blank)"

    return value


# ============================================================
# ACD AGENT NORMALISATION
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
# PROCESS ACD UPLOAD
# ============================================================

def process_acd_data(df):

    df = clean_text_columns(
        df.copy()
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

    df = pd.DataFrame(
        records
    )

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
# PRODUCTIVITY PROCESSING
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

    df = df.copy()

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
        df["Parsed Login Time"]
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
        df["Auto Call-On Duration"]
        .apply(duration_to_seconds)
    )

    df["Call Off Seconds"] = (
        df["Auto Call-Off Duration"]
        .apply(duration_to_seconds)
    )

    return df


# ============================================================
# PRODUCTIVITY UPLOAD PROCESSOR
# ============================================================

def process_productivity_upload(
    df
):

    df = clean_text_columns(
        df.copy()
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
        if column.startswith("Parsed ")
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
# PRODUCTIVITY DEDUPLICATION KEY
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

    records = worksheet.get_all_records()

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

    grouped = df.groupby(
        [
            "Username",
            "Session ID"
        ],
        dropna=False
    )

    for (
        (agent, session_id),
        group
    ) in grouped:

        group = group.copy()

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

        ready_rows = (
            group[
                [
                    "Ready History ID",
                    "Ready Duration"
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
        # Full-day reconciliation
        #
        # Call-On / Call-Off are inside Ready.
        # Therefore:
        #
        # LOGIN =
        # READY + BREAK + UNACCOUNTED
        # ----------------------------------------------------

        unaccounted_seconds = max(
            login_seconds
            - ready_seconds
            - break_seconds,
            0
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

        if not campaign_values.empty:

            campaign_name = (
                campaign_values.iloc[0]
            )

        else:

            campaign_name = ""

        records.append(
            {
                "Date": (
                    login_time.date()
                    if pd.notna(login_time)
                    else None
                ),
                "Agent": agent,
                "Session ID": session_id,
                "Login": login_time,
                "Logout": logout_time,
                "Login Seconds": login_seconds,
                "Ready Seconds": ready_seconds,
                "Break Seconds": break_seconds,
                "Call On Seconds": call_on_seconds,
                "Call Off Seconds": call_off_seconds,
                "Unaccounted Seconds": (
                    unaccounted_seconds
                ),
                "Campaign Name": campaign_name,
            }
        )

    return pd.DataFrame(
        records
    )


# ============================================================
# AGENT-DAY SUMMARY
#
# Important:
# We calculate each agent's COMPLETE DAY first.
# Then, when the user selects multiple dates,
# table values become AVERAGES PER AGENT-DAY.
# ============================================================

def build_agent_day_summary(
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

    # --------------------------------------------------------
    # Per-agent-day percentages
    # --------------------------------------------------------

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

    daily[
        "Call-On % of Ready"
    ] = np.where(
        daily["Ready_Seconds"] > 0,
        (
            daily["Call_On_Seconds"]
            / daily["Ready_Seconds"]
            * 100
        ),
        0
    )

    daily[
        "Call-On % of Login"
    ] = np.where(
        daily["Login_Seconds"] > 0,
        (
            daily["Call_On_Seconds"]
            / daily["Login_Seconds"]
            * 100
        ),
        0
    )

    return daily


# ============================================================
# AVERAGE AGENT-DAY TABLE
#
# This is the key change:
# multiple days are averaged, not added together.
# ============================================================

def build_average_agent_table(
    agent_day_df
):

    if agent_day_df.empty:
        return pd.DataFrame()

    result = (
        agent_day_df
        .groupby(
            "Agent",
            dropna=False
        )
        .agg(
            Days=(
                "Date",
                "nunique"
            ),
            Sessions=(
                "Sessions",
                "mean"
            ),
            Avg_Login_Seconds=(
                "Login_Seconds",
                "mean"
            ),
            Avg_Ready_Seconds=(
                "Ready_Seconds",
                "mean"
            ),
            Avg_Break_Seconds=(
                "Break_Seconds",
                "mean"
            ),
            Avg_Call_On_Seconds=(
                "Call_On_Seconds",
                "mean"
            ),
            Avg_Call_Off_Seconds=(
                "Call_Off_Seconds",
                "mean"
            ),
            Avg_Unaccounted_Seconds=(
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

    # --------------------------------------------------------
    # Display durations
    # --------------------------------------------------------

    result["Average Login"] = (
        result[
            "Avg_Login_Seconds"
        ]
        .apply(
            seconds_to_hhmmss
        )
    )

    result["Average Active / Ready"] = (
        result[
            "Avg_Ready_Seconds"
        ]
        .apply(
            seconds_to_hhmmss
        )
    )

    result["Average Break"] = (
        result[
            "Avg_Break_Seconds"
        ]
        .apply(
            seconds_to_hhmmss
        )
    )

    result["Average Call-On"] = (
        result[
            "Avg_Call_On_Seconds"
        ]
        .apply(
            seconds_to_hhmmss
        )
    )

    result["Average Call-Off"] = (
        result[
            "Avg_Call_Off_Seconds"
        ]
        .apply(
            seconds_to_hhmmss
        )
    )

    result["Average Unaccounted"] = (
        result[
            "Avg_Unaccounted_Seconds"
        ]
        .apply(
            seconds_to_hhmmss
        )
    )

    result["Average Sessions"] = (
        result[
            "Sessions"
        ]
        .map(
            lambda x:
            f"{x:.1f}"
        )
    )

    result["Ready %"] = (
        result[
            "Avg_Ready_Pct"
        ]
        .map(
            lambda x:
            f"{x:.1f}%"
        )
    )

    result["Break %"] = (
        result[
            "Avg_Break_Pct"
        ]
        .map(
            lambda x:
            f"{x:.1f}%"
        )
    )

    result[
        "Call-On % of Ready"
    ] = (
        result[
            "Avg_Call_On_Ready_Pct"
        ]
        .map(
            lambda x:
            f"{x:.1f}%"
        )
    )

    result[
        "Call-On % of Login"
    ] = (
        result[
            "Avg_Call_On_Login_Pct"
        ]
        .map(
            lambda x:
            f"{x:.1f}%"
        )
    )

    return result[
        [
            "Agent",
            "Days",
            "Average Sessions",
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
    ].sort_values(
        "Average Call-On",
        ascending=False
    )


# ============================================================
# DAILY AVERAGE TABLE
#
# Each date shows the average across agents on that date.
# ============================================================

def build_daily_average_table(
    agent_day_df
):

    if agent_day_df.empty:
        return pd.DataFrame()

    daily = (
        agent_day_df
        .groupby(
            "Date",
            dropna=False
        )
        .agg(
            Agents=(
                "Agent",
                "nunique"
            ),
            Average_Login_Seconds=(
                "Login_Seconds",
                "mean"
            ),
            Average_Ready_Seconds=(
                "Ready_Seconds",
                "mean"
            ),
            Average_Break_Seconds=(
                "Break_Seconds",
                "mean"
            ),
            Average_Call_On_Seconds=(
                "Call_On_Seconds",
                "mean"
            ),
            Average_Call_Off_Seconds=(
                "Call_Off_Seconds",
                "mean"
            ),
            Average_Unaccounted_Seconds=(
                "Unaccounted_Seconds",
                "mean"
            ),
            Average_Ready_Pct=(
                "Ready %",
                "mean"
            ),
            Average_Break_Pct=(
                "Break %",
                "mean"
            ),
            Average_Call_On_Ready_Pct=(
                "Call-On % of Ready",
                "mean"
            ),
            Average_Call_On_Login_Pct=(
                "Call-On % of Login",
                "mean"
            ),
        )
        .reset_index()
    )

    daily["Average Login"] = (
        daily[
            "Average_Login_Seconds"
        ]
        .apply(
            seconds_to_hhmmss
        )
    )

    daily["Average Active / Ready"] = (
        daily[
            "Average_Ready_Seconds"
        ]
        .apply(
            seconds_to_hhmmss
        )
    )

    daily["Average Break"] = (
        daily[
            "Average_Break_Seconds"
        ]
        .apply(
            seconds_to_hhmmss
        )
    )

    daily["Average Call-On"] = (
        daily[
            "Average_Call_On_Seconds"
        ]
        .apply(
            seconds_to_hhmmss
        )
    )

    daily["Average Call-Off"] = (
        daily[
            "Average_Call_Off_Seconds"
        ]
        .apply(
            seconds_to_hhmmss
        )
    )

    daily["Average Unaccounted"] = (
        daily[
            "Average_Unaccounted_Seconds"
        ]
        .apply(
            seconds_to_hhmmss
        )
    )

    daily["Ready %"] = (
        daily[
            "Average_Ready_Pct"
        ]
        .map(
            lambda x:
            f"{x:.1f}%"
        )
    )

    daily["Break %"] = (
        daily[
            "Average_Break_Pct"
        ]
        .map(
            lambda x:
            f"{x:.1f}%"
        )
    )

    daily[
        "Call-On % of Ready"
    ] = (
        daily[
            "Average_Call_On_Ready_Pct"
        ]
        .map(
            lambda x:
            f"{x:.1f}%"
        )
    )

    daily[
        "Call-On % of Login"
    ] = (
        daily[
            "Average_Call_On_Login_Pct"
        ]
        .map(
            lambda x:
            f"{x:.1f}%"
        )
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
    ].sort_values(
        "Date"
    )


# ============================================================
# BREAK ANALYSIS
#
# Uses AVERAGE break duration rather than total break duration.
# ============================================================

def build_break_summary(
    df
):

    if df.empty:
        return pd.DataFrame()

    break_df = df.copy()

    # --------------------------------------------------------
    # Convert Break Duration to seconds
    # --------------------------------------------------------

    break_df["Break Seconds"] = (
        break_df["Break Duration"]
        .apply(
            duration_to_seconds
        )
    )

    # --------------------------------------------------------
    # One record per Ready History ID
    #
    # The source CSV repeats some rows because Auto
    # Call-On/Call-Off history is nested inside Ready
    # history. We therefore deduplicate using Ready History ID.
    # --------------------------------------------------------

    break_df = (
        break_df[
            [
                "Username",
                "Ready History ID",
                "Break Reason",
                "Break Seconds",
            ]
        ]
        .drop_duplicates(
            subset=[
                "Ready History ID"
            ]
        )
    )

    # Only actual breaks
    break_df = break_df[
        break_df["Break Seconds"] > 0
    ].copy()

    if break_df.empty:
        return pd.DataFrame()

    # --------------------------------------------------------
    # Display blank break reasons as "(Blank)"
    # --------------------------------------------------------

    break_df["Break Reason"] = (
        break_df["Break Reason"]
        .apply(
            filter_display_value
        )
    )

    # --------------------------------------------------------
    # Average break duration by reason
    # --------------------------------------------------------

    summary = (
        break_df
        .groupby(
            "Break Reason",
            dropna=False
        )
        .agg(
            Agents=(
                "Username",
                "nunique"
            ),
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

    # --------------------------------------------------------
    # Create display version
    # --------------------------------------------------------

    summary["Average Break"] = (
        summary[
            "Average_Break_Seconds"
        ]
        .apply(
            seconds_to_hhmmss
        )
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Sort BEFORE removing the numeric sort column.
    # --------------------------------------------------------

    summary = summary.sort_values(
        "Average_Break_Seconds",
        ascending=False
    )

    # --------------------------------------------------------
    # Final display columns
    # --------------------------------------------------------

    return summary[
        [
            "Break Reason",
            "Agents",
            "Breaks",
            "Average Break",
        ]
    ].reset_index(
        drop=True
    )


# ============================================================
# AGENT BREAK DETAIL
# ============================================================

def build_agent_break_summary(
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
            ]
        ]
        .drop_duplicates(
            subset=[
                "Ready History ID"
            ]
        )
    )

    break_df = break_df[
        break_df["Break Seconds"] > 0
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

    summary[
        "Average Break"
    ] = (
        summary[
            "Average_Break_Seconds"
        ]
        .apply(
            seconds_to_hhmmss
        )
    )

    return summary[
        [
            "Username",
            "Break Reason",
            "Breaks",
            "Average Break",
        ]
    ].rename(
        columns={
            "Username": "Agent"
        }
    )


# ============================================================
# TIMELINE
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

    for (
        session_id,
        group
    ) in agent_df.groupby(
        "Session ID",
        dropna=False
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

            login = login_times.min()

            timeline_rows.append(
                {
                    "Session ID": session_id,
                    "Start": login,
                    "End": login,
                    "Activity": "LOGIN",
                    "Reason": "",
                }
            )

        if not logout_times.empty:

            logout = logout_times.max()

            timeline_rows.append(
                {
                    "Session ID": session_id,
                    "Start": logout,
                    "End": logout,
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

    for _, row in ready_df.iterrows():

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
            and end > start
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

    for _, row in break_df.iterrows():

        start = row[
            "Parsed Ready End Time"
        ]

        end = row[
            "Parsed Break End Time"
        ]

        duration = duration_to_seconds(
            row["Break Duration"]
        )

        if (
            pd.notna(start)
            and pd.notna(end)
            and duration > 0
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
    # CALL ON/OFF
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

    for _, row in call_df.iterrows():

        session_id = row[
            "Session ID"
        ]

        call_on_start = row[
            "Parsed Auto Call-On Start Time"
        ]

        call_on_end = row[
            "Parsed Auto Call-On End Time"
        ]

        call_off_end = row[
            "Parsed Auto Call-Off End Time"
        ]

        if (
            pd.notna(call_on_start)
            and pd.notna(call_on_end)
            and call_on_end > call_on_start
        ):

            timeline_rows.append(
                {
                    "Session ID": session_id,
                    "Start": call_on_start,
                    "End": call_on_end,
                    "Activity": "CALL-ON",
                    "Reason": "",
                }
            )

        if (
            pd.notna(call_on_end)
            and pd.notna(call_off_end)
            and call_off_end > call_on_end
        ):

            timeline_rows.append(
                {
                    "Session ID": session_id,
                    "Start": call_on_end,
                    "End": call_off_end,
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

    timeline[
        "Duration Seconds"
    ] = (
        timeline[
            "Duration Seconds"
        ]
        .fillna(0)
        .clip(lower=0)
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
        timeline[
            "Start"
        ]
        .dt.strftime(
            "%d-%m-%Y"
        )
    )

    timeline["Start Time"] = (
        timeline[
            "Start"
        ]
        .dt.strftime(
            "%H:%M:%S"
        )
    )

    timeline["End Time"] = (
        timeline[
            "End"
        ]
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
# MAIN TITLE
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
            key="acd_upload"
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
                                "required columns:"
                            )

                            st.write(
                                missing_columns
                            )

                        else:

                            processed = (
                                process_acd_data(
                                    uploaded_df[
                                        EXPECTED_COLUMNS
                                    ]
                                )
                            )

                            worksheet = (
                                get_acd_worksheet()
                            )

                            existing_ids = set(
                                worksheet.col_values(
                                    6
                                )[1:]
                            )

                            existing_ids = {
                                str(x).strip()
                                for x in existing_ids
                                if str(x).strip()
                            }

                            new_df = processed[
                                ~processed[
                                    "Call ID"
                                ].isin(
                                    existing_ids
                                )
                            ]

                            duplicate_count = (
                                len(processed)
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
    # LOAD
    # ============================================================

    try:

        acd_df = load_acd_history()

    except Exception as e:

        st.error(
            f"Unable to load ACD data: {e}"
        )

        st.stop()

    if not acd_df.empty:

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
            acd_df[
                "Parsed Call Time"
            ]
            .dt.date
        )

        acd_df["Call Time Only"] = (
            acd_df[
                "Parsed Call Time"
            ]
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

        min_date = (
            valid_dates.min()
            if not valid_dates.empty
            else date.today()
        )

        max_date = (
            valid_dates.max()
            if not valid_dates.empty
            else date.today()
        )

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

            selected_dispositions = (
                st.multiselect(
                    "🏷️ User Disposition Code",
                    disposition_values,
                    default=(
                        disposition_values
                    ),
                    key="acd_disposition_filter"
                )
            )

        if (
            isinstance(
                selected_dates,
                tuple
            )
            and len(selected_dates) == 2
        ):

            filter_start_date = (
                selected_dates[0]
            )

            filter_end_date = (
                selected_dates[1]
            )

        else:

            filter_start_date = (
                selected_dates[0]
                if isinstance(
                    selected_dates,
                    tuple
                )
                else selected_dates
            )

            filter_end_date = (
                filter_start_date
            )

        filtered_acd = (
            acd_df.copy()
        )

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

            filtered_acd = (
                filtered_acd[
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
            )

        else:

            filtered_acd = (
                filtered_acd[
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
            )

        if selected_queues:

            filtered_acd = (
                filtered_acd[
                    filtered_acd[
                        "Queue Name"
                    ]
                    .apply(
                        filter_display_value
                    )
                    .isin(
                        selected_queues
                    )
                ]
            )

        if selected_dispositions:

            filtered_acd = (
                filtered_acd[
                    filtered_acd[
                        "User Disposition Code"
                    ]
                    .apply(
                        filter_display_value
                    )
                    .isin(
                        selected_dispositions
                    )
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

        avg_aht = (
            filtered_acd[
                "AHT Seconds"
            ].mean()
            if not filtered_acd.empty
            else 0
        )

        avg_asa = (
            filtered_acd[
                "ASA Seconds"
            ].mean()
            if not filtered_acd.empty
            else 0
        )

        avg_acw = (
            filtered_acd[
                "ACW Seconds"
            ].mean()
            if not filtered_acd.empty
            else 0
        )

        st.caption(
            f"Showing **{total_calls:,} calls** "
            f"from **{filter_start_date.strftime('%d-%m-%Y')}** "
            f"to **{filter_end_date.strftime('%d-%m-%Y')}**."
        )

        k1, k2, k3, k4 = st.columns(4)

        with k1:

            st.metric(
                "📞 Calls",
                f"{total_calls:,}"
            )

        with k2:

            st.metric(
                "⏱️ Average AHT",
                seconds_to_hhmmss(
                    avg_aht
                ),
                help=(
                    "AHT = User Talk Time + "
                    "User Hold Duration + ACW Duration."
                )
            )

        with k3:

            st.metric(
                "⚡ Average ASA",
                seconds_to_hhmmss(
                    avg_asa
                ),
                help=(
                    "ASA = Average Total Wait Time."
                )
            )

        with k4:

            st.metric(
                "📝 Average ACW",
                seconds_to_hhmmss(
                    avg_acw
                ),
                help=(
                    "ACW = Average ACW Duration."
                )
            )

        if filtered_acd.empty:

            st.warning(
                "No ACD calls match the selected filters."
            )

        else:

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
                    Average_AHT_Seconds=(
                        "AHT Seconds",
                        "mean"
                    ),
                    Average_ASA_Seconds=(
                        "ASA Seconds",
                        "mean"
                    ),
                    Average_ACW_Seconds=(
                        "ACW Seconds",
                        "mean"
                    ),
                )
                .reset_index()
            )

            agent_summary[
                "Average AHT"
            ] = (
                agent_summary[
                    "Average_AHT_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            agent_summary[
                "Average ASA"
            ] = (
                agent_summary[
                    "Average_ASA_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            agent_summary[
                "Average ACW"
            ] = (
                agent_summary[
                    "Average_ACW_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            agent_summary = (
                agent_summary[
                    [
                        "Username",
                        "Calls",
                        "Average AHT",
                        "Average ASA",
                        "Average ACW",
                    ]
                ]
                .rename(
                    columns={
                        "Username": "Agent"
                    }
                )
                .sort_values(
                    "Calls",
                    ascending=False
                )
            )

            st.dataframe(
                agent_summary,
                use_container_width=True,
                hide_index=True
            )

            # ====================================================
            # DAILY
            # ====================================================

            st.markdown("---")

            st.subheader(
                "📅 Daily Performance"
            )

            daily = (
                filtered_acd
                .groupby(
                    "Call Date"
                )
                .agg(
                    Calls=(
                        "Call ID",
                        "nunique"
                    ),
                    Average_AHT_Seconds=(
                        "AHT Seconds",
                        "mean"
                    ),
                    Average_ASA_Seconds=(
                        "ASA Seconds",
                        "mean"
                    ),
                    Average_ACW_Seconds=(
                        "ACW Seconds",
                        "mean"
                    ),
                )
                .reset_index()
            )

            daily["Average AHT"] = (
                daily[
                    "Average_AHT_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            daily["Average ASA"] = (
                daily[
                    "Average_ASA_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            daily["Average ACW"] = (
                daily[
                    "Average_ACW_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            daily = daily[
                [
                    "Call Date",
                    "Calls",
                    "Average AHT",
                    "Average ASA",
                    "Average ACW",
                ]
            ]

            daily[
                "Call Date"
            ] = (
                pd.to_datetime(
                    daily[
                        "Call Date"
                    ]
                )
                .dt.strftime(
                    "%d-%m-%Y"
                )
            )

            st.dataframe(
                daily,
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

            hourly = (
                hourly
                .groupby(
                    "Hour"
                )
                .agg(
                    Calls=(
                        "Call ID",
                        "nunique"
                    ),
                    Average_AHT_Seconds=(
                        "AHT Seconds",
                        "mean"
                    ),
                    Average_ASA_Seconds=(
                        "ASA Seconds",
                        "mean"
                    ),
                    Average_ACW_Seconds=(
                        "ACW Seconds",
                        "mean"
                    ),
                )
                .reset_index()
            )

            hourly["Time"] = (
                hourly[
                    "Hour"
                ]
                .apply(
                    lambda x:
                    f"{int(x):02d}:00"
                )
            )

            hourly["Average AHT"] = (
                hourly[
                    "Average_AHT_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            hourly["Average ASA"] = (
                hourly[
                    "Average_ASA_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            hourly["Average ACW"] = (
                hourly[
                    "Average_ACW_Seconds"
                ]
                .apply(
                    seconds_to_hhmmss
                )
            )

            hourly = hourly[
                [
                    "Time",
                    "Calls",
                    "Average AHT",
                    "Average ASA",
                    "Average ACW",
                ]
            ]

            st.dataframe(
                hourly,
                use_container_width=True,
                hide_index=True
            )

            # ====================================================
            # DETAILS
            # ====================================================

            st.markdown("---")

            st.subheader(
                "📋 Detailed Call Records"
            )

            detail = (
                filtered_acd.copy()
            )

            detail["Call Date"] = (
                pd.to_datetime(
                    detail[
                        "Call Date"
                    ],
                    errors="coerce"
                )
                .dt.strftime(
                    "%d-%m-%Y"
                )
            )

            detail["Call Time Only"] = (
                detail[
                    "Call Time Only"
                ]
                .apply(
                    lambda x:
                    x.strftime("%H:%M:%S")
                    if pd.notna(x)
                    and hasattr(
                        x,
                        "strftime"
                    )
                    else ""
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
                column
                for column in detail_columns
                if column in detail.columns
            ]

            detail = (
                detail[
                    detail_columns
                ]
                .rename(
                    columns={
                        "Username": "Agent"
                    }
                )
            )

            st.dataframe(
                detail,
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

            export_acd = (
                filtered_acd.copy()
            )

            export_acd["Call Date"] = (
                pd.to_datetime(
                    export_acd[
                        "Call Date"
                    ],
                    errors="coerce"
                )
                .dt.strftime(
                    "%d-%m-%Y"
                )
            )

            export_acd["Call Time Only"] = (
                export_acd[
                    "Call Time Only"
                ]
                .apply(
                    lambda x:
                    x.strftime("%H:%M:%S")
                    if pd.notna(x)
                    and hasattr(
                        x,
                        "strftime"
                    )
                    else ""
                )
            )

            export_acd = export_acd.drop(
                columns=[
                    "Parsed Call Time",
                    "Talk Seconds",
                    "Hold Seconds",
                ],
                errors="ignore"
            )

            st.download_button(
                "📥 Download Filtered Calls CSV",
                export_acd
                .to_csv(index=False)
                .encode("utf-8"),
                file_name=(
                    "ACD_Filtered_"
                    f"{filter_start_date.strftime('%d-%m-%Y')}_"
                    "to_"
                    f"{filter_end_date.strftime('%d-%m-%Y')}.csv"
                ),
                mime="text/csv",
                key="acd_download"
            )

        st.markdown("---")

        st.caption(
            f"Historical ACD records: "
            f"{len(acd_df):,} | "
            f"Filtered records: "
            f"{len(filtered_acd):,}"
        )

    else:

        st.info(
            "No ACD data is available yet. "
            "Upload an ACD CSV report above."
        )


# ################################################################
# TAB 2 — AGENT PRODUCTIVITY
# ################################################################

with productivity_tab:

    st.header(
        "👥 Agent Productivity"
    )

    st.caption(
        "Average agent productivity by day, session, "
        "Ready/Active time, breaks and Auto Call-On."
    )

    # ============================================================
    # UPLOAD
    # ============================================================

    with st.expander(
        "📤 Upload Daily Agent Productivity CSV",
        expanded=True
    ):

        productivity_file = st.file_uploader(
            "Upload the Agent Productivity CSV",
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

                        source_df = pd.read_csv(
                            productivity_file,
                            dtype=str,
                            keep_default_na=False
                        )

                        source_df.columns = (
                            source_df.columns
                            .astype(str)
                            .str.strip()
                        )

                        missing_columns = [
                            column
                            for column in PRODUCTIVITY_COLUMNS
                            if column not in source_df.columns
                        ]

                        if missing_columns:

                            st.error(
                                "The productivity CSV is missing "
                                "required columns:"
                            )

                            st.write(
                                missing_columns
                            )

                        else:

                            processed_productivity = (
                                process_productivity_upload(
                                    source_df[
                                        PRODUCTIVITY_COLUMNS
                                    ]
                                )
                            )

                            worksheet = (
                                get_productivity_worksheet()
                            )

                            existing_records = (
                                worksheet.get_all_records()
                            )

                            existing_keys = set()

                            for existing_row in (
                                existing_records
                            ):

                                existing_keys.add(
                                    productivity_row_key(
                                        existing_row
                                    )
                                )

                            new_rows = []

                            for _, row in (
                                processed_productivity
                                .iterrows()
                            ):

                                row_dict = (
                                    row.to_dict()
                                )

                                row_key = (
                                    productivity_row_key(
                                        row_dict
                                    )
                                )

                                if row_key not in existing_keys:

                                    new_rows.append(
                                        row.tolist()
                                    )

                                    existing_keys.add(
                                        row_key
                                    )

                            if new_rows:

                                worksheet.append_rows(
                                    [
                                        [
                                            ""
                                            if pd.isna(value)
                                            else str(value)
                                            for value in row
                                        ]
                                        for row in new_rows
                                    ],
                                    value_input_option=(
                                        "USER_ENTERED"
                                    )
                                )

                                skipped = (
                                    len(
                                        processed_productivity
                                    )
                                    - len(new_rows)
                                )

                                st.success(
                                    "Productivity upload complete — "
                                    f"**{len(new_rows):,} new records** added."
                                )

                                if skipped:

                                    st.info(
                                        f"{skipped:,} "
                                        "duplicate/existing records "
                                        "were skipped."
                                    )

                                load_productivity_history.clear()

                            else:

                                st.info(
                                    "No new productivity records "
                                    "were added."
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
            f"Unable to load productivity data: {e}"
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

        valid_prod_dates = (
            productivity_df[
                "Productivity Date"
            ]
            .dropna()
        )

        prod_min_date = (
            valid_prod_dates.min()
            if not valid_prod_dates.empty
            else date.today()
        )

        prod_max_date = (
            valid_prod_dates.max()
            if not valid_prod_dates.empty
            else date.today()
        )

        with p1:

            productivity_dates = st.date_input(
                "📅 Date",
                value=(
                    prod_min_date,
                    prod_max_date
                ),
                min_value=prod_min_date,
                max_value=prod_max_date,
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

            selected_break_reasons = (
                st.multiselect(
                    "☕ Break Reason",
                    break_reasons,
                    default=break_reasons,
                    key="productivity_break_filter"
                )
            )

        if (
            isinstance(
                productivity_dates,
                tuple
            )
            and len(productivity_dates) == 2
        ):

            prod_start_date = (
                productivity_dates[0]
            )

            prod_end_date = (
                productivity_dates[1]
            )

        else:

            prod_start_date = (
                productivity_dates[0]
                if isinstance(
                    productivity_dates,
                    tuple
                )
                else productivity_dates
            )

            prod_end_date = prod_start_date

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
                    >= prod_start_date
                )
                &
                (
                    filtered_productivity[
                        "Productivity Date"
                    ]
                    <= prod_end_date
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

            filtered_productivity = (
                filtered_productivity[
                    filtered_productivity[
                        "Campaign Name"
                    ]
                    .apply(
                        filter_display_value
                    )
                    .isin(
                        selected_campaigns
                    )
                ]
            )

        # ========================================================
        # NOTE:
        #
        # Break Reason is intentionally NOT used to remove
        # entire agent/session rows from the main productivity
        # calculations.
        #
        # Otherwise selecting a break reason would incorrectly
        # destroy the agent's full-day login/ready calculation.
        #
        # It is applied only to the Break Analysis section.
        # ========================================================

        # ========================================================
        # AGENT-DAY CALCULATION
        # ========================================================

        agent_day = (
            build_agent_day_summary(
                filtered_productivity
            )
        )

        # ========================================================
        # PRODUCTIVITY KPI VALUES
        #
        # ALL ARE AVERAGES PER AGENT-DAY
        # ========================================================

        if agent_day.empty:

            st.warning(
                "No productivity records match "
                "the selected filters."
            )

        else:

            average_login = (
                agent_day[
                    "Login_Seconds"
                ].mean()
            )

            average_ready = (
                agent_day[
                    "Ready_Seconds"
                ].mean()
            )

            average_break = (
                agent_day[
                    "Break_Seconds"
                ].mean()
            )

            average_call_on = (
                agent_day[
                    "Call_On_Seconds"
                ].mean()
            )

            average_call_off = (
                agent_day[
                    "Call_Off_Seconds"
                ].mean()
            )

            average_unaccounted = (
                agent_day[
                    "Unaccounted_Seconds"
                ].mean()
            )

            average_ready_pct = (
                agent_day[
                    "Ready %"
                ].mean()
            )

            average_break_pct = (
                agent_day[
                    "Break %"
                ].mean()
            )

            average_call_on_ready_pct = (
                agent_day[
                    "Call-On % of Ready"
                ].mean()
            )

            average_call_on_login_pct = (
                agent_day[
                    "Call-On % of Login"
                ].mean()
            )

            # ====================================================
            # SUMMARY LABEL
            # ====================================================

            st.caption(
                f"Showing averages for "
                f"**{agent_day['Agent'].nunique():,} agents** "
                f"across "
                f"**{agent_day['Date'].nunique():,} agent-days** "
                f"from **{prod_start_date.strftime('%d-%m-%Y')}** "
                f"to **{prod_end_date.strftime('%d-%m-%Y')}**."
            )

            # ====================================================
            # KPI ROW 1
            # ====================================================

            pk1, pk2, pk3, pk4 = (
                st.columns(4)
            )

            with pk1:

                st.metric(
                    "🔐 Avg Login",
                    seconds_to_hhmmss(
                        average_login
                    ),
                    help=(
                        "Average Login Duration "
                        "per agent-day.\n\n"
                        "Calculated from Login Time → "
                        "Logout Time."
                    )
                )

            with pk2:

                st.metric(
                    "🟢 Avg Active / Ready",
                    seconds_to_hhmmss(
                        average_ready
                    ),
                    help=(
                        "Average Active/Ready Duration "
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
                        "Average Auto Call-On Duration "
                        "per agent-day."
                    )
                )

            with pk4:

                st.metric(
                    "☕ Avg Break",
                    seconds_to_hhmmss(
                        average_break
                    ),
                    help=(
                        "Average recorded Break Duration "
                        "per agent-day."
                    )
                )

            # ====================================================
            # KPI ROW 2
            # ====================================================

            pk5, pk6, pk7, pk8 = (
                st.columns(4)
            )

            with pk5:

                st.metric(
                    "📊 Avg Ready %",
                    f"{average_ready_pct:.1f}%",
                    help=(
                        "Average Ready utilisation per "
                        "agent-day.\n\n"
                        "Ready % = Ready Time ÷ Login Time."
                    )
                )

            with pk6:

                st.metric(
                    "📞 Avg Call-On / Ready",
                    f"{average_call_on_ready_pct:.1f}%",
                    help=(
                        "Average percentage of Ready time "
                        "spent in Auto Call-On."
                    )
                )

            with pk7:

                st.metric(
                    "📞 Avg Call-On / Login",
                    f"{average_call_on_login_pct:.1f}%",
                    help=(
                        "Average Auto Call-On time as a "
                        "percentage of Login Duration."
                    )
                )

            with pk8:

                st.metric(
                    "❓ Avg Unaccounted",
                    seconds_to_hhmmss(
                        average_unaccounted
                    ),
                    help=(
                        "Average Login time not accounted "
                        "for by Ready/Active or recorded Break.\n\n"
                        "Formula:\n"
                        "Login − Ready − Break."
                    )
                )

            # ====================================================
            # AVERAGE AGENT TABLE
            # ====================================================

            st.markdown("---")

            st.subheader(
                "👤 Average Agent Productivity"
            )

            st.caption(
                "Time values are averages per agent-day "
                "over the selected period."
            )

            average_agent_table = (
                build_average_agent_table(
                    agent_day
                )
            )

            st.dataframe(
                average_agent_table,
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
                "Each day shows the average time "
                "per agent working that day."
            )

            daily_average_table = (
                build_daily_average_table(
                    agent_day
                )
            )

            st.dataframe(
                daily_average_table,
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

            st.caption(
                "Break values below are average break "
                "duration, not total accumulated break time."
            )

            break_filtered = (
                filtered_productivity.copy()
            )

            if selected_break_reasons:

                break_filtered = (
                    break_filtered[
                        break_filtered[
                            "Break Reason"
                        ]
                        .apply(
                            filter_display_value
                        )
                        .isin(
                            selected_break_reasons
                        )
                    ]
                )

            break_summary = (
                build_break_summary(
                    break_filtered
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
            # AGENT BREAK ANALYSIS
            # ====================================================

            with st.expander(
                "👤 Average Break Time by Agent",
                expanded=False
            ):

                agent_break_summary = (
                    build_agent_break_summary(
                        break_filtered
                    )
                )

                if agent_break_summary.empty:

                    st.info(
                        "No break records available."
                    )

                else:

                    st.dataframe(
                        agent_break_summary,
                        use_container_width=True,
                        hide_index=True
                    )

            # ====================================================
            # SESSION SUMMARY
            #
            # A session is already one session, so its duration
            # is shown as a duration rather than summing sessions
            # together.
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
                    "No sessions available."
                )

            else:

                session_display = (
                    session_summary.copy()
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

            timeline_agents = sorted(
                filtered_productivity[
                    "Username"
                ]
                .dropna()
                .unique()
                .tolist()
            )

            if timeline_agents:

                timeline_agent = st.selectbox(
                    "Select an agent",
                    timeline_agents,
                    key="timeline_agent"
                )

                timeline = (
                    build_agent_timeline(
                        filtered_productivity,
                        timeline_agent
                    )
                )

                if timeline.empty:

                    st.info(
                        "No timeline events available."
                    )

                else:

                    st.dataframe(
                        timeline,
                        use_container_width=True,
                        hide_index=True,
                        height=500
                    )

            # ====================================================
            # PRODUCTIVITY RAW DATA
            # ====================================================

            st.markdown("---")

            with st.expander(
                "📄 View Uploaded Productivity Records",
                expanded=False
            ):

                raw_display = (
                    filtered_productivity.copy()
                )

                parsed_columns = [
                    column
                    for column in raw_display.columns
                    if column.startswith(
                        "Parsed "
                    )
                ]

                for column in parsed_columns:

                    raw_display[
                        column
                    ] = (
                        raw_display[
                            column
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

                raw_display = (
                    raw_display.drop(
                        columns=[
                            "Productivity Date",
                            "Login Seconds",
                            "Ready Seconds",
                            "Break Seconds",
                            "Call On Seconds",
                            "Call Off Seconds",
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
            # EXPORT AVERAGE PRODUCTIVITY
            # ====================================================

            st.markdown("---")

            st.subheader(
                "⬇️ Productivity Export"
            )

            export_productivity = (
                build_average_agent_table(
                    agent_day
                )
            )

            productivity_csv = (
                export_productivity
                .to_csv(
                    index=False
                )
                .encode(
                    "utf-8"
                )
            )

            st.download_button(
                "📥 Download Average Productivity CSV",
                productivity_csv,
                file_name=(
                    "Agent_Productivity_Average_"
                    f"{prod_start_date.strftime('%d-%m-%Y')}_"
                    "to_"
                    f"{prod_end_date.strftime('%d-%m-%Y')}.csv"
                ),
                mime="text/csv",
                key="productivity_download"
            )

            # ====================================================
            # PRODUCTIVITY FOOTER
            # ====================================================

            st.markdown("---")

            st.caption(
                f"Historical productivity records: "
                f"{len(productivity_df):,} | "
                f"Filtered source records: "
                f"{len(filtered_productivity):,} | "
                f"Agent-days: "
                f"{len(agent_day):,}"
            )
