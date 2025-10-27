import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import requests  # For free distance API
import pdfkit
import tempfile
import os
import fitz  # PyMuPDF
from openai import OpenAI, NotFoundError

# --- Initialize OpenAI Client (Optional) ---
client = None
if "OPENAI_API_KEY" in st.secrets:
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    except Exception as e:
        st.warning(f"OpenAI key not working: {str(e)}. Some features may be limited.")
else:
    st.info("No OpenAI API key found. Using free features only.")

# --- Free Distance API (OpenRouteService) ---
def get_distance(departure, destination):
    """Get km between cities using OpenRouteService (free, no API key needed for limited use)"""
    if not departure or not destination:
        return None
    try:
        url = f"https://api.openrouteservice.org/v2/directions/driving-car"
        params = {
            "api_key": "5b3ce3597851110001cf6248ee7b215f8b340f6b952953d0204a762d9b7f5",  # Demo key (rate-limited)
            "start": f"{get_coords(departure)}",
            "end": f"{get_coords(destination)}"
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return round(response.json()["features"][0]["properties"]["summary"]["distance"] / 1000, 1)  # Convert m to km
        return None
    except Exception as e:
        st.warning(f"Distance API error: {str(e)}. Try manual entry.")
        return None

def get_coords(city):
    """Get approximate coordinates for a city (simplified lookup)"""
    # Fallback: Static city coordinates (expandable list)
    coords = {
        "Sydney": "151.2093,-33.8688",
        "Melbourne": "144.9631,-37.8136",
        "London": "0.1276,-51.5072",
        "New York": "-74.0060,40.7128",
        "Paris": "2.3522,48.8566"
    }
    return coords.get(city, "0,0")  # Default to (0,0) if unknown

# --- Session State Initialization ---
if "campaign_data" not in st.session_state:
    st.session_state["campaign_data"] = {
        "Campaign Name": "Green Horizons Launch",
        "Departure": "Melbourne",
        "Destination": "Sydney",
        "Duration": 2,
        "Staff Count": 25,
        "Travel Mode": "Air",
        "Materials": [{"type": "Brochures", "quantity": 2000}, {"type": "Tote Bags", "quantity": 500}],
        "Accommodation": "4-star",
        "Local Vendors": True,
        "Travel Distance": None,  # From free API
        "Manual Distance": None    # Allow manual override
    }
if "material_count" not in st.session_state:
    st.session_state["material_count"] = len(st.session_state["campaign_data"]["Materials"])
if "rerun_trigger" not in st.session_state:
    st.session_state["rerun_trigger"] = False

# --- Sustainability Constants (No AI Needed) ---
MATERIAL_IMPACT_WEIGHTS = {
    "default": 2, "Brochures": 3, "Flyers": 3, "Posters": 4, "Banners": 5,
    "Tote Bags": 2, "Merchandise (Plastic)": 8, "Merchandise (Fabric)": 3
}
EMISSION_FACTORS = {  # kg CO2 per km per person
    "Air": 0.25, "Train": 0.06, "Car": 0.17, "Other": 0.12
}
WASTE_FACTORS = {  # % of materials likely to become waste
    "default": 30, "Brochures": 60, "Flyers": 80, "Tote Bags": 10
}

# --- PDF Extraction (Optional, Costly) ---
def extract_text_from_pdf(file):
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        return "\n".join([page.get_text() for page in doc])

def extract_campaign_data(text):
    if not client:
        st.warning("PDF extraction requires OpenAI API key.")
        return None
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": f"Extract campaign data from: {text[:2000]}"}],
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Extraction failed (cost-saving mode): {str(e)}")
        return None

# --- Material Count Management ---
def update_material_count(change):
    if change == "add":
        st.session_state["material_count"] += 1
    elif change == "remove" and st.session_state["material_count"] > 1:
        st.session_state["material_count"] -= 1
    st.session_state["rerun_trigger"] = True

# --- Sidebar Form ---
st.sidebar.header("📋 Campaign Details")
with st.sidebar.form("campaign_form"):
    # Travel
    st.subheader("Travel")
    departure = st.text_input("Departure City", st.session_state["campaign_data"]["Departure"])
    destination = st.text_input("Destination City", st.session_state["campaign_data"]["Destination"])
    travel_mode = st.selectbox("Travel Mode", ["Air", "Train", "Car", "Other"])
    
    # Distance (free API + manual override)
    col1, col2 = st.columns(2)
    with col1:
        if st.form_submit_button("🔍 Get Distance (Free API)"):
            st.session_state["campaign_data"]["Travel Distance"] = get_distance(departure, destination)
    with col2:
        manual_distance = st.number_input("Or Enter km Manually", min_value=0, value=st.session_state["campaign_data"]["Manual Distance"] or 0)
        if manual_distance > 0:
            st.session_state["campaign_data"]["Manual Distance"] = manual_distance

    # Basic info
    campaign_name = st.text_input("Campaign Name", st.session_state["campaign_data"]["Campaign Name"])
    duration = st.slider("Duration (days)", 1, 10, st.session_state["campaign_data"]["Duration"])
    staff_count = st.number_input("Staff Count", min_value=1, value=st.session_state["campaign_data"]["Staff Count"])

    # Materials
    st.subheader("Materials")
    materials = []
    for i in range(st.session_state["material_count"]):
        mat_type = st.text_input(f"Material {i+1}", st.session_state["campaign_data"]["Materials"][i]["type"] if i < len(st.session_state["campaign_data"]["Materials"]) else "")
        mat_qty = st.number_input(f"Qty {i+1}", min_value=0, value=st.session_state["campaign_data"]["Materials"][i]["quantity"] if i < len(st.session_state["campaign_data"]["Materials"]) else 0)
        materials.append({"type": mat_type, "quantity": mat_qty})
    
    # Material buttons
    col_add, col_remove = st.columns(2)
    with col_add:
        if st.form_submit_button("➕ Add Material"):
            update_material_count("add")
    with col_remove:
        if st.form_submit_button("➖ Remove Material"):
            update_material_count("remove")

    # Other
    accommodation = st.selectbox("Accommodation", ["3-star", "4-star", "5-star", "Budget"])
    local_vendors = st.checkbox("Use Local Vendors?", value=st.session_state["campaign_data"]["Local Vendors"])

    # Save
    if st.form_submit_button("💾 Save All"):
        st.session_state["campaign_data"].update({
            "Campaign Name": campaign_name, "Departure": departure, "Destination": destination,
            "Duration": duration, "Staff Count": staff_count, "Travel Mode": travel_mode,
            "Materials": materials, "Accommodation": accommodation, "Local Vendors": local_vendors
        })
        st.success("Saved!")

# --- Rerun Handling ---
if st.session_state["rerun_trigger"]:
    st.session_state["rerun_trigger"] = False
    st.rerun()

# --- Load Data ---
data = st.session_state["campaign_data"]
travel_distance = data["Manual Distance"] or data["Travel Distance"]  # Prefer manual input
total_carbon = 0
if travel_distance:
    emission_factor = EMISSION_FACTORS[data["Travel Mode"]]
    total_carbon = travel_distance * emission_factor * data["Staff Count"]

# --- Material Impact Calculations (No AI) ---
total_material_impact = 0
total_waste_estimate = 0
for mat in data["Materials"]:
    if mat["quantity"] <= 0:
        continue
    weight = MATERIAL_IMPACT_WEIGHTS.get(mat["type"], MATERIAL_IMPACT_WEIGHTS["default"])
    total_material_impact += (mat["quantity"] // 100) * weight
    waste_pct = WASTE_FACTORS.get(mat["type"], WASTE_FACTORS["default"])
    total_waste_estimate += (mat["quantity"] * waste_pct) / 100  # kg of waste

# --- Scoring (No AI) ---
def calculate_scores():
    env_score = 40
    # Travel penalty
    if travel_distance:
        env_score -= min(15, total_carbon // 100)
    else:
        env_score -= {"Air":10, "Car":6, "Train":3, "Other":5}[data["Travel Mode"]]
    # Materials penalty
    env_score -= min(15, total_material_impact)
    
    social_score = 30 - (0 if data["Local Vendors"] else 10) - (5 if data["Accommodation"] == "5-star" else 0)
    return {
        "Environmental Impact": max(0, round(env_score)),
        "Social Responsibility": max(0, round(social_score)),
        "Governance": 20,
        "Innovation": 10
    }

scores = calculate_scores()
total_score = sum(scores.values())

# --- Dashboard (Enhanced Visuals) ---
st.title("🌿 Sustainable Marketing Evaluator")
st.info("Free features: No OpenAI API key required for core functionality!")

# Travel & Emissions
st.subheader("🚗 Travel & Carbon Footprint")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Route", f"{data['Departure']} → {data['Destination']}")
with col2:
    st.metric("Distance", f"{travel_distance or 'N/A'} km")
with col3:
    st.metric("Total CO₂ Emissions", f"{total_carbon:.0f} kg" if travel_distance else "N/A")

# Emissions Breakdown Chart
if travel_distance:
    fig, ax = plt.subplots()
    ax.pie(
        [total_carbon, 5000 - total_carbon],  # Compare to 5-ton benchmark
        labels=["Your Campaign", "Remaining 5-ton Budget"],
        colors=["#FF6B6B", "#4ECDC4"],
        autopct="%1.1f%%"
    )
    ax.set_title("Carbon Budget Usage (vs 5-ton annual per person)")
    st.pyplot(fig)

# Materials & Waste
st.subheader("📦 Materials & Waste Projection")
if data["Materials"] and any(m["quantity"] > 0 for m in data["Materials"]):
    materials_df = pd.DataFrame(data["Materials"])
    materials_df["Estimated Waste (kg)"] = [
        (m["quantity"] * WASTE_FACTORS.get(m["type"], 30)) / 100 
        for _, m in materials_df.iterrows()
    ]
    st.dataframe(materials_df, use_container_width=True)
    st.metric("Total Estimated Waste", f"{total_waste_estimate:.0f} kg")
else:
    st.write("Add materials in the sidebar to see waste projections.")

# Scorecard
st.subheader("📊 Sustainability Scorecard")
st.metric("Overall Score", f"{total_score}/100")
fig, ax = plt.subplots(figsize=(10, 3))
ax.bar(scores.keys(), scores.values(), color=["#4CAF50", "#2196F3", "#FF9800", "#9C27B0"])
ax.set_ylim(0, 40)
st.pyplot(fig)

# SDG Alignment (Static)
st.subheader("🌍 SDG Alignment")
sdg_data = [
    {"sdg": "SDG 13 (Climate)", "alignment": "Good" if total_carbon < 1000 else "Needs Work"},
    {"sdg": "SDG 12 (Consumption)", "alignment": "Good" if total_waste_estimate < 500 else "Needs Work"},
    {"sdg": "SDG 8 (Local Economy)", "alignment": "Good" if data["Local Vendors"] else "Needs Work"}
]
st.dataframe(sdg_data, use_container_width=True)

# Optional AI Recommendations (If Key Available)
if client:
    st.subheader("💡 AI Recommendations (Optional)")
    if st.button("Generate (Uses API Credits)"):
        with st.spinner("Generating..."):
            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": f"Improve sustainability for: {data['Campaign Name']}, {total_carbon}kg CO2, {total_waste_estimate}kg waste"}],
                    max_tokens=200
                )
                st.markdown(response.choices[0].message.content)
            except NotFoundError:
                st.error("Use gpt-3.5-turbo (cheaper) instead of gpt-4")
            except Exception as e:
                st.error(f"API error: {str(e)}")

# PDF Export (Free)
if st.button("📄 Export Report"):
    html = f"""
    <html><body>
        <h1>{data['Campaign Name']} - Sustainability Report</h1>
        <h2>Travel: {data['Departure']} → {data['Destination']} ({travel_distance} km)</h2>
        <p>Carbon Emissions: {total_carbon:.0f} kg</p>
        <h2>Materials Waste: {total_waste_estimate:.0f} kg</h2>
        <h2>Score: {total_score}/100</h2>
    </body></html>
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdfkit.from_string(html, tmp.name)
        with open(tmp.name, "rb") as f:
            st.download_button("Download PDF", f, f"{data['Campaign Name']}_report.pdf")
    os.unlink(tmp.name)
