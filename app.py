import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image
import uuid

# ========================== CONFIG ==========================
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

USERS_FILE = "users.xlsx"
LOGO_FILE = "meesho.png"

TRACKING_FILE = f"{DATA_DIR}/tracking_master.csv"
RCA_FILE = f"{DATA_DIR}/rca_data.csv"
DELETED_FILE = f"{DATA_DIR}/deleted_rca.csv"
LOGIN_AUDIT = f"{DATA_DIR}/login_audit.csv"

MAX_REMARKS_PER_AWB = 10
DATA_RETENTION_DAYS = 365

st.set_page_config(
    page_title="Meesho Tracking",
    layout="wide"
)

# ========================== INIT FILES ==========================
def init_file(path, columns):
    if not os.path.exists(path):
        pd.DataFrame(columns=columns).to_csv(path, index=False)

init_file(TRACKING_FILE, ["awb", "created_on"])
init_file(
    RCA_FILE,
    [
        "awb", "sc_name", "rca_type",
        "email_subject", "rca_remark",
        "updated_by", "updated_on"
    ],
)
init_file(
    DELETED_FILE,
    ["awb", "rca_remark", "deleted_by", "deleted_on"]
)
init_file(
    LOGIN_AUDIT,
    ["email", "role", "login_time"]
)

# ========================== LOAD USERS ==========================
users_df = pd.read_excel(USERS_FILE)
users_df.columns = users_df.columns.str.lower().str.strip()

# ========================== SESSION ==========================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ========================== LOGO ==========================
st.image(Image.open(meesho.png), width=150)

# ========================== LOGIN ==========================
if not st.session_state.logged_in:
    st.title("🔐 Meesho Courier Tracking – Secure Login")

    email = st.text_input("Email ID")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user = users_df[users_df["email"] == email]

        if not user.empty and password == user.iloc[0]["password"]:
            st.session_state.logged_in = True
            st.session_state.email = email
            st.session_state.name = user.iloc[0]["name"]
            st.session_state.role = user.iloc[0]["role"]

            audit_df = pd.read_csv(LOGIN_AUDIT)
            audit_df.loc[len(audit_df)] = [
                email,
                st.session_state.role,
                datetime.now(),
            ]
            audit_df.to_csv(LOGIN_AUDIT, index=False)

            st.rerun()
        else:
            st.error("❌ Invalid credentials")

    st.stop()

# ========================== SIDEBAR ==========================
st.sidebar.success(f"👤 {st.session_state.name}")
st.sidebar.info(f"Role: {st.session_state.role}")

MENU_ADMIN = [
    "Dashboard",
    "Tracking",
    "RCA Update",
    "Download",
    "Admin Panel",
]
MENU_USER = [
    "Dashboard",
    "Tracking",
    "RCA Update",
]

menu = st.sidebar.radio(
    "Navigation",
    MENU_ADMIN if st.session_state.role != "user" else MENU_USER,
)

# ========================== LOAD DATA ==========================
rca_df = pd.read_csv(RCA_FILE, parse_dates=["updated_on"])
deleted_df = pd.read_csv(DELETED_FILE, parse_dates=["deleted_on"])
login_df = pd.read_csv(LOGIN_AUDIT, parse_dates=["login_time"])

# ========================== DASHBOARD ==========================
if menu == "Dashboard":
    st.header("📊 Operations Dashboard")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total RCA Records", len(rca_df))
    col2.metric("Total Users", users_df.shape[0])
    col3.metric("Active Users", login_df["email"].nunique())
    col4.metric("Deleted RCA", len(deleted_df))

    st.divider()

    # SC-wise RCA
    if not rca_df.empty:
        sc_summary = (
            rca_df.groupby("sc_name")
            .agg(
                RCA_Count=("awb", "count"),
                Users_Active=("updated_by", "nunique"),
            )
            .reset_index()
        )

        st.subheader("🏢 SC-wise RCA Summary")
        st.dataframe(sc_summary, use_container_width=True)

    # Admin analytics
    if st.session_state.role in ["admin", "superadmin"]:
        st.subheader("👥 User Login Analytics")

        daily_users = (
            login_df.groupby(login_df["login_time"].dt.date)["email"]
            .nunique()
        )
        monthly_users = (
            login_df.groupby(login_df["login_time"].dt.to_period("M"))[
                "email"
            ]
            .nunique()
        )

        col1, col2 = st.columns(2)
        col1.line_chart(daily_users)
        col2.bar_chart(monthly_users)

        never_logged = users_df[
            ~users_df["email"].isin(login_df["email"])
        ]
        st.info(f"Users never logged in: {len(never_logged)}")

