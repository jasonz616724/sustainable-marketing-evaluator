import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import openai
from openai import OpenAI, NotFoundError, AuthenticationError
import pdfkit
import tempfile
import os
import fitz  # PyMuPDF
import json
from collections import defaultdict

# --- Initialize OpenAI Client ---
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    st.error(f"OpenAI Client Error: {str(e)}. Check your API key.")
    client = None

# --- Page Configuration ---
st.set_page_config(page_title="Sustainable Marketing Evaluator", layout="wide")

# --- Initialize Session State ---
if "input_method" not in st.session_state:
    st.session_state["input_method"] = "manual"
if "campaign_data" not in st.session_state:
    st.session_state["campaign_data"] = {
        "Campaign Name": "Green Horizons Launch",
        "Location": "Sydney",
        "Duration": 2,
        "Staff Count": 25,
        "Travel Mode": "Air",
        "Materials": [{"type": "Brochures", "quantity": 2000}, {"type": "Tote Bags", "quantity": 500}],  # Dynamic list
        "Accommodation": "4-star",
        "Local Vendors": True
    }
if "material_count" not in st.session_state:
    st.session_state["material_count"] = len(st.session_state["campaign_data"]["Materials"])

# --- Sustainability Weights for Materials ---
# Higher weights = more environmental impact (penalized more)
MATERIAL_IMPACT_WEIGHTS = {
    "default": 2,  # Fallback for unknown materials
    "Brochures": 3,
    "Flyers": 3,
    "Posters": 4,
    "Banners": 5,
    "Tote Bags": 2,
    "Merchandise (Plastic)": 8,
    "Merchandise (Fabric)": 3,
    "Stickers": 6,
    "Leaflets": 3
}

# --- PDF Text Extraction ---
def extract_text_from_pdf(file, max_chars=8000):
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        full_text = []
        total_chars = 0
        for page in doc:
            page_text = page.get_text().strip()
            if not page_text:
                continue
            lines = [line for line in page_text.split('\n') 
                    if not line.strip().lower().startswith(("page", "confidential", "draft", "©"))]
            cleaned_page = '\n'.join(lines)
            if total_chars + len(cleaned_page) > max_chars:
                full_text.append(cleaned_page[:remaining])
                break
            full_text.append(cleaned_page)
            total_chars += len(cleaned_page)
        return '\n\n'.join(full_text)

