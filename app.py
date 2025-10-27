import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import openai
from openai import OpenAI
import pdfkit
import tempfile
import os
import fitz  # PyMuPDF for PDF text extraction
import json

# --- Initialize OpenAI Client ---
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- Page Configuration ---
st.set_page_config(page_title="Sustainable Marketing Evaluator", layout="wide")

# --- Initialize Session State for Form Data ---
if "input_method" not in st.session_state:
    st.session_state["input_method"] = "manual"  # Default to manual input
if "campaign_data" not in st.session_state:
    st.session_state["campaign_data"] = {
        "Campaign Name": "Green Horizons Launch",
        "Location": "Sydney",
        "Duration": 2,
        "Staff Count": 25,
        "Travel Mode": "Air",
        "Brochures": 2000,
        "Tote Bags": 500,
        "Accommodation": "4-star",
        "Local Vendors": True
    }

# --- PDF Text Extraction Function ---
def extract_text_from_pdf(file, max_chars=8000):
    """Extracts and cleans text from PDF, limiting length to prevent token overflow"""
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        full_text = []
        total_chars = 0
        
        for page in doc:
            page_text = page.get_text().strip()
            if not page_text:
                continue
            
            # Remove header/footer noise
            lines = [line for line in page_text.split('\n') 
                    if not line.strip().lower().startswith(("page", "confidential", "draft", "©"))]
            cleaned_page = '\n'.join(lines)
            
            # Enforce character limit
            if total_chars + len(cleaned_page) > max_chars:
                remaining = max_chars - total_chars
                full_text.append(cleaned_page[:remaining])
                break
                
            full_text.append(cleaned_page)
            total_chars += len(cleaned_page)
            
        return '\n\n'.join(full_text)

# --- PDF Data Extraction Function ---
def extract_campaign_data(text):
    """Extracts structured campaign data using GPT-4"""
    prompt = f"""
    You are a precision-focused sustainability analyst. Extract the following fields from the marketing plan text. 
    Follow these strict rules:
    1. If a field is not mentioned, return "NOT_FOUND" (do not guess).
    2. For "Materials Used", list ONLY specific items with quantities (e.g., "Brochures: 2000, Tote Bags: 500").
    3. For "Duration", return only a number (days).
    4. For "Staff Count", return only a number.
    5. For "Vendor Type", return "local" or "non-local" (lowercase).
    6. For "Travel Mode", return one of: "Air", "Train", "Car", "Other".

    Fields to extract:
    - Campaign Name
    - Location
    - Duration (in days)
    - Staff Count
    - Travel Mode
    - Materials Used
    - Accommodation Type (e.g., "3-star", "4-star", "5-star", "budget")
    - Vendor Type (local or non-local)

    Text:
    {text}

    Respond with ONLY a JSON object (no extra text). Example:
    {{
        "Campaign Name": "Green Expo 2023",
        "Location": "Melbourne",
        "Duration": 3,
        "Staff Count": 15,
        "Travel Mode": "Air",
        "Materials Used": "Brochures: 1000, Tote Bags: 300",
        "Accommodation Type": "4-star",
        "Vendor Type": "local"
    }}
    """
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=500
    )
    
    raw_response = response.choices[0].message.content.strip()
    if raw_response.startswith('```'):
        raw_response = raw_response.split('```')[1].strip()
    
    return json.loads(raw_response)

# --- Input Method Selection (Main Sidebar) ---
st.sidebar.header("🔍 Input Method")
input_method = st.sidebar.radio(
    "Choose how to provide campaign data:",
    ["Manual Entry", "Upload PDF"],
    index=0 if st.session_state["input_method"] == "manual" else 1,
    key="input_method_selector"
)

# Update session state based on selection
st.session_state["input_method"] = "manual" if input_method == "Manual Entry" else "pdf"

