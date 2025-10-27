import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import pdfkit
import tempfile
import os
import fitz

# --- Mock Recommendations (Aligned with Scoring Rulebook) ---
MOCK_RECOMMENDATIONS = {
    "high_carbon": [
        "Shift 50% of long-haul air travel to trains (cuts CO₂ by ~70% per staff).",
        "Cap 5-star accommodation at 20% of staff; use 3-star for the rest (reduces social impact penalty).",
        "Consolidate local staff into shared transport to eliminate redundant car trips."
    ],
    "high_plastic": [
        "Replace plastic merch with cotton alternatives (lowers material impact from 8→2).",
        "Use digital QR codes for brochures (cuts paper waste by 100%, boosts recyclability rate).",
        "Donate leftover materials to local nonprofits (counts toward Operations pillar points)."
    ],
    "low_local": [
        "Source 3+ materials from local vendors (moves Social score from 5→15 points).",
        "Partner with a local printer for any necessary brochures (reduces transport emissions).",
        "Add a sustainability clause to vendor contracts (gains Governance pillar points)."
    ],
    "balanced": [
        "Maintain 80%+ recyclability rate by expanding cotton/paper material use.",
        "Document your sustainability goals in a post-campaign report (gains Governance points).",
        "Offset remaining CO₂ via a verified project (aligns with SDG 13)."
    ]
}

# --- Session State Initialization ---
if "campaign_data" not in st.session_state:
    st.session_state["campaign_data"] = {
        "Campaign Name": "Green Horizons Launch",
        "Duration (days)": 2,
        "Staff Groups": [  # Support multiple staff groups with unique travel/accommodation
            {
                "Staff Count": 15,
                "Departure": "Melbourne",
                "Destination": "Sydney",
                "Travel Distance (km)": 870,
                "Travel Mode": "Air",
                "Accommodation": "4-star"
            },
            {
                "Staff Count": 10,
                "Departure": "Sydney (Local)",
                "Destination": "Sydney",
                "Travel Distance (km)": 0,
                "Travel Mode": "Other",
                "Accommodation": "3-star"
            }
        ],
        "Materials": [
            {"type": "Brochures", "quantity": 2000, "material_type": "Paper"},
            {"type": "Plastic Badges", "quantity": 300, "material_type": "Plastic"}
        ],
        "Local Vendors": True,
        "extracted_pdf_text": "",
        "governance_checks": [False, False, False, False, False],  # 5 Governance criteria
        "operations_checks": [False, False, False, False, False]   # 5 Operations criteria
    }
if "staff_group_count" not in st.session_state:
    st.session_state["staff_group_count"] = len(st.session_state["campaign_data"]["Staff Groups"])
if "material_count" not in st.session_state:
    st.session_state["material_count"] = len(st.session_state["campaign_data"]["Materials"])
if "rerun_trigger" not in st.session_state:
    st.session_state["rerun_trigger"] = False
if "mock_recommendations" not in st.session_state:
    st.session_state["mock_recommendations"] = []

# --- Sustainability Constants (Latest Rulebook) ---
# 1. Emission Factors (kg CO2/km/person)
EMISSION_FACTORS = {
    "Air": 0.25, "Train": 0.06, "Car": 0.17, "Bus": 0.08, "Other": 0.12
}

# 2. Material Impact (Rulebook Categories + Dropdown Options)
PREDEFINED_MATERIALS = [
    {"name": "Brochures", "type": "Paper", "weight": 3, "recyclable": True},
    {"name": "Flyers", "type": "Paper", "weight": 3, "recyclable": True},
    {"name": "Posters", "type": "Paper", "weight": 3, "recyclable": True},
    {"name": "Plastic Tote Bags", "type": "Plastic", "weight": 8, "recyclable": False},
    {"name": "Cotton Tote Bags", "type": "Cotton", "weight": 2, "recyclable": True},
    {"name": "Plastic Badges", "type": "Plastic", "weight": 8, "recyclable": False},
    {"name": "Metal Badges", "type": "Metal", "weight": 5, "recyclable": True},
    {"name": "Glass Trophies", "type": "Glass", "weight": 4, "recyclable": True},
    {"name": "Cardboard Displays", "type": "Paper", "weight": 3, "recyclable": True},
    {"name": "Polyester Banners", "type": "Fabric", "weight": 4, "recyclable": False},
    {"name": "Other (Custom)"}  # Trigger for manual input
]

# 3. Governance/Operations Criteria (Rulebook)
GOVERNANCE_CRITERIA = [
    "Written sustainability goal (e.g., 'Reduce plastic by 50%')",
    "Vendor contracts with sustainability clauses",
    "Eco-certified travel providers",
    "Certified material suppliers (FSC, Fair Trade)",
    "Planned post-campaign sustainability report"
]
OPERATIONS_CRITERIA = [
    "Campaign duration ≤ 3 days",
    "Digital alternatives for printed materials",
    "Consolidated staff travel (shared cars/trains)",
    "Leftover materials donated/recycled",
    "Accommodation near venue (walking/transit)"
]

