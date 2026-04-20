import streamlit as st

def check_password():
    """Returns True if user entered correct password."""
    
    def password_entered():
        if st.session_state["password"] == st.secrets.get("password", "admin123"):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input(
            "🔒 Passwort", 
            type="password", 
            on_change=password_entered, 
            key="password"
        )
        st.info("Standard-Passwort: admin123")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input(
            "🔒 Passwort", 
            type="password", 
            on_change=password_entered, 
            key="password"
        )
        st.error("❌ Falsches Passwort")
        return False
    else:
        return True