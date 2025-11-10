import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import sqlite3
import time
import os
from datetime import datetime
import pytz

# All Folders used in the program
DATA_FOLDER = "user_data"
REPORTS_FOLDER = "monthly_reports"
RESET_FOLDER = "last_reset"
CHARTS_FOLDER = "charts"

os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(REPORTS_FOLDER, exist_ok=True)
os.makedirs(RESET_FOLDER, exist_ok=True)
os.makedirs(CHARTS_FOLDER, exist_ok=True)

# Storing Usernames in the database
conn = sqlite3.connect("user_data.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    name TEXT PRIMARY KEY
)
""")
conn.commit()


def get_all_users():
    cursor.execute("SELECT name FROM users")
    return [row[0] for row in cursor.fetchall()]


def add_user(name):
    cursor.execute("INSERT OR IGNORE INTO users (name) VALUES (?)", (name,))
    conn.commit()


# Creating/Saving each user's csv file
def user_csv_path(name):
    return os.path.join(DATA_FOLDER, f"{name}.csv")


def load_user_data(name):
    file_path = user_csv_path(name)
    if os.path.exists(file_path):
        df = pd.read_csv(file_path, encoding="utf-8")
        # Ensure totals numeric
        if "Total" in df.columns:
            df["Total"] = pd.to_numeric(df["Total"], errors="coerce").fillna(0.0)
        return df
    else:
        return pd.DataFrame({
            "Categories": ["Food", "Travel", "Loans", "Entertainment", "Shopping", "Others", "Budget"],
            "Total": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        })


def save_user_data(name, df):
    file_path = user_csv_path(name)
    df.to_csv(file_path, index=False, encoding="utf-8")


# Reports and charts defining for each user
def current_india_dt():
    tz = pytz.timezone("Asia/Kolkata")
    return datetime.now(tz)


def month_key(dt=None):
    if dt is None:
        dt = current_india_dt()
    return dt.strftime("%Y-%m")  # e.g. "2025-11"


def month_label(dt=None):
    if dt is None:
        dt = current_india_dt()
    return dt.strftime("%B_%Y")  # e.g. "November_2025"


def report_file_path(name, dt=None):
    return os.path.join(REPORTS_FOLDER, f"{name}_{month_label(dt)}.txt")


def reset_file_path(name):
    return os.path.join(RESET_FOLDER, f"{name}.txt")


def charts_folder_for(name):
    folder = os.path.join(CHARTS_FOLDER, name)
    os.makedirs(folder, exist_ok=True)
    return folder


def pie_chart_path(name, dt=None):
    return os.path.join(charts_folder_for(name), f"{name}_{month_key(dt)}_pie.png")


def bar_chart_path(name, dt=None):
    return os.path.join(charts_folder_for(name), f"{name}_{month_key(dt)}_bar.png")


# Computing Budget and alerts

def compute_budget_status(df):
    # Sum all categories except Budget
    exp_df = df[df["Categories"] != "Budget"]
    total_expenses = exp_df["Total"].sum()
    budget_val = float(df.loc[df["Categories"] == "Budget", "Total"].values[0])
    remaining = budget_val - total_expenses
    percent_used = (total_expenses / budget_val * 100) if budget_val > 0 else 0.0
    return budget_val, total_expenses, remaining, percent_used


def show_budget_summary(df):
    budget_val, total_expenses, remaining, percent_used = compute_budget_status(df)
    st.write(f"💵 Budget: ₹{budget_val:.2f}")
    st.write(f"💸 Spent: ₹{total_expenses:.2f}")
    st.write(f"✅ Remaining: ₹{remaining:.2f}")
    st.write(f"📊 Used: {percent_used:.2f}%")
    if budget_val <= 0:
        st.info("No budget set. Please set a budget (new users).")
    else:
        if percent_used >= 100:
            st.error("🚨 Budget exceeded!")
        elif percent_used >= 80:
            st.warning("⚠️ Budget usage >= 80%")
        else:
            st.success("😊 You're within your budget")


# Generating Charts and Saving Them

def create_and_save_charts(name, df, dt=None):
    exp_df = df[df["Categories"] != "Budget"].copy()
    total = exp_df["Total"].sum()
    # BAR CHART
    fig_bar, ax_bar = plt.subplots(figsize=(6, 4))
    if total > 0:
        ax_bar.bar(exp_df["Categories"], exp_df["Total"])
        ax_bar.set_title("Expenses by Category")
        ax_bar.set_ylabel("Amount")
        ax_bar.set_xticklabels(exp_df["Categories"], rotation=30, ha="right")
    else:
        ax_bar.text(0.5, 0.5, "No expense data yet", ha='center', va='center', fontsize=12)
        ax_bar.set_xticks([])
    fig_bar.tight_layout()
    bar_path = bar_chart_path(name, dt)
    fig_bar.savefig(bar_path, dpi=150, bbox_inches="tight")
    plt.close(fig_bar)

    # PIE CHART
    fig_pie, ax_pie = plt.subplots(figsize=(6, 4))
    if total > 0:

        nonzero = exp_df[exp_df["Total"] > 0]
        if nonzero.empty:
            ax_pie.text(0.5, 0.5, "No non-zero categories", ha='center', va='center')
        else:
            ax_pie.pie(nonzero["Total"], labels=nonzero["Categories"], autopct="%1.1f%%")
            ax_pie.set_title("Expense Distribution")
    else:
        ax_pie.text(0.5, 0.5, "No expense data yet", ha='center', va='center', fontsize=12)
    pie_path = pie_chart_path(name, dt)
    fig_pie.savefig(pie_path, dpi=150, bbox_inches="tight")
    plt.close(fig_pie)

    return bar_path, pie_path


# Monthly Reports
def ensure_monthly_report_exists(name, dt=None):
    dt = dt or current_india_dt()
    rpt = report_file_path(name, dt)
    if not os.path.exists(rpt):

        df = load_user_data(name)
        budget_val = float(df.loc[df["Categories"] == "Budget", "Total"].values[0])
        if budget_val > 0:
            with open(rpt, "w", encoding="utf-8") as f:
                f.write(f"Expense Report for {name} - {dt.strftime('%B %Y')}\n")
                f.write(f"Budget: ₹{budget_val:.2f}\n")
                f.write("Timestamp | Category | Amount\n")
    return rpt


def append_expense_to_report(name, category, amount, dt=None):
    dt = dt or current_india_dt()
    rpt = report_file_path(name, dt)

    ensure_monthly_report_exists(name, dt)
    timestamp = dt.strftime("%d-%m-%Y %H:%M")
    with open(rpt, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} | {category} | ₹{amount}\n")


def finalize_month_report(name, df, dt=None):
    dt = dt or current_india_dt()
    rpt = report_file_path(name, dt)

    budget_val, total_expenses, remaining, percent_used = compute_budget_status(df)
    with open(rpt, "a", encoding="utf-8") as f:
        f.write("\n---- Month End Summary ----\n")
        f.write(f"Total Expenses: ₹{total_expenses:.2f}\n")
        f.write(f"Remaining: ₹{remaining:.2f}\n")
        f.write(f"Percent Used: {percent_used:.2f}%\n")
        if percent_used >= 100:
            f.write("Status: Budget Exceeded\n")
        elif percent_used >= 80:
            f.write("Status: Close to Budget\n")
        else:
            f.write("Status: Within Budget\n")
        f.write(f"Closed on: {dt.strftime('%d-%m-%Y')}\n")


# Main StreamLit User interface
st.set_page_config(page_title="Expense Tracker", layout="centered")

st.title("💰 Expense Tracker")

name = st.text_input("Enter your name (lowercase recommended):").strip().lower()

if name:

    all_users = get_all_users()
    is_new_user = False
    if name not in all_users:
        add_user(name)
        is_new_user = True

    df = load_user_data(name)

    # Month Handling
    india_dt = current_india_dt()
    current_mkey = month_key(india_dt)
    reset_file = reset_file_path(name)
    last_saved_month = None
    if os.path.exists(reset_file):
        with open(reset_file, "r", encoding="utf-8") as f:
            last_saved_month = f.read().strip()

    budget_val = float(df.loc[df["Categories"] == "Budget", "Total"].values[0])
    if budget_val > 0:
        ensure_monthly_report_exists(name, india_dt)
    if last_saved_month != current_mkey and india_dt.day == 1:
        prev_month_dt = india_dt.replace(day=1)
        from datetime import timedelta

        prev_last_day = prev_month_dt - timedelta(days=1)
        finalize_month_report(name, df, prev_last_day)

        df.loc[df["Categories"] != "Budget", "Total"] = 0.0
        save_user_data(name, df)
        with open(reset_file, "w", encoding="utf-8") as f:
            f.write(current_mkey)
        st.warning("📆 New month started: previous month's report finalized and expenses reset.")

    # UI for New users
    if is_new_user and budget_val == 0.0:
        st.subheader(f"Welcome, {name} — set your monthly budget")
        new_budget = st.number_input("Set monthly budget (₹)", min_value=0.0, key=f"setbudget_{name}")
        if st.button("Save Budget", key=f"savebudget_{name}"):
            df.loc[df["Categories"] == "Budget", "Total"] = float(new_budget)
            save_user_data(name, df)
            st.success("✅ Budget saved. You can now add expenses.")

            ensure_monthly_report_exists(name, india_dt)
            create_and_save_charts(name, df, india_dt)
            st.experimental_rerun()
    # Ui for Exisitng Users
    else:

        st.subheader(f"Hello, {name.capitalize()}")

        menu = st.selectbox("Choose action", ["View Summary", "Add Expense", "Modify Budget", "Generate/View Reports",
                                              "Generate/View Charts"])

        if menu == "View Summary":
            show_budget_summary(df)
            st.dataframe(df)

        elif menu == "Add Expense":
            st.write("Add an expense to a category:")
            category = st.selectbox("Category", df[df["Categories"] != "Budget"]["Categories"].tolist(),
                                    key=f"cat_{name}")
            amount = st.number_input("Amount (₹)", min_value=0.0, key=f"amt_{name}")
            if st.button("Add Expense", key=f"add_{name}"):

                df.loc[df["Categories"] == category, "Total"] += float(amount)
                save_user_data(name, df)

                ensure_monthly_report_exists(name, india_dt)
                append_expense_to_report(name, category, amount, india_dt)

                create_and_save_charts(name, df, india_dt)

                budget_val, total_exp, remaining, perc = compute_budget_status(df)
                if perc >= 100:
                    st.error("🚨 ALERT: Budget exceeded!")
                elif perc >= 80:
                    st.warning(f"⚠️ WARNING: Budget used {perc:.2f}%")
                st.success(f"✅ Added ₹{amount} to {category}")
                st.dataframe(df)

        elif menu == "Modify Budget":
            current_budget = float(df.loc[df["Categories"] == "Budget", "Total"].values[0])
            new_budget_val = st.number_input("New budget (₹)", min_value=0.0, value=current_budget, key=f"mod_{name}")
            if st.button("Update Budget", key=f"update_{name}"):
                df.loc[df["Categories"] == "Budget", "Total"] = float(new_budget_val)
                save_user_data(name, df)

                rpt = report_file_path(name, india_dt)
                if os.path.exists(rpt):
                    with open(rpt, "r", encoding="utf-8") as f:
                        old = f.read()
                    with open(rpt, "w", encoding="utf-8") as f:
                        f.write(f"Expense Report for {name} - {india_dt.strftime('%B %Y')}\n")
                        f.write(f"Budget: ₹{float(new_budget_val):.2f}\n")
                        f.write(old.splitlines(True)[2] if len(old.splitlines(True)) > 2 else "")
                st.success("✅ Budget updated")

                create_and_save_charts(name, df, india_dt)

        elif menu == "Generate/View Reports":

            ensure_monthly_report_exists(name, india_dt)

            files = sorted([f for f in os.listdir(REPORTS_FOLDER) if f.startswith(name)], reverse=True)
            if not files:
                st.info("No reports yet.")
            else:
                chosen = st.selectbox("Select report", files, key=f"reports_{name}")
                if st.button("Open Report", key=f"openrep_{name}"):
                    with open(os.path.join(REPORTS_FOLDER, chosen), "r", encoding="utf-8") as f:
                        content = f.read()
                    st.text_area("Report contents", content, height=400)

                if st.button("Download Selected Report (txt)", key=f"dlrep_{name}"):
                    with open(os.path.join(REPORTS_FOLDER, chosen), "r", encoding="utf-8") as f:
                        data = f.read()
                    st.download_button(f"Download {chosen}", data, file_name=chosen, mime="text/plain")

        elif menu == "Generate/View Charts":

            create_and_save_charts(name, df, india_dt)
            bar_path = bar_chart_path(name, india_dt)
            pie_path = pie_chart_path(name, india_dt)
            st.write("Bar Chart (saved to project folder):")
            if os.path.exists(bar_path):
                st.image(bar_path, use_column_width=True)
                with open(bar_path, "rb") as f:
                    st.download_button("Download Bar Chart (PNG)", f, file_name=os.path.basename(bar_path),
                                       mime="image/png")
            else:
                st.info("No bar chart found.")

            st.write("Pie Chart (saved to project folder):")
            if os.path.exists(pie_path):
                st.image(pie_path, use_column_width=True)
                with open(pie_path, "rb") as f:
                    st.download_button("Download Pie Chart (PNG)", f, file_name=os.path.basename(pie_path),
                                       mime="image/png")
            else:
                st.info("No pie chart found.")

        st.markdown("---")
        if st.button("Show current data (table)"):
            st.dataframe(df)
        if st.button("Save data now"):
            save_user_data(name, df)
            st.success("Data saved.")