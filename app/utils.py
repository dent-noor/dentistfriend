import os
import cloudinary
import requests
import tempfile
import streamlit as st
from datetime import datetime
from fpdf import FPDF
from dotenv import load_dotenv

load_dotenv()

def format_date(date_str):
    """Convert date string to formatted date (e.g., '2021-12-31' -> 'December 31, 2021')"""
    if isinstance(date_str, datetime):
        date_obj = date_str
    else:
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            return date_str  # Return original if parsing fails

    return date_obj.strftime("%B %d, %Y")


def show_footer():
    """Display the footer with links to GitHub, License, and Documentation"""
    st.divider()
    st.markdown(
        """
        <footer style="text-align: center">
            🔓 FOSS (Free and Open Source Software)
            <br>
            <a href="https://github.com/dent-noor/DentistFriend">GitHub</a> •
            <a href="https://github.com/dent-noor/DentistFriend/blob/main/LICENSE">License</a> •
            <a href="https://github.com/dent-noor/DentistFriend/blob/main/README.md">Documentation</a>
        </footer>
        """,
        unsafe_allow_html=True
    )


def generate_pdf(doctor_name, patient_name, treatment_plan, currency_symbol="SAR", discount=0, vat=0, total_cost=0, xray_images=None):
    """Generate a PDF document with treatment plan details and X-ray images"""

    # Initialize PDF with margins
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(left=15, top=15, right=15)

    if currency_symbol == "₹":
        display_currency = "INR"
    else:
        display_currency = currency_symbol

    pdf.add_page()

    # Document title
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Dental Treatment Plan", 0, 1, "C")

    # Date on top right
    pdf.set_font("Arial", "", 10)
    current_date = datetime.now().strftime("%B %d, %Y")
    pdf.cell(0, 6, f"Date: {current_date}", 0, 1, "R")

    # Patient information section with better spacing
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Patient Information", 0, 1, "L")
    pdf.set_draw_color(100, 100, 100)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(5)

    # Patient and doctor details with better spacing
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 7, f"Dentist: {doctor_name}".title(), 0, 1)
    pdf.cell(0, 7, f"Patient Name: {patient_name}".title(), 0, 1)
    report_id = datetime.now().strftime('%Y%m%d%H%M%S')
    pdf.cell(0, 7, f"Report ID: {report_id}", 0, 1)
    pdf.ln(5)

    if xray_images and len(xray_images) > 0:
        # Add a new page for X-rays if there's not enough space
        if pdf.get_y() > 180:
            pdf.add_page()

        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Dental X-Ray Images", 0, 1, "L")
        pdf.set_draw_color(100, 100, 100)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(10)

        # Determine grid layout based on number of images
        images_per_row = 2
        max_image_width = 80
        max_image_height = 65

        current_x = 15
        current_y = pdf.get_y()

        for i, xray in enumerate(xray_images):
            # Check if we need to move to next row or new page
            if i > 0 and i % images_per_row == 0:
                current_x = 15
                current_y += max_image_height + 15  # Image height + padding

                # Check if we need a new page
                if current_y > 250:
                    pdf.add_page()
                    current_y = 15 + 10  # Top margin + padding

            try:
                # Create a temporary file for the image
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
                    temp_img_path = temp_file.name

                # Download image from Cloudinary URL
                response = requests.get(xray["url"], stream=True)
                if response.status_code == 200:
                    with open(temp_img_path, 'wb') as f:
                        f.write(response.content)

                    # Add image to PDF with balanced dimensions
                    pdf.image(temp_img_path, x=current_x, y=current_y, w=max_image_width)

                    # Add caption under the image
                    caption_y = current_y + max_image_height - 10
                    pdf.set_xy(current_x, caption_y)
                    pdf.set_font("Arial", "", 8)
                    pdf.multi_cell(max_image_width, 5, xray.get("caption", "X-Ray Image"), 0, 'C')

                    # Clean up temporary file
                    os.remove(temp_img_path)

                    # Move x position for next image
                    current_x += max_image_width + 15  # Image width + padding
            except Exception as e:
                pdf.set_font("Arial", "", 10)
                pdf.set_xy(current_x, current_y)
                pdf.multi_cell(max_image_width, 10, "Error loading image", 0, 'C')
                current_x += max_image_width + 15

    # Treatment plan details section with proper page break
    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Treatment Plan Details", 0, 1, "L")
    pdf.set_draw_color(100, 100, 100)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(5)

    if not treatment_plan:
        pdf.set_font("Arial", "", 11)
        pdf.cell(0, 10, "No treatment procedures have been defined yet.", 0, 1)
    else:
        # Create treatment table with headers
        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(240, 240, 240)  # Lighter gray for header

        # Define table structure with optimized widths
        columns = ["Tooth", "Condition", "Procedure", "Start Date", "Cost"]
        col_widths = [20, 35, 55, 35, 25]

        # Filter available columns based on treatment plan data
        available_columns = []
        available_widths = []

        for i, col in enumerate(columns):
            if col in treatment_plan[0] or col in ["Tooth", "Procedure", "Cost"]:
                available_columns.append(col)
                available_widths.append(col_widths[i])

        # Create table header row
        for i, col in enumerate(available_columns):
            pdf.cell(available_widths[i], 10, col, 1, 0, "C", True)
        pdf.ln()

        # Add treatment data rows with alternating colors
        pdf.set_font("Arial", "", 10)
        for idx, item in enumerate(treatment_plan):
            # Alternate row colors
            if idx % 2 == 1:
                pdf.set_fill_color(245, 245, 245)
                fill = True
            else:
                fill = False

            for i, col in enumerate(available_columns):
                value = str(item.get(col, ""))
                if col == "Cost" and value:
                    try:
                        value = f"{display_currency} {float(value):.2f}"
                    except ValueError:
                        pass

                # Align different columns appropriately
                align = "R" if col == "Cost" else "L"
                pdf.cell(available_widths[i], 8, value, 1, 0, align, fill)

            pdf.ln()

    # Add cost summary section with proper spacing
    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Cost Summary", 0, 1, "L")
    pdf.set_draw_color(100, 100, 100)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(5)

    # Calculate final cost
    final_cost = total_cost
    if isinstance(discount, (int, float)):
        final_cost -= discount
    if isinstance(vat, (int, float)):
        final_cost += vat

    # Define column layout for cost table
    col1_width = 120
    col2_width = 50

    # Create cost breakdown table with better styling
    pdf.set_font("Arial", "", 10)
    pdf.set_fill_color(245, 245, 245)

    # Total row
    pdf.cell(col1_width, 8, "Total Treatment Cost", 1, 0, "L", True)
    pdf.cell(col2_width, 8, f"{display_currency} {float(total_cost):.2f}", 1, 1, "R", True)

    # Discount row (if applicable)
    if discount > 0:
        pdf.cell(col1_width, 8, "Discount", 1, 0, "L")
        pdf.cell(col2_width, 8, f"-{display_currency} {float(discount):.2f}", 1, 1, "R")

    # VAT row (if applicable)
    if vat > 0:
        pdf.cell(col1_width, 8, "VAT (15%)", 1, 0, "L")
        pdf.cell(col2_width, 8, f"+{display_currency} {float(vat):.2f}", 1, 1, "R")

    # Final total row with highlighting
    pdf.set_font("Arial", "B", 10)
    pdf.set_fill_color(230, 230, 230)  # Darker highlight for total
    pdf.cell(col1_width, 8, "Final Total", 1, 0, "L", True)
    pdf.cell(col2_width, 8, f"{display_currency} {float(final_cost):.2f}", 1, 1, "R", True)

    # Add footer with proper spacing
    pdf.ln(15)
    pdf.set_font("Arial", "I", 8)
    generation_time = datetime.now()
    pdf.cell(0, 5, "Generated by Dental Treatment Planner", 0, 1, "C")
    pdf.cell(0, 5, f"This report was generated on {generation_time.strftime('%B %d, %Y')} at {generation_time.strftime('%H:%M')}.", 0, 1, "C")

    # Generate filename and output PDF
    filename = f"{patient_name.replace(' ', '_')}_treatment_plan.pdf"
    pdf.output(filename)
    return filename