# --- PDF Upload Workflow ---
if st.session_state["input_method"] == "pdf":
    st.sidebar.header("📄 Upload Marketing Plan")
    uploaded_file = st.sidebar.file_uploader("Upload PDF (max 10 pages)", type="pdf")
    
    if uploaded_file:
        with st.spinner("Extracting data from PDF..."):
            pdf_text = extract_text_from_pdf(uploaded_file)
            
            # Show extracted text for verification
            with st.sidebar.expander("View Extracted Text", expanded=False):
                st.text_area("Raw Text", pdf_text, height=150)
            
            try:
                extracted_data = extract_campaign_data(pdf_text)
                
                # Map extracted fields to session state
                field_mapping = {
                    "Campaign Name": "Campaign Name",
                    "Location": "Location",
                    "Duration": "Duration",
                    "Staff Count": "Staff Count",
                    "Travel Mode": "Travel Mode",
                    "Accommodation Type": "Accommodation",
                    "Vendor Type": "Local Vendors",
                    "Materials Used": "Materials"
                }
                
                # Update session state with extracted data
                for extracted_key, form_key in field_mapping.items():
                    if extracted_key in extracted_data and extracted_data[extracted_key] != "NOT_FOUND":
                        if form_key == "Local Vendors":
                            st.session_state["campaign_data"][form_key] = extracted_data[extracted_key] == "local"
                        elif form_key == "Duration" or form_key == "Staff Count":
                            try:
                                st.session_state["campaign_data"][form_key] = int(extracted_data[extracted_key])
                            except ValueError:
                                pass  # Keep default if conversion fails
                        elif form_key == "Materials":
                            # Parse brochures and tote bags
                            materials = extracted_data[extracted_key]
                            if "Brochures:" in materials:
                                try:
                                    st.session_state["campaign_data"]["Brochures"] = int(materials.split("Brochures:")[1].split(",")[0].strip())
                                except (IndexError, ValueError):
                                    pass
                            if "Tote Bags:" in materials:
                                try:
                                    st.session_state["campaign_data"]["Tote Bags"] = int(materials.split("Tote Bags:")[1].split(",")[0].strip())
                                except (IndexError, ValueError):
                                    pass
                        else:
                            st.session_state["campaign_data"][form_key] = extracted_data[extracted_key]
                
                st.sidebar.success("✅ Data extracted successfully! Review and edit below.")
                
            except json.JSONDecodeError:
                st.sidebar.error("❌ Failed to parse data. Please check PDF formatting.")
            except Exception as e:
                st.sidebar.error(f"❌ Error: {str(e)[:50]}")

# --- Manual Input Form ---
st.sidebar.header("📋 Campaign Details")
with st.sidebar.form("campaign_form"):
    # Campaign Name
    campaign_name = st.text_input(
        "Campaign Name",
        st.session_state["campaign_data"]["Campaign Name"]
    )
    
    # Location
    location = st.text_input(
        "Location",
        st.session_state["campaign_data"]["Location"]
    )
    
    # Duration
    duration = st.slider(
        "Duration (days)",
        1, 10,
        st.session_state["campaign_data"]["Duration"]
    )
    
    # Staff Count
    staff_count = st.number_input(
        "Staff Count",
        min_value=1,
        value=st.session_state["campaign_data"]["Staff Count"]
    )
    
    # Travel Mode
    travel_mode = st.selectbox(
        "Travel Mode",
        ["Air", "Train", "Car"],
        index=["Air", "Train", "Car"].index(st.session_state["campaign_data"]["Travel Mode"])
    )
    
    # Materials
    col1, col2 = st.columns(2)
    with col1:
        brochures = st.number_input(
            "Brochures",
            min_value=0,
            value=st.session_state["campaign_data"]["Brochures"]
        )
    with col2:
        tote_bags = st.number_input(
            "Tote Bags",
            min_value=0,
            value=st.session_state["campaign_data"]["Tote Bags"]
        )
    
    # Accommodation
    accommodation = st.selectbox(
        "Accommodation",
        ["3-star", "4-star", "5-star"],
        index=["3-star", "4-star", "5-star"].index(st.session_state["campaign_data"]["Accommodation"])
    )
    
    # Local Vendors
    local_vendors = st.checkbox(
        "Using Local Vendors?",
        value=st.session_state["campaign_data"]["Local Vendors"]
    )
    
    # Save button
    submit = st.form_submit_button("Save Details")
    if submit:
        # Update session state with form data
        st.session_state["campaign_data"].update({
            "Campaign Name": campaign_name,
            "Location": location,
            "Duration": duration,
            "Staff Count": staff_count,
            "Travel Mode": travel_mode,
            "Brochures": brochures,
            "Tote Bags": tote_bags,
            "Accommodation": accommodation,
            "Local Vendors": local_vendors
        })
        st.sidebar.success("✅ Details saved!")

# --- Load Form Data from Session State ---
data = st.session_state["campaign_data"]
campaign_name = data["Campaign Name"]
location = data["Location"]
duration = data["Duration"]
staff_count = data["Staff Count"]
travel_mode = data["Travel Mode"]
brochures = data["Brochures"]
tote_bags = data["Tote Bags"]
accommodation = data["Accommodation"]
local_vendors = data["Local Vendors"]

