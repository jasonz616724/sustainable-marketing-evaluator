import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import pdfkit
import tempfile
import os
import fitz 

# --- Page Configuration ---
st.set_page_config(page_title="Mock Sustainable Marketing Evaluator", layout="wide")

# --- Mock AI Recommendations (Pre-written feedback) ---
MOCK_RECOMMENDATIONS = {
    "high_carbon": [
        "Consider switching 50% of staff travel from air to train to reduce CO2 emissions by ~70%.",
        "Replace plastic materials with biodegradable alternatives (e.g., compostable brochures).",
        "Shorten the campaign duration by 1 day to lower overall energy consumption."
    ],
    "high_plastic": [
        "Swap plastic tote bags for cotton alternatives (reduces material impact by 75%).",
        "Use digital QR codes instead of printed flyers to cut paper waste by 100%.",
        "Partner with local recycling facilities to ensure 100% of leftover materials are recycled."
    ],
    "low_local": [
        "Source 3+ key materials from local vendors to boost community support and reduce transport emissions.",
        "Choose a locally owned hotel for accommodation to align with SDG 8 (Decent Work).",
        "Collaborate with local influencers instead of international ones to reduce travel needs."
    ],
    "balanced": [
        "Maintain high recyclability rates by expanding use of paper and cotton materials.",
        "Offset remaining travel emissions by donating to a verified carbon offset project.",
        "Document your sustainability practices in a post-campaign report to set a benchmark."
    ]
}

# --- Session State Initialization ---
if "campaign_data" not in st.session_state:
    st.session_state["campaign_data"] = {
        "Campaign Name": "Green Horizons Launch",
        "Departure": "Melbourne",
        "Destination": "Sydney",
        "Travel Distance (km)": 870,
        "Duration (days)": 2,
        "Staff Count": 25,
        "Travel Mode": "Air",
        "Materials": [
            {"type": "Brochures", "quantity": 2000, "material_type": "Paper"},
            {"type": "Tote Bags", "quantity": 500, "material_type": "Plastic"}
        ],
        "Accommodation": "4-star",
        "Local Vendors": True,
        "extracted_pdf_text": ""  # For mock PDF extraction
    }
if "material_count" not in st.session_state:
    st.session_state["material_count"] = len(st.session_state["campaign_data"]["Materials"])
if "rerun_trigger" not in st.session_state:
    st.session_state["rerun_trigger"] = False
if "mock_recommendations" not in st.session_state:
    st.session_state["mock_recommendations"] = []

# --- Sustainability Constants (Static) ---
EMISSION_FACTORS = {
    "Air": 0.25, "Train": 0.06, "Car": 0.17, "Bus": 0.08, "Other": 0.12
}
MATERIAL_IMPACT = {
    "Paper": {"weight": 3, "recyclable": True},
    "Plastic": {"weight": 8, "recyclable": False},
    "Cotton": {"weight": 2, "recyclable": True},
    "Fabric": {"weight": 3, "recyclable": True},
    "Metal": {"weight": 5, "recyclable": True},
    "Glass": {"weight": 4, "recyclable": True},
    "Other": {"weight": 5, "recyclable": False}
}

# --- Helper Functions ---
def update_material_count(change):
    if change == "add":
        st.session_state["material_count"] += 1
    elif change == "remove" and st.session_state["material_count"] > 1:
        st.session_state["material_count"] -= 1
    st.session_state["rerun_trigger"] = True

def extract_text_from_pdf(file):
    """Mock PDF extraction: just returns raw text (no AI processing)"""
    try:
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            text = "\n\n".join([page.get_text().strip() for page in doc])
            st.session_state["campaign_data"]["extracted_pdf_text"] = text
            return text
    except Exception as e:
        st.error(f"PDF extraction failed: {str(e)}")
        return ""

