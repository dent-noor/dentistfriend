import os
import smtplib
import streamlit as st
import pandas as pd
import json
import plotly.express as px
from datetime import datetime
from firebase_admin import firestore
from dotenv import load_dotenv
from utils import format_date, show_footer

load_dotenv()


# Utility function to format item names
def format_item_name(item_name: str) -> str:
    """
    Returns the item name with the first letter of each word capitalized
    if the word is completely in lowercase.
    If any word already contains capital letters, it remains unchanged.
    """
    words = item_name.split()
    formatted_words = [word.capitalize() if word == word.lower() else word for word in words]
    return " ".join(formatted_words)


# Initialize Firestore database connection
database = firestore.client()
doctor_email = st.session_state["doctor_email"] if "doctor_email" in st.session_state else None
stock_collection = database.collection("doctors").document(doctor_email).collection("stock") if doctor_email else None


def import_data_to_firebase():
    """Import CSV or JSON files into Firebase database"""
    st.subheader("Import Data", divider="green")

    uploaded_file = st.file_uploader("Choose a file", type=['csv', 'json'])
    if uploaded_file is not None:
        file_type = uploaded_file.name.split('.')[-1].lower()
        try:
            # Read file data based on type
            if file_type == 'csv':
                df = pd.read_csv(uploaded_file)
                data = df.to_dict('records')
            else:  # JSON file
                data = json.load(uploaded_file)

            if not isinstance(data, list):
                data = [data]

            with st.spinner('Importing data...'):
                batch = database.batch()
                counter = 0
                batch_size = 500  # Firestore batch limit

                for item in data:
                    # Validate required fields
                    if 'name' not in item or 'quantity' not in item or 'expiry_date' not in item:
                        st.error("File must contain 'name', 'quantity', and 'expiry_date' fields")
                        return

                    try:
                        # Process each item
                        formatted_name = format_item_name(item['name'])
                        expiry_date = item['expiry_date']
                        # Create unique document ID
                        item_id = f"{formatted_name.lower().replace(' ', '_')}_{expiry_date}"
                        doc_ref = stock_collection.document(item_id)

                        item_data = {
                            "quantity": int(item['quantity']),
                            "expiry_date": expiry_date,
                            "low_threshold": int(item.get('low_threshold', 5)),
                            "display_name": formatted_name
                        }

                        batch.set(doc_ref, item_data, merge=True)
                        counter += 1

                        # Commit batch if limit reached
                        if counter >= batch_size:
                            batch.commit()
                            batch = database.batch()
                            counter = 0
                    except Exception as item_error:
                        st.error(f"Error processing item: {str(item_error)}")
                        continue

                # Commit any remaining items in the batch
                if counter > 0:
                    batch.commit()

            st.success(f"Successfully imported {len(data)} items")
            st.session_state.inventory_data = fetch_stock()
            st.rerun()
        except Exception as e:
            st.error(f"Error importing data: {str(e)}")


def fetch_stock():
    """Fetch all inventory items from Firestore database"""
    stock_documents = stock_collection.stream()
    return {doc.id: doc.to_dict() for doc in stock_documents}


def store_stock(item_id, item_quantity, expiry_date, formatted_name, low_threshold=5):
    """Store or update inventory item in Firestore database.
    Also saves the display name for proper capitalization.
    """
    item_doc = stock_collection.document(item_id).get()
    if item_doc.exists:
        st.warning(
            f"Item '{formatted_name}' with the same expiry date already exists. Please edit the existing item instead.")
        return False
    stock_collection.document(item_id).set({
        "quantity": item_quantity,
        "expiry_date": expiry_date,
        "low_threshold": low_threshold,
        "display_name": formatted_name
    }, merge=True)
    return True


def modify_stock(item_name, quantity_remove):
    """Decrease quantity or remove item from inventory"""
    item_reference = stock_collection.document(item_name)
    item_document = item_reference.get()
    if item_document.exists:
        item_data = item_document.to_dict()
        current_quantity = item_data["quantity"]
        item_reference.update({"quantity": current_quantity - quantity_remove})
        st.success(f"Quantity Updated: {quantity_remove} units of '{item_data.get('display_name', item_name)}' removed")
        st.session_state.inventory_data = fetch_stock()


