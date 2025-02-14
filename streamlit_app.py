import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import json
import io
import mimetypes

# Set page config
st.set_page_config(
    page_title="School Observation Form",
    layout="wide",
    initial_sidebar_state="collapsed"
)

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
        # Try to open existing sheet
        sheet = client.open("School_Observations").worksheet(sheet_name)
        return sheet
    except Exception:
        try:
            # If sheet doesn't exist, create it
            workbook = client.open("School_Observations")
        except Exception:
            # If workbook doesn't exist, create it
            workbook = client.create("School_Observations")
            workbook.share(None, perm_type='anyone', role='writer')
        
        sheet = workbook.add_worksheet(sheet_name, 1000, 20)
        
        # Set up headers based on sheet type
        if sheet_name == "Observations":
            headers = [
                "Timestamp", "PM Name", "School Name", "Visit Date", 
                "Visit Type", "Teacher Details", "Observations", 
                "Infrastructure Data", "Community Data", "Media Links"
            ]
        elif sheet_name == "Schools":
            headers = ["School Name", "Program Manager", "Added Date"]
        elif sheet_name == "Teachers":
            headers = ["School Name", "Teacher Name", "Is Trained", "Added Date"]
        
        sheet.insert_row(headers, 1)
        return sheet

def handle_media_upload(drive_service, teacher_name, school_name, visit_date, folder_id):
    """Handle media file uploads"""
    if not folder_id:
        st.warning("Please configure Google Drive folder ID in the sidebar first")
        return []
        
    if not check_folder_access(drive_service, folder_id):
        st.error("Cannot access specified Google Drive folder")
        return []
    
    uploaded_files = []
    unique_key = f"{teacher_name}_{school_name}_{visit_date}_{datetime.now().timestamp()}"
    
    col1, col2 = st.columns(2)
    
    with col1:
        photos = st.file_uploader(
            "Upload Photos (JPG, PNG)",
            type=['jpg', 'jpeg', 'png'],
            accept_multiple_files=True,
            key=f"photos_{unique_key}"
        )
        
        if photos:
            for photo in photos:
                with st.spinner(f"Uploading {photo.name}..."):
                    result = upload_to_drive(
                        drive_service,
                        photo.getvalue(),
                        f"{school_name}_{teacher_name}_{visit_date}_{photo.name}",
                        photo.type,
                        folder_id
                    )
                    if result:
                        uploaded_files.append({
                            'type': 'photo',
                            'name': photo.name,
                            'drive_file_id': result['id'],
                            'link': result['link']
                        })
                        st.success(f"Uploaded {photo.name}")
    
    with col2:
        videos = st.file_uploader(
            "Upload Videos (MP4)",
            type=['mp4'],
            accept_multiple_files=True,
            key=f"videos_{unique_key}"
        )
        
        if videos:
            for video in videos:
                with st.spinner(f"Uploading {video.name}..."):
                    result = upload_to_drive(
                        drive_service,
                        video.getvalue(),
                        f"{school_name}_{teacher_name}_{visit_date}_{video.name}",
                        video.type,
                        folder_id
                    )
                    if result:
                        uploaded_files.append({
                            'type': 'video',
                            'name': video.name,
                            'drive_file_id': result['id'],
                            'link': result['link']
                        })
                        st.success(f"Uploaded {video.name}")
    
    return uploaded_files

def save_observation(sheets_client, data):
    """Save observation data to Google Sheets"""
    sheet = get_or_create_sheet(sheets_client, "Observations")
    if not sheet:
        st.error("Unable to access observations sheet")
        return False
        
    try:
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            data["basic_details"]["pm_name"],
            data["basic_details"]["school_name"],
            data["basic_details"]["visit_date"],
            data["basic_details"]["visit_type"],
            json.dumps(data["teacher_details"]),
            json.dumps(data.get("observations", {})),
            json.dumps(data.get("infrastructure", {})) if data["basic_details"]["visit_type"] == "Monthly" else "{}",
            json.dumps(data.get("community", {})) if data["basic_details"]["visit_type"] == "Monthly" else "{}",
            json.dumps(data.get("media_files", []))
        ]
        sheet.append_row(row)
        return True
    except Exception as e:
        st.error(f"Error saving observation: {str(e)}")
        return False

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

[Rest of the original form sections (basic_details_section, teacher_selection_section, etc.) 
with modified classroom_observation_section to use the new handle_media_upload function]

# Modified classroom_observation_section to include new media upload
def classroom_observation_section():
    st.subheader("Classroom Observation")
    
    if "teacher_details" not in st.session_state:
        st.error("Please select teachers first")
        st.session_state.page = 2
        return
    
    all_teachers = (
        st.session_state.teacher_details["trained_teachers"] +
        st.session_state.teacher_details["untrained_teachers"]
    )
    
    if not all_teachers:
        st.error("No teachers selected")
        return
    
    tabs = st.tabs(all_teachers)
    observations = {}
    media_files = []
    
    for i, teacher in enumerate(all_teachers):
        with tabs[i]:
            # [Original metrics collection code]
            
            st.write("---")
            st.subheader("Media Upload")
            
            teacher_media = handle_media_upload(
                drive_service,
                teacher,
                st.session_state.basic_details["school_name"],
                st.session_state.basic_details["visit_date"],
                folder_id
            )
            
            if teacher_media:
                media_files.extend(teacher_media)
                st.write("Uploaded Files:")
                for file in teacher_media:
                    st.write(f"- [{file['name']}]({file['link']})")
    
    if media_files:
        st.session_state.media_files = media_files

    # [Rest of the original section code]

def main():
    st.title("School Observation Form")
    
    # Show progress
    total_pages = 5 if st.session_state.get('visit_type') == 'Monthly' else 3
    progress_text = f"Page {st.session_state.page} of {total_pages}"
    st.progress(st.session_state.page / total_pages, text=progress_text)
    
    # Display appropriate section
    if st.session_state.page == 1:
        basic_details_section()
    elif st.session_state.page == 2:
        teacher_selection_section()
    elif st.session_state.page == 3:
        classroom_observation_section()
    elif st.session_state.page == 4 and st.session_state.visit_type == "Monthly":
        infrastructure_section()
    elif st.session_state.page == 5 and st.session_state.visit_type == "Monthly":
        community_section()

if __name__ == "__main__":
    main()
