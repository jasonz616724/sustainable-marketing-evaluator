import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import pdfkit
import tempfile
import os
import fitz  # For PDF text extraction (no AI)

# --- Page Configuration ---
st.set_page_config(page_title="Sustainable Marketing Evaluator", layout="wide")

# --- Session State Initialization ---
if "campaign_data" not in st.session_state:
    st.session_state["campaign_data"] = {
        "Campaign Name": "Green Horizons Launch",
        "Departure": "Melbourne",
        "Destination": "Sydney",
        "Travel Distance (km)": 870,  # Manual input
        "Duration (days)": 2,
        "Staff Count": 25,
        "Travel Mode": "Air",
        "Materials": [
            {"type": "Brochures", "quantity": 2000, "material_type": "Paper"},
            {"type": "Tote Bags", "quantity": 500, "material_type": "Cotton"}
        ],
        "Accommodation": "4-star",
        "Local Vendors": True
    }
if "material_count" not in st.session_state:
    st.session_state["material_count"] = len(st.session_state["campaign_data"]["Materials"])
if "rerun_trigger" not in st.session_state:
    st.session_state["rerun_trigger"] = False

# --- Sustainability Constants (Static, No AI) ---
# Emission factors (kg CO2 per km per person)
EMISSION_FACTORS = {
    "Air": 0.25,       # Short-haul flights
    "Train": 0.06,     # Electric trains
    "Car": 0.17,       # Average gasoline car
    "Bus": 0.08,       # Public bus
    "Other": 0.12
}

# Material impact weights (higher = more unsustainable)
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
    """Update number of material entries"""
    if change == "add":
        st.session_state["material_count"] += 1
    elif change == "remove" and st.session_state["material_count"] > 1:
        st.session_state["material_count"] -= 1
    st.session_state["rerun_trigger"] = True

def extract_text_from_pdf(file):
    """Extract raw text from PDF (no AI processing)"""
    try:
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            return "\n\n".join([page.get_text().strip() for page in doc])
    except Exception as e:
        st.error(f"PDF extraction failed: {str(e)}")
        return ""

# --- Sidebar Input Form ---
st.sidebar.header("📋 Campaign Details")
with st.sidebar.form("campaign_form"):
    # Travel Information
    st.subheader("Travel Details")
    departure = st.text_input(
        "Departure City",
        st.session_state["campaign_data"]["Departure"]
    )
    destination = st.text_input(
        "Destination City",
        st.session_state["campaign_data"]["Destination"]
    )
    travel_distance = st.number_input(
        "Travel Distance (km)",
        min_value=0,
        value=st.session_state["campaign_data"]["Travel Distance (km)"]
    )
    travel_mode = st.selectbox(
        "Travel Mode",
        ["Air", "Train", "Car", "Bus", "Other"],
        index=["Air", "Train", "Car", "Bus", "Other"].index(st.session_state["campaign_data"]["Travel Mode"])
    )

    # Basic Campaign Info
    st.subheader("Campaign Basics")
    campaign_name = st.text_input(
        "Campaign Name",
        st.session_state["campaign_data"]["Campaign Name"]
    )
    duration = st.slider(
        "Duration (days)",
        1, 30,
        st.session_state["campaign_data"]["Duration (days)"]
    )
    staff_count = st.number_input(
        "Number of Staff",
        min_value=1,
        value=st.session_state["campaign_data"]["Staff Count"]
    )

    # Materials Section
    st.subheader("Marketing Materials")
    st.caption("Add materials used (e.g., brochures, merch)")
    
    materials = []
    for i in range(st.session_state["material_count"]):
        # Get existing data or defaults
        default_type = ""
        default_qty = 0
        default_mat_type = "Paper"
        if i < len(st.session_state["campaign_data"]["Materials"]):
            default_type = st.session_state["campaign_data"]["Materials"][i]["type"]
            default_qty = st.session_state["campaign_data"]["Materials"][i]["quantity"]
            default_mat_type = st.session_state["campaign_data"]["Materials"][i]["material_type"]
        
        # Input fields
        col1, col2, col3 = st.columns([3, 2, 3])
        with col1:
            mat_name = st.text_input(f"Material {i+1} Name", default_type, key=f"mat_{i}_name")
        with col2:
            mat_qty = st.number_input(f"Quantity", min_value=0, value=default_qty, key=f"mat_{i}_qty")
        with col3:
            mat_type = st.selectbox(
                "Material Type",
                list(MATERIAL_IMPACT.keys()),
                index=list(MATERIAL_IMPACT.keys()).index(default_mat_type),
                key=f"mat_{i}_type"
            )
        materials.append({
            "type": mat_name,
            "quantity": mat_qty,
            "material_type": mat_type
        })
    
    # Add/remove materials
    col_add, col_remove = st.columns(2)
    with col_add:
        if st.form_submit_button("➕ Add Material"):
            update_material_count("add")
    with col_remove:
        if st.form_submit_button("➖ Remove Last Material"):
            update_material_count("remove")

    # Other Details
    st.subheader("Additional Details")
    accommodation = st.selectbox(
        "Accommodation Type",
        ["Budget", "3-star", "4-star", "5-star"],
        index=["Budget", "3-star", "4-star", "5-star"].index(st.session_state["campaign_data"]["Accommodation"])
    )
    local_vendors = st.checkbox(
        "Using Local Vendors?",
        value=st.session_state["campaign_data"]["Local Vendors"]
    )

    # Save all data
    if st.form_submit_button("💾 Save All Details"):
        st.session_state["campaign_data"].update({
            "Campaign Name": campaign_name,
            "Departure": departure,
            "Destination": destination,
            "Travel Distance (km)": travel_distance,
            "Duration (days)": duration,
            "Staff Count": staff_count,
            "Travel Mode": travel_mode,
            "Materials": materials,
            "Accommodation": accommodation,
            "Local Vendors": local_vendors
        })
        st.success("✅ Details saved!")

