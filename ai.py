import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import pdfkit
import tempfile
import os
import fitz
import requests  # For API calls
from datetime import datetime

# --- Page Config ---
st.set_page_config(page_title="Sustainable Marketing Evaluator", layout="wide")

# --- ChatGPT-5 API Configuration (No hardcoded key) ---
AI_API_ENDPOINT = "https://api.openai.com/v1/chat/completions"  # Replace with your endpoint
# API key fetched from Streamlit secrets (never hardcoded)
try:
    AI_API_KEY = st.secrets["AI_API_KEY"]
except KeyError:
    st.warning("API key not found in secrets. Some AI features may be limited.")
    AI_API_KEY = None

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
            }
        ],
        "Materials": [
            {"type": "Brochures", "quantity": 2000, "material_type": "Paper", 
             "custom_name": "", "custom_weight": 0, "custom_recyclable": False}
        ],
        "Local Vendor %": 70,
        "extracted_pdf_text": "",
        "governance_checks": [False, False, False, False, False],
        "operations_checks": [False, False, False, False, False],
        "ai_recommendations": [],
        "ai_material_analysis": {}
    }
if "staff_group_count" not in st.session_state:
    st.session_state["staff_group_count"] = len(st.session_state["campaign_data"]["Staff Groups"])
if "material_count" not in st.session_state:
    st.session_state["material_count"] = len(st.session_state["campaign_data"]["Materials"])
if "rerun_trigger" not in st.session_state:
    st.session_state["rerun_trigger"] = False

# --- Constants (Rulebook Aligned) ---
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

# --- AI Helper Functions (Secure API Calls) ---
def ai_api_call(prompt, system_message="You are a sustainability analyst for marketing campaigns."):
    """Secure API call to ChatGPT-5 (uses secrets for key)."""
    if not AI_API_KEY:
        return {"choices": [{"message": {"content": "AI features require an API key (add to secrets)."}}]}
    
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AI_API_KEY}"  # Key from secrets, not hardcoded
        }
        payload = {
            "model": "gpt-5",  # Replace with your model name
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ]
        }
        response = requests.post(AI_API_ENDPOINT, headers=headers, json=payload, timeout=10)
        response.raise_for_status()  # Raise error for 4xx/5xx responses
        return response.json()
    except Exception as e:
        st.error(f"AI API Error: {str(e)}")
        return {"choices": [{"message": {"content": "Failed to connect to AI service."}}]}

# --- Core AI-Powered Features ---
def ai_estimate_distance(departure, destination):
    """AI-powered distance estimation between cities."""
    if not departure or not destination or departure == destination:
        return 0
    prompt = f"""Estimate the distance in kilometers between {departure} and {destination} for a marketing campaign. 
    Return ONLY the numeric distance (no extra text). Example: 870"""
    response = ai_api_call(prompt)
    try:
        return float(response["choices"][0]["message"]["content"].strip())
    except:
        st.warning("AI could not estimate distance. Using manual input.")
        return None

def ai_analyze_pdf(pdf_text):
    """AI extracts campaign details from PDF to auto-populate forms."""
    if not pdf_text:
        return {}
    prompt = f"""Analyze this marketing campaign PDF text and extract:
    - Campaign duration (days)
    - Number of staff
    - Materials used (name and quantity)
    - Local vendor percentage
    - Travel cities (departure/destination)
    
    Text: {pdf_text[:2000]}  # Truncated for token efficiency
    
    Return as a JSON with keys: duration, staff_count, materials, local_vendor_pct, travel_cities."""
    response = ai_api_call(prompt)
    try:
        import json
        return json.loads(response["choices"][0]["message"]["content"])
    except:
        st.warning("AI could not parse PDF. Use manual input.")
        return {}

def ai_generate_recommendations():
    """AI generates tailored sustainability recommendations (rulebook-aligned)."""
    data = st.session_state["campaign_data"]
    scores = calculate_scores()
    prompt = f"""Generate 3 sustainability recommendations for a marketing campaign using these details:
    - Total score: {sum(scores.values())}/100 (Environmental: {scores['Environmental Impact']}, Social: {scores['Social Responsibility']})
    - Carbon emissions: {calculate_total_carbon()} kg
    - Materials: {[m['type'] for m in data['Materials']]}
    - Local vendors: {data['Local Vendor %']}%
    - Staff travel: {[f"{g['Departure']}→{g['Destination']}" for g in data['Staff Groups']]}
    
    Follow these rules:
    1. Prioritize fixes for lowest-scoring pillars.
    2. Reference impact weights from the rulebook (e.g., plastic=8, cotton=2).
    3. Include specific metrics (e.g., "cuts CO2 by 30%").
    """
    response = ai_api_call(prompt)
    return [rec.strip() for rec in response["choices"][0]["message"]["content"].split("-") if rec.strip()]

