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

def basic_details_section():
    st.header("Basic Details")
    
    col1, col2 = st.columns(2)
    with col1:
        pm_name = st.text_input("Program Manager Name")
        if pm_name:
            schools = get_pm_schools(pm_name)
            school_name = st.selectbox("School Name", options=schools if schools else ["No schools found"])
    
    with col2:
        visit_date = st.date_input("Date of Visit", datetime.now())
        visit_type = st.selectbox("Visit Type", options=["Daily", "Monthly"])
    
    if st.button("Next →"):
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
    st.header("Teacher Selection")
    
    if "basic_details" not in st.session_state:
        st.error("Please fill in basic details first")
        st.session_state.page = 1
        return
    
    school_name = st.session_state.basic_details["school_name"]
    teachers = get_school_teachers(school_name)
    
    st.subheader("Trained Teachers")
    trained_teachers = st.multiselect(
        "Select trained teachers to observe",
        options=teachers["trained"]
    )
    
    st.subheader("Untrained Teachers")
    untrained_teachers = st.multiselect(
        "Select untrained teachers to observe",
        options=teachers["untrained"]
    )
    
    # Option to add new teacher
    if st.checkbox("Add New Teacher"):
        new_teacher_name = st.text_input("New Teacher Name")
        training_status = st.radio(
            "Training Status",
            options=["Trained", "Untrained"]
        )
        if st.button("Add Teacher"):
            if add_new_teacher(
                school_name,
                new_teacher_name,
                training_status == "Trained"
            ):
                st.success(f"Added teacher {new_teacher_name}")
                st.experimental_rerun()
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Previous"):
            st.session_state.page = 1
    with col2:
        if st.button("Next →"):
            if trained_teachers or untrained_teachers:
                st.session_state.teacher_details = {
                    "trained_teachers": trained_teachers,
                    "untrained_teachers": untrained_teachers
                }
                st.session_state.page = 3
            else:
                st.error("Please select at least one teacher")

def classroom_observation_section():
    st.header("Classroom Observation")
    
    if "teacher_details" not in st.session_state:
        st.error("Please select teachers first")
        st.session_state.page = 2
        return
    
    observations = {}
    
    all_teachers = (
        st.session_state.teacher_details["trained_teachers"] +
        st.session_state.teacher_details["untrained_teachers"]
    )
    
    for teacher in all_teachers:
        st.subheader(f"Observation for {teacher}")
        
        # Teacher actions
        st.write("Teacher Actions")
        teacher_metrics = {
            "lesson_plan": st.selectbox(
                "Has the teacher shared the lesson plan in advance?",
                options=["Yes", "No", "Sometimes"],
                key=f"{teacher}_lesson_plan"
            ),
            "movement": st.selectbox(
                "Is the teacher moving around in the classroom?",
                options=["Yes", "No", "Sometimes"],
                key=f"{teacher}_movement"
            ),
            "activities": st.selectbox(
                "Is the teacher using hands-on activities?",
                options=["Yes", "No", "Sometimes"],
                key=f"{teacher}_activities"
            )
        }
        
        # Student actions
        st.write("Student Actions")
        student_metrics = {
            "questions": st.selectbox(
                "Are children asking questions?",
                options=["Yes", "No", "Sometimes"],
                key=f"{teacher}_questions"
            ),
            "explanation": st.selectbox(
                "Are children explaining their work?",
                options=["Yes", "No", "Sometimes"],
                key=f"{teacher}_explanation"
            ),
            "involvement": st.selectbox(
                "Are children involved in the activities?",
                options=["Yes", "No", "Sometimes"],
                key=f"{teacher}_involvement"
            )
        }
        
        observations[teacher] = {
            "teacher_metrics": teacher_metrics,
            "student_metrics": student_metrics
        }
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Previous"):
            st.session_state.page = 2
    with col2:
        if st.button("Next →"):
            st.session_state.observations = observations
            st.session_state.page = 4

def infrastructure_section():
    st.header("Infrastructure Assessment")
    
    if st.session_state.basic_details["visit_type"] == "Monthly":
        subjects = ["Mathematics", "Science", "Language", "Social Studies"]
        infrastructure_data = {}
        
        for subject in subjects:
            st.subheader(f"{subject} Infrastructure")
            infrastructure_data[subject] = {
                "materials": st.selectbox(
                    f"Are learning materials available for {subject}?",
                    options=["Yes", "No", "Partial"],
                    key=f"{subject}_materials"
                ),
                "storage": st.selectbox(
                    f"Is there proper storage for {subject} materials?",
                    options=["Yes", "No", "Partial"],
                    key=f"{subject}_storage"
                ),
                "condition": st.selectbox(
                    f"What is the condition of {subject} materials?",
                    options=["Good", "Fair", "Poor"],
                    key=f"{subject}_condition"
                )
            }
        
        st.session_state.infrastructure = infrastructure_data
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Previous"):
            st.session_state.page = 3
    with col2:
        if st.button("Next →"):
            st.session_state.page = 5

def community_section():
    st.header("Community Engagement")
    
    if st.session_state.basic_details["visit_type"] == "Monthly":
        community_data = {
            "parent_meetings": st.number_input(
                "Number of parent meetings conducted this month",
                min_value=0
            ),
            "parent_attendance": st.slider(
                "Average parent attendance percentage",
                0, 100, 50
            ),
            "community_events": st.number_input(
                "Number of community events organized",
                min_value=0
            ),
            "smc_meetings": st.number_input(
                "Number of School Management Committee meetings",
                min_value=0
            )
        }
        
        community_data["notes"] = st.text_area(
            "Additional community engagement notes"
        )
        
        st.session_state.community = community_data
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Previous"):
            st.session_state.page = 4
    with col2:
        if st.button("Submit Form"):
            # Compile all data
            form_data = {
                "basic_details": st.session_state.basic_details,
                "teacher_details": st.session_state.teacher_details,
                "observations": st.session_state.get("observations", {}),
                "infrastructure": st.session_state.get("infrastructure", {}),
                "community": st.session_state.get("community", {})
            }
            
            if save_observation(form_data):
                st.success("Form submitted successfully!")
                st.session_state.page = 1  # Reset to first page
                # Clear session state except page number
                for key in list(st.session_state.keys()):
                    if key != "page":
                        del st.session_state[key]
            else:
                st.error("Error submitting form. Please try again.")

def main():
    st.title("School Observation Form")
    
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

if __name__ == "__main__":
    main()
