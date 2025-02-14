# utility.py
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import gspread
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
    """Get Google Drive and Sheets services using service account."""
    try:
        # Debug: Print secrets structure
        if "gcp_service_account" not in st.secrets:
            st.error("No 'gcp_service_account' secret found")
            return None, None
        
        # Try to parse the service account info
        service_account_info = st.secrets["gcp_service_account"]
        st.write("Service Account Info Type:", type(service_account_info))
        st.write("Available keys:", service_account_info.keys())
        
        # Check specific required fields
        required_fields = ["type", "project_id", "private_key_id", "private_key", "client_email"]
        for field in required_fields:
            if field not in service_account_info:
                st.error(f"Missing required field: {field}")
            else:
                # Safely print the first few characters of each field
                value = service_account_info[field]
                safe_value = str(value)[:10] + "..." if len(str(value)) > 10 else str(value)
                st.write(f"{field}: {safe_value}")
        
        # Manually construct the credentials dict
        credentials_dict = {
            "type": service_account_info["type"],
            "project_id": service_account_info["project_id"],
            "private_key_id": service_account_info["private_key_id"],
            "private_key": service_account_info["private_key"],
            "client_email": service_account_info["client_email"],
            "client_id": service_account_info.get("client_id", ""),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": service_account_info.get("client_x509_cert_url", "")
        }
        
        # Try to create credentials
        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict,
            scopes=SCOPES
        )
        
        # Create services
        drive_service = build('drive', 'v3', credentials=credentials)
        sheets_client = gspread.authorize(credentials)
        
        st.success("Successfully created Google services!")
        return drive_service, sheets_client
        
    except Exception as e:
        st.error("Failed to initialize Google services")
        st.error(f"Error Type: {type(e)}")
        st.error(f"Error Message: {str(e)}")
        
        # If it's a credentials error, print more details
        if hasattr(e, 'args') and e.args:
            st.error("Detailed error information:")
            for arg in e.args:
                st.error(str(arg))
        
        return None, None

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