def send_alert(email, expiry_items, days_threshold):
    """Send email alert for items nearing expiry"""
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        return "Email credentials not found in environment variables"
    items_list = "\n".join(
        [f"- {item['Item']}: {item['Quantity']} units, expires in {item['Days Left']} days ({item['Expiry Date']})"
         for item in expiry_items])
    subject = f"Dental Supply Alert: Items Expiring Within {days_threshold} Days"
    body = f"""
Hello,

This is an automated alert from your Dental Supply Tracker.

The following items in your inventory are expiring within {days_threshold} days:

{items_list}

Please review these items and take appropriate action.

Regards,
Dental Supply Tracker
"""
    full_message = f"Subject: {subject}\n\n{body}"
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(user=ADMIN_EMAIL, password=ADMIN_PASSWORD)
        server.sendmail(from_addr=ADMIN_EMAIL, to_addrs=email, msg=full_message)
        server.quit()
        return "Email alert sent successfully"
    except Exception as e:
        return str(e)


def main():
    if st.session_state["logged_in"]:
        # ✅ Show logout on sidebar
        with st.sidebar:
            if st.button("Logout", use_container_width=True):
                st.session_state.clear()
                st.rerun()
    st.title("Dental Supply Tracker")
    st.markdown("""
        <style>
        .stButton > button {
                background-color: #87d2f5;
                color: black;
                padding: 15px 10px;
                border-radius: 10px;
                border: none;
                font-size: 16px;
                font-weight: bold;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                transition: all 0.3s ease;
            }
        .stButton > button:hover {
                background-color: #03b1fc;
                transform: translateY(-2px);
                box-shadow: 0 6px 8px rgba(0, 0, 0, 0.2);
            }
        .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
                font-size:19px;
            }
        </style>
        """,
        unsafe_allow_html=True
    )

    if st.session_state.get("doctor_email") is None:
        st.error("Doctor Authentication Required: Please log in to access the inventory system")
        return
    if 'inventory_data' not in st.session_state:
        st.session_state.inventory_data = fetch_stock()

    tab_inventory, tab_alerts, tab_reports = st.tabs(["Inventory", "Alerts", "Reports"])
    with tab_inventory:
        st.session_state.inventory_data = fetch_stock()
        display_inventory()
    with tab_alerts:
        display_alerts()
    with tab_reports:
        display_reports()


def display_inventory():
    """Display and manage the inventory tab"""
    st.header("Current Inventory")
    show_inventory()
    st.subheader("Inventory Management")

    # Create three columns for Add, Edit, and Import
    col_add, col_edit, col_import = st.columns(3)

    with col_add:
        with st.container(border=True):
            st.subheader("Add Inventory")
            add_items()

    with col_edit:
        with st.container(border=True):
            st.subheader("Edit Inventory")
            edit_inventory()

    with col_import:
        with st.container(border=True):
            import_data_to_firebase()