def ai_estimate_material_impact(material_name):
    """AI estimates impact weight/recyclability for custom materials (rulebook-aligned)."""
    if not material_name:
        return (5, False)  # Default
    prompt = f"""Estimate the sustainability impact of "{material_name}" for a marketing campaign using this rulebook:
    - Impact weight scale: 1 (low, e.g., biodegradable) to 10 (high, e.g., non-recyclable plastic)
    - Recyclable: Yes/No
    
    Examples from rulebook:
    - Cotton tote bags: weight 2, recyclable=Yes
    - Plastic badges: weight 8, recyclable=No
    
    Return ONLY as "weight: X, recyclable: Y" (no extra text)."""
    response = ai_api_call(prompt)
    try:
        content = response["choices"][0]["message"]["content"]
        weight = int(content.split("weight: ")[1].split(",")[0])
        recyclable = "Yes" in content.split("recyclable: ")[1]
        return (weight, recyclable)
    except:
        st.warning(f"AI could not estimate {material_name}. Using default.")
        return (5, False)

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

    for m in st.session_state["campaign_data"]["Materials"]:
        qty = m["quantity"]
        if qty <= 0:
            continue
        total_quantity += qty
        if m["material_type"] == "Plastic":
            total_plastic += qty

        if m["type"] == "Other (Custom)":
            weight = m["custom_weight"] if m["custom_weight"] != 0 else 5
            recyclable = m["custom_recyclable"]
        else:
            matches = [p for p in PREDEFINED_MATERIALS if p["name"] == m["type"]]
            weight = matches[0]["weight"] if matches else 5
            recyclable = matches[0]["recyclable"] if matches else False

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
    local_score = min(15, round(data["Local Vendor %"] / 100 * 15))
    total_acc_score = 0
    total_staff = sum(group["Staff Count"] for group in data["Staff Groups"])
    for group in data["Staff Groups"]:
        acc_score = 15 if group["Accommodation"] in ["Budget", "3-star"] else 10 if group["Accommodation"] == "4-star" else 5
        total_acc_score += acc_score * group["Staff Count"]
    accommodation_score = total_acc_score // total_staff if total_staff > 0 else 0
    social_score = local_score + accommodation_score

    # 3. Governance (20) + 4. Operations (10)
    governance_score = sum(data["governance_checks"]) * 4
    operations_score = sum(data["operations_checks"]) * 2

    return {
        "Environmental Impact": environmental_score,
        "Social Responsibility": social_score,
        "Governance": governance_score,
        "Operations": operations_score
    }

# --- Sidebar ---
st.sidebar.header("📋 Campaign Setup")

# 1. AI-Enhanced PDF Upload
st.sidebar.subheader("📄 Marketing Plan (AI Analysis)")
uploaded_pdf = st.sidebar.file_uploader("Upload PDF for AI extraction", type="pdf")
if uploaded_pdf:
    with st.spinner("AI is analyzing PDF..."):
        pdf_text = extract_text_from_pdf(uploaded_pdf)
        st.session_state["campaign_data"]["extracted_pdf_text"] = pdf_text
        with st.sidebar.expander("View Extracted Text"):
            st.text_area("", pdf_text, height=150)
        
        # Auto-populate form with AI analysis
        pdf_analysis = ai_analyze_pdf(pdf_text)
        if pdf_analysis:
            st.sidebar.success("AI populated form fields from PDF!")
            if "duration" in pdf_analysis:
                st.session_state["campaign_data"]["Duration (days)"] = pdf_analysis["duration"]
            if "local_vendor_pct" in pdf_analysis:
                st.session_state["campaign_data"]["Local Vendor %"] = pdf_analysis["local_vendor_pct"]

# 2. Basic Info
st.sidebar.subheader("🎯 Campaign Details")
campaign_name = st.sidebar.text_input(
    "Campaign Name",
    st.session_state["campaign_data"]["Campaign Name"],
    placeholder="Enter full campaign name",
    label_visibility="collapsed"
)
st.sidebar.text("Campaign Name")
duration = st.sidebar.slider(
    "Duration (days)",
    1, 30,
    st.session_state["campaign_data"]["Duration (days)"]
)