# --- Sustainability Scoring Logic ---
def calculate_scores():
    """Calculates sustainability scores based on campaign parameters"""
    env_score = 40
    if travel_mode == "Air":
        env_score -= 12
    elif travel_mode == "Car":
        env_score -= 6
    else:
        env_score -= 3
        
    env_score -= min(5, (brochures // 1000) * 5)
    env_score -= min(4, (tote_bags // 300) * 4)

    social_score = 30
    if not local_vendors:
        social_score -= 10
    if accommodation == "5-star":
        social_score -= 5

    gov_score = 20
    innovation_score = 10

    return {
        "Environmental Impact": max(0, round(env_score)),
        "Social Responsibility": max(0, round(social_score)),
        "Governance & Ethics": gov_score,
        "Innovation & Inclusion": innovation_score
    }

scores = calculate_scores()
total_score = sum(scores.values())

# --- Enhanced SDG Information ---
sdg_details = {
    "SDG 12: Responsible Consumption and Production": {
        "goal": "Ensure sustainable consumption and production patterns",
        "targets": [
            "Halve per capita global food waste at the retail and consumer levels",
            "Achieve the environmentally sound management of chemicals and all wastes",
            "Reduce waste generation through prevention, reduction, recycling, and reuse"
        ],
        "alignment": "✅ Aligned" if (brochures < 1000 and tote_bags < 300) else "⚠️ Partial",
        "explanation": f"Your campaign uses {brochures} brochures and {tote_bags} tote bags. Reducing printed materials and using recyclable tote bags strengthens alignment with SDG 12."
    },
    "SDG 13: Climate Action": {
        "goal": "Take urgent action to combat climate change and its impacts",
        "targets": [
            "Strengthen resilience and adaptive capacity to climate-related hazards",
            "Integrate climate change measures into national policies, strategies, and planning",
            "Improve education, awareness-raising, and human and institutional capacity on climate change mitigation"
        ],
        "alignment": "✅ Aligned" if travel_mode in ["Train", "Car"] else "⚠️ Partial",
        "explanation": f"Travel mode ({travel_mode}) significantly impacts carbon emissions. Air travel has higher emissions than train or car travel, reducing alignment with SDG 13."
    },
    "SDG 8: Decent Work and Economic Growth": {
        "goal": "Promote sustained, inclusive, and sustainable economic growth, full and productive employment, and decent work for all",
        "targets": [
            "Achieve higher levels of economic productivity through diversification, technological upgrading, and innovation",
            "Promote development-oriented policies that support productive activities, decent job creation, entrepreneurship, and innovation",
            "Protect labor rights and promote safe and secure working environments for all workers"
        ],
        "alignment": "✅ Aligned" if local_vendors else "⚠️ Partial",
        "explanation": f"Using {'' if local_vendors else 'non-'}local vendors directly impacts local economies. Local sourcing supports decent work and economic growth in the campaign location (SDG 8)."
    },
    "SDG 5 & 11: Gender Equality & Sustainable Cities": {
        "goal": "SDG 5: Achieve gender equality; SDG 11: Make cities inclusive, safe, resilient, and sustainable",
        "targets": [
            "SDG 5: Ensure women's full participation in decision-making",
            "SDG 11: Provide universal access to safe, inclusive green spaces",
            "SDG 11: Strengthen efforts to protect cultural and natural heritage"
        ],
        "alignment": "⚠️ Partial (needs more data)",
        "explanation": "Alignment depends on gender diversity in staff (SDG 5) and whether the campaign venue is accessible, green, and supports local communities (SDG 11)."
    }
}

# --- AI Recommendations Generator ---
def generate_ai_recommendations(description):
    """Generates sustainability recommendations using GPT-4"""
    prompt = f"""
    You are a sustainability expert. Based on the following campaign, suggest 3 specific ways to:
    1. Reduce environmental impact
    2. Improve social responsibility
    3. Enhance SDG alignment

    Campaign Description:
    {description}

    Provide clear, actionable recommendations with specific metrics where possible.
    """
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=300
    )
    return response.choices[0].message.content.strip()

# --- HTML Report Generator ---
def generate_html_report():
    """Generates HTML content for PDF export"""
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial; padding: 20px; }}
            h1, h2 {{ color: #2E8B57; }}
            .section {{ margin-bottom: 25px; }}
            .sdg-box {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <h1>ESG Sustainability Report</h1>
        
        <div class="section">
            <h2>Campaign Overview</h2>
            <p><strong>Campaign:</strong> {campaign_name}</p>
            <p><strong>Location:</strong> {location}</p>
            <p><strong>Duration:</strong> {duration} days</p>
            <p><strong>Staff Count:</strong> {staff_count}</p>
            <p><strong>Travel Mode:</strong> {travel_mode}</p>
            <p><strong>Total Sustainability Score:</strong> {total_score}/100</p>
        </div>

        <div class="section">
            <h2>SDG Alignment Details</h2>
            {''.join(f'''
                <div class="sdg-box">
                    <h3>{sdg}</h3>
                    <p><strong>Goal:</strong> {details['goal']}</p>
                    <p><strong>Key Targets:</strong></p>
                    <ul>
                        {''.join(f"<li>{t}</li>" for t in details['targets'])}
                    </ul>
                    <p><strong>Alignment:</strong> {details['alignment']}</p>
                    <p><strong>Explanation:</strong> {details['explanation']}</p>
                </div>
            ''' for sdg, details in sdg_details.items())}
        </div>

        <div class="section">
            <h2>Sustainability Recommendations</h2>
            <ul>
                {''.join(f"<li>{rec}</li>" for rec in ai_recommendations.split('\n') if rec.strip())}
            </ul>
        </div>
    </body>
    </html>
    """
    return html

# --- Main Dashboard Layout ---
st.title("🌿 Sustainable Marketing Evaluator Dashboard")

# Input Method Indicator
st.info(f"Current Input Method: {'Manual Entry' if st.session_state['input_method'] == 'manual' else 'PDF Upload'}")

# Campaign Summary Section
st.subheader("Campaign Summary")
st.write(f"**Campaign Name:** {campaign_name}")
st.write(f"**Location:** {location}")
st.write(f"**Duration:** {duration} days")
st.write(f"**Staff Count:** {staff_count}")
st.write(f"**Travel Mode:** {travel_mode}")
st.write(f"**Materials:** {brochures} brochures, {tote_bags} tote bags")
st.write(f"**Accommodation:** {accommodation}")
st.write(f"**Local Vendors:** {'Yes' if local_vendors else 'No'}")

# Sustainability Scorecard Section
st.subheader("📊 Sustainability Scorecard")
st.metric("Overall Sustainability Score", f"{total_score}/100")

fig, ax = plt.subplots(figsize=(10, 5))
ax.bar(scores.keys(), scores.values(), color=["#4CAF50", "#2196F3", "#FF9800", "#9C27B0"])
ax.set_ylim(0, 40)
ax.set_ylabel("Score")
ax.set_title("Sustainability Performance Breakdown")
st.pyplot(fig)

# Enhanced SDG Section
st.subheader("🌍 SDG Alignment Details")
for sdg, details in sdg_details.items():
    with st.expander(sdg):
        st.write(f"**Global Goal:** {details['goal']}")
        st.write("**Key Targets:**")
        for target in details['targets']:
            st.write(f"- {target}")
        st.write(f"**Campaign Alignment:** {details['alignment']}")
        st.write(f"**Explanation:** {details['explanation']}")

# AI Recommendations Section
st.subheader("🧠 AI Sustainability Recommendations")
campaign_description = (
    f"{campaign_name} in {location} with {staff_count} staff traveling by {travel_mode}, "
    f"using {brochures} brochures and {tote_bags} tote bags, staying in {accommodation} accommodation. "
    f"Local vendors: {'used' if local_vendors else 'not used'}."
)

if st.button("Generate AI Recommendations"):
    with st.spinner("Analyzing sustainability opportunities..."):
        ai_recommendations = generate_ai_recommendations(campaign_description)
        st.session_state["ai_recommendations"] = ai_recommendations
else:
    ai_recommendations = st.session_state.get("ai_recommendations", "")

if ai_recommendations:
    st.markdown(ai_recommendations)

# ESG Report Preview and Export
st.subheader("📄 ESG Report Preview")
with st.expander("View ESG Report Summary"):
    st.write(f"**Campaign:** {campaign_name}")
    st.write(f"**Location:** {location}")
    st.write(f"**Duration:** {duration} days")
    st.write(f"**Total Score:** {total_score}/100")
    st.write("**SDG Contributions:**")
    for sdg, details in sdg_details.items():
        st.write(f"- {sdg}: {details['alignment']}")
    if ai_recommendations:
        st.write("**Recommendations:**")
        for rec in ai_recommendations.split("\n"):
            if rec.strip():
                st.write(f"- {rec}")

# PDF Export Functionality
if st.button("📄 Export ESG Report as PDF"):
    if "ai_recommendations" not in st.session_state:
        st.warning("Please generate AI recommendations first before exporting.")
    else:
        try:
            html_content = generate_html_report()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
                pdfkit.from_string(html_content, tmpfile.name)
                
                with open(tmpfile.name, "rb") as f:
                    st.download_button(
                        label="Download ESG Report PDF",
                        data=f,
                        file_name=f"{campaign_name.replace(' ', '_')}_ESG_Report.pdf",
                        mime="application/pdf"
                    )
            os.unlink(tmpfile.name)
        except Exception as e:
            st.error(f"Failed to generate PDF: {str(e)}. Ensure pdfkit and wkhtmltopdf are installed.")