def display_alerts():
    """Display alerts tab with expiry and low stock warnings"""
    st.header("Inventory Alerts")

    doctor_doc = database.collection("doctors").document(doctor_email).get()
    if doctor_doc.exists:
        doctor_data = doctor_doc.to_dict()
        if "alert_email" in doctor_data and doctor_data["alert_email"]:
            st.session_state["enable_email_alerts"] = True
            st.session_state["alert_email"] = doctor_data["alert_email"]
    else:
        st.error("Doctor profile not found. Please ensure you are logged in correctly.")
        return
    if "email_alert_sent" not in st.session_state:
        st.session_state["email_alert_sent"] = False
    inventory_data = st.session_state.inventory_data
    if not inventory_data:
        st.info("No inventory items found. Please add items in the Inventory tab.")
        return
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("Low Stock Alerts", divider="green")
            global_threshold = st.slider("Global Low Stock Threshold", min_value=1, max_value=50, value=1)
            low_stock_items = []
            for item_id, details in inventory_data.items():
                item_threshold = details.get("low_threshold", global_threshold)
                if details["quantity"] <= item_threshold:
                    display_name = details.get("display_name", item_id.split('_')[
                        0].capitalize() if '_' in item_id else item_id.capitalize())
                    expiry_date = details["expiry_date"]
                    low_stock_items.append({
                        "Item": display_name,
                        "Quantity": details["quantity"],
                        "Threshold": item_threshold,
                        "Expiry Date": format_date(expiry_date)
                    })
            if low_stock_items:
                st.markdown("### 🚨 Low Stock Items")
                low_stock_df = pd.DataFrame(low_stock_items)
                st.dataframe(low_stock_df, use_container_width=True)
                fig = px.bar(
                    low_stock_df,
                    x="Item",
                    y="Quantity",
                    title="Items Below Threshold",
                    color="Quantity",
                    color_continuous_scale="Reds_r",
                    hover_data=["Threshold", "Expiry Date"]
                )
                fig.update_layout(xaxis_title="Item", yaxis_title="Quantity")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.success("✅ All items have sufficient quantity")

    with col2:
        with st.container(border=True):
            st.subheader("Expiry Alerts", divider="green")
            days_threshold = st.slider("Days Until Expiry Warning", min_value=1, max_value=180, value=30)
            today = datetime.today().date()
            expiry_items = []
            for item, details in inventory_data.items():
                try:
                    expiry_date = datetime.strptime(details["expiry_date"], "%Y-%m-%d").date()
                    days_until_expiry = (expiry_date - today).days
                    if days_until_expiry <= days_threshold:
                        display_name = details.get("display_name", item.split('_')[
                            0].capitalize() if '_' in item else item.capitalize())
                        expiry_items.append({
                            "Item": display_name,
                            "Quantity": details["quantity"],
                            "Expiry Date": format_date(details["expiry_date"]),
                            "Days Left": days_until_expiry
                        })
                except ValueError as e:
                    st.error(f"Date format error for item '{item}': {str(e)}")
                    continue
            if expiry_items and st.session_state.get("enable_email_alerts", False) and not st.session_state[
                "email_alert_sent"]:
                alert_email = st.session_state.get("alert_email")
                if alert_email:
                    result = send_alert(alert_email, expiry_items, days_threshold)
                    if "successfully" in result:
                        st.session_state["email_alert_sent"] = True
                        st.success(f"Email alert sent to {alert_email}")
                    else:
                        st.error(f"Failed to send email alert: {result}")
            if expiry_items:
                st.markdown("### ⚠️ Items Near Expiry")
                expiry_df = pd.DataFrame(expiry_items)
                expiry_df = expiry_df.sort_values("Days Left")
                st.dataframe(expiry_df, use_container_width=True)
                if len(expiry_df) > 0:
                    fig = px.bar(
                        expiry_df,
                        x="Item",
                        y="Days Left",
                        title=f"Items Expiring Within {days_threshold} Days",
                        color="Days Left",
                        color_continuous_scale="RdYlGn",
                    )
                    fig.update_layout(xaxis_title="Item", yaxis_title="Days Until Expiry")
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.success("✅ No items are nearing expiration")
                st.session_state["email_alert_sent"] = False

            # Add divider before Alert settings
            #st.divider()
    with st.container(border=True):
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
        st.subheader("Alert Settings", divider="green")
        previous_email_alert_state = st.session_state.get("enable_email_alerts", False)
        enable_email_alerts = st.checkbox("Enable Email Alerts", value=previous_email_alert_state)
        if enable_email_alerts and not previous_email_alert_state:
            if "alert_email" not in st.session_state:
                st.session_state["alert_email"] = st.session_state.get("doctor_email", "")
            if doctor_email:
                try:
                    database.collection("doctors").document(doctor_email).set({
                        "alert_email": st.session_state["alert_email"]
                    }, merge=True)
                except Exception as e:
                    st.error(f"Failed to save alert settings: {str(e)}")
            else:
                st.error("Cannot save alert settings: No doctor email available")
            st.session_state["email_alert_sent"] = False
        if not enable_email_alerts and previous_email_alert_state:
            if doctor_email:
                try:
                    database.collection("doctors").document(doctor_email).update({
                        "alert_email": firestore.DELETE_FIELD
                    })
                except Exception as e:
                    st.error(f"Failed to update alert settings: {str(e)}")
            else:
                st.error("Cannot update alert settings: No doctor email available")
        st.session_state["enable_email_alerts"] = enable_email_alerts
        if enable_email_alerts:
            col1, col2, col3 = st.columns([2, 1,1])
            with col1:
                alert_email = st.text_input(
                    "Alert Email",
                    value=st.session_state.get("alert_email", ""),
                    placeholder="Enter email for alerts"
                )
            with col2:
                if st.button("Update Email", use_container_width=True):
                    if not alert_email or "@" not in alert_email:
                        st.error("Please enter a valid email address")
                    else:
                        st.session_state["alert_email"] = alert_email
                        if doctor_email:
                            try:
                                database.collection("doctors").document(doctor_email).set({
                                    "alert_email": alert_email
                                }, merge=True)
                                st.session_state["email_alert_sent"] = False
                                st.success(f"Email updated: Alerts will be sent to {alert_email}")
                            except Exception as e:
                                st.error(f"Failed to update email: {str(e)}")
                        else:
                            st.error("Cannot save email settings: No doctor email available")
            with col3:
                if st.button("Send Test Alert", use_container_width=True):
                    if not alert_email or "@" not in alert_email:
                        st.error("Please enter a valid email address")
                    elif expiry_items:
                        try:
                            result = send_alert(alert_email, expiry_items, days_threshold)
                            if "successfully" in result:
                                st.success(f"Test email alert sent to {alert_email}")
                            else:
                                st.error(f"Failed to send test email alert: {result}")
                        except Exception as e:
                            st.error(f"Error sending test email: {str(e)}")
                    else:
                        st.warning("No items are near expiry. Add items that will expire soon to test the alert.")


