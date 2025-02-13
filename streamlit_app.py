import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import json

# Set page config
st.set_page_config(page_title="School Observation Form", layout="wide")

# Google Sheets setup
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Function to connect to Google Sheets
@st.cache_resource
def connect_to_gsheets():
    # Get the Google Sheets credentials from Streamlit secrets
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    client = gspread.authorize(credentials)
    return client

def get_or_create_sheet(sheet_name):
    client = connect_to_gsheets()
    try:
        # Try to open existing sheet
        sheet = client.open("School_Observations").worksheet(sheet_name)
    except:
        # If sheet doesn't exist, create it
        try:
            workbook = client.open("School_Observations")
        except:
            # If workbook doesn't exist, create it
            workbook = client.create("School_Observations")
            # Share with anyone who has the link
            workbook.share(None, perm_type='anyone', role='writer')
        
        sheet = workbook.add_worksheet(sheet_name, 1000, 20)
        
        # Set up headers based on sheet type
        if sheet_name == "Observations":
            headers = ["Timestamp", "PM Name", "School Name", "Visit Date", "Visit Type", 
                      "Teacher Name", "Is Trained", "Teacher Metrics", "Student Metrics", 
                      "Infrastructure Data", "Community Data"]
        elif sheet_name == "Schools":
            headers = ["School Name", "Program Manager", "Added Date"]
        elif sheet_name == "Teachers":
            headers = ["School Name", "Teacher Name", "Is Trained", "Added Date"]
        
        sheet.insert_row(headers, 1)
    
    return sheet

# Initialize session state
if 'page' not in st.session_state:
    st.session_state.page = 1

def get_pm_schools(pm_name):
    schools_sheet = get_or_create_sheet("Schools")
    schools_data = schools_sheet.get_all_records()
    return [school["School Name"] for school in schools_data if school["Program Manager"] == pm_name]

def get_school_teachers(school_name):
    teachers_sheet = get_or_create_sheet("Teachers")
    teachers_data = teachers_sheet.get_all_records()
    teachers = {
        "trained": [],
        "untrained": []
    }
    for teacher in teachers_data:
        if teacher["School Name"] == school_name:
            if teacher["Is Trained"]:
                teachers["trained"].append(teacher["Teacher Name"])
            else:
                teachers["untrained"].append(teacher["Teacher Name"])
    return teachers

def save_observation(data):
    try:
        observations_sheet = get_or_create_sheet("Observations")
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            data["basic_details"]["pm_name"],
            data["basic_details"]["school_name"],
            data["basic_details"]["visit_date"],
            data["basic_details"]["visit_type"],
            json.dumps(data["teacher_details"]),
            json.dumps(data.get("observations", {})),
            json.dumps(data.get("infrastructure", {})),
            json.dumps(data.get("community", {}))
        ]
        observations_sheet.append_row(row)
        return True
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")
        return False

def add_new_teacher(school_name, teacher_name, is_trained):
    try:
        teachers_sheet = get_or_create_sheet("Teachers")
        row = [
            school_name,
            teacher_name,
            is_trained,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ]
        teachers_sheet.append_row(row)
        return True
    except Exception as e:
        st.error(f"Error adding teacher: {str(e)}")
        return False

[rest of the form sections remain similar to previous version...]

def view_data_section():
    st.title("View Observations")
    
    observations_sheet = get_or_create_sheet("Observations")
    data = observations_sheet.get_all_records()
    
    if data:
        df = pd.DataFrame(data)
        
        # Filters
        col1, col2 = st.columns(2)
        with col1:
            pm_filter = st.multiselect(
                "Filter by Program Manager",
                options=df["PM Name"].unique()
            )
        with col2:
            school_filter = st.multiselect(
                "Filter by School",
                options=df["School Name"].unique()
            )
        
        # Apply filters
        if pm_filter:
            df = df[df["PM Name"].isin(pm_filter)]
        if school_filter:
            df = df[df["School Name"].isin(school_filter)]
        
        # Display data
        st.dataframe(df)
        
        # Download option
        if st.button("Download as Excel"):
            df.to_excel("observations.xlsx", index=False)
            with open("observations.xlsx", "rb") as f:
                st.download_button(
                    "Click to Download",
                    f,
                    "school_observations.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    else:
        st.info("No observations recorded yet")

def main():
    st.title("School Observation Form")
    
    # Add sidebar for navigation
    menu = ["Submit Observation", "View Data"]
    choice = st.sidebar.selectbox("Menu", menu)
    
    if choice == "Submit Observation":
        # Display progress
        st.progress(st.session_state.page / 5)
        
        # Display appropriate section based on current page
        if st.session_state.page == 1:
            basic_details_section()
        elif st.session_state.page == 2:
            teacher_selection_section()
        elif st.session_state.page == 3:
            classroom_observation_section()
        elif st.session_state.page == 4:
            infrastructure_section()
        elif st.session_state.page == 5:
            community_section()
    else:
        view_data_section()

if __name__ == "__main__":
    main()