# --- PDF Data Extraction (Updated for Dynamic Materials) ---
def extract_campaign_data(text):
    if not client:
        st.error("OpenAI client not initialized.")
        return None

    prompt = f"""
    Extract campaign data with THIS FOCUS: list ALL materials used (with quantities). 
    Follow rules:
    1. Return "NOT_FOUND" for missing fields.
    2. Materials: list EVERY item (e.g., "Brochures: 2000, Flyers: 500, Plastic Merch: 100").
    3. Duration/Staff Count: numbers only.
    4. Vendor Type: "local" or "non-local".
    5. Travel Mode: "Air", "Train", "Car", "Other".

    Fields: Campaign Name, Location, Duration (days), Staff Count, Travel Mode, Materials Used, 
            Accommodation Type, Vendor Type.

    Text: {text}

    Respond with ONLY JSON. Example:
    {{
        "Campaign Name": "Eco Fest",
        "Location": "Melbourne",
        "Duration": 3,
        "Staff Count": 10,
        "Travel Mode": "Train",
        "Materials Used": "Brochures: 500, Banners: 10, Fabric Merch: 200",
        "Accommodation Type": "3-star",
        "Vendor Type": "local"
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500
        )
        raw_response = response.choices[0].message.content.strip()
        if raw_response.startswith('```'):
            raw_response = raw_response.split('```')[1].strip()
        return json.loads(raw_response)
    except Exception as e:
        st.error(f"Extraction failed: {str(e)}")
        return None

# --- Input Method Selection ---
st.sidebar.header("🔍 Input Method")
input_method = st.sidebar.radio(
    "Choose data entry method:",
    ["Manual Entry", "Upload PDF"],
    index=0 if st.session_state["input_method"] == "manual" else 1,
    key="input_method_selector"
)
st.session_state["input_method"] = "manual" if input_method == "Manual Entry" else "pdf"

# --- PDF Upload Workflow (Updated for Materials) ---
if st.session_state["input_method"] == "pdf" and client:
    st.sidebar.header("📄 Upload Marketing Plan")
    uploaded_file = st.sidebar.file_uploader("Upload PDF", type="pdf")
    
    if uploaded_file:
        with st.spinner("Extracting data..."):
            pdf_text = extract_text_from_pdf(uploaded_file)
            with st.sidebar.expander("View Extracted Text"):
                st.text_area("Raw Text", pdf_text, height=150)
            
            extracted_data = extract_campaign_data(pdf_text)
            if extracted_data:
                # Update basic fields
                st.session_state["campaign_data"].update({
                    "Campaign Name": extracted_data.get("Campaign Name", st.session_state["campaign_data"]["Campaign Name"]),
                    "Location": extracted_data.get("Location", st.session_state["campaign_data"]["Location"]),
                    "Duration": int(extracted_data.get("Duration", st.session_state["campaign_data"]["Duration"])),
                    "Staff Count": int(extracted_data.get("Staff Count", st.session_state["campaign_data"]["Staff Count"])),
                    "Travel Mode": extracted_data.get("Travel Mode", st.session_state["campaign_data"]["Travel Mode"]),
                    "Accommodation": extracted_data.get("Accommodation Type", st.session_state["campaign_data"]["Accommodation"]),
                    "Local Vendors": extracted_data.get("Vendor Type", "local").lower() == "local"
                })

                # Parse materials (e.g., "Brochures: 500, Banners: 10" → list of dicts)
                if "Materials Used" in extracted_data and extracted_data["Materials Used"] != "NOT_FOUND":
                    materials_str = extracted_data["Materials Used"]
                    materials_list = []
                    for item in materials_str.split(","):
                        item = item.strip()
                        if ":" in item:
                            mat_type, mat_qty = item.split(":", 1)
                            try:
                                materials_list.append({
                                    "type": mat_type.strip(),
                                    "quantity": int(mat_qty.strip())
                                })
                            except ValueError:
                                continue  # Skip if quantity is invalid
                    if materials_list:
                        st.session_state["campaign_data"]["Materials"] = materials_list
                        st.session_state["material_count"] = len(materials_list)

                st.sidebar.success("✅ Data extracted! Review below.")

# --- Manual Input Form (Dynamic Materials) ---
st.sidebar.header("📋 Campaign Details")
with st.sidebar.form("campaign_form"):
    # Basic fields
    campaign_name = st.text_input("Campaign Name", st.session_state["campaign_data"]["Campaign Name"])
    location = st.text_input("Location", st.session_state["campaign_data"]["Location"])
    duration = st.slider("Duration (days)", 1, 10, st.session_state["campaign_data"]["Duration"])
    staff_count = st.number_input("Staff Count", min_value=1, value=st.session_state["campaign_data"]["Staff Count"])
    travel_mode = st.selectbox(
        "Travel Mode", ["Air", "Train", "Car", "Other"],
        index=["Air", "Train", "Car", "Other"].index(st.session_state["campaign_data"]["Travel Mode"])
    )
    accommodation = st.selectbox(
        "Accommodation", ["3-star", "4-star", "5-star", "Budget"],
        index=["3-star", "4-star", "5-star", "Budget"].index(st.session_state["campaign_data"]["Accommodation"])
    )
    local_vendors = st.checkbox("Using Local Vendors?", value=st.session_state["campaign_data"]["Local Vendors"])

    # Dynamic materials section
    st.subheader("Materials Used")
    st.caption("Add/remove materials and their quantities")
    
    # Initialize materials in session state if empty
    if not st.session_state["campaign_data"]["Materials"]:
        st.session_state["campaign_data"]["Materials"] = [{"type": "", "quantity": 0}]
    
    # Display current materials with edit fields
    materials = []
    for i in range(st.session_state["material_count"]):
        # Use existing data if available, else empty
        default_type = st.session_state["campaign_data"]["Materials"][i]["type"] if i < len(st.session_state["campaign_data"]["Materials"]) else ""
        default_qty = st.session_state["campaign_data"]["Materials"][i]["quantity"] if i < len(st.session_state["campaign_data"]["Materials"]) else 0
        
        col1, col2 = st.columns([2, 1])
        with col1:
            mat_type = st.text_input(f"Material {i+1} Type", default_type, key=f"mat_type_{i}")
        with col2:
            mat_qty = st.number_input(f"Quantity", min_value=0, value=default_qty, key=f"mat_qty_{i}")
        materials.append({"type": mat_type, "quantity": mat_qty})
    
    # Buttons to add/remove materials
    col_add, col_remove = st.columns(2)
    with col_add:
        add_material = st.form_submit_button("➕ Add Material")
    with col_remove:
        remove_material = st.form_submit_button("➖ Remove Last Material")
    
    # Update material count based on buttons
    if add_material:
        st.session_state["material_count"] += 1
        st.experimental_rerun()  # Refresh to show new field
    if remove_material and st.session_state["material_count"] > 1:
        st.session_state["material_count"] -= 1
        st.experimental_rerun()  # Refresh to remove field

    # Save all data
    submit = st.form_submit_button("💾 Save All Details")
    if submit:
        st.session_state["campaign_data"].update({
            "Campaign Name": campaign_name,
            "Location": location,
            "Duration": duration,
            "Staff Count": staff_count,
            "Travel Mode": travel_mode,
            "Materials": materials,  # Update with dynamic materials
            "Accommodation": accommodation,
            "Local Vendors": local_vendors
        })
        st.sidebar.success("✅ All details saved!")

# --- Load Campaign Data ---
data = st.session_state["campaign_data"]
campaign_name = data["Campaign Name"]
location = data["Location"]
duration = data["Duration"]
staff_count = data["Staff Count"]
travel_mode = data["Travel Mode"]
materials = data["Materials"]
accommodation = data["Accommodation"]
local_vendors = data["Local Vendors"]

# --- Sustainability Scoring (Updated for Materials) ---
def calculate_scores():
    # Environmental impact (40% weight)
    env_score = 40

    # Travel impact penalty
    if travel_mode == "Air":
        env_score -= 12
    elif travel_mode == "Car":
        env_score -= 6
    elif travel_mode == "Other":
        env_score -= 8  # Assume moderate impact for "Other"

    # Materials impact penalty (weighted by material type)
    total_material_impact = 0
    for mat in materials:
        if mat["quantity"] <= 0 or not mat["type"].strip():
            continue  # Skip empty/invalid entries
        # Get weight for material type (use default if unknown)
        weight = MATERIAL_IMPACT_WEIGHTS.get(mat["type"], MATERIAL_IMPACT_WEIGHTS["default"])
        # Calculate impact (scaled by quantity)
        total_material_impact += (mat["quantity"] // 100) * weight  # Penalty per 100 units
    
    # Apply materials penalty (capped at 15 to avoid negative scores)
    env_score -= min(15, total_material_impact)

    # Social responsibility (30% weight)
    social_score = 30
    if not local_vendors:
        social_score -= 10
    if accommodation == "5-star":
        social_score -= 5

    # Fixed scores
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

# --- SDG Details (Updated for Materials) ---
sdg_details = {
    "SDG 12: Responsible Consumption": {
        "goal": "Ensure sustainable consumption/production patterns",
        "targets": ["Reduce waste", "Promote recyclable materials"],
        "alignment": "✅ Aligned" if total_material_impact < 10 else "⚠️ Partial",
        "explanation": f"Total material impact: {total_material_impact}. Reduce high-impact materials (e.g., plastic) to improve alignment."
    },
    "SDG 13: Climate Action": {
        "goal": "Combat climate change",
        "targets": ["Reduce carbon emissions"],
        "alignment": "✅ Aligned" if travel_mode in ["Train", "Other"] else "⚠️ Partial",
        "explanation": f"Travel mode ({travel_mode}) affects carbon footprint."
    },
    "SDG 8: Decent Work": {
        "goal": "Promote sustainable economic growth",
        "alignment": "✅ Aligned" if local_vendors else "⚠️ Partial"
    }
}

# --- AI Recommendations (Updated for Materials) ---
def generate_ai_recommendations():
    if not client:
        return ""
    
    # Describe materials for AI
    materials_desc = ", ".join([f"{m['type']} ({m['quantity']} units)" for m in materials if m["quantity"] > 0])
    prompt = f"""
    Analyze this campaign for sustainability improvements:
    - Name: {campaign_name}
    - Location: {location}
    - Staff: {staff_count} (travel: {travel_mode})
    - Materials: {materials_desc}
    - Accommodation: {accommodation}
    - Local vendors: {'Yes' if local_vendors else 'No'}

    Suggest 3 specific changes to reduce environmental impact, with focus on materials.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"Recommendations failed: {str(e)}")
        return ""

