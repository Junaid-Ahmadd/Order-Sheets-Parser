import streamlit as st
import google.generativeai as genai
import json
import pandas as pd
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="Order Sheet Parser", layout="wide")
st.title("⚖️ Order Sheet Parser")

# --- CUSTOM CSS FOR HTML TABLE ---
st.markdown("""
<style>
    .custom-table {
        width: 100%;
        border-collapse: collapse;
        font-family: 'Times New Roman', Times, serif;
        font-size: 16px;
        color: #000;
    }
    .custom-table th {
        background-color: #f0f0f0;
        color: #000;
        font-weight: bold;
        border: 2px solid #000;
        padding: 10px;
        text-align: left;
    }
    .custom-table td {
        background-color: #fff;
        border: 1px solid #000;
        padding: 10px;
        vertical-align: top;
        color: #000;
    }
    /* Force Column Widths */
    .custom-table th:nth-child(1), .custom-table td:nth-child(1) {
        width: 15%;
        white-space: nowrap;
    }
    .custom-table th:nth-child(2), .custom-table td:nth-child(2) {
        width: 85%;
    }
</style>
""", unsafe_allow_html=True)

# --- API SETUP & SECURITY ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except Exception as e:
    st.error("🚨 API Key not found! Please set `GEMINI_API_KEY` in your Streamlit secrets.")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("Instructions")
    st.info("Upload your case files (PDFs or Images). The AI will read all of them and merge the timeline into one table.")

# --- FILE UPLOADER (Accepts Multiple) ---
uploaded_files = st.file_uploader(
    "Upload Order Sheets (Select multiple files)",
    type=['pdf', 'png', 'jpg', 'jpeg'],
    accept_multiple_files=True
)

# --- BACKEND LOGIC ---
def process_single_file(uploaded_file):
    """Sends a single file to Gemini and gets a JSON list of hearings."""
    
    # Using JSON Mode
    # Keeping 'gemini-flash-latest' as it was verified to work
    model = genai.GenerativeModel(
        model_name="gemini-flash-latest",
        generation_config={"response_mime_type": "application/json"}
    )
    
    prompt = """
    You are a Pakistani Legal Assistant. Analyze this Order Sheet.
    
    Task: Extract a chronological list of hearings.
    Rules:
    1. Extract the Date (DD-MM-YYYY) and the Order Summary.
    2. If multiple orders are on one page, extract all of them.
    3. The Summary must be detailed (2-3 sentences).
    4. Return valid JSON: [{"date": "...", "summary": "..."}]
    """

    content = [prompt]
    
    if uploaded_file.type == "application/pdf":
        content.append({"mime_type": "application/pdf", "data": uploaded_file.getvalue()})
    else:
        content.append({"mime_type": uploaded_file.type, "data": uploaded_file.getvalue()})

    try:
        response = model.generate_content(content)
        return json.loads(response.text)
    except Exception as e:
        st.error(f"Error reading file {uploaded_file.name}: {e}")
        return []

# --- MAIN EXECUTION ---
if uploaded_files:
    # --- SESSION STATE LOGIC ---
    # Create a unique key based on file names and sizes to detect changes
    current_files_key = ",".join([f"{f.name}-{f.size}" for f in uploaded_files])
    
    # Initialize session state for data if not present
    if 'processed_data' not in st.session_state:
        st.session_state.processed_data = None
    if 'files_key' not in st.session_state:
        st.session_state.files_key = ""

    # Check if files have changed or if we haven't processed yet
    if st.session_state.files_key != current_files_key:
        all_data = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, file in enumerate(uploaded_files):
            status_text.text(f"Reading file {i+1}/{len(uploaded_files)}: {file.name}...")
            file_data = process_single_file(file)
            if file_data:
                all_data.extend(file_data)
            progress_bar.progress((i + 1) / len(uploaded_files))
            time.sleep(0.5) 

        status_text.success("Processing Complete!")
        
        # Store in session state
        st.session_state.processed_data = all_data
        st.session_state.files_key = current_files_key
    
    # Display Data if available
    if st.session_state.processed_data:
        df = pd.DataFrame(st.session_state.processed_data)
        
        # Rename columns for display
        df_display = df.rename(columns={"date": "Date", "summary": "Order Proceedings"})
        
        # Convert to HTML with Custom Class
        html_table = df_display.to_html(classes='custom-table', index=False, escape=False)
        
        st.subheader("Generated Case Timeline")
        st.markdown(html_table, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True) # Spacer
        
        # Download Button
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download Timeline as CSV",
            csv,
            "Master_Case_Timeline.csv",
            "text/csv",
            key='download-csv'
            # Note: Clicking this triggers a rerun, but session state will prevent re-processing
        )
    elif st.session_state.processed_data == []:
        st.warning("No dates found in the uploaded documents.")

elif not uploaded_files:
    # Clear session state if files are removed
    if 'processed_data' in st.session_state:
        del st.session_state.processed_data
    if 'files_key' in st.session_state:
        del st.session_state.files_key