# 3. Local Vendors
st.sidebar.subheader("🏘️ Local Vendor Usage")
local_vendor_pct = st.sidebar.slider(
    "% of vendors that are local (0-100)",
    0, 100,
    st.session_state["campaign_data"]["Local Vendor %"]
)

# 4. Staff Groups + AI Distance Estimation
st.sidebar.subheader("👥 Staff Travel Groups")
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
        f"Staff Count", min_value=1, value=default_data["Staff Count"], key=f"staff_{i}_count"
    )
    departure = st.sidebar.text_input(
        f"Departure City", default_data["Departure"], key=f"staff_{i}_departure"
    )
    destination = st.sidebar.text_input(
        f"Destination City", default_data["Destination"], key=f"staff_{i}_dest"
    )

    # AI Distance Estimation
    col_dist, col_btn = st.sidebar.columns([3, 2])
    with col_dist:
        travel_distance = st.sidebar.number_input(
            f"Distance (km)", min_value=0, value=default_data["Travel Distance (km)"], key=f"staff_{i}_dist"
        )
    with col_btn:
        if st.sidebar.button("🤖 AI Estimate", key=f"dist_btn_{i}"):
            with st.spinner("AI calculating distance..."):
                estimated = ai_estimate_distance(departure, destination)
                if estimated:
                    travel_distance = estimated
                    st.sidebar.success(f"AI Estimate: {estimated} km")

    travel_mode = st.sidebar.selectbox(
        f"Travel Mode", ["Air", "Train", "Car", "Bus", "Other"],
        index=["Air", "Train", "Car", "Bus", "Other"].index(default_data["Travel Mode"]),
        key=f"staff_{i}_mode"
    )
    accommodation = st.sidebar.selectbox(
        f"Accommodation", ["Budget", "3-star", "4-star", "5-star"],
        index=["Budget", "3-star", "4-star", "5-star"].index(default_data["Accommodation"]),
        key=f"staff_{i}_acc"
    )

    staff_groups.append({
        "Staff Count": staff_count, "Departure": departure, "Destination": destination,
        "Travel Distance (km)": travel_distance, "Travel Mode": travel_mode, "Accommodation": accommodation
    })

# 5. Materials + AI Custom Material Analysis
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

    mat_type_options = [m["name"] for m in PREDEFINED_MATERIALS]
    try:
        default_index = mat_type_options.index(default_mat["type"])
    except ValueError:
        default_index = 0

    mat_type = st.sidebar.selectbox(
        f"Material {i+1}", mat_type_options, index=default_index, key=f"mat_{i}_type"
    )

    quantity = st.sidebar.number_input(
        f"Quantity", min_value=0, value=default_mat["quantity"], key=f"mat_{i}_qty"
    )

    custom_name = ""
    custom_weight = 0
    custom_recyclable = False
    material_type = "Custom"

    if mat_type == "Other (Custom)":
        custom_name = st.sidebar.text_input(
            "Custom Material Name", default_mat["custom_name"], key=f"mat_{i}_custom_name"
        )
        # AI Impact Estimation for Custom Materials
        if st.sidebar.button("🤖 AI Estimate Impact", key=f"mat_ai_{i}") and custom_name:
            with st.spinner("AI analyzing material..."):
                weight, recyclable = ai_estimate_material_impact(custom_name)
                custom_weight = weight
                custom_recyclable = recyclable
                st.sidebar.success(f"AI: Weight={weight}, Recyclable={recyclable}")
        else:
            custom_weight = default_mat["custom_weight"]
            custom_recyclable = default_mat["custom_recyclable"]
    else:
        for m in PREDEFINED_MATERIALS:
            if m["name"] == mat_type:
                material_type = m["type"]
                break

    materials.append({
        "type": mat_type, "quantity": quantity, "material_type": material_type,
        "custom_name": custom_name, "custom_weight": custom_weight, "custom_recyclable": custom_recyclable
    })

# 6. Governance & Operations (Polished)
st.sidebar.subheader("📋 Governance Standards")
gov_checks = []
for i, criteria in enumerate(GOVERNANCE_CRITERIA):
    with st.sidebar.expander(criteria, expanded=st.session_state["campaign_data"]["governance_checks"][i]):
        checked = st.checkbox("Fulfills criterion", 
                             value=st.session_state["campaign_data"]["governance_checks"][i],
                             key=f"gov_{i}")
        gov_checks.append(checked)

