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
        "Location": "Sydney",  # Destination
        "Departure": "Melbourne",
        "Duration": 2,
        "Staff Count": 25,
        "Travel Mode": "Air",
        "Materials": [{"type": "Brochures", "quantity": 2000}, {"type": "Tote Bags", "quantity": 500}],
        "Accommodation": "4-star",
        "Local Vendors": True,
        "Travel Distance": None  # km, estimated by AI
    }
if "material_count" not in st.session_state:
    st.session_state["material_count"] = len(st.session_state["campaign_data"]["Materials"])
if "rerun_trigger" not in st.session_state:
    st.session_state["rerun_trigger"] = False

# --- Sustainability Weights ---
MATERIAL_IMPACT_WEIGHTS = {
    "default": 2,
    "Brochures": 3, "Flyers": 3, "Posters": 4, "Banners": 5,
    "Tote Bags": 2, "Merchandise (Plastic)": 8, "Merchandise (Fabric)": 3,
    "Stickers": 6, "Leaflets": 3
}

# --- Emission Factors (kg CO2 per km per person) ---
# Source: https://www.icao.int/environmental-protection/CarbonOffset/Pages/default.aspx
EMISSION_FACTORS = {
    "Air": 0.25,       # Short-haul flights
    "Train": 0.06,     # Electric trains
    "Car": 0.17,       # Average gasoline car
    "Other": 0.12      # E.g., buses
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
                remaining = max_chars - total_chars
                full_text.append(cleaned_page[:remaining])
                break
            full_text.append(cleaned_page)
            total_chars += len(cleaned_page)
        return '\n\n'.join(full_text)

# --- AI: Extract Campaign Data (Including Locations) ---
def extract_campaign_data(text):
    if not client:
        st.error("OpenAI client not initialized.")
        return None

    prompt = f"""
    Extract campaign data with these KEY fields:
    - Departure Location (origin city)
    - Destination Location (event city)
    - All materials with quantities
    - Travel Mode, Duration, Staff Count, etc.

    Text: {text}

    Respond with ONLY JSON (example structure):
    {{
        "Campaign Name": "Eco Fest",
        "Departure Location": "Melbourne",
        "Destination Location": "Sydney",
        "Duration": 3,
        "Staff Count": 10,
        "Travel Mode": "Train",
        "Materials Used": "Brochures: 500, Banners: 10",
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

# --- AI: Estimate Travel Distance (km) ---
def estimate_travel_distance(departure, destination, travel_mode):
    if not client or not departure or not destination:
        return None

    prompt = f"""
    Estimate the typical travel distance in KILOMETERS between {departure} and {destination}
    for {travel_mode} travel. Return ONLY the number (no text, no units). If unknown, return 0.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=10
        )
        distance = response.choices[0].message.content.strip()
        return float(distance) if distance.isdigit() else None
    except Exception as e:
        st.warning(f"Could not estimate distance: {str(e)}")
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

# --- PDF Upload Workflow ---
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
                # Update locations and travel
                st.session_state["campaign_data"].update({
                    "Campaign Name": extracted_data.get("Campaign Name", st.session_state["campaign_data"]["Campaign Name"]),
                    "Departure": extracted_data.get("Departure Location", st.session_state["campaign_data"]["Departure"]),
                    "Location": extracted_data.get("Destination Location", st.session_state["campaign_data"]["Location"]),
                    "Duration": int(extracted_data.get("Duration", st.session_state["campaign_data"]["Duration"])),
                    "Staff Count": int(extracted_data.get("Staff Count", st.session_state["campaign_data"]["Staff Count"])),
                    "Travel Mode": extracted_data.get("Travel Mode", st.session_state["campaign_data"]["Travel Mode"]),
                    "Accommodation": extracted_data.get("Accommodation Type", st.session_state["campaign_data"]["Accommodation"]),
                    "Local Vendors": extracted_data.get("Vendor Type", "local").lower() == "local"
                })

                # Parse materials
                if "Materials Used" in extracted_data and extracted_data["Materials Used"] != "NOT_FOUND":
                    materials_list = []
                    for item in extracted_data["Materials Used"].split(","):
                        item = item.strip()
                        if ":" in item:
                            mat_type, mat_qty = item.split(":", 1)
                            try:
                                materials_list.append({
                                    "type": mat_type.strip(),
                                    "quantity": int(mat_qty.strip())
                                })
                            except ValueError:
                                continue
                    if materials_list:
                        st.session_state["campaign_data"]["Materials"] = materials_list
                        st.session_state["material_count"] = len(materials_list)

                # Estimate distance from extracted locations
                if st.session_state["campaign_data"]["Departure"] and st.session_state["campaign_data"]["Location"]:
                    distance = estimate_travel_distance(
                        st.session_state["campaign_data"]["Departure"],
                        st.session_state["campaign_data"]["Location"],
                        st.session_state["campaign_data"]["Travel Mode"]
                    )
                    if distance:
                        st.session_state["campaign_data"]["Travel Distance"] = distance

                st.sidebar.success("✅ Data extracted! Review below.")

