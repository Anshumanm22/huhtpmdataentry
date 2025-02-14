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