# ========================== TRACKING ==========================
if menu == "Tracking":
    st.header("📦 Track Shipment(s)")

    awbs = st.text_area(
        "Enter AWB(s) – single or multiple",
        help="One AWB per line",
    ).splitlines()

    if st.button("Track"):
        for awb in awbs:
            st.subheader(f"AWB: {awb}")
            data = rca_df[rca_df["awb"] == awb]

            if data.empty:
                st.warning("No RCA found. You can add remarks in RCA Update.")
            else:
                st.dataframe(
                    data.sort_values("updated_on", ascending=False),
                    use_container_width=True,
                )

# ========================== RCA UPDATE ==========================
if menu == "RCA Update":
    st.header("✍ RCA Update (Bulk Supported)")

    awbs = st.text_area(
        "Paste AWB(s) – max 10,000",
        height=150,
    ).splitlines()

    sc_name = st.text_input("SC Name")
    rca_type = st.selectbox(
        "RCA Type",
        ["Pendency", "Shortage", "Loss"],
    )
    email_subject = st.text_input("Email Subject Line")
    rca_remark = st.text_area("RCA Remark")

    if st.button("Submit RCA"):
        for awb in awbs[:10000]:
            existing = rca_df[rca_df["awb"] == awb]

            if len(existing) >= MAX_REMARKS_PER_AWB:
                oldest_idx = (
                    existing.sort_values("updated_on")
                    .iloc[0]
                    .name
                )
                rca_df.drop(oldest_idx, inplace=True)

            rca_df.loc[len(rca_df)] = [
                awb,
                sc_name,
                rca_type,
                email_subject,
                rca_remark,
                st.session_state.email,
                datetime.now(),
            ]

        rca_df.to_csv(RCA_FILE, index=False)
        st.success("✅ RCA updated successfully")

# ========================== DOWNLOAD ==========================
if menu == "Download":
    st.header("📥 Download Reports")

    if st.session_state.role in ["admin", "superadmin"]:
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            rca_df.to_excel(writer, "RCA_Data", index=False)
            deleted_df.to_excel(writer, "Deleted_RCA", index=False)
            login_df.to_excel(writer, "Login_Audit", index=False)

        st.download_button(
            "⬇ Download Complete System Data (Excel)",
            output.getvalue(),
            "Meesho_RCA_Full_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        st.warning("🚫 Download restricted to Admin only")

# ========================== ADMIN PANEL ==========================
if menu == "Admin Panel" and st.session_state.role in ["admin", "superadmin"]:
    st.header("🛠 Admin & SuperAdmin Controls")

    with st.expander("➕ Create User"):
        new_email = st.text_input("Email")
        new_role = st.selectbox("Role", ["user", "admin", "superadmin"])
        new_name = st.text_input("Name")
        new_pwd = st.text_input("Password")

        if st.button("Create User"):
            users_df.loc[len(users_df)] = [
                new_email,
                new_role,
                new_name,
                new_pwd,
            ]
            users_df.to_excel(USERS_FILE, index=False)
            st.success("User created successfully")

# ========================== PASSWORD CHANGE ==========================
with st.expander("🔑 Change Password"):
    new_pwd = st.text_input("New Password", type="password")
    if st.button("Update Password"):
        users_df.loc[
            users_df["email"] == st.session_state.email, "password"
        ] = new_pwd
        users_df.to_excel(USERS_FILE, index=False)
        st.success("Password updated")

# ========================== LOGOUT ==========================
st.sidebar.divider()
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()



