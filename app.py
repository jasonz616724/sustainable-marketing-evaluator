import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import openai
import pdfkit
import tempfile
import os
import fitz  # PyMuPDF for PDF text extraction
import json

# --- Page Configuration ---
st.set_page_config(page_title="Sustainable Marketing Evaluator", layout="wide")

# --- Load OpenAI API Key ---
openai.api_key = st.secrets["OPENAI_API_KEY"]

# --- PDF Upload and Text Extraction Functions ---
st.sidebar.header("📄 Upload Marketing Plan (PDF)")
uploaded_file = st.sidebar.file_uploader("Upload PDF", type="pdf")

def extract_text_from_pdf(file, max_chars=8000):
    """
    Extracts text from PDF while cleaning noise and limiting length
    Args:
        file: Uploaded PDF file object
        max_chars: Maximum characters to process (prevents token overflow)
    Returns:
        Cleaned text string from PDF
    """
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        full_text = []
        total_chars = 0
        
        for page in doc:
            # Extract and clean page text
            page_text = page.get_text().strip()
            if not page_text:
                continue  # Skip empty pages
            
            # Remove header/footer noise patterns
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

def extract_campaign_data(text):
    """
    Uses GPT-4 to extract structured campaign data from text
    Args:
        text: Cleaned text from PDF
    Returns:
        Dictionary with extracted campaign metrics
    """
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
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,  # Low temperature for consistent output
        max_tokens=500
    )
    
    # Clean response to ensure valid JSON
    raw_response = response.choices[0].message.content.strip()
    # Remove markdown code blocks if present
    if raw_response.startswith('```'):
        raw_response = raw_response.split('```')[1].strip()
    
    return json.loads(raw_response)

