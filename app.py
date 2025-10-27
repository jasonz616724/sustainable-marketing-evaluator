import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import pdfkit
import tempfile
import os
import fitz
import requests  # For free distance API

# --- Page Config ---
st.set_page_config(page_title="Sustainable Marketing Evaluator", layout="wide")

# --- Mock Recommendations ---
MOCK_RECOMMENDATIONS = {
    "high_carbon": [
        "Shift 50% of long-haul air travel to trains (cuts CO₂ by ~70% per staff).",
        "Cap 5-star accommodation at 20% of staff; use 3-star for the rest.",
        "Consolidate local staff into shared transport to eliminate redundant trips."
    ],
    "high_plastic": [
        "Replace plastic merch with cotton alternatives (lowers impact from 8→2).",
        "Use digital QR codes for brochures (cuts paper waste by 100%).",
        "Donate leftovers to local nonprofits (counts toward Operations points)."
    ],
    "low_local": [
        "Increase local vendor use to 50%+ (raises Social score by 5+ points).",
        "Partner with local printers for materials (reduces transport emissions).",
        "Add sustainability clauses to vendor contracts (gains Governance points)."
    ],
    "balanced": [
        "Maintain 80%+ recyclability by expanding cotton/paper material use.",
        "Document goals in a post-campaign report (gains Governance points).",
        "Offset remaining CO₂ via verified projects (aligns with SDG 13)."
    ]
}