def display_reports():
    """Display reports tab with analytics and export options."""
    st.header("Inventory Reports")

    inventory_data = st.session_state.inventory_data
    if inventory_data:
        today = datetime.today().date()

        # Summary Statistics Block
        st.subheader("Summary Statistics", divider="green")
        total_items = len(inventory_data)
        total_units = sum(item["quantity"] for item in inventory_data.values())
        expiring_soon = sum(1 for details in inventory_data.values()
                            if (datetime.strptime(details["expiry_date"], "%Y-%m-%d").date() - today).days <= 30)

        metric_col1, metric_col2, metric_col3 = st.columns(3)
        with metric_col1:
            st.metric("Total Items", total_items)
        with metric_col2:
            st.metric("Total Units", total_units)
        with metric_col3:
            st.metric("Expiring Soon (30 days)", expiring_soon)

        # Create inventory records for visualization and export
        inventory_records = []
        for item_id, details in inventory_data.items():
            display_name = details.get("display_name",
                                       item_id.split('_')[0].capitalize() if '_' in item_id else item_id.capitalize())
            expiry_date = datetime.strptime(details["expiry_date"], "%Y-%m-%d").date()
            formatted_date = expiry_date.strftime("%b %d, %Y")
            display_full_name = f"{display_name} ({formatted_date})"
            days_until_expiry = (expiry_date - today).days

            inventory_records.append({
                "Item": display_name,
                "Display Name": display_full_name,
                "Quantity": details["quantity"],
                "Days Until Expiry": days_until_expiry,
                "Expiry Date": details["expiry_date"],
                "Low Threshold": details.get("low_threshold", 5)
            })

        # Create DataFrame for visualizations
        viz_df = pd.DataFrame(inventory_records)

        # Visualization code remains the same...
        # [Previous visualization code here]

        # Export Options
        st.subheader("Export Options", divider="green")

        # Prepare export data in the specified format
        export_records = []
        for item_id, details in inventory_data.items():
            display_name = details.get("display_name",
                                       item_id.split('_')[0].capitalize() if '_' in item_id else item_id.capitalize())
            export_records.append({
                "name": display_name,
                "quantity": details["quantity"],
                "expiry_date": details["expiry_date"],
                "low_threshold": details.get("low_threshold", 5)
            })

        # Create DataFrame with specific columns for export
        export_df = pd.DataFrame(export_records)
        export_df = export_df[["name", "quantity", "expiry_date", "low_threshold"]]

        export_col1, export_col2 = st.columns(2)

        with export_col1:
            # CSV Export
            csv = export_df.to_csv(index=False, quoting=1)
            st.download_button(
                label="📄 Download CSV Report",
                data=csv,
                file_name=f"inventory_report_{datetime.today().strftime('%Y-%m-%d')}.csv",
                mime="text/csv",
                help="Download inventory report in CSV format"
            )

        with export_col2:
            # JSON Export
            json_records = export_df.to_dict('records')
            json_data = json.dumps(json_records, indent=2)
            st.download_button(
                label="📄 Download JSON Report",
                data=json_data,
                file_name=f"inventory_report_{datetime.today().strftime('%Y-%m-%d')}.json",
                mime="application/json",
                help="Download inventory report in JSON format"
            )
    else:
        st.info("No inventory data available. Add items in the Inventory tab to generate reports.")