# --- Default Campaign Values ---
defaults = {
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

# --- Handle PDF Upload and Data Extraction ---
if uploaded_file:
    with st.spinner("Extracting campaign details..."):
        # Extract and display raw text for debugging
        pdf_text = extract_text_from_pdf(uploaded_file)
        with st.expander("View Extracted Text (for debugging)"):
            st.text_area("Raw Text from PDF", pdf_text, height=200)
        
        try:
            extracted = extract_campaign_data(pdf_text)
            
            # Identify missing fields
            missing_fields = [k for k, v in extracted.items() if v == "NOT_FOUND"]
            if missing_fields:
                st.warning(f"⚠️ Missing fields: {', '.join(missing_fields)}. Using defaults for these.")
            
            # Map extracted data to form fields
            field_mapping = {
                "Accommodation": "Accommodation Type",
                "Local Vendors": "Vendor Type",
                "Brochures": "Materials Used",
                "Tote Bags": "Materials Used"
            }
            
            for key in defaults:
                extracted_key = field_mapping.get(key, key)
                
                if extracted_key in extracted and extracted[extracted_key] != "NOT_FOUND":
                    # Handle materials splitting
                    if key in ["Brochures", "Tote Bags"] and extracted_key == "Materials Used":
                        materials = extracted[extracted_key]
                        if key == "Brochures" and "Brochures:" in materials:
                            try:
                                defaults[key] = int(materials.split("Brochures:")[1].split(",")[0].strip())
                            except (IndexError, ValueError):
                                pass  # Keep default on parsing error
                        if key == "Tote Bags" and "Tote Bags:" in materials:
                            try:
                                defaults[key] = int(materials.split("Tote Bags:")[1].split(",")[0].strip())
                            except (IndexError, ValueError):
                                pass  # Keep default on parsing error
                    
                    # Handle vendor type conversion
                    elif key == "Local Vendors":
                        defaults[key] = extracted[extracted_key] == "local"
                    
                    # Handle numeric fields
                    elif key in ["Duration", "Staff Count"]:
                        try:
                            defaults[key] = int(extracted[extracted_key])
                        except (ValueError, TypeError):
                            pass  # Keep default on parsing error
                    
                    # Handle text fields
                    else:
                        defaults[key] = extracted[extracted_key]
        
        except json.JSONDecodeError:
            st.error("⚠️ Failed to parse response. The AI returned invalid JSON format.")
        except Exception as e:
            st.error(f"⚠️ Extraction failed: {str(e)}. Please check PDF content formatting.")

# --- Sidebar Input Form ---
st.sidebar.header("📋 Review & Edit Campaign Details")
campaign_name = st.sidebar.text_input("Campaign Name", defaults["Campaign Name"])
location = st.sidebar.text_input("Location", defaults["Location"])
duration = st.sidebar.slider("Duration (days)", 1, 10, defaults["Duration"])
staff_count = st.sidebar.number_input("Staff Count", min_value=1, value=defaults["Staff Count"])
travel_mode = st.sidebar.selectbox(
    "Travel Mode", 
    ["Air", "Train", "Car"], 
    index=["Air", "Train", "Car"].index(defaults["Travel Mode"])
)
brochures = st.sidebar.number_input("Printed Brochures", min_value=0, value=defaults["Brochures"])
tote_bags = st.sidebar.number_input("Tote Bags", min_value=0, value=defaults["Tote Bags"])
accommodation = st.sidebar.selectbox(
    "Accommodation", 
    ["3-star", "4-star", "5-star"], 
    index=["3-star", "4-star", "5-star"].index(defaults["Accommodation"])
)
local_vendors = st.sidebar.checkbox("Using Local Vendors?", value=defaults["Local Vendors"])

# --- Sustainability Scoring Logic ---
def calculate_scores():
    """Calculates sustainability scores based on campaign parameters"""
    # Environmental impact scoring (40% weight)
    env_score = 40
    if travel_mode == "Air":
        env_score -= 12  # Highest impact penalty
    elif travel_mode == "Car":
        env_score -= 6   # Medium impact penalty
    else:
        env_score -= 3   # Lowest impact penalty
        
    env_score -= min(5, (brochures // 1000) * 5)  # Penalize excessive brochures
    env_score -= min(4, (tote_bags // 300) * 4)    # Penalize excessive tote bags

    # Social responsibility scoring (30% weight)
    social_score = 30
    if not local_vendors:
        social_score -= 10  # Penalty for non-local vendors
    if accommodation == "5-star":
        social_score -= 5   # Penalty for luxury accommodation

    # Fixed baseline scores for remaining categories
    gov_score = 20         # Governance & Ethics (20% weight)
    innovation_score = 10  # Innovation & Inclusion (10% weight)

    return {
        "Environmental Impact": max(0, round(env_score)),
        "Social Responsibility": max(0, round(social_score)),
        "Governance & Ethics": gov_score,
        "Innovation & Inclusion": innovation_score
    }

# Calculate scores
scores = calculate_scores()
total_score = sum(scores.values())

# --- SDG Alignment Mapping ---
sdg_status = {
    "SDG 12 (Responsible Consumption)": "✅ Aligned",
    "SDG 13 (Climate Action)": "⚠️ Partial",
    "SDG 8 (Decent Work)": "✅ Aligned",
    "SDG 5 & 11 (Gender & Cities)": "⚠️ Partial"
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
    
    response = openai.ChatCompletion.create(
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
            .metric {{ font-weight: bold; }}
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
            <h2>SDG Contributions</h2>
            <ul>
                {''.join(f"<li>{sdg}: {status}</li>" for sdg, status in sdg_status.items())}
            </ul>
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

# Score visualization
fig, ax = plt.subplots(figsize=(10, 5))
ax.bar(scores.keys(), scores.values(), color=["#4CAF50", "#2196F3", "#FF9800", "#9C27B0"])
ax.set_ylim(0, 40)
ax.set_ylabel("Score")
ax.set_title("Sustainability Performance Breakdown")
st.pyplot(fig)

# SDG Alignment Section
st.subheader("🌍 SDG Alignment")
for sdg, status in sdg_status.items():
    st.write(f"{sdg}: {status}")

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
    for sdg, status in sdg_status.items():
        st.write(f"- {sdg}: {status}")
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
            os.unlink(tmpfile.name)  # Clean up temporary file
        except Exception as e:
            st.error(f"Failed to generate PDF: {str(e)}. Ensure pdfkit and wkhtmltopdf are installed.")
