import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd
from datetime import datetime

# Set page config
st.set_page_config(page_title="PM Visit Form", layout="wide")

# Initialize session state
if 'page' not in st.session_state:
    st.session_state.page = 1
if 'form_data' not in st.session_state:
    st.session_state.form_data = {}

@st.cache_resource
def get_google_services():
    """Get Google Drive and Sheets services using service account."""
    try:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=['https://www.googleapis.com/auth/drive.file',
                   'https://www.googleapis.com/auth/spreadsheets']
        )
        
        drive_service = build('drive', 'v3', credentials=credentials)
        sheets_service = build('sheets', 'v4', credentials=credentials)
        
        return drive_service, sheets_service
    except Exception as e:
        st.error(f"Error setting up Google services: {str(e)}")
        return None, None

class VisitFormApp:
    def __init__(self):
        self.drive_service, self.sheets_service = get_google_services()
        self.SHEET_ID = "YOUR_SHEET_ID"  # Replace with your sheet ID
        self.load_mappings()
        self.setup_sidebar()
        
    def load_mappings(self):
        """Load school and teacher data from Google Sheets"""
        try:
            # Load Schools data
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.SHEET_ID,
                range='Schools!A:B'  # Assuming column A is PM, column B is School
            ).execute()
            
            schools_values = result.get('values', [])
            if not schools_values:
                raise ValueError("No data found in Schools sheet")
                
            schools_df = pd.DataFrame(schools_values[1:], columns=schools_values[0])
            self.pm_school_mapping = schools_df.groupby('Program Manager')['School'].apply(list).to_dict()
            
            # Load Teachers data
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.SHEET_ID,
                range='Teachers!A:C'  # Assuming columns: School, Teacher Name, Training Status
            ).execute()
            
            teachers_values = result.get('values', [])
            if not teachers_values:
                raise ValueError("No data found in Teachers sheet")
                
            teachers_df = pd.DataFrame(teachers_values[1:], columns=teachers_values[0])
            
            # Process teacher mapping
            self.school_teacher_mapping = {}
            for school in teachers_df['School'].unique():
                school_data = teachers_df[teachers_df['School'] == school]
                self.school_teacher_mapping[school] = {
                    'trained': school_data[school_data['Training Status'] == 'Trained']['Teacher Name'].tolist(),
                    'untrained': school_data[school_data['Training Status'] == 'Untrained']['Teacher Name'].tolist()
                }
                
        except Exception as e:
            st.error(f"Error loading mappings: {str(e)}")
            self.pm_school_mapping = {}
            self.school_teacher_mapping = {}

    def save_form_data(self):
        """Save form data to Observations tab"""
        try:
            # Format data for the observations sheet
            data = [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Timestamp
                st.session_state.form_data["pm_name"],         # Program Manager
                st.session_state.form_data["school_name"],     # School
                st.session_state.form_data["visit_date"],      # Visit Date
                st.session_state.form_data["visit_type"]       # Visit Type
            ]
            
            # Add teacher observations
            observations = st.session_state.form_data.get("observations", {})
            for teacher, metrics in observations.items():
                teacher_data = [
                    teacher,
                    # Teacher metrics
                    metrics['teacher_metrics'].get('lesson_plan', ''),
                    metrics['teacher_metrics'].get('movement', ''),
                    metrics['teacher_metrics'].get('activities', ''),
                    # Student metrics
                    metrics['student_metrics'].get('questions', ''),
                    metrics['student_metrics'].get('participation', ''),
                    metrics['student_metrics'].get('peer_learning', '')
                ]
                data.extend(teacher_data)
            
            # Add infrastructure data if monthly visit
            if st.session_state.form_data["visit_type"] == "Monthly":
                infrastructure = st.session_state.form_data.get("infrastructure", {})
                infra_data = []
                for subject, metrics in infrastructure.items():
                    infra_data.extend([
                        metrics.get('materials', ''),
                        metrics.get('storage', ''),
                        metrics.get('condition', '')
                    ])
                data.extend(infra_data)
            
            # Append to Observations sheet
            body = {
                'values': [data]
            }
            
            result = self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.SHEET_ID,
                range='Observations!A1',
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            st.success("Form data saved successfully!")
            st.session_state.page = 1
            st.session_state.form_data = {}
            
        except Exception as e:
            st.error(f"Error saving form data: {str(e)}")
            st.error(str(e))

    # [Rest of the class methods remain the same...]

    def run(self):
        """Main app entry point"""
        st.title("Program Manager Visit Form")
        
        if st.session_state.page == 1:
            self.section_1_basic_details()
        elif st.session_state.page == 2:
            self.section_2_teacher_selection()
        elif st.session_state.page == 3:
            self.section_3_classroom_observation()
        elif st.session_state.page == 4:
            self.section_4_infrastructure()
        elif st.session_state.page == 5:
            self.section_5_community()

if __name__ == "__main__":
    app = VisitFormApp()
    app.run()