# --- Handle Reruns for Material Count ---
if st.session_state["rerun_trigger"]:
    st.session_state["rerun_trigger"] = False
    st.rerun()

# --- Load Campaign Data ---
data = st.session_state["campaign_data"]

# --- Calculate Sustainability Metrics (No AI) ---
# 1. Carbon Emissions from Travel
emission_factor = EMISSION_FACTORS[data["Travel Mode"]]
total_carbon = data["Travel Distance (km)"] * emission_factor * data["Staff Count"]

# 2. Material Impact Score
total_material_impact = 0
recyclable_materials = 0
total_materials = 0
for mat in data["Materials"]:
    if mat["quantity"] <= 0:
        continue
    total_materials += mat["quantity"]
    mat_weight = MATERIAL_IMPACT[mat["material_type"]]["weight"]
    total_material_impact += (mat["quantity"] // 100) * mat_weight  # Impact per 100 units
    if MATERIAL_IMPACT[mat["material_type"]]["recyclable"]:
        recyclable_materials += mat["quantity"]

# 3. Recyclability Rate
recyclable_rate = (recyclable_materials / total_materials) * 100 if total_materials > 0 else 0

# 4. Sustainability Scores (0-100)
def calculate_scores():
    # Environmental Score (40% of total)
    env_score = 40
    # Penalize high carbon emissions
    carbon_penalty = min(15, total_carbon // 500)  # Penalty per 500kg CO2
    env_score -= carbon_penalty
    # Penalize high material impact
    material_penalty = min(15, total_material_impact // 5)  # Penalty per 5 impact units
    env_score -= material_penalty
    # Reward recyclability
    if recyclable_rate > 70:
        env_score += 5  # Bonus for high recyclability

    # Social Score (30% of total)
    social_score = 30
    if not data["Local Vendors"]:
        social_score -= 10  # Penalty for non-local vendors
    if data["Accommodation"] == "5-star":
        social_score -= 5  # Penalty for luxury accommodation

    # Governance & Operational Scores (30% total)
    governance_score = 20
    operational_score = 10

    return {
        "Environmental Impact": max(0, round(env_score)),
        "Social Responsibility": max(0, round(social_score)),
        "Governance": governance_score,
        "Operations": operational_score
    }

scores = calculate_scores()
total_score = sum(scores.values())

# --- PDF Upload (Text Only, No AI) ---
st.sidebar.header("📄 Optional: Upload Marketing Plan")
uploaded_pdf = st.sidebar.file_uploader("Upload PDF (text extraction only)", type="pdf")
if uploaded_pdf:
    with st.sidebar.expander("View Extracted Text (No AI)"):
        pdf_text = extract_text_from_pdf(uploaded_pdf)
        st.text_area("Raw PDF Text", pdf_text, height=200)

# --- Main Dashboard ---
st.title("🌿 Sustainable Marketing Evaluator")
st.info("100% AI-free: No API costs, fully manual calculations")

# Travel & Carbon Footprint
st.subheader("🚗 Travel & Carbon Footprint")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Route", f"{data['Departure']} → {data['Destination']}")
with col2:
    st.metric("Distance", f"{data['Travel Distance (km)']} km")
with col3:
    st.metric("Total CO₂ Emissions", f"{total_carbon:.0f} kg")

# Carbon Breakdown Chart
fig, ax = plt.subplots(figsize=(8, 4))
ax.bar(
    ["Your Campaign", "Average Benchmark\n(Industry Standard)"],
    [total_carbon, 1500],  # Compare to 1.5-ton benchmark
    color=["#FF6B6B", "#4ECDC4"]
)
ax.set_ylabel("CO₂ Emissions (kg)")
ax.set_title("Carbon Footprint Comparison")
st.pyplot(fig)

# Materials Analysis
st.subheader("📦 Materials & Recyclability")
if total_materials > 0:
    # Materials table
    materials_df = pd.DataFrame(data["Materials"])
    materials_df = materials_df[materials_df["quantity"] > 0]  # Filter out zeros
    materials_df["Impact"] = [
        (m["quantity"] // 100) * MATERIAL_IMPACT[m["material_type"]]["weight"]
        for _, m in materials_df.iterrows()
    ]
    st.dataframe(materials_df, use_container_width=True)

    # Recyclability gauge
    fig, ax = plt.subplots(figsize=(6, 2))
    ax.bar(
        ["Recyclable Materials"],
        [recyclable_rate],
        color="#4CAF50",
        width=0.4
    )
    ax.set_ylim(0, 100)
    ax.set_ylabel("Recyclability Rate (%)")
    st.pyplot(fig)
else:
    st.write("Add materials in the sidebar to see analysis.")

# Sustainability Scorecard
st.subheader("📊 Sustainability Scorecard")
st.metric("Overall Sustainability Score", f"{total_score}/100")

# Score breakdown chart
fig, ax = plt.subplots(figsize=(10, 5))
ax.bar(
    scores.keys(),
    scores.values(),
    color=["#4CAF50", "#2196F3", "#FF9800", "#9C27B0"]
)
ax.set_ylim(0, 40)
ax.set_ylabel("Score (0-40)")
st.pyplot(fig)

# SDG Alignment (Static Mapping)
st.subheader("🌍 SDG Alignment")
sdg_alignment = [
    {
        "SDG Goal": "SDG 13: Climate Action",
        "Alignment": "Strong" if total_carbon < 1000 else "Moderate" if total_carbon < 2000 else "Weak",
        "Reason": f"Carbon emissions: {total_carbon:.0f} kg (lower = better)"
    },
    {
        "SDG Goal": "SDG 12: Responsible Consumption",
        "Alignment": "Strong" if recyclable_rate > 70 else "Moderate" if recyclable_rate > 30 else "Weak",
        "Reason": f"Recyclable materials: {recyclable_rate:.0f}% (higher = better)"
    },
    {
        "SDG Goal": "SDG 8: Decent Work",
        "Alignment": "Strong" if data["Local Vendors"] else "Weak",
        "Reason": "Local vendors support community economic growth"
    }
]
st.dataframe(sdg_alignment, use_container_width=True)

# Actionable Recommendations (Static, No AI)
st.subheader("💡 Improvement Recommendations")
recommendations = []
if total_carbon > 1000:
    recommendations.append(f"Reduce travel emissions: Switch from {data['Travel Mode']} to train (saves ~{total_carbon * 0.7:.0f} kg CO2)")
if recyclable_rate < 50:
    recommendations.append(f"Increase recyclability: Replace non-recyclable materials (currently {recyclable_rate:.0f}% recyclable)")
if not data["Local Vendors"]:
    recommendations.append("Use local vendors to boost SDG 8 alignment and reduce supply chain emissions")

for rec in recommendations:
    st.write(f"- {rec}")

# PDF Report Export
st.subheader("📄 Export Sustainability Report")
if st.button("Generate PDF Report"):
    try:
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial; margin: 20px; }}
                .section {{ margin-bottom: 30px; }}
                h1 {{ color: #2E8B57; }}
                table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; }}
            </style>
        </head>
        <body>
            <h1>Sustainability Report: {data['Campaign Name']}</h1>
            
            <div class="section">
                <h2>Travel Details</h2>
                <p>Route: {data['Departure']} → {data['Destination']}</p>
                <p>Distance: {data['Travel Distance (km)']} km | Mode: {data['Travel Mode']}</p>
                <p>Total CO₂ Emissions: {total_carbon:.0f} kg</p>
            </div>
            
            <div class="section">
                <h2>Materials Summary</h2>
                <table>
                    <tr><th>Material</th><th>Quantity</th><th>Type</th></tr>
                    {''.join(f"<tr><td>{m['type']}</td><td>{m['quantity']}</td><td>{m['material_type']}</td></tr>" for m in data["Materials"] if m["quantity"] > 0)}
                </table>
                <p>Recyclability Rate: {recyclable_rate:.0f}%</p>
            </div>
            
            <div class="section">
                <h2>Sustainability Score: {total_score}/100</h2>
                <ul>
                    {''.join(f"<li>{k}: {v}/40</li>" for k, v in scores.items())}
                </ul>
            </div>
            
            <div class="section">
                <h2>Recommendations</h2>
                <ul>
                    {''.join(f"<li>{rec}</li>" for rec in recommendations)}
                </ul>
            </div>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
            pdfkit.from_string(html, tmpfile.name)
            
            with open(tmpfile.name, "rb") as f:
                st.download_button(
                    label="Download PDF",
                    data=f,
                    file_name=f"{data['Campaign Name'].replace(' ', '_')}_sustainability_report.pdf",
                    mime="application/pdf"
                )
        os.unlink(tmpfile.name)
    except Exception as e:
        st.error(f"PDF generation failed: {str(e)}. Ensure 'wkhtmltopdf' is installed.")
