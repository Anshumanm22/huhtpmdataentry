import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import json
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
import mimetypes

# Set page config
st.set_page_config(
    page_title="School Observation Form",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Google Sheets setup
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

@st.cache_resource
def connect_to_gsheets():
    """Create a Google Sheets client"""
    try:
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPES
        )
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {str(e)}")
        return None

def get_or_create_sheet(sheet_name):
    """Get or create a specific worksheet"""
    client = connect_to_gsheets()
    if not client:
        return None
        
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
            # Share with anyone who has the link
            workbook.share(None, perm_type='anyone', role='writer')
        
        sheet = workbook.add_worksheet(sheet_name, 1000, 20)
        
        # Set up headers based on sheet type
        if sheet_name == "Observations":
            headers = ["Timestamp", "PM Name", "School Name", "Visit Date", "Visit Type", 
                      "Teacher Details", "Observations", "Infrastructure Data", "Community Data"]
        elif sheet_name == "Schools":
            headers = ["School Name", "Program Manager", "Added Date"]
        elif sheet_name == "Teachers":
            headers = ["School Name", "Teacher Name", "Is Trained", "Added Date"]
        
        sheet.insert_row(headers, 1)
        return sheet
    
    return None

def get_program_managers():
    """Get list of all program managers from Schools sheet"""
    sheet = get_or_create_sheet("Schools")
    if not sheet:
        st.error("Unable to access schools data")
        return []
        
    try:
        schools_data = sheet.get_all_records()
        # Get unique PM names
        pm_names = list(set(school["Program Manager"] for school in schools_data))
        return sorted(pm_names)  # Sort alphabetically
    except Exception as e:
        st.error(f"Error fetching program managers: {str(e)}")
        return []


def get_pm_schools(pm_name):
    """Get schools for a specific program manager"""
    sheet = get_or_create_sheet("Schools")
    if not sheet:
        st.error("Unable to access schools data")
        return []
        
    try:
        schools_data = sheet.get_all_records()
        return [school["School Name"] for school in schools_data if school["Program Manager"].lower() == pm_name.lower()]
    except Exception as e:
        st.error(f"Error fetching schools: {str(e)}")
        return []

def get_school_teachers(school_name):
    """Get teachers for a specific school"""
    sheet = get_or_create_sheet("Teachers")
    if not sheet:
        st.error("Unable to access teachers data")
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

def save_observation(data):
    """Save observation data to Google Sheets"""
    sheet = get_or_create_sheet("Observations")
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
            json.dumps(data.get("community", {})) if data["basic_details"]["visit_type"] == "Monthly" else "{}"
        ]
        sheet.append_row(row)
        return True
    except Exception as e:
        st.error(f"Error saving observation: {str(e)}")
        return False

def add_new_teacher(school_name, teacher_name, is_trained):
    """Add a new teacher to the database"""
    sheet = get_or_create_sheet("Teachers")
    if not sheet:
        st.error("Unable to access teachers sheet")
        return False
        
    try:
        # Check if teacher already exists
        teachers_data = sheet.get_all_records()
        for teacher in teachers_data:
            if (teacher["School Name"] == school_name and 
                teacher["Teacher Name"].lower() == teacher_name.lower()):
                st.error("Teacher already exists in this school")
                return False
        
        row = [
            school_name,
            teacher_name,
            is_trained,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ]
        sheet.append_row(row)
        return True
    except Exception as e:
        st.error(f"Error adding teacher: {str(e)}")
        return False

# Initialize session state
if 'page' not in st.session_state:
    st.session_state.page = 1
    st.session_state.visit_type = 'Daily'

def basic_details_section():
    st.subheader("Basic Details")
    
    col1, col2 = st.columns(2)
    with col1:
        program_managers = get_program_managers()
        pm_name = st.selectbox(
            "Program Manager Name",
            options=program_managers if program_managers else ["No program managers found"],
            help="Select your name from the list"
        )
        if pm_name:
            schools = get_pm_schools(pm_name)
            school_name = st.selectbox(
                "School Name",
                options=schools if schools else ["No schools found"]
            )
    
    with col2:
        visit_date = st.date_input("Date of Visit", datetime.now())
        visit_type = st.selectbox("Visit Type", options=["Daily", "Monthly"])
        st.session_state.visit_type = visit_type
    
    if st.button("Next →", type="primary"):
        if pm_name and school_name != "No schools found":
            st.session_state.basic_details = {
                "pm_name": pm_name,
                "school_name": school_name,
                "visit_date": visit_date.strftime("%Y-%m-%d"),
                "visit_type": visit_type
            }
            st.session_state.page = 2
        else:
            st.error("Please fill in all fields")

