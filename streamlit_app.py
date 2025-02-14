# app.py
import streamlit as st
from datetime import datetime
from utility import get_google_services
from form_sections import (
    basic_details_section, teacher_selection_section,
    classroom_observation_section, infrastructure_section,
    community_section, save_observation
)

import streamlit as st
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import json
import io
import mimetypes

# Google API setup
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive'
]

@st.cache_resource
def get_google_services():
    """Initialize Google Drive and Sheets services"""
    try:
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPES
        )
        drive_service = build('drive', 'v3', credentials=credentials)
        sheets_client = gspread.authorize(credentials)
        return drive_service, sheets_client
    except Exception as e:
        st.error(f"Failed to initialize Google services: {str(e)}")
        return None, None

def check_folder_access(service, folder_id):
    """Verify access to Google Drive folder"""
    try:
        service.files().list(
            q=f"'{folder_id}' in parents",
            fields="files(id, name)",
            spaces='drive'
        ).execute()
        return True
    except Exception as e:
        st.error(f"Error accessing folder: {str(e)}")
        return False

def upload_to_drive(service, file_data, filename, mimetype, folder_id):
    """Upload file to Google Drive"""
    try:
        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        
        media = MediaIoBaseUpload(
            io.BytesIO(file_data),
            mimetype=mimetype,
            resumable=True
        )
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink',
            supportsAllDrives=True
        ).execute()
        
        return {
            'id': file.get('id'),
            'link': file.get('webViewLink')
        }
    except Exception as e:
        st.error(f"Error uploading {filename}: {str(e)}")
        return None

def get_or_create_sheet(client, sheet_name):
    """Get or create a specific worksheet"""
    try:
        sheet = client.open("School_Observations").worksheet(sheet_name)
        return sheet
    except Exception:
        try:
            workbook = client.open("School_Observations")
        except Exception:
            workbook = client.create("School_Observations")
            workbook.share(None, perm_type='anyone', role='writer')
        
        sheet = workbook.add_worksheet(sheet_name, 1000, 20)
        
        headers = {
            "Observations": [
                "Timestamp", "PM Name", "School Name", "Visit Date", 
                "Visit Type", "Teacher Details", "Observations", 
                "Infrastructure Data", "Community Data", "Media Links"
            ],
            "Schools": ["School Name", "Program Manager", "Added Date"],
            "Teachers": ["School Name", "Teacher Name", "Is Trained", "Added Date"]
        }
        
        if sheet_name in headers:
            sheet.insert_row(headers[sheet_name], 1)
        
        return sheet

def get_program_managers(sheets_client):
    """Get list of all program managers"""
    sheet = get_or_create_sheet(sheets_client, "Schools")
    if not sheet:
        return []
    
    try:
        schools_data = sheet.get_all_records()
        pm_names = list(set(school["Program Manager"] for school in schools_data))
        return sorted(pm_names)
    except Exception as e:
        st.error(f"Error fetching program managers: {str(e)}")
        return []

def get_pm_schools(sheets_client, pm_name):
    """Get schools for a specific program manager"""
    sheet = get_or_create_sheet(sheets_client, "Schools")
    if not sheet:
        return []
    
    try:
        schools_data = sheet.get_all_records()
        return [school["School Name"] for school in schools_data 
                if school["Program Manager"].lower() == pm_name.lower()]
    except Exception as e:
        st.error(f"Error fetching schools: {str(e)}")
        return []

def get_school_teachers(sheets_client, school_name):
    """Get teachers for a specific school"""
    sheet = get_or_create_sheet(sheets_client, "Teachers")
    if not sheet:
        return {"trained": [], "untrained": []}
    
    try:
        teachers_data = sheet.get_all_records()
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
    except Exception as e:
        st.error(f"Error fetching teachers: {str(e)}")
        return {"trained": [], "untrained": []}



# Set page config
st.set_page_config(
    page_title="School Observation Form",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize session state
if 'page' not in st.session_state:
    st.session_state.page = 1
    st.session_state.visit_type = 'Daily'

# Sidebar configuration
st.sidebar.title("Settings")
folder_id = st.sidebar.text_input(
    "Google Drive Folder ID",
    help="ID of the folder where media files will be uploaded"
)

# Initialize Google services
drive_service, sheets_client = get_google_services()

if not drive_service or not sheets_client:
    st.error("Failed to initialize Google services. Please check your configuration.")
    st.stop()

def submit_form():
    """Handle form submission"""
    form_data = {
        "basic_details": st.session_state.basic_details,
        "teacher_details": st.session_state.teacher_details,
        "observations": st.session_state.get("observations", {}),
        "infrastructure": st.session_state.get("infrastructure", {}) 
            if st.session_state.visit_type == "Monthly" else {},
        "community": st.session_state.get("community", {}) 
            if st.session_state.visit_type == "Monthly" else {},
        "media_files": st.session_state.get("media_files", [])
    }
    
    if save_observation(sheets_client, form_data):
        st.success("Form submitted successfully!")
        # Clear session state except page number
        for key in list(st.session_state.keys()):
            if key != "page":
                del st.session_state[key]
        st.session_state.page = 1
        st.rerun()
    else:
        st.error("Error submitting form. Please try again.")

def main():
    st.title("School Observation Form")
    
    # Show progress
    total_pages = 5 if st.session_state.get('visit_type') == 'Monthly' else 3
    progress_text = f"Page {st.session_state.page} of {total_pages}"
    st.progress(st.session_state.page / total_pages, text=progress_text)
    
    # Display appropriate section
    if st.session_state.page == 1:
        basic_details_section(sheets_client)
    elif st.session_state.page == 2:
        teacher_selection_section(sheets_client)
    elif st.session_state.page == 3:
        if classroom_observation_section(drive_service, folder_id):
            submit_form()
    elif st.session_state.page == 4 and st.session_state.visit_type == "Monthly":
        infrastructure_section()
    elif st.session_state.page == 5 and st.session_state.visit_type == "Monthly":
        if community_section():
            submit_form()

if __name__ == "__main__":
    main()