def update_tooth(tooth_number):
    """Update tooth condition in session state."""
    selected_value = st.session_state[f"tooth_{tooth_number}"]
    st.session_state[f"tooth_condition_{tooth_number}"] = selected_value


def render_chart(dental_data, dental_chart=None):
    """Render interactive dental chart with colored teeth boxes based on patient type."""
    if dental_chart is None:
        dental_chart = {}

    # Get patient type from session state (default to adult if not specified)
    patient_type = st.session_state.patient_selected.get("patient_type", "adult").lower()

    # Use appropriate teeth map and rows based on patient type
    if patient_type == "child" and "child" in dental_data:
        teeth_map = dental_data["child"]["teeth_map"].copy()
        teeth_rows = dental_data["child"]["teeth_rows"]
    else:
        # Default to adult dental chart
        teeth_map = dental_data["adult"]["teeth_map"].copy()
        teeth_rows = dental_data["adult"]["teeth_rows"]

    # Merge existing dental chart data with teeth map
    for tooth in teeth_map:
        if tooth in dental_chart:
            teeth_map[tooth] = dental_chart[tooth]

    # Define color mapping for different health conditions
    condition_colors = {
        "Healthy": "#008000",  # Green
        "Decayed": "#9B2226",  # Dark Red
        "Missing": "#ADB5BD",  # Gray
        "Cavity": "#6C757D",   # Dark Gray
        "Implant": "#6C757D",  # Dark Gray
        "Extraction": "#774936", # Brown
        # "Root Canal": "#FFA500", # Orange
        "Fractured": "#9B2226",  # Dark Red
        "Filled": "#007BFF",   # Blue
        "Discolored": "#FFD700", # Gold
        "Loose": "#FF7F50",    # Coral
        "Crowded": "#800080",  # Purple
        "Gingivitis": "#FF69B4", # Pink
        "Periodontitis": "#FF0000", # Red
        "Impacted": "#6C757D", # Dark Gray
        "Abrasion": "#FF4500",  # Orange Red
        "Anodontia": "#ADB5BD", # Gray
        "Attrition": "#FF8C00", # Dark Orange
        "Erosion": "#DAA520",   # Golden Rod
        "Hyperdontia": "#4B0082", # Indigo
        # Default for any other condition
        "default": "#008000"   # Green
    }

    # Track if chart has been modified
    chart_changed = False

    st.header("Dental Chart Assessment")

    with st.container(border=True):
        # Process each row of teeth in the dental chart
        for teeth_row in teeth_rows:
            # Create appropriate number of columns based on row length
            cols = st.columns(len(teeth_row))

            for i, tooth_number in enumerate(teeth_row):
                with cols[i]:
                    # Get current condition from the session state first (for immediate updates)
                    # or fall back to dental_chart, or default to "Healthy"
                    current_condition = st.session_state.get(f"tooth_condition_{tooth_number}",
                                                          dental_chart.get(tooth_number, "Healthy"))

                    # Get the appropriate color for this tooth's condition
                    tooth_color = condition_colors.get(current_condition, condition_colors["default"])

                    # Create a visual box for the tooth with the appropriate color
                    st.markdown(
                        f"""
                        <div style="
                            background-color: {tooth_color};
                            color: white;
                            text-align: center;
                            padding: 10px 0;
                            border-radius: 5px;
                            font-weight: bold;
                            margin-bottom: 5px;
                        ">
                            {tooth_number}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    # Dropdown selector for tooth condition
                    default_index = 0
                    try:
                        default_index = dental_data["health_conditions"].index(current_condition)
                    except (ValueError, IndexError):
                        default_index = 0

                    selected_condition = st.selectbox(
                        f"Tooth {tooth_number}",
                        dental_data["health_conditions"],
                        index=default_index,
                        key=f"tooth_{tooth_number}",
                        label_visibility="collapsed",
                        on_change=update_tooth,
                        args=(tooth_number,)
                    )

                    # Store selected condition in session state for immediate visual updates
                    st.session_state[f"tooth_condition_{tooth_number}"] = selected_condition

                    # Track changes to dental chart
                    if tooth_number not in dental_chart or dental_chart[tooth_number] != selected_condition:
                        dental_chart[tooth_number] = selected_condition
                        chart_changed = True

                        # Auto-select unhealthy teeth for potential treatment
                        if selected_condition != "Healthy":
                            st.session_state.tooth_selected = tooth_number

    return dental_chart, chart_changed


def get_currency_symbol(currency_code):
    """Return the appropriate currency symbol based on currency code."""
    currency_symbols = {
        "SAR": "SAR",
        "INR": "₹"
    }
    return currency_symbols.get(currency_code, currency_code)


def configure_cloudinary():
    """Configure Cloudinary using environment variables"""
    cloudinary.config(
        cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
        api_key=os.getenv('CLOUDINARY_API_KEY'),
        api_secret=os.getenv('CLOUDINARY_API_SECRET'),
        secure=True
    )


def custom_css():
    st.markdown("""
        <style>
            .stButton > button {
                padding: 12px 8px;
                font-size: 16px;
                font-weight: 500;
                border-radius: 8px;
                transition: all 0.3s ease;
                box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
            }

            .stButton > button:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
            }

            .stButton > button svg {
                height: 20px;
                width: 20px;
                margin-right: 6px;
            }

            .stAlert {
                border-radius: 8px;
            }
        </style>
    """, unsafe_allow_html=True)
