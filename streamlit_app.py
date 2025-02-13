import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import json

# Set page config with improved layout and theme
st.set_page_config(
    page_title="School Observation Form",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Add custom CSS for better button visibility and form layout
st.markdown("""
    <style>
    .stButton > button {
        width: 100%;
        margin-top: 20px;
        margin-bottom: 20px;
        background-color: #ff4c4c;
        color: white;
    }
    .nav-button {
        padding: 15px 30px;
        font-size: 16px;
    }
    .form-header {
        margin-bottom: 30px;
    }
    </style>
""", unsafe_allow_html=True)

# Google Sheets setup remains the same
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

@st.cache_resource
def connect_to_gsheets():
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    return gspread.authorize(credentials)

def get_or_create_sheet(sheet_name):
    # Previous implementation remains the same
    pass

# Initialize session state with default values
if 'page' not in st.session_state:
    st.session_state.page = 1
    st.session_state.visit_type = 'Daily'  # Default visit type

def basic_details_section():
    st.markdown("<h2 class='form-header'>Basic Details</h2>", unsafe_allow_html=True)
    
    # Create three columns for better spacing
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        pm_name = st.text_input("Program Manager Name", 
                               help="Enter your full name as registered")
    
    with col2:
        # Only show schools if PM name is entered
        if pm_name:
            schools = get_pm_schools(pm_name)
            school_name = st.selectbox(
                "School Name",
                options=schools if schools else ["No schools found"],
                help="Select the school you are visiting"
            )
        else:
            school_name = None
            st.info("Enter Program Manager name to see schools")
    
    with col3:
        visit_date = st.date_input(
            "Date of Visit",
            datetime.now(),
            help="Select the date of your visit"
        )
        
    # Visit type selector with immediate effect
    visit_type = st.radio(
        "Visit Type",
        options=["Daily", "Monthly"],
        horizontal=True,
        help="Monthly visits include additional infrastructure and community sections"
    )
    st.session_state.visit_type = visit_type
    
    # Clear "Next" button at the bottom
    if st.button("Continue to Teacher Selection →", type="primary"):
        if pm_name and school_name != "No schools found":
            st.session_state.basic_details = {
                "pm_name": pm_name,
                "school_name": school_name,
                "visit_date": visit_date.strftime("%Y-%m-%d"),
                "visit_type": visit_type
            }
            st.session_state.page = 2
        else:
            st.error("Please fill in all required fields")

def teacher_selection_section():
    st.markdown("<h2 class='form-header'>Teacher Selection</h2>", unsafe_allow_html=True)
    
    if "basic_details" not in st.session_state:
        st.error("Please fill in basic details first")
        st.session_state.page = 1
        return
    
    school_name = st.session_state.basic_details["school_name"]
    
    # Add new teacher in an expander to reduce visual clutter
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
                if add_new_teacher(school_name, new_teacher_name, training_status == "Trained"):
                    st.success(f"Added teacher {new_teacher_name}")
                    st.rerun()
            else:
                st.error("Please enter teacher name")

    # Get existing teachers
    teachers = get_school_teachers(school_name)
    
    # Display existing teachers in two columns
    col1, col2 = st.columns(2)
    with col1:
        trained_teachers = st.multiselect(
            "Select Trained Teachers to Observe",
            options=teachers["trained"]
        )
    with col2:
        untrained_teachers = st.multiselect(
            "Select Untrained Teachers to Observe",
            options=teachers["untrained"]
        )
    
    # Navigation buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back to Basic Details", key="back_to_basic"):
            st.session_state.page = 1
    with col2:
        if st.button("Continue to Observations →", type="primary", key="to_observations"):
            if trained_teachers or untrained_teachers:
                st.session_state.teacher_details = {
                    "trained_teachers": trained_teachers,
                    "untrained_teachers": untrained_teachers
                }
                st.session_state.page = 3
            else:
                st.error("Please select at least one teacher to observe")

def classroom_observation_section():
    st.markdown("<h2 class='form-header'>Classroom Observation</h2>", unsafe_allow_html=True)
    
    if "teacher_details" not in st.session_state:
        st.error("Please select teachers first")
        st.session_state.page = 2
        return
    
    all_teachers = (
        st.session_state.teacher_details["trained_teachers"] +
        st.session_state.teacher_details["untrained_teachers"]
    )
    
    # Create tabs for each teacher
    tabs = st.tabs(all_teachers)
    observations = {}
    
    for i, teacher in enumerate(all_teachers):
        with tabs[i]:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Teacher Actions")
                teacher_metrics = {
                    "lesson_plan": st.selectbox(
                        "Lesson plan shared in advance?",
                        options=["Yes", "No", "Sometimes"],
                        key=f"{teacher}_lesson_plan"
                    ),
                    "movement": st.selectbox(
                        "Moving around classroom?",
                        options=["Yes", "No", "Sometimes"],
                        key=f"{teacher}_movement"
                    ),
                    "activities": st.selectbox(
                        "Using hands-on activities?",
                        options=["Yes", "No", "Sometimes"],
                        key=f"{teacher}_activities"
                    )
                }
            
            with col2:
                st.subheader("Student Actions")
                student_metrics = {
                    "questions": st.selectbox(
                        "Students asking questions?",
                        options=["Yes", "No", "Sometimes"],
                        key=f"{teacher}_questions"
                    ),
                    "explanation": st.selectbox(
                        "Students explaining work?",
                        options=["Yes", "No", "Sometimes"],
                        key=f"{teacher}_explanation"
                    ),
                    "involvement": st.selectbox(
                        "Students involved in activities?",
                        options=["Yes", "No", "Sometimes"],
                        key=f"{teacher}_involvement"
                    )
                }
            
            observations[teacher] = {
                "teacher_metrics": teacher_metrics,
                "student_metrics": student_metrics
            }
    
    # Navigation
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("← Back", key="back_to_teachers"):
            st.session_state.page = 2
    with col3:
        next_text = "Continue to Infrastructure →" if st.session_state.visit_type == "Monthly" else "Submit Form"
        if st.button(next_text, type="primary", key="next_from_obs"):
            st.session_state.observations = observations
            if st.session_state.visit_type == "Monthly":
                st.session_state.page = 4
            else:
                submit_form()

def infrastructure_section():
    if st.session_state.visit_type != "Monthly":
        st.session_state.page = 3
        return
        
    st.markdown("<h2 class='form-header'>Infrastructure Assessment</h2>", unsafe_allow_html=True)
    
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
    
    # Navigation
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back to Observations"):
            st.session_state.page = 3
    with col2:
        if st.button("Continue to Community →", type="primary"):
            st.session_state.page = 5

def community_section():
    if st.session_state.visit_type != "Monthly":
        st.session_state.page = 3
        return
        
    st.markdown("<h2 class='form-header'>Community Engagement</h2>", unsafe_allow_html=True)
    
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
        "Additional Notes",
        placeholder="Enter any additional observations or comments..."
    )
    
    st.session_state.community = community_data
    
    # Navigation
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back to Infrastructure"):
            st.session_state.page = 4
    with col2:
        if st.button("Submit Form", type="primary"):
            submit_form()

def submit_form():
    """Handle form submission and data saving"""
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
    
    # Show progress only for Monthly visits when appropriate
    if st.session_state.get('visit_type') == 'Monthly':
        progress_text = f"Page {st.session_state.page} of 5"
        st.progress(st.session_state.page / 5, text=progress_text)
    elif st.session_state.get('visit_type') == 'Daily':
        progress_text = f"Page {st.session_state.page} of 3"
        st.progress(st.session_state.page / 3, text=progress_text)
    
    # Display appropriate section based on current page and visit type
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
