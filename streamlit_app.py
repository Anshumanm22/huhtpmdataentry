# app.py
from .utility import get_google_services
from .form_sections import (
    basic_details_section, 
    teacher_selection_section,
    classroom_observation_section, 
    infrastructure_section,
    community_section, 
    save_observation
)

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