# --- Main Dashboard ---
st.title("🌿 Sustainable Marketing Evaluator Dashboard")
st.info(f"Input Method: {'Manual Entry' if st.session_state['input_method'] == 'manual' else 'PDF Upload'}")

# Campaign Summary
st.subheader("Campaign Summary")
st.write(f"**Name:** {campaign_name} | **Location:** {location} | **Duration:** {duration} days")
st.write(f"**Staff:** {staff_count} | **Travel:** {travel_mode} | **Accommodation:** {accommodation}")

# Materials Table
st.subheader("📦 Materials Used")
if materials and any(m["quantity"] > 0 for m in materials):
    materials_df = pd.DataFrame(materials)
    materials_df = materials_df[materials_df["quantity"] > 0]  # Hide empty entries
    st.dataframe(materials_df, use_container_width=True)
else:
    st.write("No materials listed. Add materials in the sidebar.")

# Scorecard
st.subheader("📊 Sustainability Scorecard")
st.metric("Overall Score", f"{total_score}/100")
fig, ax = plt.subplots(figsize=(10, 5))
ax.bar(scores.keys(), scores.values(), color=["#4CAF50", "#2196F3", "#FF9800", "#9C27B0"])
ax.set_ylim(0, 40)
st.pyplot(fig)

# SDG Alignment
st.subheader("🌍 SDG Alignment")
for sdg, details in sdg_details.items():
    with st.expander(sdg):
        st.write(f"**Goal:** {details['goal']}")
        st.write(f"**Alignment:** {details['alignment']}")
        st.write(f"**Explanation:** {details['explanation']}")

