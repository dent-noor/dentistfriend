import streamlit as st
#from Dashboard import show_support
#from utils import show_footer

def chat():
    if st.session_state["logged_in"]:
        # ✅ Show logout on sidebar
        with st.sidebar:
            #st.markdown("---")
            if st.button("Logout", use_container_width=True):
                st.session_state.clear()
                st.rerun()
    st.title("Dental Scheduling System")
    st.markdown("## 🚧 Under Development...")
    st.markdown("The appointment scheduling feature is coming soon")

    # st.divider()
    #show_support()

chat()
#show_footer()
