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
        # Debug: Check if secrets are loaded
        if "gcp_service_account" not in st.secrets:
            st.error("gcp_service_account not found in secrets")
            return None, None
            
        # Debug: Check service account structure
        required_fields = ["type", "project_id", "private_key", "client_email"]
        missing_fields = [field for field in required_fields if field not in st.secrets["gcp_service_account"]]
        if missing_fields:
            st.error(f"Missing required fields in service account: {missing_fields}")
            return None, None
            
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
        services = get_google_services()
        if not services or None in services:
            st.error("Failed to initialize Google services")
            self.drive_service = None
            self.sheets_service = None
            self.pm_school_mapping = {}
            self.school_teacher_mapping = {}
        else:
            self.drive_service, self.sheets_service = services
            self.SHEET_ID = "1V6aftxdLQs-ZCbqxQo5Bt-JZf6Md3HyN5CbRZz3vzrM"  # Your sheet ID
            self.load_mappings()
        self.setup_sidebar()
        
    def load_mappings(self):
        """Load school and teacher data from Google Sheets"""
        if not self.sheets_service:
            st.error("Google Sheets service not available")
            return
            
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
    
    def setup_sidebar(self):
        """Setup sidebar navigation"""
        with st.sidebar:
            st.header("Visit Form Sections")
            current_section = st.session_state.page
            sections = [
                "Basic Details",
                "Teacher Selection",
                "Classroom Observation",
                "Infrastructure (Monthly)",
                "Community Engagement (Monthly)"
            ]
            
            for i, section in enumerate(sections, 1):
                if i == current_section:
                    st.markdown(f"**→ {i}. {section}**")
                else:
                    st.markdown(f"{i}. {section}")

    def section_1_basic_details(self):
        """Basic Details Form Section"""
        st.header("Basic Details")
        
        if not self.pm_school_mapping:
            st.error("Unable to load Program Manager mappings. Please check the configuration.")
            return
            
        col1, col2 = st.columns(2)
        with col1:
            pm_name = st.selectbox(
                "Program Manager",
                options=list(self.pm_school_mapping.keys())
            )
            
            if pm_name:
                school_options = self.pm_school_mapping[pm_name]
                school_name = st.selectbox(
                    "School",
                    options=school_options
                )
        
        with col2:
            visit_date = st.date_input("Date of Visit")
            visit_type = st.selectbox(
                "Visit Type",
                options=["Daily", "Monthly"]
            )
        
        if st.button("Next →", type="primary"):
            if pm_name and school_name and visit_date:
                st.session_state.form_data.update({
                    "pm_name": pm_name,
                    "school_name": school_name,
                    "visit_date": visit_date.strftime("%Y-%m-%d"),
                    "visit_type": visit_type
                })
                st.session_state.page = 2
                st.rerun()
            else:
                st.error("Please fill all required fields")

    def section_2_teacher_selection(self):
        """Teacher Selection Form Section"""
        st.header("Teacher Selection")
        
        if "school_name" not in st.session_state.form_data:
            st.error("Please complete basic details first")
            st.session_state.page = 1
            return
        
        school = st.session_state.form_data["school_name"]
        teachers = self.school_teacher_mapping.get(school, {"trained": [], "untrained": []})
        
        col1, col2 = st.columns(2)
        with col1:
            selected_trained = st.multiselect(
                "Select Trained Teachers",
                options=teachers["trained"]
            )
        
        with col2:
            selected_untrained = st.multiselect(
                "Select Untrained Teachers",
                options=teachers["untrained"]
            )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Previous"):
                st.session_state.page = 1
                st.rerun()
        
        with col2:
            if st.button("Next →", type="primary"):
                if selected_trained or selected_untrained:
                    st.session_state.form_data.update({
                        "trained_teachers": selected_trained,
                        "untrained_teachers": selected_untrained
                    })
                    st.session_state.page = 3
                    st.rerun()
                else:
                    st.error("Please select at least one teacher")

    def section_3_classroom_observation(self):
        """Classroom Observation Form Section"""
        st.header("Classroom Observation")
        
        if "trained_teachers" not in st.session_state.form_data:
            st.error("Please select teachers first")
            st.session_state.page = 2
            return
        
        all_teachers = (
            st.session_state.form_data["trained_teachers"] +
            st.session_state.form_data["untrained_teachers"]
        )
        
        if not all_teachers:
            st.error("No teachers selected")
            return
        
        tabs = st.tabs(all_teachers)
        observations = {}
        
        for i, teacher in enumerate(all_teachers):
            with tabs[i]:
                st.subheader(f"Observing {teacher}")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("##### Teacher Actions")
                    teacher_metrics = {
                        "lesson_plan": st.selectbox(
                            "Has the teacher shared the lesson plan?",
                            options=["Yes", "No", "Sometimes"],
                            key=f"{teacher}_lesson"
                        ),
                        "movement": st.selectbox(
                            "Is the teacher moving around?",
                            options=["Yes", "No", "Sometimes"],
                            key=f"{teacher}_movement"
                        ),
                        "activities": st.selectbox(
                            "Is the teacher using hands-on activities?",
                            options=["Yes", "No", "Sometimes"],
                            key=f"{teacher}_activities"
                        )
                    }
                
                with col2:
                    st.markdown("##### Student Actions")
                    student_metrics = {
                        "questions": st.selectbox(
                            "Are students asking questions?",
                            options=["Yes", "No", "Sometimes"],
                            key=f"{teacher}_questions"
                        ),
                        "participation": st.selectbox(
                            "Are students participating in activities?",
                            options=["Yes", "No", "Sometimes"],
                            key=f"{teacher}_participation"
                        ),
                        "peer_learning": st.selectbox(
                            "Are students helping each other learn?",
                            options=["Yes", "No", "Sometimes"],
                            key=f"{teacher}_peer"
                        )
                    }
                
                observations[teacher] = {
                    "teacher_metrics": teacher_metrics,
                    "student_metrics": student_metrics
                }
        
        st.session_state.form_data["observations"] = observations
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Previous"):
                st.session_state.page = 2
                st.rerun()
        
        with col2:
            next_button = "Next →" if st.session_state.form_data["visit_type"] == "Monthly" else "Submit"
            if st.button(next_button, type="primary"):
                if st.session_state.form_data["visit_type"] == "Monthly":
                    st.session_state.page = 4
                else:
                    self.save_form_data()
                st.rerun()

    def section_4_infrastructure(self):
        """Infrastructure Assessment Form Section"""
        st.header("Infrastructure Assessment")
        
        if st.session_state.form_data["visit_type"] != "Monthly":
            st.session_state.page = 3
            return
        
        subjects = ["Mathematics", "Science", "Language", "Social Studies"]
        infrastructure_data = {}
        
        for subject in subjects:
            with st.expander(f"{subject} Infrastructure", expanded=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    materials = st.selectbox(
                        "Learning materials available?",
                        options=["Yes", "No", "Partial"],
                        key=f"{subject}_materials"
                    )
                with col2:
                    storage = st.selectbox(
                        "Proper storage available?",
                        options=["Yes", "No", "Partial"],
                        key=f"{subject}_storage"
                    )
                with col3:
                    condition = st.selectbox(
                        "Material condition",
                        options=["Good", "Fair", "Poor"],
                        key=f"{subject}_condition"
                    )
                
                infrastructure_data[subject] = {
                    "materials": materials,
                    "storage": storage,
                    "condition": condition
                }
        
        st.session_state.form_data["infrastructure"] = infrastructure_data
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Previous"):
                st.session_state.page = 3
                st.rerun()
        
        with col2:
            if st.button("Next →", type="primary"):
                st.session_state.page = 5
                st.rerun()

    def section_5_community(self):
        """Community Engagement Form Section"""
        st.header("Community Engagement")
        
        if st.session_state.form_data["visit_type"] != "Monthly":
            st.session_state.page = 3
            return
        
        col1, col2 = st.columns(2)
        with col1:
            community_data = {
                "parent_meetings": st.number_input(
                    "Number of parent meetings this month",
                    min_value=0
                ),
                "parent_attendance": st.slider(
                    "Average parent attendance (%)",
                    0, 100, 50
                )
            }
        
        with col2:
            community_data.update({
                "community_events": st.number_input(
                    "Number of community events",
                    min_value=0
                ),
                "smc_meetings": st.number_input(
                    "Number of SMC meetings",
                    min_value=0
                )
            })
        
        community_data["notes"] = st.text_area(
            "Additional Notes"
        )
        
        st.session_state.form_data["community"] = community_data
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Previous"):
                st.session_state.page = 4
                st.rerun()
        
        with col2:
            if st.button("Submit", type="primary"):
                self.save_form_data()
                st.rerun()

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
