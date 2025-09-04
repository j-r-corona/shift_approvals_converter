import streamlit as st
import pandas as pd
import io
import zipfile
import os

st.set_page_config(page_title="Shift Approvals Processor", layout="centered")

# ---------------- Authentication ----------------
def login():
    st.title("🔒 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username == st.secrets["auth"]["username"] and password == st.secrets["auth"]["password"]:
            st.session_state["logged_in"] = True
            st.success("✅ Login successful")
            st.experimental_rerun()  # refresh page to show app
        else:
            st.error("❌ Invalid credentials")

# Check login state
if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
    login()
    st.stop()
    
    
st.title("Shift Approvals Processor")


def process_file(uploaded_file):
    """
    Very close to your original function:
    - Reads Excel
    - Processes by Rota
    - Returns dict { category: (filename, csv_bytes, dataframe) }
    """
    df = pd.read_excel(uploaded_file, skiprows=3)
    df['Recorded'] = df['Recorded'].replace('No Recorded Shift', pd.NA)
    dfs = {category: group for category, group in df.groupby("Rota")}
    day_name = str(df['Date of Shift'].iloc[0]).replace("/", "_")

    dfs_final = {}
    for category, df_cat in dfs.items():
        df_new = df_cat.pivot(index='Employee Name', columns='Date of Shift', values='Recorded')
        df_final = df_new.copy()
        columns_num = df_new.columns
        count = 0

        for i in range(len(columns_num)):
            df_new[['Start Time', 'End Time']] = df_new.iloc[:, i].str.split(' - ', expand=True)
            df_new['Start Time'] = df_new['Start Time'].replace('No Recorded Shift', pd.NA)
            df_new['End Time'] = df_new['End Time'].replace('', pd.NA)

            df_new['Start Datetime'] = pd.to_datetime(
                df_new.columns[i] + ' ' + df_new['Start Time'],
                format='%d/%m/%Y %H:%M', errors='coerce'
            )
            df_new['End Datetime'] = pd.to_datetime(
                df_new.columns[i] + ' ' + df_new['End Time'],
                format='%d/%m/%Y %H:%M', errors='coerce'
            )

            mask = df_new['End Datetime'] < df_new['Start Datetime']
            df_new.loc[mask, 'End Datetime'] = df_new.loc[mask, 'End Datetime'] + pd.Timedelta(days=1)

            day = pd.to_datetime(df_new.columns[i], dayfirst=True).day_name() + " Hours"
            hours_worked = round(
                (df_new['End Datetime'] - df_new['Start Datetime']).dt.total_seconds() / 3600,
                2
            )
            df_final.insert(loc=i+1+count, column=day, value=hours_worked)
            count += 1

            df_new = df_new.drop(['Start Datetime', 'End Datetime', "Start Time", "End Time"], axis=1)

        df_final.fillna(0, inplace=True)
        df_final.reset_index(inplace=True)

        filename = f"{category}_{day_name}.csv"
        csv_bytes = df_final.to_csv(index=True).encode("utf-8")
        dfs_final[category] = (filename, csv_bytes, df_final)

    return dfs_final


# --------- Streamlit UI ---------
uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx"])

if uploaded_file:
    with st.spinner("Processing file…"):
        try:
            results = process_file(uploaded_file)
        except Exception as e:
            st.error(f"Error: {e}")
            st.stop()

    st.success("Files processed successfully!")


    # Download all as ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, csv_bytes, _df in results.values():
            zf.writestr(filename, csv_bytes)
    zip_buffer.seek(0)

    st.download_button(
        label="Download All as .zip",
        data=zip_buffer,
        file_name="processed_shifts.zip",
        mime="application/zip"
    )