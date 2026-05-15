import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Grading Dashboard", layout="wide")
st.title("🎓 Project Evaluation Dashboard")

# 1. Authenticate with Google Sheets using Streamlit Secrets
@st.cache_resource
def get_google_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    # It reads your secure JSON key from Streamlit Secrets
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    # Open the exact name of your Google Sheet
    return client.open("Merged_Project_Rubric_115_Students").sheet1

sheet = get_google_sheet()

# 2. Build the UI
st.write("Enter marks below. Saving will update the Google Sheet live.")

col1, col2 = st.columns(2)
with col1:
    st.header("📊 Mid-Term Marks")
    row_number = st.number_input("Enter Excel Row Number (e.g., 4 for Student 1):", min_value=4, value=4)
    tk_mid = st.number_input("Industry Guide - TK (Max 5)", min_value=0, max_value=5, value=0)
    pm_mid = st.number_input("Industry Guide - PM (Max 10)", min_value=0, max_value=10, value=0)
    dd_mid = st.number_input("Industry Guide - DD (Max 10)", min_value=0, max_value=10, value=0)

# 3. Save Data to Google Sheet
if st.button("💾 Save Marks to Database"):
    try:
        with st.spinner('Saving securely to cloud...'):
            # Update specific cells based on the row number
            # (Example: updating columns F, G, and H, which are 6, 7, 8 in gspread)
            sheet.update_cell(row_number, 6, tk_mid)
            sheet.update_cell(row_number, 7, pm_mid)
            sheet.update_cell(row_number, 8, dd_mid)
            
        st.success(f"Marks saved successfully for Row {row_number}!")
    except Exception as e:
        st.error(f"Error saving data: {e}")