def show_inventory():
    """Display the current inventory status with conditional formatting"""
    inventory_data = st.session_state.inventory_data
    if inventory_data:
        st.session_state.inventory_records = []
        for item_id, details in inventory_data.items():
            display_name = details.get("display_name",
                                       item_id.split('_')[0].capitalize() if '_' in item_id else item_id.capitalize())
            today = datetime.today().date()
            expiry_date = datetime.strptime(details["expiry_date"], "%Y-%m-%d").date()
            days_until_expiry = (expiry_date - today).days
            quantity = details["quantity"]
            item_threshold = details.get("low_threshold", 5)
            status = "Normal"
            if days_until_expiry <= 30:
                status = "⚠️ Expiring Soon"
            if quantity <= item_threshold:
                status = "🚨 Low Stock"
            if days_until_expiry <= 0:
                status = "❌ Expired"
            if quantity == 0:
                status = "❌ Out of Stock"
            st.session_state.inventory_records.append({
                "Item": display_name,
                "Quantity": details["quantity"],
                "Expiry Date": format_date(details["expiry_date"]),
                "Days Until Expiry": days_until_expiry,
                "Status": status,
                "ID": item_id
            })
        inventory_df = pd.DataFrame(st.session_state.inventory_records)

        def status_priority(status):
            priorities = {"❌ Expired": 0, "❌ Out of Stock": 1, "🚨 Low Stock": 2, "⚠️ Expiring Soon": 3, "Normal": 4}
            return priorities.get(status, 4)

        inventory_df["Status Priority"] = inventory_df["Status"].apply(status_priority)
        inventory_df = inventory_df.sort_values("Status Priority")
        display_df = inventory_df.drop(columns=["Status Priority", "ID"])
        if "active_filter" not in st.session_state:
            st.session_state.active_filter = "All Items"
        if st.session_state.active_filter != "All Items":
            filtered_df = display_df[display_df["Status"] == st.session_state.active_filter]
        else:
            filtered_df = display_df
        filtered_df = filtered_df.reset_index(drop=True)
        filtered_df.index = filtered_df.index + 1
        st.dataframe(
            filtered_df,
            use_container_width=True,
            column_config={
                "Quantity": st.column_config.NumberColumn(
                    "Quantity",
                    help="Number of units in stock",
                    format="%d"
                ),
                "Days Until Expiry": st.column_config.NumberColumn(
                    "Days Until Expiry",
                    help="Days remaining until item expires",
                    format="%d days"
                ),
                "Status": st.column_config.TextColumn(
                    "Status",
                    help="Inventory status indicator"
                )
            },
            height=400
        )
        st.write("### Filter Inventory")
        filter_cols = st.columns(6)
        if st.session_state.active_filter != "All Items":
            st.info(f"Showing {len(filtered_df)} items with status: {st.session_state.active_filter}")
        else:
            st.info(f"Showing all {len(filtered_df)} items")

        def get_button_style(filter_name):
            return "primary" if st.session_state.active_filter == filter_name else "secondary"

        with filter_cols[0]:
            if st.button("All Items", key="all_items", use_container_width=True, type=get_button_style("All Items")):
                st.session_state.active_filter = "All Items"
                st.rerun()
        with filter_cols[1]:
            if st.button("Normal", key="normal", use_container_width=True, type=get_button_style("Normal")):
                st.session_state.active_filter = "Normal"
                st.rerun()
        with filter_cols[2]:
            if st.button("🚨 Low Stock", key="low_stock", use_container_width=True,
                         type=get_button_style("🚨 Low Stock")):
                st.session_state.active_filter = "🚨 Low Stock"
                st.rerun()
        with filter_cols[3]:
            if st.button("⚠️ Expiring Soon", key="expiring_soon", use_container_width=True,
                         type=get_button_style("⚠️ Expiring Soon")):
                st.session_state.active_filter = "⚠️ Expiring Soon"
                st.rerun()
        with filter_cols[4]:
            if st.button("❌ Expired", key="expired", use_container_width=True, type=get_button_style("❌ Expired")):
                st.session_state.active_filter = "❌ Expired"
                st.rerun()
        with filter_cols[5]:
            if st.button("❌ Out of Stock", key="out_of_stock", use_container_width=True,
                         type=get_button_style("❌ Out of Stock")):
                st.session_state.active_filter = "❌ Out of Stock"
                st.rerun()
    else:
        st.info("Inventory Status: No items currently in stock")