def get_mock_recommendations():
    """Generate mock recommendations based on campaign data"""
    data = st.session_state["campaign_data"]
    total_carbon = data["Travel Distance (km)"] * EMISSION_FACTORS[data["Travel Mode"]] * data["Staff Count"]
    plastic_quantity = sum(m["quantity"] for m in data["Materials"] if m["material_type"] == "Plastic")

    # Logic to pick relevant mock recommendations
    if total_carbon > 2000:
        return MOCK_RECOMMENDATIONS["high_carbon"]
    elif plastic_quantity > 1000:
        return MOCK_RECOMMENDATIONS["high_plastic"]
    elif not data["Local Vendors"]:
        return MOCK_RECOMMENDATIONS["low_local"]
    else:
        return MOCK_RECOMMENDATIONS["balanced"]

# --- Sidebar: Input Form + PDF Upload ---
st.sidebar.header("📋 Campaign Details")

# PDF Upload (Mock Extraction)
st.sidebar.subheader("📄 Upload Marketing Plan (Mock)")
uploaded_pdf = st.sidebar.file_uploader("Upload PDF to extract text", type="pdf")
if uploaded_pdf:
    with st.spinner("Extracting text (mock)..."):
        pdf_text = extract_text_from_pdf(uploaded_pdf)
        with st.sidebar.expander("View Extracted Text"):
            st.text_area("Raw PDF Content", pdf_text, height=150)
        st.sidebar.success("✅ Text extracted (mock: no AI processing)")

# Campaign Form
with st.sidebar.form("campaign_form"):
    # Travel Info
    st.subheader("Travel Details")
    departure = st.text_input("Departure City", st.session_state["campaign_data"]["Departure"])
    destination = st.text_input("Destination City", st.session_state["campaign_data"]["Destination"])
    travel_distance = st.number_input("Travel Distance (km)", min_value=0, value=st.session_state["campaign_data"]["Travel Distance (km)"])
    travel_mode = st.selectbox("Travel Mode", ["Air", "Train", "Car", "Bus", "Other"],
                             index=["Air", "Train", "Car", "Bus", "Other"].index(st.session_state["campaign_data"]["Travel Mode"]))

    # Basic Info
    campaign_name = st.text_input("Campaign Name", st.session_state["campaign_data"]["Campaign Name"])
    duration = st.slider("Duration (days)", 1, 30, st.session_state["campaign_data"]["Duration (days)"])
    staff_count = st.number_input("Staff Count", min_value=1, value=st.session_state["campaign_data"]["Staff Count"])

    # Materials
    st.subheader("Materials")
    materials = []
    for i in range(st.session_state["material_count"]):
        default_type = st.session_state["campaign_data"]["Materials"][i]["type"] if i < len(st.session_state["campaign_data"]["Materials"]) else ""
        default_qty = st.session_state["campaign_data"]["Materials"][i]["quantity"] if i < len(st.session_state["campaign_data"]["Materials"]) else 0
        default_mat_type = st.session_state["campaign_data"]["Materials"][i]["material_type"] if i < len(st.session_state["campaign_data"]["Materials"]) else "Paper"

        col1, col2, col3 = st.columns([3, 2, 3])
        with col1:
            mat_name = st.text_input(f"Material {i+1} Name", default_type, key=f"mat_{i}_name")
        with col2:
            mat_qty = st.number_input(f"Quantity", min_value=0, value=default_qty, key=f"mat_{i}_qty")
        with col3:
            mat_type = st.selectbox("Type", list(MATERIAL_IMPACT.keys()),
                                 index=list(MATERIAL_IMPACT.keys()).index(default_mat_type),
                                 key=f"mat_{i}_type")
        materials.append({"type": mat_name, "quantity": mat_qty, "material_type": mat_type})

    # Add/Remove Materials
    col_add, col_remove = st.columns(2)
    with col_add:
        if st.form_submit_button("➕ Add Material"):
            update_material_count("add")
    with col_remove:
        if st.form_submit_button("➖ Remove Material"):
            update_material_count("remove")

    # Other Details
    accommodation = st.selectbox("Accommodation", ["Budget", "3-star", "4-star", "5-star"],
                               index=["Budget", "3-star", "4-star", "5-star"].index(st.session_state["campaign_data"]["Accommodation"]))
    local_vendors = st.checkbox("Use Local Vendors?", value=st.session_state["campaign_data"]["Local Vendors"])

    # Save
    if st.form_submit_button("💾 Save Details"):
        st.session_state["campaign_data"].update({
            "Campaign Name": campaign_name, "Departure": departure, "Destination": destination,
            "Travel Distance (km)": travel_distance, "Duration (days)": duration,
            "Staff Count": staff_count, "Travel Mode": travel_mode, "Materials": materials,
            "Accommodation": accommodation, "Local Vendors": local_vendors
        })
        st.success("Saved!")