# --- Session State ---
if "campaign_data" not in st.session_state:
    st.session_state["campaign_data"] = {
        "Campaign Name": "Green Horizons Launch 2024: Sustainable Futures Summit",
        "Duration (days)": 2,
        "Staff Groups": [
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
        "Local Vendor %": 70,  # New: % of vendors that are local
        "extracted_pdf_text": "",
        "governance_checks": [False, False, False, False, False],
        "operations_checks": [False, False, False, False, False]
    }
if "staff_group_count" not in st.session_state:
    st.session_state["staff_group_count"] = len(st.session_state["campaign_data"]["Staff Groups"])
if "material_count" not in st.session_state:
    st.session_state["material_count"] = len(st.session_state["campaign_data"]["Materials"])
if "rerun_trigger" not in st.session_state:
    st.session_state["rerun_trigger"] = False
if "mock_recommendations" not in st.session_state:
    st.session_state["mock_recommendations"] = []

# --- Constants ---
EMISSION_FACTORS = {
    "Air": 0.25, "Train": 0.06, "Car": 0.17, "Bus": 0.08, "Other": 0.12
}

PREDEFINED_MATERIALS = [
    {"name": "Brochures", "type": "Paper", "weight": 3, "recyclable": True},
    {"name": "Flyers", "type": "Paper", "weight": 3, "recyclable": True},
    {"name": "Plastic Tote Bags", "type": "Plastic", "weight": 8, "recyclable": False},
    {"name": "Cotton Tote Bags", "type": "Cotton", "weight": 2, "recyclable": True},
    {"name": "Metal Badges", "type": "Metal", "weight": 5, "recyclable": True},
    {"name": "Other (Custom)"}
]

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
            return "\n\n".join([page.get_text().strip() for page in doc])
    except Exception as e:
        st.error(f"PDF Extraction Error: {str(e)}")
        return ""

# --- Free Distance API (OpenRouteService) ---
def get_distance(departure, destination):
    """Estimate distance between cities using free API (no key required)"""
    if not departure or not destination or departure == destination:
        return 0
    try:
        url = "https://api.openrouteservice.org/v2/directions/driving-car"
        params = {
            "api_key": "5b3ce3597851110001cf6248ee7b215f8b340f6b952953d0204a762d9b7f5",  # Demo key (rate-limited)
            "start": f"{get_coords(departure)}",
            "end": f"{get_coords(destination)}"
        }
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            return round(response.json()["features"][0]["properties"]["summary"]["distance"] / 1000, 1)  # m → km
        return None
    except:
        return None  # Fallback to manual input

def get_coords(city):
    """Fallback coordinates for major cities (expandable)"""
    coords = {
        "Sydney": "151.2093,-33.8688", "Melbourne": "144.9631,-37.8136",
        "London": "-0.1276,51.5072", "New York": "-74.0060,40.7128",
        "Paris": "2.3522,48.8566", "Tokyo": "139.6917,35.6895"
    }
    return coords.get(city, "0,0")  # Default if unknown

# --- Calculation Functions ---
def calculate_total_carbon():
    total = 0
    for group in st.session_state["campaign_data"]["Staff Groups"]:
        if group["Travel Distance (km)"] <= 0:
            continue
        emission_factor = EMISSION_FACTORS[group["Travel Mode"]]
        total += group["Travel Distance (km)"] * emission_factor * group["Staff Count"]
    return total

def calculate_material_metrics():
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
    data = st.session_state["campaign_data"]
    total_carbon = calculate_total_carbon()
    total_material_impact, recyclable_rate, _ = calculate_material_metrics()

    # 1. Environmental (40 points)
    travel_score = 20 if total_carbon <= 500 else 17 if 501 <= total_carbon <= 1000 else 14 if 1001 <= total_carbon <= 1500 else 11 if 1501 <= total_carbon <= 2000 else 8
    material_penalty = min(10, total_material_impact // 5)
    recyclable_bonus = 5 if recyclable_rate >= 70 else 2 if 30 <= recyclable_rate < 70 else 0
    material_score = max(0, 20 - material_penalty + recyclable_bonus)
    environmental_score = travel_score + material_score

    # 2. Social (30 points)
    # Local vendors: 0-15 points based on % (new mixed scoring)
    local_score = min(15, round(data["Local Vendor %"] / 100 * 15))
    # Accommodation: weighted average
    total_acc_score = 0
    total_staff = sum(group["Staff Count"] for group in data["Staff Groups"])
    for group in data["Staff Groups"]:
        acc_score = 15 if group["Accommodation"] in ["Budget", "3-star"] else 10 if group["Accommodation"] == "4-star" else 5
        total_acc_score += acc_score * group["Staff Count"]
    accommodation_score = total_acc_score // total_staff if total_staff > 0 else 0
    social_score = local_score + accommodation_score

    # 3. Governance (20 points) + 4. Operations (10 points)
    governance_score = sum(data["governance_checks"]) * 4
    operations_score = sum(data["operations_checks"]) * 2

    return {
        "Environmental Impact": environmental_score,
        "Social Responsibility": social_score,
        "Governance": governance_score,
        "Operations": operations_score
    }

def get_mock_recommendations():
    data = st.session_state["campaign_data"]
    total_carbon = calculate_total_carbon()
    _, _, total_plastic = calculate_material_metrics()

    if total_carbon > 2000:
        return MOCK_RECOMMENDATIONS["high_carbon"]
    elif total_plastic > 500:
        return MOCK_RECOMMENDATIONS["high_plastic"]
    elif data["Local Vendor %"] < 50:
        return MOCK_RECOMMENDATIONS["low_local"]
    else:
        return MOCK_RECOMMENDATIONS["balanced"]

# --- Sidebar ---
st.sidebar.header("📋 Campaign Setup")

# 1. PDF Upload
st.sidebar.subheader("📄 Marketing Plan")
uploaded_pdf = st.sidebar.file_uploader("Upload PDF to extract details", type="pdf")
if uploaded_pdf:
    with st.spinner("Extracting content..."):
        pdf_text = extract_text_from_pdf(uploaded_pdf)
        with st.sidebar.expander("View Extracted Text"):
            st.text_area("", pdf_text, height=150)

# 2. Basic Info
st.sidebar.subheader("🎯 Campaign Details")
campaign_name = st.sidebar.text_input(
    "Campaign Name",
    st.session_state["campaign_data"]["Campaign Name"],
    placeholder="Enter full campaign name",
    label_visibility="collapsed"  # More space for input
)
st.sidebar.text("Campaign Name")  # Label below input for clarity

duration = st.sidebar.slider(
    "Duration (days)",
    1, 30,
    st.session_state["campaign_data"]["Duration (days)"]
)

# 3. Local Vendors (Mixed %)
st.sidebar.subheader("🏘️ Local Vendor Usage")
local_vendor_pct = st.sidebar.slider(
    "% of vendors that are local (0-100)",
    0, 100,
    st.session_state["campaign_data"]["Local Vendor %"]
)
st.sidebar.caption("e.g., 70% = 7 out of 10 vendors are local")

# 4. Staff Groups + Auto-Distance
st.sidebar.subheader("👥 Staff Travel Groups")
st.sidebar.caption("Add groups with unique travel plans")

col_add_staff, col_remove_staff = st.sidebar.columns(2)
with col_add_staff:
    if st.button("➕ Add Staff Group"):
        update_staff_count("add")
with col_remove_staff:
    if st.button("➖ Remove Last Group"):
        update_staff_count("remove")

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
        f"Departure City",
        default_data["Departure"],
        key=f"staff_{i}_departure"
    )
    destination = st.sidebar.text_input(
        f"Destination City",
        default_data["Destination"],
        key=f"staff_{i}_dest"
    )

    # Auto-distance + manual override
    col_dist, col_btn = st.sidebar.columns([3, 2])
    with col_dist:
        travel_distance = st.sidebar.number_input(
            f"Distance (km)",
            min_value=0,
            value=default_data["Travel Distance (km)"],
            key=f"staff_{i}_dist"
        )
    with col_btn:
        if st.sidebar.button("📌 Auto-Estimate", key=f"dist_btn_{i}"):
            estimated = get_distance(departure, destination)
            if estimated:
                travel_distance = estimated
                st.sidebar.success(f"Estimated: {estimated} km")
            else:
                st.sidebar.info("Enter manually (city not found)")

    travel_mode = st.sidebar.selectbox(
        f"Travel Mode",
        ["Air", "Train", "Car", "Bus", "Other"],
        index=["Air", "Train", "Car", "Bus", "Other"].index(default_data["Travel Mode"]),
        key=f"staff_{i}_mode"
    )
    accommodation = st.sidebar.selectbox(
        f"Accommodation",
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

# 5. Materials (Dropdown + Custom)
st.sidebar.subheader("📦 Materials")
col_add_mat, col_remove_mat = st.sidebar.columns(2)
with col_add_mat:
    if st.button("➕ Add Material"):
        update_material_count("add")
with col_remove_mat:
    if st.button("➖ Remove Last Material"):
        update_material_count("remove")

materials = []
for i in range(st.session_state["material_count"]):
    default_mat = st.session_state["campaign_data"]["Materials"][i] if i < len(st.session_state["campaign_data"]["Materials"]) else {
        "type": "Brochures", "quantity": 1000, "material_type": "Paper",
        "custom_name": "", "custom_weight": 3, "custom_recyclable": True
    }

    mat_type = st.sidebar.selectbox(
        f"Material {i+1}",
        [m["name"] for m in PREDEFINED_MATERIALS],
        index=[m["name"] for m in PREDEFINED_MATERIALS].index(default_mat["type"]),
        key=f"mat_{i}_type"
    )

    quantity = st.sidebar.number_input(
        f"Quantity",
        min_value=0,
        value=default_mat["quantity"],
        key=f"mat_{i}_qty"
    )

    custom_name = ""
    custom_weight = 0
    custom_recyclable = False
    material_type = "Custom"

    if mat_type == "Other (Custom)":
        custom_name = st.sidebar.text_input(
            "Custom Name",
            default_mat["custom_name"],
            key=f"mat_{i}_custom_name"
        )
        custom_weight = st.sidebar.slider(
            "Impact Weight (1-10)",
            1, 10,
            default_mat["custom_weight"],
            key=f"mat_{i}_custom_weight"
        )
        custom_recyclable = st.sidebar.checkbox(
            "Recyclable?",
            default_mat["custom_recyclable"],
            key=f"mat_{i}_custom_recyclable"
        )
    else:
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

# 6. Polished Governance & Operations (Card-style checkboxes)
st.sidebar.subheader("📋 Governance Standards")
gov_checks = []
for i, criteria in enumerate(GOVERNANCE_CRITERIA):
    with st.sidebar.expander(criteria, expanded=st.session_state["campaign_data"]["governance_checks"][i]):
        checked = st.checkbox(
            "Fulfills this criterion",
            value=st.session_state["campaign_data"]["governance_checks"][i],
            key=f"gov_{i}"
        )
        gov_checks.append(checked)

st.sidebar.subheader("⚙️ Operational Efficiency")
ops_checks = []
for i, criteria in enumerate(OPERATIONS_CRITERIA):
    with st.sidebar.expander(criteria, expanded=st.session_state["campaign_data"]["operations_checks"][i]):
        checked = st.checkbox(
            "Fulfills this criterion",
            value=st.session_state["campaign_data"]["operations_checks"][i],
            key=f"ops_{i}"
        )
        ops_checks.append(checked)

# Save Button
if st.sidebar.button("💾 Save All Details", use_container_width=True):
    st.session_state["campaign_data"].update({
        "Campaign Name": campaign_name,
        "Duration (days)": duration,
        "Staff Groups": staff_groups,
        "Materials": materials,
        "Local Vendor %": local_vendor_pct,
        "governance_checks": gov_checks,
        "operations_checks": ops_checks
    })
    st.sidebar.success("✅ Details saved!")

# --- Rerun Handling ---
if st.session_state["rerun_trigger"]:
    st.session_state["rerun_trigger"] = False
    st.rerun()

# --- Dashboard ---
data = st.session_state["campaign_data"]
total_carbon = calculate_total_carbon()
total_material_impact, recyclable_rate, total_plastic = calculate_material_metrics()
scores = calculate_scores()
total_score = sum(scores.values())

st.title("🌿 Sustainable Marketing Evaluator")

# 1. Campaign Summary
st.subheader("📝 Campaign Overview")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Campaign Name", data["Campaign Name"])
with col2:
    st.metric("Duration", f"{data['Duration (days)']} days")
with col3:
    st.metric("Total Staff", sum(g["Staff Count"] for g in data["Staff Groups"]))

# 2. Staff & Travel
st.subheader("👥 Staff Travel Details")
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

# 4. Materials
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

# 5. Scorecard
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

# 6. Recommendations
st.subheader("💡 Sustainability Recommendations")
if st.button("Generate Insights", use_container_width=True):
    with st.spinner("Analyzing data..."):
        st.session_state["mock_recommendations"] = get_mock_recommendations()

if st.session_state["mock_recommendations"]:
    for i, rec in enumerate(st.session_state["mock_recommendations"], 1):
        st.write(f"{i}. {rec}")

# 7. PDF Export
st.subheader("📄 Export Report")
if st.button("Generate PDF Report", use_container_width=True):
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
            <div class="section"><h2>Summary</h2>
                <p>Duration: {data['Duration (days)']} days | Total Staff: {sum(g['Staff Count'] for g in data['Staff Groups'])}</p>
                <p>Overall Score: {total_score}/100 | Local Vendors: {data['Local Vendor %']}%</p>
            </div>
            <div class="section"><h2>Carbon Emissions</h2>
                <p>Total CO₂: {total_carbon:.0f} kg</p>
            </div>
            <div class="section"><h2>Recommendations</h2>
                <ul>{''.join(f'<li>{r}</li>' for r in st.session_state["mock_recommendations"])}</ul>
            </div>
        </body></html>
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdfkit.from_string(html, tmp.name)
            with open(tmp.name, "rb") as f:
                st.download_button(
                    "Download PDF",
                    f,
                    f"{data['Campaign Name'].replace(' ', '_')}_report.pdf",
                    use_container_width=True
                )
        os.unlink(tmp.name)
    except Exception as e:
        st.error(f"PDF generation failed: {e}. Install 'wkhtmltopdf' first.")