def add_items():
    """Add new items to inventory or update existing items"""
    column_first, column_second, column_third = st.columns(3)
    with column_first:
        raw_item_name = st.text_input("Item Name", placeholder="Enter item name").strip()
    with column_second:
        item_quantity = st.number_input("Quantity", min_value=1, step=1)
    with column_third:
        low_threshold = st.number_input("Low Stock Threshold", min_value=1, value=5, step=1)
    expiry_date = st.date_input("Expiry Date", min_value=datetime.today().date())
    if st.button("➕ Add Item", use_container_width=True):
        if raw_item_name:
            formatted_name = format_item_name(raw_item_name)
            expiry_string = expiry_date.strftime("%Y-%m-%d")
            item_id = f"{formatted_name.lower().replace(' ', '_')}_{expiry_string}"
            if item_id in st.session_state.inventory_data:
                st.warning(
                    f"Item '{formatted_name}' with the same expiry date already exists. Please edit the existing item instead.")
            else:
                success = store_stock(item_id, item_quantity, expiry_string, formatted_name, low_threshold)
                if success:
                    st.success(
                        f"Item Added: {item_quantity} units of '{formatted_name}' (Expires: {format_date(expiry_string)}) added to inventory")
                    st.session_state["email_alert_sent"] = False
                    st.session_state.inventory_data = fetch_stock()
                    st.rerun()
        else:
            st.error("Entry Error: Please enter a valid item name")


def edit_inventory():
    """Edit or remove items from inventory based on a user search query.
    The search can be any substring or the full name of the item.
    """
    search_query = st.text_input("Enter Item Name or Substring to Edit", placeholder="Enter search query").strip()

    # Clear edit state if no query is provided or on re-run
    if not search_query:
        st.session_state.pop("edit_item_id", None)
        st.session_state.pop("matching_items", None)
        st.session_state.edit_search_mode = False

    find_edit_button = st.button("🔍 Find Items", use_container_width=True)
    if search_query and find_edit_button:
        st.session_state.pop("edit_item_id", None)
        st.session_state.pop("matching_items", None)
        st.session_state.edit_search_mode = True
        matching_items = {}
        # Match any substring from the search query in the display name (case-insensitive)
        for item_id, details in st.session_state.inventory_data.items():
            stored_name = details.get("display_name", item_id.split('_')[0] if '_' in item_id else item_id)
            if search_query.lower() in stored_name.lower():
                matching_items[item_id] = {
                    "name": stored_name,
                    "expiry_date": details["expiry_date"],
                    "quantity": details["quantity"],
                    "low_threshold": details.get("low_threshold", 5)
                }
        if not matching_items:
            st.error(f"No items found matching '{search_query}'.")
            st.session_state.edit_search_mode = False
            return
        st.session_state.matching_items = matching_items
        st.session_state.search_term = search_query
    if st.session_state.get("edit_search_mode") and "matching_items" in st.session_state:
        matching_items = st.session_state.matching_items
        edit_item = None
        if len(matching_items) == 1:
            edit_item = list(matching_items.keys())[0]
            st.session_state.edit_item_id = edit_item
        else:
            item_options = []
            for item_id, details in matching_items.items():
                display_text = f"{details['name']} (Expires: {format_date(details['expiry_date'])}) - {details['quantity']} units"
                item_options.append({"id": item_id, "display": display_text})
            selected_option = st.selectbox(
                "Select Item to Edit",
                options=[item["display"] for item in item_options],
                index=0,
                key="item_selector"
            )
            selected_index = item_options.index(
                next(item for item in item_options if item["display"] == selected_option))
            edit_item = item_options[selected_index]["id"]
            st.session_state.edit_item_id = edit_item
    if st.session_state.get("edit_item_id") and st.session_state.edit_item_id in st.session_state.inventory_data:
        handle_item_editing(st.session_state.edit_item_id)
    elif "edit_item_id" in st.session_state:
        st.error("The selected item no longer exists in the inventory.")
        st.session_state.edit_search_mode = False
        st.session_state.pop("edit_item_id", None)
        st.session_state.pop("matching_items", None)