# --- Handle Reruns ---
if st.session_state["rerun_trigger"]:
    st.session_state["rerun_trigger"] = False
    st.rerun()

# --- Load Data & Calculate Metrics ---
data = st.session_state["campaign_data"]
total_carbon = data["Travel Distance (km)"] * EMISSION_FACTORS[data["Travel Mode"]] * data["Staff Count"]
total_material_impact = sum((m["quantity"]//100) * MATERIAL_IMPACT[m["material_type"]]["weight"] for m in data["Materials"] if m["quantity"] > 0)
recyclable_rate = sum(m["quantity"] for m in data["Materials"] if m["quantity"] > 0 and MATERIAL_IMPACT[m["material_type"]]["recyclable"]) / \
                 (sum(m["quantity"] for m in data["Materials"] if m["quantity"] > 0) + 1) * 100  # +1 to avoid division by zero

# --- Scoring ---
def calculate_scores():
    env_score = 40 - min(15, total_carbon//500) - min(15, total_material_impact//5)
    social_score = 30 - (0 if data["Local Vendors"] else 10) - (5 if data["Accommodation"] == "5-star" else 0)
    return {
        "Environmental Impact": max(0, round(env_score)),
        "Social Responsibility": max(0, round(social_score)),
        "Governance": 20,
        "Operations": 10
    }
scores = calculate_scores()
total_score = sum(scores.values())

# --- Main Dashboard ---
st.title("🌿 Mock Sustainable Marketing Evaluator")
st.info("No AI/APIs used! PDF upload and recommendations are mocked.")

# Travel & Carbon
st.subheader("🚗 Travel & Carbon Footprint")
col1, col2, col3 = st.columns(3)
with col1: st.metric("Route", f"{data['Departure']} → {data['Destination']}")
with col2: st.metric("Distance", f"{data['Travel Distance (km)']} km")
with col3: st.metric("Total CO₂", f"{total_carbon:.0f} kg")

# Materials
st.subheader("📦 Materials")
if any(m["quantity"] > 0 for m in data["Materials"]):
    df = pd.DataFrame(data["Materials"])
    st.dataframe(df[df["quantity"] > 0], use_container_width=True)
else:
    st.write("Add materials in the sidebar.")

# Scorecard
st.subheader("📊 Scorecard")
st.metric("Overall Score", f"{total_score}/100")
fig, ax = plt.subplots(figsize=(10, 5))
ax.bar(scores.keys(), scores.values(), color=["#4CAF50", "#2196F3", "#FF9800", "#9C27B0"])
st.pyplot(fig)

# Mock AI Recommendations
st.subheader("💡 Mock Sustainability Recommendations")
if st.button("Generate Recommendations"):
    with st.spinner("Analyzing (mock)..."):
        st.session_state["mock_recommendations"] = get_mock_recommendations()

if st.session_state["mock_recommendations"]:
    for i, rec in enumerate(st.session_state["mock_recommendations"], 1):
        st.write(f"{i}. {rec}")

# PDF Export
if st.button("📄 Export Report"):
    try:
        html = f"<h1>{data['Campaign Name']} Report</h1><p>Score: {total_score}/100</p>"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdfkit.from_string(html, tmp.name)
            with open(tmp.name, "rb") as f:
                st.download_button("Download PDF", f, f"{data['Campaign Name']}_report.pdf")
        os.unlink(tmp.name)
    except Exception as e:
        st.error(f"PDF error: {e}")
