import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import pdfkit
import tempfile
import os
import fitz

# --- Mock Recommendations (Aligned with Latest Rulebook) ---
MOCK_RECOMMENDATIONS = {
    "high_carbon": [
        "Shift 50% of long-haul air travel to trains (cuts CO₂ by ~70% per staff).",
        "Cap 5-star accommodation at 20% of staff; use 3-star for the rest (reduces social penalty).",
        "Consolidate local staff into shared transport to eliminate redundant car trips."
    ],
    "high_plastic": [
        "Replace plastic merch with cotton alternatives (lowers material impact from 8→2).",
        "Use digital QR codes for brochures (cuts paper waste by 100%, boosts recyclability).",
        "Donate leftover materials to local nonprofits (counts toward Operations points)."
    ],
    "low_local": [
        "Source 3+ materials from local vendors (moves Social score from 5→15 points).",
        "Partner with a local printer for brochures (reduces transport emissions).",
        "Add sustainability clauses to vendor contracts (gains Governance points)."
    ],
    "balanced": [
        "Maintain 80%+ recyclability by expanding cotton/paper material use.",
        "Document goals in a post-campaign report (gains Governance points).",
        "Offset remaining CO₂ via verified projects (aligns with SDG 13)."
    ]
}

# --- Session State Initialization ---
if "campaign_data" not in st.session_state:
    st.session_state["campaign_data"] = {
        "Campaign Name": "Green Horizons Launch",
        "Duration (days)": 2,
        "Staff Groups": [  # Multiple staff groups with unique travel/accommodation
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
            {"type": "Brochures", "quantity": 2000, "material_type": "Paper", "custom_name": "", "custom_weight": 0, "custom_recyclable": False},
            {"type": "Plastic Badges", "quantity": 300, "material_type": "Plastic", "custom_name": "", "custom_weight": 0, "custom_recyclable": False}
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

# 2. Predefined Materials (Dropdown Options) + Properties
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
    {"name": "Other (Custom)"}  # Triggers manual input
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
    """Total CO2 from all staff groups (Rulebook 1.1)"""
    total = 0
    for group in st.session_state["campaign_data"]["Staff Groups"]:
        if group["Travel Distance (km)"] <= 0:
            continue
        emission_factor = EMISSION_FACTORS[group["Travel Mode"]]
        group_carbon = group["Travel Distance (km)"] * emission_factor * group["Staff Count"]
        total += group_carbon
    return total

def calculate_material_metrics():
    """Total Material Impact + Recyclability Rate (Rulebook 1.2)"""
    total_impact = 0
    total_recyclable = 0
    total_quantity = 0
    total_plastic = 0

    for mat in st.session_state["campaign_data"]["Materials"]:
        qty = mat["quantity"]
        if qty <= 0:
            continue
        total_quantity += qty
        if mat["material_type"] == "Plastic":
            total_plastic += qty

        # Get material properties (predefined or custom)
        if mat["type"] == "Other (Custom)":
            weight = mat["custom_weight"]
            recyclable = mat["custom_recyclable"]
        else:
            for pre_mat in PREDEFINED_MATERIALS:
                if pre_mat["name"] == mat["type"]:
                    weight = pre_mat["weight"]
                    recyclable = pre_mat["recyclable"]
                    break

        total_impact += (qty // 100) * weight
        if recyclable:
            total_recyclable += qty

    recyclable_rate = (total_recyclable / total_quantity * 100) if total_quantity > 0 else 100
    return total_impact, recyclable_rate, total_plastic

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
    recyclable_bonus = 5 if recyclable_rate >= 70 else 2 if 30 <= recyclable_rate < 70 else 0
    material_score = max(0, 20 - material_penalty + recyclable_bonus)
    environmental_score = travel_score + material_score

    # 2. Social Responsibility (30 points)
    # 2.1 Local Vendors (15 points)
    local_score = 15 if data["Local Vendors"] else 0
    # 2.2 Accommodation (15 points: weighted average)
    total_acc_score = 0
    total_staff = sum(group["Staff Count"] for group in data["Staff Groups"])
    for group in data["Staff Groups"]:
        acc = group["Accommodation"]
        acc_score = 15 if acc in ["Budget", "3-star"] else 10 if acc == "4-star" else 5
        total_acc_score += acc_score * group["Staff Count"]
    accommodation_score = total_acc_score // total_staff if total_staff > 0 else 0
    social_score = local_score + accommodation_score

    # 3. Governance (20 points: 4 per checked criterion)
    governance_score = sum(data["governance_checks"]) * 4

    # 4. Operations (10 points: 2 per checked criterion)
    operations_score = sum(data["operations_checks"]) * 2

    return {
        "Environmental Impact": environmental_score,
        "Social Responsibility": social_score,
        "Governance": governance_score,
        "Operations": operations_score
    }

def get_mock_recommendations():
    """Mock recommendations based on campaign gaps"""
    data = st.session_state["campaign_data"]
    total_carbon = calculate_total_carbon()
    _, _, total_plastic = calculate_material_metrics()

    if total_carbon > 2000:
        return MOCK_RECOMMENDATIONS["high_carbon"]
    elif total_plastic > 500:
        return MOCK_RECOMMENDATIONS["high_plastic"]
    elif not data["Local Vendors"]:
        return MOCK_RECOMMENDATIONS["low_local"]
    else:
        return MOCK_RECOMMENDATIONS["balanced"]

# --- Sidebar: Inputs ---
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
st.sidebar.subheader("👥 Staff Groups")
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
st.sidebar.subheader("📦 Materials")
st.sidebar.caption("Select from dropdown; use 'Other' for custom materials")

# Add/Remove Materials
col_add_mat, col_remove_mat = st.sidebar.columns(2)
with col_add_mat:
    if st.button("➕ Add Material"):
        update_material_count("add")
with col_remove_mat:
    if st.button("➖ Remove Last Material"):
        update_material_count("remove")

# Material Inputs (Dropdown + Custom Text Box)
materials = []
for i in range(st.session_state["material_count"]):
    # Load existing data or defaults
    default_mat = st.session_state["campaign_data"]["Materials"][i] if i < len(st.session_state["campaign_data"]["Materials"]) else {
        "type": "Brochures", "quantity": 1000, "material_type": "Paper",
        "custom_name": "", "custom_weight": 3, "custom_recyclable": True
    }

    # Material type dropdown
    mat_type = st.sidebar.selectbox(
        f"Material {i+1} Type",
        [m["name"] for m in PREDEFINED_MATERIALS],
        index=[m["name"] for m in PREDEFINED_MATERIALS].index(default_mat["type"]),
        key=f"mat_{i}_type"
    )

    # Quantity
    quantity = st.sidebar.number_input(
        f"Quantity (Material {i+1})",
        min_value=0,
        value=default_mat["quantity"],
        key=f"mat_{i}_qty"
    )

    # Custom material fields (only if "Other (Custom)" is selected)
    custom_name = ""
    custom_weight = 0
    custom_recyclable = False
    material_type = "Custom"  # Default for "Other"

    if mat_type == "Other (Custom)":
        custom_name = st.sidebar.text_input(
            "Custom Material Name",
            default_mat["custom_name"],
            key=f"mat_{i}_custom_name"
        )
        custom_weight = st.sidebar.slider(
            "Custom Impact Weight (1-10)",
            1, 10,
            default_mat["custom_weight"],
            key=f"mat_{i}_custom_weight"
        )
        custom_recyclable = st.sidebar.checkbox(
            "Is this recyclable?",
            default_mat["custom_recyclable"],
            key=f"mat_{i}_custom_recyclable"
        )
    else:
        # Get type from predefined materials
        for m in PREDEFINED_MATERIALS:
            if m["name"] == mat_type:
                material_type = m["type"]
                break

    materials.append({
        "type": mat_type,
        "quantity": quantity,
        "material_type": material_type,
        "custom_name": custom_name,
        "custom_weight": custom_weight,
        "custom_recyclable": custom_recyclable
    })

# 5. Governance & Operations Criteria
st.sidebar.subheader("📋 Governance Criteria")
gov_checks = []
for i, criteria in enumerate(GOVERNANCE_CRITERIA):
    checked = st.sidebar.checkbox(
        criteria,
        value=st.session_state["campaign_data"]["governance_checks"][i],
        key=f"gov_{i}"
    )
    gov_checks.append(checked)

st.sidebar.subheader("⚙️ Operations Criteria")
ops_checks = []
for i, criteria in enumerate(OPERATIONS_CRITERIA):
    checked = st.sidebar.checkbox(
        criteria,
        value=st.session_state["campaign_data"]["operations_checks"][i],
        key=f"ops_{i}"
    )
    ops_checks.append(checked)

# Save All Data
if st.sidebar.button("💾 Save All Details"):
    st.session_state["campaign_data"].update({
        "Campaign Name": campaign_name,
        "Duration (days)": duration,
        "Staff Groups": staff_groups,
        "Materials": materials,
        "Local Vendors": local_vendors,
        "governance_checks": gov_checks,
        "operations_checks": ops_checks
    })
    st.sidebar.success("✅ All details saved!")

# --- Handle Reruns ---
if st.session_state["rerun_trigger"]:
    st.session_state["rerun_trigger"] = False
    st.rerun()

# --- Load Data & Calculate Metrics ---
data = st.session_state["campaign_data"]
total_carbon = calculate_total_carbon()
total_material_impact, recyclable_rate, total_plastic = calculate_material_metrics()
scores = calculate_scores()
total_score = sum(scores.values())

# --- Main Dashboard ---
st.title("🌿 Sustainable Marketing Evaluator")
st.info("No AI/APIs used. All scoring aligns with the latest rulebook.")

# 1. Campaign Summary
st.subheader("📝 Campaign Summary")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Name", data["Campaign Name"])
with col2:
    st.metric("Duration", f"{data['Duration (days)']} days")
with col3:
    st.metric("Total Staff", sum(g["Staff Count"] for g in data["Staff Groups"]))

# 2. Staff Groups & Travel
st.subheader("👥 Staff Groups & Travel")
staff_df = pd.DataFrame(data["Staff Groups"])
st.dataframe(staff_df, use_container_width=True)

# 3. Carbon Footprint
st.subheader("🚨 Carbon Footprint")
st.metric("Total CO₂ Emissions", f"{total_carbon:.0f} kg")
fig, ax = plt.subplots(figsize=(8, 4))
ax.bar(
    ["Your Campaign", "Industry Benchmark (2000kg)"],
    [total_carbon, 2000],
    color=["#FF6B6B", "#4ECDC4"]
)
ax.set_ylabel("CO₂ (kg)")
st.pyplot(fig)

# 4. Materials Breakdown
st.subheader("📦 Materials Analysis")
if any(m["quantity"] > 0 for m in data["Materials"]):
    mat_data = []
    for m in data["Materials"]:
        if m["quantity"] <= 0:
            continue
        name = m["custom_name"] if m["type"] == "Other (Custom)" else m["type"]
        mat_data.append({
            "Material": name,
            "Quantity": m["quantity"],
            "Type": m["material_type"],
            "Recyclable": "✅" if (m["custom_recyclable"] if m["type"] == "Other (Custom)" else 
                                 [p for p in PREDEFINED_MATERIALS if p["name"] == m["type"]][0]["recyclable"]) else "❌"
        })
    st.dataframe(pd.DataFrame(mat_data), use_container_width=True)
    st.metric("Recyclability Rate", f"{recyclable_rate:.1f}%")
else:
    st.write("Add materials in the sidebar to see analysis.")

# 5. Sustainability Scorecard
st.subheader("📊 Sustainability Scorecard")
st.metric("Overall Score", f"{total_score}/100")
fig, ax = plt.subplots(figsize=(10, 5))
ax.bar(
    scores.keys(),
    scores.values(),
    color=["#4CAF50", "#2196F3", "#FF9800", "#9C27B0"]
)
ax.set_ylim(0, 40)
ax.set_ylabel("Score (0-40)")
st.pyplot(fig)

# 6. Mock Recommendations
st.subheader("💡 Mock Sustainability Recommendations")
if st.button("Generate Recommendations"):
    with st.spinner("Analyzing (mock)..."):
        st.session_state["mock_recommendations"] = get_mock_recommendations()

if st.session_state["mock_recommendations"]:
    for i, rec in enumerate(st.session_state["mock_recommendations"], 1):
        st.write(f"{i}. {rec}")

# 7. PDF Export
st.subheader("📄 Export Report")
if st.button("Generate PDF Report"):
    try:
        html = f"""
        <html>
        <head><style>
            body {{ font-family: Arial; margin: 20px; }}
            .section {{ margin: 20px 0; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; }}
        </style></head>
        <body>
            <h1>{data['Campaign Name']} - Sustainability Report</h1>
            
            <div class="section">
                <h2>Summary</h2>
                <p>Duration: {data['Duration (days)']} days | Total Staff: {sum(g['Staff Count'] for g in data['Staff Groups'])}</p>
                <p>Overall Score: {total_score}/100</p>
            </div>
            
            <div class="section">
                <h2>Carbon Emissions</h2>
                <p>Total CO₂: {total_carbon:.0f} kg</p>
            </div>
            
            <div class="section">
                <h2>Recommendations</h2>
                <ul>
                    {''.join(f'<li>{r}</li>' for r in st.session_state["mock_recommendations"])}
                </ul>
            </div>
        </body></html>
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdfkit.from_string(html, tmp.name)
            with open(tmp.name, "rb") as f:
                st.download_button(
                    "Download PDF",
                    f,
                    f"{data['Campaign Name']}_sustainability_report.pdf"
                )
        os.unlink(tmp.name)
    except Exception as e:
        st.error(f"PDF generation failed: {e}. Ensure 'wkhtmltopdf' is installed.")
