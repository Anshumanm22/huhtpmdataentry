
# form_sections.py
import streamlit as st
from datetime import datetime
from utils import *

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

def add_new_teacher(sheets_client, school_name, teacher_name, is_trained):
    """Add a new teacher to the database"""
    sheet = get_or_create_sheet(sheets_client, "Teachers")
    if not sheet:
        return False
    
    try:
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

def save_observation(sheets_client, data):
    """Save observation data to Google Sheets"""
    sheet = get_or_create_sheet(sheets_client, "Observations")
    if not sheet:
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

def basic_details_section(sheets_client):
    st.subheader("Basic Details")
    
    col1, col2 = st.columns(2)
    with col1:
        program_managers = get_program_managers(sheets_client)
        pm_name = st.selectbox(
            "Program Manager Name",
            options=program_managers if program_managers else ["No program managers found"]
        )
        if pm_name:
            schools = get_pm_schools(sheets_client, pm_name)
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

def teacher_selection_section(sheets_client):
    st.subheader("Teacher Selection")
    
    if "basic_details" not in st.session_state:
        st.error("Please fill in basic details first")
        st.session_state.page = 1
        return
    
    school_name = st.session_state.basic_details["school_name"]
    teachers = get_school_teachers(sheets_client, school_name)
    
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
                    sheets_client,
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

# form_sections.py (continued)

def classroom_observation_section(drive_service, folder_id):
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
                    ),
                    "encouragement": st.selectbox(
                        "Is the teacher encouraging participation?",
                        options=["Yes", "No", "Sometimes"],
                        key=f"{teacher}_encouragement"
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
                    ),
                    "peer_learning": st.selectbox(
                        "Are students helping each other learn?",
                        options=["Yes", "No", "Sometimes"],
                        key=f"{teacher}_peer_learning"
                    )
                }
            
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
            
            observations[teacher] = {
                "teacher_metrics": teacher_metrics,
                "student_metrics": student_metrics
            }
    
    if media_files:
        st.session_state.media_files = media_files
    
    st.session_state.observations = observations
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Previous"):
            st.session_state.page = 2
    with col2:
        next_text = "Next →" if st.session_state.visit_type == "Monthly" else "Submit"
        if st.button(next_text, type="primary"):
            if st.session_state.visit_type == "Monthly":
                st.session_state.page = 4
            else:
                return True

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
            return True
    
    return False