# --- Update Material Count ---
def update_material_count(change):
    if change == "add":
        st.session_state["material_count"] += 1
    elif change == "remove" and st.session_state["material_count"] > 1:
        st.session_state["material_count"] -= 1
    st.session_state["rerun_trigger"] = True

# --- Manual Input Form ---
st.sidebar.header("📋 Campaign Details")
with st.sidebar.form("campaign_form"):
    # Travel locations
    st.subheader("Travel Details")
    departure = st.text_input("Departure City", st.session_state["campaign_data"]["Departure"])
    destination = st.text_input("Destination City", st.session_state["campaign_data"]["Location"])
    
    # Basic fields
    campaign_name = st.text_input("Campaign Name", st.session_state["campaign_data"]["Campaign Name"])
    duration = st.slider("Duration (days)", 1, 10, st.session_state["campaign_data"]["Duration"])
    staff_count = st.number_input("Staff Count", min_value=1, value=st.session_state["campaign_data"]["Staff Count"])
    travel_mode = st.selectbox(
        "Travel Mode", ["Air", "Train", "Car", "Other"],
        index=["Air", "Train", "Car", "Other"].index(st.session_state["campaign_data"]["Travel Mode"])
    )
    
    # Materials section
    st.subheader("Materials Used")
    st.caption("Add/remove materials and quantities")
    
    materials = []
    for i in range(st.session_state["material_count"]):
        default_type = st.session_state["campaign_data"]["Materials"][i]["type"] if i < len(st.session_state["campaign_data"]["Materials"]) else ""
        default_qty = st.session_state["campaign_data"]["Materials"][i]["quantity"] if i < len(st.session_state["campaign_data"]["Materials"]) else 0
        
        col1, col2 = st.columns([2, 1])
        with col1:
            mat_type = st.text_input(f"Material {i+1} Type", default_type, key=f"mat_type_{i}")
        with col2:
            mat_qty = st.number_input(f"Quantity", min_value=0, value=default_qty, key=f"mat_qty_{i}")
        materials.append({"type": mat_type, "quantity": mat_qty})
    
    # Material buttons
    col_add, col_remove = st.columns(2)
    with col_add:
        if st.form_submit_button("➕ Add Material"):
            update_material_count("add")
    with col_remove:
        if st.form_submit_button("➖ Remove Last Material"):
            update_material_count("remove")

    # Other fields
    accommodation = st.selectbox(
        "Accommodation", ["3-star", "4-star", "5-star", "Budget"],
        index=["3-star", "4-star", "5-star", "Budget"].index(st.session_state["campaign_data"]["Accommodation"])
    )
    local_vendors = st.checkbox("Using Local Vendors?", value=st.session_state["campaign_data"]["Local Vendors"])

    # Save and estimate distance
    if st.form_submit_button("💾 Save & Calculate Distance"):
        # Update basic data
        st.session_state["campaign_data"].update({
            "Campaign Name": campaign_name,
            "Departure": departure,
            "Location": destination,
            "Duration": duration,
            "Staff Count": staff_count,
            "Travel Mode": travel_mode,
            "Materials": materials,
            "Accommodation": accommodation,
            "Local Vendors": local_vendors
        })

        # Estimate travel distance
        if departure and destination:
            with st.spinner("Estimating travel distance..."):
                distance = estimate_travel_distance(departure, destination, travel_mode)
                if distance:
                    st.session_state["campaign_data"]["Travel Distance"] = distance
                    st.sidebar.success(f"✅ Distance estimated: {distance} km")
                else:
                    st.session_state["campaign_data"]["Travel Distance"] = None
                    st.sidebar.warning("Could not estimate distance. Using default impact.")
        else:
            st.sidebar.warning("Enter departure and destination to calculate distance.")

# --- Trigger Rerun ---
if st.session_state["rerun_trigger"]:
    st.session_state["rerun_trigger"] = False
    st.rerun()

