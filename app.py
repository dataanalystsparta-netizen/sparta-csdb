
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
# CONFIGURATION
# ============================================================

SPREADSHEET_ID = "1R7ioNIYj7iAK3kN21WWlrxy9J9qEdRM9GOebCnUQNpI"

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


PRODUCTIVITY_GOOGLE_COLUMNS = PRODUCTIVITY_COLUMNS + [
    "Upload Date"
]


# ============================================================
# TITLE
# ============================================================

st.title("📞 ACD Time & Agent Performance")

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

    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )

    return gspread.authorize(credentials)


# ============================================================
# GET ACD WORKSHEET
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
# GET PRODUCTIVITY WORKSHEET
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
            cols=len(PRODUCTIVITY_GOOGLE_COLUMNS)
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

        else:

            return int(float(value))

    except Exception:

        return 0


def seconds_to_hhmmss(seconds):

    if pd.isna(seconds):
        return "00:00:00"

    seconds = int(
        round(
            float(seconds)
        )
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

    return seconds_to_hhmmss(value)


def filter_display_value(value):

    if pd.isna(value):
        return "(Blank)"

    value = str(value).strip()

    if value == "":
        return "(Blank)"

    return value


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

    df = df.copy()

    df = clean_text_columns(
        df
    )

    # --------------------------------------------------------
    # Call ID
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Agent
    # --------------------------------------------------------

    df = normalise_agent_names(
        df
    )

    # --------------------------------------------------------
    # Call time
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Duration calculations
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # AHT
    # --------------------------------------------------------

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
# PRODUCTIVITY HELPERS
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

    # --------------------------------------------------------
    # Parse all relevant timestamps
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Agent name
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Daily date
    #
    # The session's LOGIN DATE defines the agent-day.
    # --------------------------------------------------------

    df["Productivity Date"] = (
        df["Parsed Login Time"]
        .dt.date
    )

    # --------------------------------------------------------
    # Login duration
    #
    # Use the report's Total Login Duration.
    # --------------------------------------------------------

    df["Login Seconds"] = (
        df["Total Login Duration"]
        .apply(duration_to_seconds)
    )

    # --------------------------------------------------------
    # Ready / Active duration
    # --------------------------------------------------------

    df["Ready Seconds"] = (
        df["Ready Duration"]
        .apply(duration_to_seconds)
    )

    # --------------------------------------------------------
    # Break duration
    # --------------------------------------------------------

    df["Break Seconds"] = (
        df["Break Duration"]
        .apply(duration_to_seconds)
    )

    # --------------------------------------------------------
    # Auto Call-On / Off
    # --------------------------------------------------------

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
# PROCESS PRODUCTIVITY CSV
# ============================================================

def process_productivity_upload(
    df
):

    df = df.copy()

    df = clean_text_columns(
        df
    )

    # --------------------------------------------------------
    # Make sure all columns exist
    # --------------------------------------------------------

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

    # Remove temporary parsed/calculation columns
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
# PRODUCTIVITY UNIQUE ROW KEY
#
# We use the available history IDs to protect the sheet
# against uploading the same daily CSV multiple times.
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

    # Best case: session + ready history + auto-call history
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

    # If one history ID is blank, fall back to the entire
    # source row so legitimate records aren't discarded.
    values = [
        str(
            row.get(
                column,
                ""
            )
        ).strip()
        for column in PRODUCTIVITY_COLUMNS
    ]

    return "ROW|" + "|".join(values)


# ============================================================
# LOAD PRODUCTIVITY HISTORY
# ============================================================

@st.cache_data(ttl=60)
def load_productivity_history():

    worksheet = get_productivity_worksheet()

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

    df = clean_text_columns(
        df
    )

    return df


# ============================================================
# BUILD PRODUCTIVITY DATASET
# ============================================================

def prepare_productivity_dataframe(
    df
):

    if df.empty:

        return df.copy()

    df = df.copy()

    df = normalise_productivity_data(
        df
    )

    return df


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

        # ----------------------------------------------------
        # Login / logout
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

            login_time = login_times.min()

        else:

            login_time = pd.NaT

        if not logout_times.empty:

            logout_time = logout_times.max()

        else:

            logout_time = pd.NaT

        # ----------------------------------------------------
        # Login duration
        # ----------------------------------------------------

        if (
            pd.notna(login_time)
            and pd.notna(logout_time)
        ):

            calculated_login_seconds = (
                logout_time
                - login_time
            ).total_seconds()

        else:

            calculated_login_seconds = (
                group[
                    "Total Login Duration"
                ]
                .apply(duration_to_seconds)
                .max()
            )

        # ----------------------------------------------------
        # Ready histories are unique events
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Break histories
        #
        # Break duration is attached to the ready history.
        # Therefore take one value per ready history.
        # ----------------------------------------------------

        break_rows = (
            group[
                [
                    "Ready History ID",
                    "Break Duration",
                    "Break Reason"
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
        # Auto call histories are also unique
        # ----------------------------------------------------

        call_rows = (
            group[
                [
                    "Auto Call On/Off History ID",
                    "Auto Call-On Duration",
                    "Auto Call-Off Duration"
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
        # Unaccounted
        #
        # Call-On / Call-Off are states within the agent's
        # ready period, therefore we DO NOT subtract them
        # again from login time.
        #
        # Login = Ready + Break + Unaccounted
        # ----------------------------------------------------

        unaccounted_seconds = max(
            calculated_login_seconds
            - ready_seconds
            - break_seconds,
            0
        )

        if pd.notna(login_time):

            productivity_date = (
                login_time.date()
            )

        else:

            productivity_date = None

        records.append(
            {
                "Date": productivity_date,
                "Agent": agent,
                "Session ID": session_id,
                "Login": login_time,
                "Logout": logout_time,
                "Login Seconds": calculated_login_seconds,
                "Ready Seconds": ready_seconds,
                "Break Seconds": break_seconds,
                "Call On Seconds": call_on_seconds,
                "Call Off Seconds": call_off_seconds,
                "Unaccounted Seconds": unaccounted_seconds,
                "Campaign Name": (
                    group[
                        "Campaign Name"
                    ]
                    .replace("", np.nan)
                    .dropna()
                    .iloc[0]
                    if not group[
                        "Campaign Name"
                    ].replace("", np.nan).dropna().empty
                    else ""
                ),
            }
        )

    result = pd.DataFrame(
        records
    )

    return result


# ============================================================
# AGENT-DAY SUMMARY
# ============================================================

def build_agent_day_summary(
    df
):

    session_df = build_session_summary(
        df
    )

    if session_df.empty:

        return pd.DataFrame()

    grouped = (
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
    # Percentages
    # --------------------------------------------------------

    grouped["Ready %"] = np.where(
        grouped["Login_Seconds"] > 0,
        (
            grouped["Ready_Seconds"]
            / grouped["Login_Seconds"]
            * 100
        ),
        0
    )

    grouped["Break %"] = np.where(
        grouped["Login_Seconds"] > 0,
        (
            grouped["Break_Seconds"]
            / grouped["Login_Seconds"]
            * 100
        ),
        0
    )

    grouped["Call-On % of Ready"] = np.where(
        grouped["Ready_Seconds"] > 0,
        (
            grouped["Call_On_Seconds"]
            / grouped["Ready_Seconds"]
            * 100
        ),
        0
    )

    grouped["Call-On % of Login"] = np.where(
        grouped["Login_Seconds"] > 0,
        (
            grouped["Call_On_Seconds"]
            / grouped["Login_Seconds"]
            * 100
        ),
        0
    )

    # --------------------------------------------------------
    # Display durations
    # --------------------------------------------------------

    grouped["Login"] = (
        grouped["Login_Seconds"]
        .apply(seconds_to_hhmmss)
    )

    grouped["Active / Ready"] = (
        grouped["Ready_Seconds"]
        .apply(seconds_to_hhmmss)
    )

    grouped["Break"] = (
        grouped["Break_Seconds"]
        .apply(seconds_to_hhmmss)
    )

    grouped["Call-On"] = (
        grouped["Call_On_Seconds"]
        .apply(seconds_to_hhmmss)
    )

    grouped["Call-Off"] = (
        grouped["Call_Off_Seconds"]
        .apply(seconds_to_hhmmss)
    )

    grouped["Unaccounted"] = (
        grouped["Unaccounted_Seconds"]
        .apply(seconds_to_hhmmss)
    )

    result = grouped[
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

    result["Date"] = pd.to_datetime(
        result["Date"],
        errors="coerce"
    )

    result = result.sort_values(
        [
            "Date",
            "Agent"
        ]
    )

    result["Date"] = (
        result["Date"]
        .dt.strftime(
            "%d-%m-%Y"
        )
    )

    return result


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
        break_df["Break Duration"]
        .apply(
            duration_to_seconds
        )
    )

    # One break value per Ready History ID
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
        break_df["Break Seconds"] > 0
    ].copy()

    if break_df.empty:

        return pd.DataFrame()

    break_df["Break Reason Display"] = (
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
                "Break Reason Display"
            ],
            dropna=False
        )
        .agg(
            Breaks=(
                "Ready History ID",
                "nunique"
            ),
            Total_Break_Seconds=(
                "Break Seconds",
                "sum"
            )
        )
        .reset_index()
    )

    summary["Total Break"] = (
        summary[
            "Total_Break_Seconds"
        ]
        .apply(
            seconds_to_hhmmss
        )
    )

    summary = summary.rename(
        columns={
            "Username": "Agent",
            "Break Reason Display": "Break Reason",
        }
    )

    return summary[
        [
            "Agent",
            "Break Reason",
            "Breaks",
            "Total Break",
        ]
    ].sort_values(
        [
            "Agent",
            "Total Break"
        ],
        ascending=[
            True,
            False
        ]
    )


# ============================================================
# BUILD TIMELINE
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

            login_time = login_times.min()

            timeline_rows.append(
                {
                    "Session ID": session_id,
                    "Start": login_time,
                    "End": login_time,
                    "Activity": "LOGIN",
                    "Reason": "",
                }
            )

        if not logout_times.empty:

            logout_time = logout_times.max()

            timeline_rows.append(
                {
                    "Session ID": session_id,
                    "Start": logout_time,
                    "End": logout_time,
                    "Activity": "LOGOUT",
                    "Reason": "",
                }
            )

    # --------------------------------------------------------
    # READY / ACTIVE
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

        if pd.notna(start) and pd.notna(end):

            if end >= start:

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
    # BREAKS
    #
    # Break starts at Ready End Time and ends at Break End Time.
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

        break_seconds = duration_to_seconds(
            row[
                "Break Duration"
            ]
        )

        if (
            pd.notna(start)
            and pd.notna(end)
            and break_seconds > 0
        ):

            reason = filter_display_value(
                row[
                    "Break Reason"
                ]
            )

            timeline_rows.append(
                {
                    "Session ID": row[
                        "Session ID"
                    ],
                    "Start": start,
                    "End": end,
                    "Activity": "BREAK",
                    "Reason": reason,
                }
            )

    # --------------------------------------------------------
    # AUTO CALL-ON / CALL-OFF
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

        # Call-On interval
        if (
            pd.notna(call_on_start)
            and pd.notna(call_on_end)
            and call_on_end >= call_on_start
        ):

            if (
                call_on_end
                > call_on_start
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

        # Call-Off interval
        if (
            pd.notna(call_on_end)
            and pd.notna(call_off_end)
            and call_off_end >= call_on_end
        ):

            if (
                call_off_end
                > call_on_end
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

    # --------------------------------------------------------
    # Duration
    # --------------------------------------------------------

    timeline["Duration Seconds"] = (
        timeline["End"]
        - timeline["Start"]
    ).dt.total_seconds()

    timeline["Duration Seconds"] = (
        timeline["Duration Seconds"]
        .fillna(0)
        .clip(lower=0)
    )

    timeline["Duration"] = (
        timeline["Duration Seconds"]
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
# ################################################################
#
# TAB 1 — ACD PERFORMANCE
#
# ################################################################
# ################################################################

with acd_tab:

    # ============================================================
    # ACD UPLOAD
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
                "call-detail CSV report."
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
                        "Validating and importing ACD report..."
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

                            new_df = processed_df[
                                ~processed_df[
                                    "Call ID"
                                ].isin(
                                    existing_call_ids
                                )
                            ].copy()

                            duplicate_count = (
                                len(processed_df)
                                - len(new_df)
                            )

                            if not new_df.empty:

                                rows_to_append = (
                                    new_df
                                    .fillna("")
                                    .astype(str)
                                    .values
                                    .tolist()
                                )

                                worksheet.append_rows(
                                    rows_to_append,
                                    value_input_option=(
                                        "USER_ENTERED"
                                    )
                                )

                                st.success(
                                    f"ACD upload complete — "
                                    f"**{len(new_df):,} new calls** "
                                    f"added."
                                )

                                if duplicate_count > 0:

                                    st.info(
                                        f"**{duplicate_count:,} "
                                        f"existing/duplicate Call IDs** "
                                        f"were skipped."
                                    )

                                load_acd_history.clear()

                            else:

                                st.info(
                                    "No new ACD calls were added. "
                                    "All uploaded Call IDs already exist."
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
        # ACD TOP FILTERS
        # ========================================================

        st.subheader(
            "🔎 Dashboard Filters"
        )

        f1, f2, f3, f4 = st.columns(4)

        valid_dates = (
            acd_df["Call Date"]
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
                key="acd_date_filter",
                help=(
                    "Filter ALL ACD dashboard values "
                    "by Call Date."
                )
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
                key="acd_time_filter",
                help=(
                    "Filter ALL ACD dashboard values "
                    "by Call Time."
                )
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
                options=queue_values,
                default=queue_values,
                key="acd_queue_filter",
                help=(
                    "'(Blank)' represents calls where "
                    "Queue Name is blank."
                )
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
                options=disposition_values,
                default=disposition_values,
                key="acd_disposition_filter",
                help=(
                    "'(Blank)' represents calls where "
                    "User Disposition Code is blank."
                )
            )

        # ========================================================
        # DATE RANGE
        # ========================================================

        if isinstance(
            selected_dates,
            tuple
        ):

            if len(selected_dates) == 2:

                filter_start_date = (
                    selected_dates[0]
                )

                filter_end_date = (
                    selected_dates[1]
                )

            elif len(selected_dates) == 1:

                filter_start_date = (
                    selected_dates[0]
                )

                filter_end_date = (
                    selected_dates[0]
                )

            else:

                filter_start_date = min_date
                filter_end_date = max_date

        else:

            filter_start_date = selected_dates
            filter_end_date = selected_dates

        # ========================================================
        # APPLY ACD FILTERS
        # ========================================================

        filtered_acd = acd_df.copy()

        filtered_acd = filtered_acd[
            filtered_acd["Call Date"].notna()
        ]

        filtered_acd = filtered_acd[
            (
                filtered_acd["Call Date"]
                >= filter_start_date
            )
            &
            (
                filtered_acd["Call Date"]
                <= filter_end_date
            )
        ]

        start_time = selected_time_range[0]
        end_time = selected_time_range[1]

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

            filtered_acd = filtered_acd[
                queue_mask
            ]

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

            filtered_acd = filtered_acd[
                disposition_mask
            ]

        # ========================================================
        # ACD SUMMARY
        # ========================================================

        st.caption(
            f"Showing **{filtered_acd['Call ID'].nunique():,} calls** "
            f"from **{filter_start_date.strftime('%d-%m-%Y')}** "
            f"to **{filter_end_date.strftime('%d-%m-%Y')}**, "
            f"between **{start_time.strftime('%H:%M')}** "
            f"and **{end_time.strftime('%H:%M')}**."
        )

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

        # ========================================================
        # KPI CARDS
        # ========================================================

        k1, k2, k3, k4 = st.columns(4)

        with k1:

            st.metric(
                "📞 Calls",
                f"{total_calls:,}",
                help=(
                    "Total number of unique calls "
                    "in the selected filters.\n\n"
                    "Calls with no assigned agent are "
                    "included as 'Call Dropped'."
                )
            )

        with k2:

            st.metric(
                "⏱️ Average AHT",
                format_average_seconds(
                    avg_aht
                ),
                help=(
                    "Average Handling Time (AHT)\n\n"
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
                    "Average Speed of Answer (ASA)\n\n"
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
                    "Average After Call Work (ACW)\n\n"
                    "Average of ACW Duration."
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

            daily_summary[
                "Call Date"
            ] = (
                pd.to_datetime(
                    daily_summary[
                        "Call Date"
                    ]
                )
                .dt.strftime(
                    "%d-%m-%Y"
                )
            )

            st.dataframe(
                daily_summary,
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

            hourly_df = filtered_acd.copy()

            hourly_df["Hour"] = (
                hourly_df[
                    "Parsed Call Time"
                ]
                .dt.hour
            )

            hourly_summary = (
                hourly_df
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

            # ====================================================
            # DETAILED CALL RECORDS
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

            display_df[
                "Call Time Only"
            ] = (
                display_df[
                    "Call Time Only"
                ]
                .apply(
                    lambda x:
                    x.strftime(
                        "%H:%M:%S"
                    )
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
                if column in display_df.columns
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
            # ACD EXPORT
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

            download_df[
                "Call Time Only"
            ] = (
                download_df[
                    "Call Time Only"
                ]
                .apply(
                    lambda x:
                    x.strftime(
                        "%H:%M:%S"
                    )
                    if pd.notna(x)
                    and hasattr(
                        x,
                        "strftime"
                    )
                    else ""
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

            csv_data = (
                download_df
                .to_csv(
                    index=False
                )
                .encode(
                    "utf-8"
                )
            )

            st.download_button(
                label=(
                    "📥 Download Filtered "
                    "Calls CSV"
                ),
                data=csv_data,
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


# ################################################################
# ################################################################
#
# TAB 2 — AGENT PRODUCTIVITY
#
# ################################################################
# ################################################################

with productivity_tab:

    st.header(
        "👥 Agent Productivity"
    )

    st.caption(
        "Daily agent login, Active/Ready, breaks, Call-On, "
        "Call-Off and full-day reconciliation."
    )

    # ============================================================
    # PRODUCTIVITY UPLOAD
    # ============================================================

    with st.expander(
        "📤 Upload Daily Agent Productivity CSV",
        expanded=True
    ):

        productivity_file = st.file_uploader(
            "Upload the Agent Productivity CSV",
            type=["csv"],
            key="productivity_upload",
            help=(
                "Upload the daily agent session/history "
                "CSV export."
            )
        )

        if productivity_file is not None:

            if st.button(
                "⬆️ Import Productivity Report",
                type="primary",
                key="import_productivity"
            ):

                try:

                    with st.spinner(
                        "Validating and importing productivity report..."
                    ):

                        productivity_upload_df = (
                            pd.read_csv(
                                productivity_file,
                                dtype=str,
                                keep_default_na=False
                            )
                        )

                        productivity_upload_df.columns = (
                            productivity_upload_df.columns
                            .astype(str)
                            .str.strip()
                        )

                        missing_columns = [
                            column
                            for column in PRODUCTIVITY_COLUMNS
                            if column not in productivity_upload_df.columns
                        ]

                        if missing_columns:

                            st.error(
                                "The productivity CSV is missing "
                                "required columns:"
                            )

                            for column in missing_columns:

                                st.write(
                                    f"- {column}"
                                )

                        else:

                            productivity_upload_df = (
                                productivity_upload_df[
                                    PRODUCTIVITY_COLUMNS
                                ]
                                .copy()
                            )

                            processed_productivity = (
                                process_productivity_upload(
                                    productivity_upload_df
                                )
                            )

                            worksheet = (
                                get_productivity_worksheet()
                            )

                            # ------------------------------------------------
                            # Read existing rows
                            # ------------------------------------------------

                            existing_records = (
                                worksheet.get_all_records()
                            )

                            existing_keys = set()

                            if existing_records:

                                for existing_row in (
                                    existing_records
                                ):

                                    existing_keys.add(
                                        productivity_row_key(
                                            existing_row
                                        )
                                    )

                            # ------------------------------------------------
                            # Only append new rows
                            # ------------------------------------------------

                            new_rows = []

                            for _, row in (
                                processed_productivity
                                .iterrows()
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

                                st.success(
                                    "Productivity upload complete — "
                                    f"**{len(new_rows):,} new records** "
                                    "added."
                                )

                                duplicate_count = (
                                    len(processed_productivity)
                                    - len(new_rows)
                                )

                                if duplicate_count > 0:

                                    st.info(
                                        f"**{duplicate_count:,} "
                                        "existing/duplicate records** "
                                        "were skipped."
                                    )

                                load_productivity_history.clear()

                            else:

                                st.info(
                                    "No new productivity records "
                                    "were added. The uploaded report "
                                    "already exists in the historical data."
                                )

                except Exception as e:

                    st.error(
                        f"Error importing productivity report: {e}"
                    )

    # ============================================================
    # LOAD PRODUCTIVITY HISTORY
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

        # ========================================================
        # PREPARE PRODUCTIVITY DATA
        # ========================================================

        productivity_df = (
            prepare_productivity_dataframe(
                productivity_df
            )
        )

        # ========================================================
        # PRODUCTIVITY FILTERS
        # ========================================================

        st.markdown("---")

        st.subheader(
            "🔎 Productivity Filters"
        )

        p1, p2, p3, p4 = st.columns(4)

        valid_productivity_dates = (
            productivity_df[
                "Productivity Date"
            ]
            .dropna()
        )

        if not valid_productivity_dates.empty:

            productivity_min_date = (
                valid_productivity_dates.min()
            )

            productivity_max_date = (
                valid_productivity_dates.max()
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
                key="productivity_date_filter",
                help=(
                    "Filter the complete productivity "
                    "dashboard by agent login date."
                )
            )

        productivity_agents = sorted(
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

            selected_productivity_agents = (
                st.multiselect(
                    "👤 Agent",
                    options=productivity_agents,
                    default=productivity_agents,
                    key="productivity_agent_filter",
                    help=(
                        "Select the agents to include "
                        "in the productivity dashboard."
                    )
                )
            )

        productivity_campaigns = sorted(
            {
                filter_display_value(x)
                for x in productivity_df[
                    "Campaign Name"
                ]
            }
        )

        with p3:

            selected_productivity_campaigns = (
                st.multiselect(
                    "📣 Campaign",
                    options=productivity_campaigns,
                    default=productivity_campaigns,
                    key="productivity_campaign_filter",
                    help=(
                        "Filter productivity results "
                        "by Campaign Name."
                    )
                )
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
                options=break_reasons,
                default=break_reasons,
                key="productivity_break_filter",
                help=(
                    "Filter records by Break Reason. "
                    "'(Blank)' includes records without "
                    "a break reason."
                )
            )

        # ========================================================
        # PRODUCTIVITY DATE RANGE
        # ========================================================

        if isinstance(
            productivity_dates,
            tuple
        ):

            if len(productivity_dates) == 2:

                productivity_start_date = (
                    productivity_dates[0]
                )

                productivity_end_date = (
                    productivity_dates[1]
                )

            elif len(productivity_dates) == 1:

                productivity_start_date = (
                    productivity_dates[0]
                )

                productivity_end_date = (
                    productivity_dates[0]
                )

            else:

                productivity_start_date = (
                    productivity_min_date
                )

                productivity_end_date = (
                    productivity_max_date
                )

        else:

            productivity_start_date = productivity_dates
            productivity_end_date = productivity_dates

        # ========================================================
        # APPLY PRODUCTIVITY FILTERS
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

        if selected_productivity_agents:

            filtered_productivity = (
                filtered_productivity[
                    filtered_productivity[
                        "Username"
                    ].isin(
                        selected_productivity_agents
                    )
                ]
            )

        if selected_productivity_campaigns:

            campaign_mask = (
                filtered_productivity[
                    "Campaign Name"
                ]
                .apply(
                    filter_display_value
                )
                .isin(
                    selected_productivity_campaigns
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
        # FILTER SUMMARY
        # ========================================================

        st.caption(
            f"Showing productivity data from "
            f"**{productivity_start_date.strftime('%d-%m-%Y')}** "
            f"to "
            f"**{productivity_end_date.strftime('%d-%m-%Y')}**."
        )

        # ========================================================
        # BUILD AGENT-DAY SUMMARY
        # ========================================================

        agent_day_summary = (
            build_agent_day_summary(
                filtered_productivity
            )
        )

        # ========================================================
        # PRODUCTIVITY KPIs
        # ========================================================

        if agent_day_summary.empty:

            st.warning(
                "No productivity records match "
                "the selected filters."
            )

        else:

            # ====================================================
            # NUMERIC SUMMARY
            # ====================================================

            # Build numerical values separately because the
            # display summary intentionally contains HH:MM:SS.

            session_summary = (
                build_session_summary(
                    filtered_productivity
                )
            )

            if not session_summary.empty:

                total_login_seconds = (
                    session_summary[
                        "Login Seconds"
                    ].sum()
                )

                total_ready_seconds = (
                    session_summary[
                        "Ready Seconds"
                    ].sum()
                )

                total_break_seconds = (
                    session_summary[
                        "Break Seconds"
                    ].sum()
                )

                total_call_on_seconds = (
                    session_summary[
                        "Call On Seconds"
                    ].sum()
                )

                total_unaccounted_seconds = (
                    session_summary[
                        "Unaccounted Seconds"
                    ].sum()
                )

            else:

                total_login_seconds = 0
                total_ready_seconds = 0
                total_break_seconds = 0
                total_call_on_seconds = 0
                total_unaccounted_seconds = 0

            overall_ready_pct = (
                (
                    total_ready_seconds
                    / total_login_seconds
                    * 100
                )
                if total_login_seconds > 0
                else 0
            )

            overall_break_pct = (
                (
                    total_break_seconds
                    / total_login_seconds
                    * 100
                )
                if total_login_seconds > 0
                else 0
            )

            overall_call_on_ready_pct = (
                (
                    total_call_on_seconds
                    / total_ready_seconds
                    * 100
                )
                if total_ready_seconds > 0
                else 0
            )

            overall_call_on_login_pct = (
                (
                    total_call_on_seconds
                    / total_login_seconds
                    * 100
                )
                if total_login_seconds > 0
                else 0
            )

            # ====================================================
            # KPI CARDS
            # ====================================================

            pk1, pk2, pk3, pk4 = (
                st.columns(4)
            )

            with pk1:

                st.metric(
                    "🔐 Total Login",
                    seconds_to_hhmmss(
                        total_login_seconds
                    ),
                    help=(
                        "Total time agents were logged in "
                        "during the selected period.\n\n"
                        "Based on Login Time → Logout Time "
                        "for each agent session."
                    )
                )

            with pk2:

                st.metric(
                    "🟢 Active / Ready",
                    seconds_to_hhmmss(
                        total_ready_seconds
                    ),
                    help=(
                        "Total Ready/Active time.\n\n"
                        "Calculated from the report's "
                        "Ready Duration values."
                    )
                )

            with pk3:

                st.metric(
                    "📞 Call-On",
                    seconds_to_hhmmss(
                        total_call_on_seconds
                    ),
                    help=(
                        "Total Auto Call-On time.\n\n"
                        "Calculated from Auto Call-On Duration."
                    )
                )

            with pk4:

                st.metric(
                    "☕ Break",
                    seconds_to_hhmmss(
                        total_break_seconds
                    ),
                    help=(
                        "Total recorded break time.\n\n"
                        "Calculated from Break Duration."
                    )
                )

            # ====================================================
            # SECOND KPI ROW
            # ====================================================

            pk5, pk6, pk7, pk8 = (
                st.columns(4)
            )

            with pk5:

                st.metric(
                    "📊 Ready %",
                    f"{overall_ready_pct:.1f}%",
                    help=(
                        "Ready utilisation against login time.\n\n"
                        "Ready % = Active / Ready Time "
                        "÷ Total Login Time."
                    )
                )

            with pk6:

                st.metric(
                    "📞 Call-On % of Ready",
                    f"{overall_call_on_ready_pct:.1f}%",
                    help=(
                        "Percentage of Ready time spent "
                        "in Auto Call-On.\n\n"
                        "Call-On % of Ready = Call-On Time "
                        "÷ Ready Time."
                    )
                )

            with pk7:

                st.metric(
                    "📞 Call-On % of Login",
                    f"{overall_call_on_login_pct:.1f}%",
                    help=(
                        "Call-On time as a percentage of "
                        "the complete logged-in period.\n\n"
                        "Call-On % of Login = Call-On Time "
                        "÷ Login Time."
                    )
                )

            with pk8:

                st.metric(
                    "❓ Unaccounted",
                    seconds_to_hhmmss(
                        total_unaccounted_seconds
                    ),
                    help=(
                        "Logged-in time that is not accounted "
                        "for by Ready/Active or recorded Break time.\n\n"
                        "Formula:\n"
                        "Login − Ready − Break.\n\n"
                        "Call-On/Call-Off are NOT subtracted "
                        "again because they occur within the "
                        "agent's Ready period."
                    )
                )

            # ====================================================
            # AGENT PRODUCTIVITY TABLE
            # ====================================================

            st.markdown("---")

            st.subheader(
                "👤 Agent Daily Productivity"
            )

            st.caption(
                "This table reconstructs each agent's day "
                "from their login/logout session and recorded "
                "Ready, Break and Auto Call histories."
            )

            display_agent_day = (
                agent_day_summary.copy()
            )

            display_agent_day[
                "Ready %"
            ] = (
                display_agent_day[
                    "Ready %"
                ]
                .map(
                    lambda x:
                    f"{x:.1f}%"
                )
            )

            display_agent_day[
                "Break %"
            ] = (
                display_agent_day[
                    "Break %"
                ]
                .map(
                    lambda x:
                    f"{x:.1f}%"
                )
            )

            display_agent_day[
                "Call-On % of Ready"
            ] = (
                display_agent_day[
                    "Call-On % of Ready"
                ]
                .map(
                    lambda x:
                    f"{x:.1f}%"
                )
            )

            display_agent_day[
                "Call-On % of Login"
            ] = (
                display_agent_day[
                    "Call-On % of Login"
                ]
                .map(
                    lambda x:
                    f"{x:.1f}%"
                )
            )

            st.dataframe(
                display_agent_day,
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
                    "No recorded breaks match the selected filters."
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
                "🔐 Session Summary"
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

                timeline_agent = st.selectbox(
                    "Select an agent",
                    options=available_agents,
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

                    st.caption(
                        "The timeline shows the actual event "
                        "sequence reconstructed from the "
                        "session, Ready, Break and Auto Call "
                        "history records."
                    )

            # ====================================================
            # RAW PRODUCTIVITY HISTORY
            # ====================================================

            st.markdown("---")

            with st.expander(
                "📄 View Uploaded Productivity Records",
                expanded=False
            ):

                raw_productivity_display = (
                    filtered_productivity.copy()
                )

                # Display source dates cleanly
                for column in [
                    "Parsed Login Time",
                    "Parsed Logout Time",
                    "Parsed Ready Start Time",
                    "Parsed Ready End Time",
                    "Parsed Break End Time",
                    "Parsed Auto Call-On Start Time",
                    "Parsed Auto Call-On End Time",
                    "Parsed Auto Call-Off End Time",
                ]:

                    if column in raw_productivity_display.columns:

                        raw_productivity_display[
                            column
                        ] = (
                            raw_productivity_display[
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

                raw_productivity_display = (
                    raw_productivity_display
                    .drop(
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
                    raw_productivity_display,
                    use_container_width=True,
                    hide_index=True,
                    height=500
                )

            # ====================================================
            # PRODUCTIVITY EXPORT
            # ====================================================

            st.markdown("---")

            st.subheader(
                "⬇️ Productivity Export"
            )

            export_productivity = (
                agent_day_summary.copy()
            )

            # Numeric percentages for export
            export_productivity[
                "Ready %"
            ] = (
                export_productivity[
                    "Ready %"
                ]
                .round(2)
            )

            export_productivity[
                "Break %"
            ] = (
                export_productivity[
                    "Break %"
                ]
                .round(2)
            )

            export_productivity[
                "Call-On % of Ready"
            ] = (
                export_productivity[
                    "Call-On % of Ready"
                ]
                .round(2)
            )

            export_productivity[
                "Call-On % of Login"
            ] = (
                export_productivity[
                    "Call-On % of Login"
                ]
                .round(2)
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
                label=(
                    "📥 Download Agent "
                    "Productivity CSV"
                ),
                data=productivity_csv,
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
            # PRODUCTIVITY FOOTER
            # ====================================================

            st.markdown("---")

            st.caption(
                f"Historical productivity records: "
                f"{len(productivity_df):,} | "
                f"Filtered source records: "
                f"{len(filtered_productivity):,}"
            )
