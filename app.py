import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- App Configuration ---
st.set_page_config(page_title="Smart Project Evaluation", layout="wide", page_icon="🎓")

# --- Google Sheets Authentication ---
@st.cache_resource
def init_connection():
    """Authenticates with Google Sheets using Streamlit Secrets."""
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    # Reads the JSON key stored in Streamlit Cloud Secrets
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    # Open the Google Sheet by its exact name
    return client.open("Merged_Project_Rubric_115_Students").sheet1

# Attempt to connect
try:
    sheet = init_connection()
except Exception as e:
    st.error("⚠️ Connection Error: Please ensure your Google Service Account is configured in Streamlit Secrets.")
    st.stop()

# --- Data Fetching & Parsing ---
@st.cache_data(ttl=10) # Refresh data every 10 seconds to catch updates from other teachers
def fetch_and_parse_data():
    all_data = sheet.get_all_values()
    
    # 1. Detect columns dynamically
    header_row = 2 # 0-indexed in Python list (Row 3 in Excel)
    name_col, reg_col = 2, 1 # Default index for Name and Reg
    
    for c, val in enumerate(all_data[header_row]):
        if "Student Name" in str(val): name_col = c
        if "Registration No" in str(val): reg_col = c

    # 2. Detect marks columns grouped by Phase and Evaluator
    mid_term_fields = []
    final_fields = []
    current_phase = ""
    current_eval = ""

    for c in range(len(all_data[header_row])):
        val1 = str(all_data[0][c]).strip().upper() # Row 1
        val2 = str(all_data[1][c]).strip()         # Row 2
        val3 = str(all_data[2][c]).strip()         # Row 3

        if val1: 
            current_phase = "MID-TERM" if "MID" in val1 else "FINAL" if "FINAL" in val1 else ""
        if val2:
            current_eval = val2.split("[")[0].strip()

        if "(" in val3 and ")" in val3 and "Total" not in val3 and "TOTAL" not in val3:
            max_mark = int(''.join(filter(str.isdigit, val3)))
            # gspread uses 1-based indexing for columns, so we add 1 to `c`
            field_data = {"col": c + 1, "label": val3, "evaluator": current_eval, "max": max_mark}
            
            if current_phase == "MID-TERM":
                mid_term_fields.append(field_data)
            elif current_phase == "FINAL":
                final_fields.append(field_data)

    # 3. Load Students
    students = []
    for r in range(3, len(all_data)): # Start from Row 4 (index 3)
        name = all_data[r][name_col]
        reg = all_data[r][reg_col]
        if name or reg:
            students.append({
                "row": r + 1, # gspread uses 1-based indexing
                "display": f"{reg or 'N/A'} - {name or 'Unknown Student'}",
                "data": all_data[r]
            })
            
    return {"mid": mid_term_fields, "final": final_fields, "students": students}

with st.spinner("Connecting to Google Sheets..."):
    structure = fetch_and_parse_data()

# --- Main Dashboard UI ---
st.title("🎓 Smart Project Evaluation Dashboard")

if 'student_idx' not in st.session_state:
    st.session_state.student_idx = 0

student_options = [s["display"] for s in structure["students"]]

# Navigation Bar
col_prev, col_sel, col_next = st.columns([1, 4, 1])
with col_prev:
    st.write("") 
    if st.button("⬅ Previous Student"):
        st.session_state.student_idx = max(0, st.session_state.student_idx - 1)
with col_sel:
    selected_student_display = st.selectbox("Select Student:", options=student_options, index=st.session_state.student_idx)
    st.session_state.student_idx = student_options.index(selected_student_display)
with col_next:
    st.write("")
    if st.button("Next Student ➡"):
        st.session_state.student_idx = min(len(student_options) - 1, st.session_state.student_idx + 1)

current_student = structure["students"][st.session_state.student_idx]
target_row = current_student["row"]
student_data = current_student["data"]

new_marks = {}

# --- Form Layout ---
col_left, col_right = st.columns(2)

def build_input_group(container, phase_fields, bg_color_hex):
    total_sum = 0.0
    evaluators = {}
    for field in phase_fields:
        evaluators.setdefault(field["evaluator"], []).append(field)
        
    for eval_name, fields in evaluators.items():
        with container.container():
            st.markdown(f"**{eval_name}**")
            input_cols = st.columns(len(fields))
            for i, field in enumerate(fields):
                # Retrieve existing value from the pre-fetched data
                existing_val = student_data[field["col"] - 1]
                initial_value = float(existing_val) if existing_val.replace('.', '', 1).isdigit() else None
                
                if initial_value is not None and initial_value > field["max"]:
                    initial_value = float(field["max"])

                with input_cols[i]:
                    val = st.number_input(
                        label=field["label"],
                        min_value=0.0,
                        max_value=float(field["max"]),
                        value=initial_value,
                        step=1.0,
                        key=f"col_{field['col']}"
                    )
                    new_marks[field["col"]] = val
                    if val:
                        total_sum += val
            st.divider()
    return total_sum

with col_left:
    st.subheader("📊 MID-TERM MARKS (Max: 100)")
    mid_total = build_input_group(col_left, structure["mid"], "#EBF5FB")

with col_right:
    st.subheader("🏆 FINAL PRESENTATION MARKS (Max: 300)")
    final_total = build_input_group(col_right, structure["final"], "#FDEDEC")

# --- Footer & Save Action ---
st.markdown("---")
tot_col1, tot_col2, tot_col3, save_col = st.columns([2, 2, 3, 2])

tot_col1.metric("Mid-Term Total", f"{mid_total:g} / 100")
tot_col2.metric("Final Total", f"{final_total:g} / 300")
tot_col3.metric("GRAND TOTAL", f"{mid_total + final_total:g} / 400")

with save_col:
    st.write("") 
    if st.button("💾 SAVE MARKS TO CLOUD", use_container_width=True, type="primary"):
        with st.spinner("Saving to Google Sheets..."):
            try:
                # Prepare batch update to make it fast
                cells_to_update = []
                for col_idx, val in new_marks.items():
                    cell = gspread.Cell(row=target_row, col=col_idx, value=val if val is not None else "")
                    cells_to_update.append(cell)
                
                sheet.update_cells(cells_to_update)
                fetch_and_parse_data.clear() # Force data refresh on next load
                st.success(f"Marks successfully saved for {current_student['display']}!")
            except Exception as e:
                st.error(f"Error saving to Google Sheets: {e}")