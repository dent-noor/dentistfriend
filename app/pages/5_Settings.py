import json
import streamlit as st
from firebase_admin import firestore
from utils import show_footer, get_currency_symbol

# Load default data from JSON file
with open("app/data.json", "r") as file:
    default_data = json.load(file)


def main():
    if st.session_state["logged_in"]:
        # ✅ Show logout on sidebar
        with st.sidebar:
            #st.markdown("---")
            if st.button("Logout", use_container_width=True):
                st.session_state.clear()
                st.rerun()
    st.title("⚙️ Doctor Settings")

    # Check if user is authenticated
    if st.session_state.get("doctor_email") is None:
        st.error("Doctor Authentication Required: Please log in to access settings")
        return

    # Initialize Firestore database client and retrieve doctor information
    database = firestore.client()
    doctor_email = st.session_state.get("doctor_email")
    doctor_settings = load_settings(database, doctor_email)

    # Create tabs for different setting categories
    tab1, tab2, tab3 = st.tabs(["Treatment Procedures", "Dental Chart", "Currency Settings"])

    with tab1:
        # Show the updated treatments management interface
        manage_treatments(database, doctor_email, doctor_settings)

    with tab2:
        show_chart()

    with tab3:
        show_currency(database, doctor_email, doctor_settings)


def load_settings(database, doctor_email):
    """Load doctor settings from Firestore or create default settings if none exist."""
    try:
        doctor_ref = database.collection("doctors").document(doctor_email)
        settings_doc = doctor_ref.collection("settings").document("config").get()

        # Check if settings document exists
        if settings_doc.exists:
            settings = settings_doc.to_dict()
        else:
            # Create default settings if none exist
            settings = {
                "treatment_procedures": ["Cleaning"],
                "price_estimates": {"Cleaning": 100},
                "currency": "SAR"
            }
            save_settings(database, doctor_email, settings)

        return settings
    except Exception as e:
        st.error(f"Settings load failed: {e}")


def save_settings(database, doctor_email, settings):
    """Save updated settings to Firestore database."""
    try:
        doctor_ref = database.collection("doctors").document(doctor_email)
        doctor_ref.collection("settings").document("config").set(settings)
    except Exception as e:
        st.error(f"Settings save failed: {e}")


def manage_treatments(database, doctor_email, doctor_settings):
    """Display and manage treatment procedures, prices, and delete functionality."""

    # Add custom CSS to align the delete button
    st.markdown("""
        <style>
        .stButton button {
            margin-top: 25px;  /* Aligns with input box */
            height: 42px;      /* Match input box height */
            padding: 0px;      /* Reduce padding */
        }
        div[data-testid="column"] > div:has(button) {
            height: fit-content;
            flex-grow: 0;
        }
        </style>
    """, unsafe_allow_html=True)

    st.header("Treatment Procedures Configuration")
    st.info("Manage your treatment procedures and their associated prices")

    # Get current currency symbol for display
    currency_symbol = get_currency_symbol(doctor_settings.get("currency", "SAR"))

    # Extract current procedures and prices from settings
    procedures = doctor_settings.get("treatment_procedures", [])
    prices = doctor_settings.get("price_estimates", {})

    # Container for treatment procedures
    if procedures:
        to_delete = []

        for i, procedure in enumerate(procedures):
            cols = st.columns([5, 3, 0.6])  # Adjusted column ratio for better alignment
            with cols[0]:
                new_name = st.text_input(
                    f"Procedure {i + 1}",
                    value=procedure,
                    key=f"procedure_{i}"
                ).title()
                procedures[i] = new_name

            with cols[1]:
                prices[procedure] = st.number_input(
                    f"Price ({currency_symbol})",
                    min_value=0.0,
                    value=float(prices.get(procedure, 0)),
                    step=10.0,
                    format="%.2f",
                    key=f"price_{procedure}"
                )

            with cols[2]:
                if st.button("❌", key=f"delete_procedure_{i}", use_container_width=True):
                    to_delete.append(i)

        # Handle deletion
        if to_delete:
            for index in sorted(to_delete, reverse=True):
                procedure_name = procedures.pop(index)
                if procedure_name in prices:
                    prices.pop(procedure_name)

            doctor_settings["treatment_procedures"] = procedures
            doctor_settings["price_estimates"] = prices
            save_settings(database, doctor_email, doctor_settings)
            st.success("Treatment procedures have been successfully updated")
            st.rerun()

    else:
        st.caption("No procedures added yet.")

    # Add new procedure section
    with st.expander("Add New Procedure", expanded=True):
        st.subheader("Create a New Procedure")
        cols = st.columns([5, 3])
        with cols[0]:
            new_procedure = st.text_input("Procedure Name", key="new_procedure").title()
        with cols[1]:
            new_price = st.number_input(
                f"Price ({currency_symbol})",
                min_value=0.0,
                step=10.0,
                format="%.2f",
                key="new_price"
            )

        if st.button("Save Procedure", use_container_width=True):
            if new_procedure:
                if new_procedure not in procedures:
                    procedures.append(new_procedure)
                    prices[new_procedure] = new_price
                    doctor_settings["treatment_procedures"] = procedures
                    doctor_settings["price_estimates"] = prices
                    save_settings(database, doctor_email, doctor_settings)
                    st.success(f"New procedure '{new_procedure}' has been successfully added")
                    st.rerun()
                else:
                    st.error("This procedure already exists in your list")
            else:
                st.error("Please provide a valid procedure name")


def show_chart():
    """Display dental chart configuration options."""
    st.header("Dental Chart Configuration")
    st.info("Customize your dental chart settings and health conditions")

    with st.expander("Dental Notation System", expanded=True):
        st.subheader("FDI World Dental Federation Notation (ISO 3950)")
        st.info("""
            This application uses the FDI (Fédération Dentaire Internationale) notation system, also known as ISO 3950.

            This two-digit system divides the mouth into four quadrants:
            - Upper Right (1): teeth 18-11
            - Upper Left (2): teeth 21-28
            - Lower Right (4): teeth 48-41
            - Lower Left (3): teeth 31-38

            The first digit indicates the quadrant, while the second digit indicates the tooth position from the midline.
        """)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Upper Jaw**")
            st.markdown("18 17 16 15 14 13 12 11 | 21 22 23 24 25 26 27 28")
        with col2:
            st.markdown("**Lower Jaw**")
            st.markdown("48 47 46 45 44 43 42 41 | 31 32 33 34 35 36 37 38")


def show_currency(database, doctor_email, doctor_settings):
    """Display and manage currency settings."""
    st.header("Currency Settings")
    st.info("Set your preferred currency for price estimates")

    current_currency = doctor_settings.get("currency", "SAR")

    # Currency options
    currency_options = {
        "SAR": "Saudi Riyal (SAR)",
        "INR": "Indian Rupee (₹)"
    }

    selected_currency = st.selectbox(
        "Select Currency",
        options=list(currency_options.keys()),
        format_func=lambda x: currency_options[x],
        index=list(currency_options.keys()).index(current_currency)
        if current_currency in currency_options
        else 0
    )

    if st.button("✔️ Save Currency Preference", use_container_width=True):
        if selected_currency != current_currency:
            doctor_settings["currency"] = selected_currency
            save_settings(database, doctor_email, doctor_settings)
            st.success(f"Currency updated to {currency_options[selected_currency]}")
            st.rerun()


main()
show_footer()
