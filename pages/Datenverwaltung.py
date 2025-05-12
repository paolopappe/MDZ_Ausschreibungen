import streamlit as st
from uuid import uuid4

from utils.db_management import _db_manager


def init_page() -> None:
    st.set_page_config(
        page_title="Datenverwaltung",
        initial_sidebar_state="expanded",
    )
    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = str(uuid4())


def make_title() -> None:
    # Titel der App
    st.title("Ihre Daten")
    

def get_filepaths():
    return list(_db_manager._file_index.keys())


def update_uploader_key():
    st.session_state.uploader_key = str(uuid4())


def show_data_management_area():

    init_page()
    make_title()
    
	# enlist all the data and add the possibility to modify it
    if (filepaths := get_filepaths()):
        with st.container(border=True):
            for i, filepath in enumerate(filepaths):
                filename_col, deletion_col = st.columns([6, 1])
                filename_col.markdown(f"**{filepath}**")
                with deletion_col.popover("🗑️"):
                    st.text("Löschen Datei?")
                    if st.button("Ja", key=i):
                        _db_manager.delete_pdf(filepath)
                        st.rerun()  # update tables und so

    if not len(_db_manager):
        st.info("Sie haben noch keine Daten hochgeladen.")
                
    if filepaths:
        st.markdown(f"Total Chunks: {len(_db_manager)}")

    st.subheader("Weitere Daten laden" if filepaths else "Daten laden")
    uploaded_files = st.file_uploader(
        "Weitere Daten laden",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key=st.session_state.uploader_key   # every type a new key to clear the state 
    )
    if uploaded_files:
        with st.spinner("Ihre Daten werden vorbereitet. Es kann wenige Minuten dauern."):
            for i, uploaded_file in enumerate(uploaded_files):
                bytes_data = uploaded_file.getvalue()
                _db_manager.add_pdf(uploaded_file.name, bytes_data)
        update_uploader_key()
        st.rerun()  # update tables und so

    
if __name__ == "__main__":
    show_data_management_area()