# AI Recommendations
st.subheader("🧠 AI Sustainability Recommendations")
if st.button("Generate Recommendations") and client:
    with st.spinner("Analyzing..."):
        st.session_state["ai_recommendations"] = generate_ai_recommendations()

if "ai_recommendations" in st.session_state and st.session_state["ai_recommendations"]:
    st.markdown(st.session_state["ai_recommendations"])

# PDF Export
if st.button("📄 Export ESG Report") and "ai_recommendations" in st.session_state:
    try:
        html = f"""
        <html><head><style>
            body {{ font-family: Arial; padding: 20px; }}
            .material-table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            .material-table th, td {{ border: 1px solid #ddd; padding: 8px; }}
        </style></head><body>
            <h1>ESG Report: {campaign_name}</h1>
            <h2>Materials</h2>
            <table class="material-table">
                <tr><th>Type</th><th>Quantity</th></tr>
                {''.join(f"<tr><td>{m['type']}</td><td>{m['quantity']}</td></tr>" for m in materials if m["quantity"] > 0)}
            </table>
            <h2>Total Score: {total_score}/100</h2>
            <h2>Recommendations</h2>
            <p>{st.session_state['ai_recommendations'].replace('\n', '<br>')}</p>
        </body></html>
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdfkit.from_string(html, tmp.name)
            with open(tmp.name, "rb") as f:
                st.download_button("Download PDF", f, f"{campaign_name}_ESG_Report.pdf")
        os.unlink(tmp.name)
    except Exception as e:
        st.error(f"PDF export failed: {str(e)}")