def teacher_selection_section():
    st.subheader("Teacher Selection")
    
    if "basic_details" not in st.session_state:
        st.error("Please fill in basic details first")
        st.session_state.page = 1
        return
    
    school_name = st.session_state.basic_details["school_name"]
    teachers = get_school_teachers(school_name)
    
    with st.expander("Add New Teacher"):
        col1, col2 = st.columns([2, 1])
        with col1:
            new_teacher_name = st.text_input("New Teacher Name")
        with col2:
            training_status = st.radio(
                "Training Status",
                options=["Trained", "Untrained"],
                horizontal=True
            )
        if st.button("Add Teacher", key="add_teacher"):
            if new_teacher_name:
                if add_new_teacher(
                    school_name,
                    new_teacher_name,
                    training_status == "Trained"
                ):
                    st.success(f"Added teacher {new_teacher_name}")
                    st.rerun()
            else:
                st.error("Please enter teacher name")

    col1, col2 = st.columns(2)
    with col1:
        trained_teachers = st.multiselect(
            "Select Trained Teachers",
            options=teachers["trained"]
        )
    with col2:
        untrained_teachers = st.multiselect(
            "Select Untrained Teachers",
            options=teachers["untrained"]
        )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Previous"):
            st.session_state.page = 1
    with col2:
        if st.button("Next →", type="primary"):
            if trained_teachers or untrained_teachers:
                st.session_state.teacher_details = {
                    "trained_teachers": trained_teachers,
                    "untrained_teachers": untrained_teachers
                }
                st.session_state.page = 3
            else:
                st.error("Please select at least one teacher")

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
    
    for i, teacher in enumerate(all_teachers):
        with tabs[i]:
            col1, col2 = st.columns(2)
            with col1:
                st.write("Teacher Actions")
                teacher_metrics = {
                    "lesson_plan": st.selectbox(
                        "Has the teacher shared the lesson plan?",
                        options=["Yes", "No", "Sometimes"],
                        key=f"{teacher}_lesson_plan"
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
                st.write("Student Actions")
                student_metrics = {
                    "questions": st.selectbox(
                        "Are students asking questions?",
                        options=["Yes", "No", "Sometimes"],
                        key=f"{teacher}_questions"
                    ),
                    "explanation": st.selectbox(
                        "Are students explaining their work?",
                        options=["Yes", "No", "Sometimes"],
                        key=f"{teacher}_explanation"
                    ),
                    "involvement": st.selectbox(
                        "Are students involved in activities?",
                        options=["Yes", "No", "Sometimes"],
                        key=f"{teacher}_involvement"
                    )
                }
            # Add this after the student_metrics section for each teacher
st.write("---")
st.subheader("Media Upload")
media_files = handle_media_upload(
    teacher,
    st.session_state.basic_details["school_name"],
    st.session_state.basic_details["visit_date"]
)
if media_files:
    st.write("Uploaded Files:")
    for file in media_files:
        st.write(f"- [{file['name']}]({file['link']})")

observations[teacher].update({
    "media_files": media_files
})
            observations[teacher] = {
                "teacher_metrics": teacher_metrics,
                "student_metrics": student_metrics
            }
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Previous"):
            st.session_state.page = 2
    with col2:
        next_text = "Next →" if st.session_state.visit_type == "Monthly" else "Submit"
        if st.button(next_text, type="primary"):
            st.session_state.observations = observations
            if st.session_state.visit_type == "Monthly":
                st.session_state.page = 4
            else:
                submit_form()

def infrastructure_section():
    if st.session_state.visit_type != "Monthly":
        st.session_state.page = 3
        return
    
    st.subheader("Infrastructure Assessment")
    
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
    
    st.session_state.infrastructure = infrastructure_data
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Previous"):
            st.session_state.page = 3
    with col2:
        if st.button("Next →", type="primary"):
            st.session_state.page = 5

def community_section():
    if st.session_state.visit_type != "Monthly":
        st.session_state.page = 3
        return
    
    st.subheader("Community Engagement")
    
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
    
    st.session_state.community = community_data
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Previous"):
            st.session_state.page = 4
    with col2:
        if st.button("Submit", type="primary"):
            submit_form()

def submit_form():
    form_data = {
        "basic_details": st.session_state.basic_details,
        "teacher_details": st.session_state.teacher_details,
        "observations": st.session_state.get("observations", {}),
        "infrastructure": st.session_state.get("infrastructure", {}) if st.session_state.visit_type == "Monthly" else {},
        "community": st.session_state.get("community", {}) if st.session_state.visit_type == "Monthly" else {}
    }
    
    if save_observation(form_data):
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
    
    # Show progress based on visit type
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