# --- Helper Functions ---
def update_staff_count(change):
    if change == "add":
        st.session_state["staff_group_count"] += 1
    elif change == "remove" and st.session_state["staff_group_count"] > 1:
        st.session_state["staff_group_count"] -= 1
    st.session_state["rerun_trigger"] = True

def update_material_count(change):
    if change == "add":
        st.session_state["material_count"] += 1
    elif change == "remove" and st.session_state["material_count"] > 1:
        st.session_state["material_count"] -= 1
    st.session_state["rerun_trigger"] = True

def extract_text_from_pdf(file):
    try:
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            text = "\n\n".join([page.get_text().strip() for page in doc])
            st.session_state["campaign_data"]["extracted_pdf_text"] = text
            return text
    except Exception as e:
        st.error(f"PDF Extraction Error: {str(e)}")
        return ""

def calculate_total_carbon():
    """Calculate total CO2 from all staff groups (Rulebook 1.1)"""
    total = 0
    for group in st.session_state["campaign_data"]["Staff Groups"]:
        if group["Travel Distance (km)"] <= 0:
            continue
        emission_factor = EMISSION_FACTORS[group["Travel Mode"]]
        group_carbon = group["Travel Distance (km)"] * emission_factor * group["Staff Count"]
        total += group_carbon
    return total