def handle_item_editing(edit_item):
    """Handle the editing interface for a specific inventory item"""
    item_details = st.session_state.inventory_data[edit_item]
    base_name = item_details.get("display_name", edit_item.split('_')[0] if '_' in edit_item else edit_item)
    st.info(
        f"Editing: '{base_name}' | Current quantity: {item_details['quantity']} units | Expiry date: {format_date(item_details['expiry_date'])}")
    edit_col1, edit_col2, edit_col3 = st.columns(3)
    with edit_col1:
        new_quantity = st.number_input("New Quantity", min_value=0, value=item_details['quantity'], step=1)
    with edit_col2:
        try:
            current_expiry = datetime.strptime(item_details['expiry_date'], "%Y-%m-%d").date()
            today = datetime.today().date()
            if current_expiry < today:
                current_expiry = today
            new_expiry = st.date_input("New Expiry Date", value=current_expiry, min_value=today)
        except Exception as e:
            st.error(f"Date validation error: {e}")
            new_expiry = datetime.today().date()
    with edit_col3:
        new_threshold = st.number_input("New Low Stock Threshold", min_value=1,
                                        value=item_details.get('low_threshold', 5), step=1)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Save Changes", use_container_width=True, key="save_changes"):
            expiry_string = new_expiry.strftime("%Y-%m-%d")
            base_name_clean = base_name  # retain the name as is
            new_item_id = f"{base_name_clean.lower().replace(' ', '_')}_{expiry_string}"
            if new_item_id != edit_item:
                if new_item_id in st.session_state.inventory_data:
                    st.error(
                        f"Cannot update: An item with name '{base_name_clean}' and expiry date {format_date(expiry_string)} already exists")
                else:
                    stock_collection.document(new_item_id).set({
                        "quantity": new_quantity,
                        "expiry_date": expiry_string,
                        "low_threshold": new_threshold,
                        "display_name": base_name_clean
                    }, merge=True)
                    stock_collection.document(edit_item).delete()
                    st.success(f"Item Updated with new expiry: '{base_name_clean}' has been updated successfully")
                    st.session_state["email_alert_sent"] = False
                    st.session_state.pop("edit_item_id", None)
                    st.session_state.pop("matching_items", None)
                    st.session_state.inventory_data = fetch_stock()
                    st.rerun()
            else:
                stock_collection.document(edit_item).set({
                    "quantity": new_quantity,
                    "expiry_date": expiry_string,
                    "low_threshold": new_threshold,
                    "display_name": base_name_clean
                }, merge=True)
                st.success(f"Item Updated: '{base_name_clean}' has been updated successfully")
                st.session_state["email_alert_sent"] = False
                st.session_state.pop("edit_item_id", None)
                st.session_state.pop("matching_items", None)
                st.session_state.inventory_data = fetch_stock()
                st.rerun()
    with col2:
        if st.button("🗑️ Delete Item", use_container_width=True, key="delete_item"):
            try:
                stock_collection.document(edit_item).delete()
                st.success(
                    f"Item Removed: '{base_name}' (Expires: {format_date(item_details['expiry_date'])}) has been deleted from inventory")
                st.session_state["email_alert_sent"] = False
                st.session_state.pop("edit_item_id", None)
                st.session_state.pop("matching_items", None)
                st.session_state.inventory_data = fetch_stock()
                st.rerun()
            except Exception as e:
                st.error(f"Error deleting item: {str(e)}")


main()
show_footer()