# --- Load Campaign Data ---
data = st.session_state["campaign_data"]
campaign_name = data["Campaign Name"]
departure = data["Departure"]
destination = data["Location"]
duration = data["Duration"]
staff_count = data["Staff Count"]
travel_mode = data["Travel Mode"]
materials = data["Materials"]
accommodation = data["Accommodation"]
local_vendors = data["Local Vendors"]
travel_distance = data["Travel Distance"]  # km

# --- Calculate Impacts ---
# Material impact
total_material_impact = 0
for mat in materials:
    if mat["quantity"] <= 0 or not mat["type"].strip():
        continue
    weight = MATERIAL_IMPACT_WEIGHTS.get(mat["type"], MATERIAL_IMPACT_WEIGHTS["default"])
    total_material_impact += (mat["quantity"] // 100) * weight

# Travel carbon impact (kg CO2)
total_carbon = 0
if travel_distance:
    emission_factor = EMISSION_FACTORS.get(travel_mode, EMISSION_FACTORS["Other"])
    total_carbon = travel_distance * emission_factor * staff_count  # per person * number of staff

# --- Sustainability Scoring ---
def calculate_scores():
    env_score = 40

    # Travel impact penalty (distance-based)
    if travel_distance:
        # Scale penalty by carbon (capped at 15)
        carbon_penalty = min(15, total_carbon // 100)  # Penalty per 100kg CO2
        env_score -= carbon_penalty
    else:
        # Fallback: mode-only penalty
        if travel_mode == "Air":
            env_score -= 10
        elif travel_mode == "Car":
            env_score -= 6
        else:
            env_score -= 4

    # Materials impact penalty
    env_score -= min(15, total_material_impact)

    # Social responsibility
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

# --- SDG Details (Updated for Travel Distance) ---
sdg_details = {
    "SDG 12: Responsible Consumption": {
        "goal": "Ensure sustainable consumption/production patterns",
        "alignment": "✅ Aligned" if total_material_impact < 10 else "⚠️ Partial",
        "explanation": f"Total material impact: {total_material_impact}. Reduce high-impact materials."
    },
    "SDG 13: Climate Action": {
        "goal": "Combat climate change",
        "alignment": "✅ Aligned" if (total_carbon < 500 or not travel_distance) else "⚠️ Partial",
        "explanation": f"Estimated travel emissions: {total_carbon:.0f}kg CO2. Switch to trains or reduce distance to improve alignment."
    },
    "SDG 8: Decent Work": {
        "goal": "Promote sustainable economic growth",
        "alignment": "✅ Aligned" if local_vendors else "⚠️ Partial"
    }
}

# --- AI Recommendations (Distance-Aware) ---
def generate_ai_recommendations():
    if not client:
        return ""
    
    materials_desc = ", ".join([f"{m['type']} ({m['quantity']} units)" for m in materials if m["quantity"] > 0])
    travel_desc = f"{staff_count} staff traveling {travel_distance or 'unknown'} km by {travel_mode} from {departure} to {destination}"
    
    prompt = f"""
    Analyze this campaign for sustainability improvements:
    - Name: {campaign_name}
    - Travel: {travel_desc}
    - Materials: {materials_desc}
    - Accommodation: {accommodation}
    - Local vendors: {'Yes' if local_vendors else 'No'}

    Suggest 3 specific changes to reduce carbon emissions (focus on travel and materials).
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

# Travel & Campaign Summary
st.subheader("🚗 Travel Details")
st.write(f"**Route:** {departure} → {destination} | **Mode:** {travel_mode}")
if travel_distance:
    st.write(f"**Estimated Distance:** {travel_distance:.0f} km | **Estimated Carbon Emissions:** {total_carbon:.0f} kg CO2")
else:
    st.write("**Distance:** Not estimated (enter locations and click 'Save & Calculate Distance')")

st.subheader("📋 Campaign Summary")
st.write(f"**Name:** {campaign_name} | **Duration:** {duration} days | **Staff:** {staff_count}")
st.write(f"**Accommodation:** {accommodation} | **Local Vendors:** {'Yes' if local_vendors else 'No'}")

# Materials Table
st.subheader("📦 Materials Used")
if materials and any(m["quantity"] > 0 for m in materials):
    materials_df = pd.DataFrame(materials)
    materials_df = materials_df[materials_df["quantity"] > 0]
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
            <h2>Travel Details</h2>
            <p>Route: {departure} → {destination} ({travel_distance or 'unknown'} km, {travel_mode})</p>
            <p>Estimated Emissions: {total_carbon:.0f} kg CO2</p>
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