def calculate_material_metrics():
    """Calculate Total Material Impact + Recyclability Rate (Rulebook 1.2)"""
    total_impact = 0
    total_recyclable = 0
    total_quantity = 0

    for mat in st.session_state["campaign_data"]["Materials"]:
        qty = mat["quantity"]
        if qty <= 0:
            continue
        total_quantity += qty

        # Get material properties (from predefined or custom)
        if mat["material_type"] == "Custom":
            weight = mat["custom_weight"]
            recyclable = mat["custom_recyclable"]
        else:
            for pre_mat in PREDEFINED_MATERIALS:
                if pre_mat["type"] == mat["material_type"]:
                    weight = pre_mat["weight"]
                    recyclable = pre_mat["recyclable"]
                    break

        # Calculate impact and recyclable quantity
        total_impact += (qty // 100) * weight
        if recyclable:
            total_recyclable += qty

    # Recyclability Rate (avoid division by zero)
    recyclable_rate = (total_recyclable / total_quantity * 100) if total_quantity > 0 else 100
    return total_impact, recyclable_rate, total_quantity

def calculate_scores():
    """Full scoring per latest rulebook (4 pillars)"""
    data = st.session_state["campaign_data"]
    total_carbon = calculate_total_carbon()
    total_material_impact, recyclable_rate, _ = calculate_material_metrics()

    # 1. Environmental Impact (40 points)
    # 1.1 Travel Carbon (20 points)
    if total_carbon <= 500:
        travel_score = 20
    elif 501 <= total_carbon <= 1000:
        travel_score = 17
    elif 1001 <= total_carbon <= 1500:
        travel_score = 14
    elif 1501 <= total_carbon <= 2000:
        travel_score = 11
    else:
        travel_score = 8

    # 1.2 Material Impact (20 points)
    material_penalty = min(10, total_material_impact // 5)
    if recyclable_rate >= 70:
        recyclable_bonus = 5
    elif 30 <= recyclable_rate < 70:
        recyclable_bonus = 2
    else:
        recyclable_bonus = 0
    material_score = max(0, 20 - material_penalty + recyclable_bonus)
    environmental_score = travel_score + material_score

    # 2. Social Responsibility (30 points)
    # 2.1 Local Vendors (15 points)
    local_score = 15 if data["Local Vendors"] else 0
    # 2.2 Accommodation (15 points: average across staff groups)
    total_acc_score = 0
    total_staff = sum(group["Staff Count"] for group in data["Staff Groups"])
    for group in data["Staff Groups"]:
        acc = group["Accommodation"]
        acc_score = 15 if acc in ["Budget", "3-star"] else 10 if acc == "4-star" else 5
        total_acc_score += acc_score * group["Staff Count"]
    accommodation_score = total_acc_score // total_staff  # Weighted average
    social_score = local_score + accommodation_score

    # 3. Governance (20 points: 4 per checked criteria)
    governance_score = sum(data["governance_checks"]) * 4

    # 4. Operations (10 points: 2 per checked criteria)
    operations_score = sum(data["operations_checks"]) * 2

    return {
        "Environmental Impact": environmental_score,
        "Social Responsibility": social_score,
        "Governance": governance_score,
        "Operations": operations_score
    }

def get_mock_recommendations():
    """Mock recommendations aligned with rulebook gaps"""
    data = st.session_state["campaign_data"]
    total_carbon = calculate_total_carbon()
    _, _, total_plastic = calculate_material_metrics()
    total_plastic = sum(m["quantity"] for m in data["Materials"] if m["material_type"] == "Plastic")

    if total_carbon > 2000:
        return MOCK_RECOMMENDATIONS["high_carbon"]
    elif total_plastic > 500:
        return MOCK_RECOMMENDATIONS["high_plastic"]
    elif not data["Local Vendors"]:
        return MOCK_RECOMMENDATIONS["low_local"]
    else:
        return MOCK_RECOMMENDATIONS["balanced"]

# --- Sidebar: Inputs + PDF Upload ---
st.sidebar.header("📋 Campaign Setup")

# 1. PDF Upload (Mock Extraction)
st.sidebar.subheader("📄 Upload Marketing Plan (Mock)")
uploaded_pdf = st.sidebar.file_uploader("Extract raw text (no AI)", type="pdf")
if uploaded_pdf:
    with st.spinner("Extracting text..."):
        pdf_text = extract_text_from_pdf(uploaded_pdf)
        with st.sidebar.expander("View Extracted Text"):
            st.text_area("Raw PDF Content", pdf_text, height=150)
        st.sidebar.success("✅ Text extracted (mock)")

# 2. Basic Campaign Info
st.sidebar.subheader("🎯 Basic Info")
campaign_name = st.sidebar.text_input(
    "Campaign Name",
    st.session_state["campaign_data"]["Campaign Name"]
)
duration = st.sidebar.slider(
    "Duration (days)",
    1, 30,
    st.session_state["campaign_data"]["Duration (days)"]
)
local_vendors = st.sidebar.checkbox(
    "Use Local Vendors?",
    value=st.session_state["campaign_data"]["Local Vendors"]
)

# 3. Staff Groups (Multiple with Unique Travel/Accommodation)
st.sidebar.subheader("👥 Staff Groups (Unique Travel/Accommodation)")
st.sidebar.caption("Add groups for staff with different travel plans (e.g., local vs. remote)")

# Add/Remove Staff Groups
col_add_staff, col_remove_staff = st.sidebar.columns(2)
with col_add_staff:
    if st.button("➕ Add Staff Group"):
        update_staff_count("add")
with col_remove_staff:
    if st.button("➖ Remove Last Group"):
        update_staff_count("remove")

# Staff Group Inputs
staff_groups = []
for i in range(st.session_state["staff_group_count"]):
    st.sidebar.markdown(f"**Group {i+1}**")
    # Load existing data or defaults
    default_data = st.session_state["campaign_data"]["Staff Groups"][i] if i < len(st.session_state["campaign_data"]["Staff Groups"]) else {
        "Staff Count": 5, "Departure": "City A", "Destination": "City B",
        "Travel Distance (km)": 100, "Travel Mode": "Car", "Accommodation": "3-star"
    }

    staff_count = st.sidebar.number_input(
        f"Staff Count (Group {i+1})",
        min_value=1,
        value=default_data["Staff Count"],
        key=f"staff_{i}_count"
    )
    departure = st.sidebar.text_input(
        f"Departure (Group {i+1})",
        default_data["Departure"],
        key=f"staff_{i}_departure"
    )
    destination = st.sidebar.text_input(
        f"Destination (Group {i+1})",
        default_data["Destination"],
        key=f"staff_{i}_dest"
    )
    travel_distance = st.sidebar.number_input(
        f"Travel Distance (km) (Group {i+1})",
        min_value=0,
        value=default_data["Travel Distance (km)"],
        key=f"staff_{i}_dist"
    )
    travel_mode = st.sidebar.selectbox(
        f"Travel Mode (Group {i+1})",
        ["Air", "Train", "Car", "Bus", "Other"],
        index=["Air", "Train", "Car", "Bus", "Other"].index(default_data["Travel Mode"]),
        key=f"staff_{i}_mode"
    )
    accommodation = st.sidebar.selectbox(
        f"Accommodation (Group {i+1})",
        ["Budget", "3-star", "4-star", "5-star"],
        index=["Budget", "3-star", "4-star", "5-star"].index(default_data["Accommodation"]),
        key=f"staff_{i}_acc"
    )

    staff_groups.append({
        "Staff Count": staff_count,
        "Departure": departure,
        "Destination": destination,
        "Travel Distance (km)": travel_distance,
        "Travel Mode": travel_mode,
        "Accommodation": accommodation
    })

# 4. Materials (Dropdown + Custom Input)
st.sidebar.subheader("📦 Materials (Predefined + Custom)")
st.sidebar.caption("Select from dropdown; use 'Other' for custom materials")

# Add/Remove Materials
col_add_mat, col_remove_mat = st.sidebar.columns(2)
with col_add_mat:
    if st.button("➕ Add Material"):
        update_material_count("add")
with col_remove_mat:
    if st.button("➖ Remove Last Material"):
        update_material_count("remove")

# Material Inputs (Dropdown + Custom Text Box