st.sidebar.subheader("⚙️ Operational Efficiency")
ops_checks = []
for i, criteria in enumerate(OPERATIONS_CRITERIA):
    with st.sidebar.expander(criteria, expanded=st.session_state["campaign_data"]["operations_checks"][i]):
        checked = st.checkbox("Fulfills criterion", 
                             value=st.session_state["campaign_data"]["operations_checks"][i],
                             key=f"ops_{i}")
        ops_checks.append(checked)

# Save Button
if st.sidebar.button("💾 Save All Details", use_container_width=True):
    st.session_state["campaign_data"].update({
        "Campaign Name": campaign_name, "Duration (days)": duration,
        "Staff Groups": staff_groups, "Materials": materials,
        "Local Vendor %": local_vendor_pct,
        "governance_checks": gov_checks, "operations_checks": ops_checks
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
with col1: st.metric("Campaign Name", data["Campaign Name"])
with col2: st.metric("Duration", f"{data['Duration (days)']} days")
with col3: st.metric("Total Staff", sum(g["Staff Count"] for g in data["Staff Groups"]))

# 2. Staff & Travel
st.subheader("👥 Staff Travel Details")
st.dataframe(pd.DataFrame(data["Staff Groups"]), use_container_width=True)

# 3. Carbon Footprint
st.subheader("🚨 Carbon Footprint")
st.metric("Total CO₂ Emissions", f"{total_carbon:.0f} kg")
fig, ax = plt.subplots(figsize=(8, 4))
ax.bar(["Your Campaign", "Industry Benchmark"], [total_carbon, 2000], color=["#FF6B6B", "#4ECDC4"])
ax.set_ylabel("CO₂ (kg)")
st.pyplot(fig)

# 4. Materials Analysis
st.subheader("📦 Materials Analysis")
if any(m["quantity"] > 0 for m in data["Materials"]):
    mat_data = []
    for m in data["Materials"]:
        if m["quantity"] <= 0: continue
        name = m["custom_name"] if m["type"] == "Other (Custom)" else m["type"]
        if m["type"] == "Other (Custom)":
            recyclable = m["custom_recyclable"]
        else:
            matches = [p for p in PREDEFINED_MATERIALS if p["name"] == m["type"]]
            recyclable = matches[0]["recyclable"] if matches else False
        mat_data.append({
            "Material": name, "Quantity": m["quantity"], 
            "Type": m["material_type"], "Recyclable": "✅" if recyclable else "❌"
        })
    st.dataframe(pd.DataFrame(mat_data), use_container_width=True)
    st.metric("Recyclability Rate", f"{recyclable_rate:.1f}%")

# 5. Scorecard
st.subheader("📊 Sustainability Scorecard")
st.metric("Overall Score", f"{total_score}/100")
fig, ax = plt.subplots(figsize=(10, 5))
ax.bar(scores.keys(), scores.values(), color=["#4CAF50", "#2196F3", "#FF9800", "#9C27B0"])
ax.set_ylim(0, 40)
st.pyplot(fig)

# 6. AI Recommendations
st.subheader("💡 AI-Powered Recommendations")
if st.button("Generate AI Insights", use_container_width=True):
    with st.spinner("AI is generating tailored recommendations..."):
        st.session_state["campaign_data"]["ai_recommendations"] = ai_generate_recommendations()

if st.session_state["campaign_data"]["ai_recommendations"]:
    for i, rec in enumerate(st.session_state["campaign_data"]["ai_recommendations"], 1):
        st.write(f"{i}. {rec}")

# 7. AI-Enhanced PDF Export
st.subheader("📄 Export AI-Generated Report")
if st.button("Generate PDF Report", use_container_width=True):
    try:
        # AI-enhanced report content
        report_prompt = f"""Generate a professional sustainability report for:
        - Campaign: {data['Campaign Name']}
        - Score: {total_score}/100
        - Key metrics: {total_carbon} kg CO₂, {recyclable_rate}% recyclability
        - Recommendations: {st.session_state['campaign_data']['ai_recommendations']}
        
        Format: Title, Executive Summary, Metrics Table, Recommendations, Next Steps."""
        report_content = ai_api_call(report_prompt)["choices"][0]["message"]["content"]

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdfkit.from_string(report_content, tmp.name)
            with open(tmp.name, "rb") as f:
                st.download_button(
                    "Download PDF", f, 
                    f"{data['Campaign Name'].replace(' ', '_')}_report.pdf",
                    use_container_width=True
                )
        os.unlink(tmp.name)
    except Exception as e:
        st.error(f"PDF generation failed: {e}. Install 'wkhtmltopdf'.")
