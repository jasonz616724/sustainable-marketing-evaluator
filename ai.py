import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import pdfkit
import tempfile
import os
import fitz
import json
from openai import OpenAI

# --- Page Configuration ---
st.set_page_config(page_title="Sustainable Marketing Evaluator", layout="wide")
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# --- Initialize OpenAI Client ---
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    OPENAI_AVAILABLE = True
except KeyError:
    st.warning("⚠️ OPENAI_API_KEY not found in Streamlit Secrets. AI features disabled.")
    OPENAI_AVAILABLE = False
except Exception as e:
    st.error(f"⚠️ OpenAI client error: {str(e)}")
    OPENAI_AVAILABLE = False

# --- Session State Initialization ---
if "campaign_data" not in st.session_state:
    st.session_state["campaign_data"] = {
        "Campaign Name": "Green Horizons Launch 2024",
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
        "governance_checks": [False]*5,
        "operations_checks": [False]*5,
        "ai_recommendations": [],
    }
if "staff_group_count" not in st.session_state:
    st.session_state["staff_group_count"] = len(st.session_state["campaign_data"]["Staff Groups"])
if "material_count" not in st.session_state:
    st.session_state["material_count"] = len(st.session_state["campaign_data"]["Materials"])
if "rerun_trigger" not in st.session_state:
    st.session_state["rerun_trigger"] = False

# --- Constants ---

EMISSION_FACTORS = {
    # Flight seat classes (most accurate per IATA data)
    "Air - Economy": 0.25,
    "Air - Premium Economy": 0.35,
    "Air - Business": 0.60,
    "Air - First Class": 0.90,
    # Other travel modes (unchanged)
    "Train": 0.06,
    "Car": 0.17,
    "Bus": 0.08,
    "Other": 0.12
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

# --- Core AI Function ---
def get_ai_response(prompt, system_msg="You are a sustainability analyst. Be concise."):
    if not OPENAI_AVAILABLE:
        return "❌ AI requires OPENAI_API_KEY in secrets."
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
            temperature=0.6,
            timeout=15
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"⚠️ AI error: {str(e)}")
        return "❌ AI response failed. Try again."

# --- Helper Functions ---
def update_staff_count(change_type):
    if change_type == "add":
        st.session_state["staff_group_count"] += 1
    elif change_type == "remove" and st.session_state["staff_group_count"] > 1:
        st.session_state["staff_group_count"] -= 1
    st.session_state["rerun_trigger"] = True

def update_material_count(change_type):
    if change_type == "add":
        st.session_state["material_count"] += 1
    elif change_type == "remove" and st.session_state["material_count"] > 1:
        st.session_state["material_count"] -= 1
    st.session_state["rerun_trigger"] = True

def extract_pdf_text(uploaded_file):
    try:
        with fitz.open(stream=uploaded_file.read(), filetype="pdf") as pdf_doc:
            return "\n\n".join([page.get_text().strip() for page in pdf_doc])
    except Exception as e:
        st.error(f"⚠️ PDF extraction failed: {str(e)}")
        return ""

#--- AI-Enhanced Features ---
def ai_estimate_travel_distance(departure, destination):
    if not departure or not destination or departure.strip().lower() == destination.strip().lower():
        st.info("ℹ️ Departure and destination are the same or missing—distance set to 0.")
        return 0
    
    # Strict prompt to avoid commas/units
    prompt = f"""Estimate the travel distance in kilometers between {departure.strip()} and {destination.strip()}.
    Return ONLY a raw number (no commas, units like 'km', or extra text). Examples: 870, 1250, 16000.
    Do NOT add explanations, symbols, or formatting."""
    
    try:
        response = get_ai_response(
            prompt,
            system_msg="You are a geography expert. Return ONLY a numeric value (no text, commas, or units)."
        )
        response = response.strip()
    except Exception as e:
        st.error(f"⚠️ AI Request Failed: {str(e)}")
        return None
    
    # --- Key Fix: Clean the response to remove commas and non-numeric characters ---
    try:
        # Remove commas, letters, and symbols (keep only numbers and decimals)
        cleaned_response = response.replace(",", "").replace("km", "").strip()
        cleaned_response = ''.join([c for c in cleaned_response if c.isdigit() or c == '.'])
        
        if not cleaned_response:
            raise ValueError("No valid numbers found in response.")
        
        distance = float(cleaned_response)
        st.success(f"✅ AI Estimated Distance: {distance:.0f} km")
        return distance
    
    except ValueError:
        st.error(f"⚠️ Could not parse distance. AI response: '{response}'. Use manual input.")
        return None
    except Exception as e:
        st.error(f"⚠️ Error: {str(e)}. AI response: '{response}'")
        return None
def ai_extract_pdf_data(pdf_text):
    if not pdf_text:
        return {}
    
    prompt = f"Extract from PDF text: {pdf_text[:2000]}\nReturn JSON with: duration (days), staff_count, materials (name/quantity), local_vendor_pct, travel_cities (departure/destination). Use null if missing."
    response = get_ai_response(prompt, "Data extractor: Return only valid JSON.")
    try:
        return json.loads(response)
    except:
        st.warning(f"⚠️ AI PDF parse failed (response: {response[:100]}...). Enter manually.")
        return {}

def ai_generate_sustainability_tips():
    data = st.session_state["campaign_data"]
    scores = calculate_sustainability_scores()
    total_carbon = calculate_total_carbon_emission()
    _, recyclable_rate, _ = calculate_material_metrics()
    
    prompt = f"3 actionable tips for {data['Campaign Name']}:\nScore: {sum(scores.values())}/100, CO₂: {total_carbon}kg, Recyclable: {recyclable_rate}%, Local Vendors: {data['Local Vendor %']}%\nLow scores: {[k for k, v in scores.items() if v < 10]}\nStart with verbs (e.g., 'Switch...')."
    response = get_ai_response(prompt)
    return [tip.strip() for tip in response.split("-") if tip.strip() and not tip.strip().isdigit()]

def ai_analyze_custom_material(material_name):
    # 1. Validate input first (prevent empty requests)
    if not material_name or material_name.strip() == "":
        st.warning("⚠️ Please enter a custom material name first (e.g., 'Bamboo Utensils').")
        return (5, False)
    
    # 2. Refine prompt to force strict format
    prompt = f"""Analyze the marketing campaign material named "{material_name.strip()}". 
    Follow these rules EXACTLY:
    1. Impact weight: A number between 1 (low impact, e.g., bamboo) and 10 (high impact, e.g., non-recyclable plastic).
    2. Recyclable: Only "Yes" or "No" (no other words).
    Return ONLY in this format: "weight: X, recyclable: Y" (replace X with number, Y with Yes/No).
    Examples: 
    - For "Cotton Tote Bag": "weight: 2, recyclable: Yes"
    - For "Plastic Water Bottle": "weight: 8, recyclable: No"
    Do NOT add extra text, explanations, or formatting."""
    
    # 3. Get AI response
    try:
        response = get_ai_response(
            prompt, 
            system_msg="You are a materials science expert. Return ONLY the EXACT format requested—no extra content."
        )
        response = response.strip()  # Clean up extra spaces/newlines
    
    except Exception as e:
        st.error(f"⚠️ AI Request Failed: {str(e)}")
        return (5, False)
    
    # 4. Robust parsing (no debug log)
    try:
        # Extract weight
        if "weight: " not in response:
            raise ValueError("Missing 'weight: ' in response")
        weight_str = response.split("weight: ")[1].split(",")[0].strip()
        weight = int(weight_str)
        weight = max(1, min(10, weight))  # Clamp to 1-10
        
        # Extract recyclable
        if "recyclable: " not in response:
            raise ValueError("Missing 'recyclable: ' in response")
        recyclable_str = response.split("recyclable: ")[1].strip().lower()
        recyclable = recyclable_str == "yes"
        
        # Success feedback
        st.success(f"✅ AI Analyzed '{material_name}': Weight = {weight}, Recyclable = {recyclable}")
        return (weight, recyclable)
    
    # 5. Handle parsing failures
    except ValueError as ve:
        st.error(f"⚠️ AI Response Format Error: {ve}. Raw response: '{response}'")
        return (5, False)
    except Exception as e:
        st.error(f"⚠️ Unexpected Error: {str(e)}. Raw response: '{response}'")
        return (5, False)

        
# --- Calculation Functions ---
def calculate_total_carbon_emission():
    """Calculate total CO₂ emissions, with flight seat class differentiation."""
    total_emission = 0
    for group in st.session_state["campaign_data"]["Staff Groups"]:
        distance = group["Travel Distance (km)"]
        if distance <= 0:
            continue
        
        # Get emission factor (automatically uses seat class for flights)
        travel_mode = group["Travel Mode"]
        emission_factor = EMISSION_FACTORS.get(travel_mode, 0.12)  # Default to "Other"
        
        # Calculate emissions for the group
        group_emissions = distance * emission_factor * group["Staff Count"]
        total_emission += group_emissions
        
        # Optional: Show breakdown per group (for transparency)
        # st.write(f"Group Emissions ({travel_mode}): {group_emissions:.1f} kg")
    
    return round(total_emission, 1)
    
def calculate_material_metrics():
    total_impact, total_recyclable, total_qty, total_plastic = 0, 0, 0, 0
    for mat in st.session_state["campaign_data"]["Materials"]:
        qty = mat["quantity"]
        if qty <= 0:
            continue
        total_qty += qty
        if mat["material_type"] == "Plastic":
            total_plastic += qty
        
        if mat["type"] == "Other (Custom)":
            weight = mat["custom_weight"] if mat["custom_weight"] != 0 else 5
            recyclable = mat["custom_recyclable"]
        else:
            match = next((m for m in PREDEFINED_MATERIALS if m["name"] == mat["type"]), None)
            weight = match["weight"] if match else 5
            recyclable = match["recyclable"] if match else False
        
        total_impact += (qty // 100) * weight
        if recyclable:
            total_recyclable += qty
    
    recyclable_rate = (total_recyclable / total_qty * 100) if total_qty > 0 else 100
    return total_impact, round(recyclable_rate, 1), total_plastic

def calculate_sustainability_scores():
    data = st.session_state["campaign_data"]
    total_carbon = calculate_total_carbon_emission()
    total_mat_impact, recyclable_rate, _ = calculate_material_metrics()

    # Environmental Impact (40 pts)
    travel_score = 20 if total_carbon <= 500 else 17 if 501<=total_carbon<=1000 else 14 if 1001<=total_carbon<=1500 else 11 if 1501<=total_carbon<=2000 else 8
    mat_penalty = min(10, total_mat_impact // 5)
    recyclable_bonus = 5 if recyclable_rate >=70 else 2 if 30<=recyclable_rate<70 else 0
    env_score = travel_score + max(0, 20 - mat_penalty + recyclable_bonus)

    # Social Responsibility (30 pts)
    local_score = min(15, round(data["Local Vendor %"] / 100 * 15))
    total_staff = sum(g["Staff Count"] for g in data["Staff Groups"])
    acc_score_map = {"Budget":15, "3-star":15, "4-star":10, "5-star":5}
    total_acc_score = sum(acc_score_map[g["Accommodation"]] * g["Staff Count"] for g in data["Staff Groups"])
    acc_score = total_acc_score // total_staff if total_staff >0 else 0
    social_score = local_score + acc_score

    # Governance (20 pts) + Operations (10 pts)
    gov_score = sum(data["governance_checks"]) * 4
    ops_score = sum(data["operations_checks"]) * 2

    return {
        "Environmental Impact": env_score,
        "Social Responsibility": social_score,
        "Governance": gov_score,
        "Operations": ops_score
    }

# --- Sidebar UI ---
st.sidebar.header("📋 Campaign Setup")

# 1. PDF Upload
st.sidebar.subheader("📄 Marketing Plan (AI Analysis)")
uploaded_pdf = st.sidebar.file_uploader("Upload PDF for AI Extraction", type="pdf")
if uploaded_pdf:
    with st.spinner("🔍 Analyzing PDF..."):
        pdf_text = extract_pdf_text(uploaded_pdf)
        st.session_state["campaign_data"]["extracted_pdf_text"] = pdf_text
        
        with st.sidebar.expander("View Extracted Text", False):
            st.text_area("Content", pdf_text, 150, disabled=True)
        
        if OPENAI_AVAILABLE:
            pdf_data = ai_extract_pdf_data(pdf_text)
            if pdf_data:
                st.sidebar.success("✅ AI populated form!")
                if "duration" in pdf_data and pdf_data["duration"]:
                    st.session_state["campaign_data"]["Duration (days)"] = pdf_data["duration"]
                if "local_vendor_pct" in pdf_data and pdf_data["local_vendor_pct"]:
                    st.session_state["campaign_data"]["Local Vendor %"] = pdf_data["local_vendor_pct"]

# 2. Basic Details
st.sidebar.subheader("🎯 Campaign Details")
campaign_name = st.sidebar.text_input("Campaign Name", st.session_state["campaign_data"]["Campaign Name"])
duration = st.sidebar.slider("Duration (days)", 1, 30, st.session_state["campaign_data"]["Duration (days)"])

# 3. Local Vendors
st.sidebar.subheader("🏘️ Local Vendors")
local_vendor_pct = st.sidebar.slider("% Local Vendors", 0, 100, st.session_state["campaign_data"]["Local Vendor %"])

# 4. Staff Travel
st.sidebar.subheader("👥 Staff Travel Groups")
col_add_staff, col_remove_staff = st.sidebar.columns(2)
with col_add_staff:
    if st.button("➕ Add Group", "add_staff"):
        update_staff_count("add")
with col_remove_staff:
    if st.button("➖ Remove Group", "remove_staff"):
        update_staff_count("remove")

staff_groups = []
for i in range(st.session_state["staff_group_count"]):
    st.sidebar.markdown(f"**Group {i+1}**")
    default = st.session_state["campaign_data"]["Staff Groups"][i] if i < len(st.session_state["campaign_data"]["Staff Groups"]) else {
        "Staff Count": 5, "Departure": "City A", "Destination": "City B",
        "Travel Distance (km)": 100, "Travel Mode": "Car", "Accommodation": "3-star"
    }

    staff_count = st.sidebar.number_input(f"Staff Count", 1, value=default["Staff Count"], key=f"staff_{i}_count")
    departure = st.sidebar.text_input(f"Departure", default["Departure"], key=f"staff_{i}_dep")
    destination = st.sidebar.text_input(f"Destination", default["Destination"], key=f"staff_{i}_dest")
    
    col_dist, col_btn = st.sidebar.columns([3, 2])
    with col_dist:
        travel_dist = st.sidebar.number_input(f"Distance (km)", 0, value=default["Travel Distance (km)"], key=f"staff_{i}_dist")
    with col_btn:
        if st.button("🤖 AI Estimate", key=f"staff_ai_{i}") and OPENAI_AVAILABLE:
            with st.spinner("Estimating..."):
                estimated = ai_estimate_travel_distance(departure, destination)
                if estimated:
                    travel_dist = estimated
                    st.sidebar.success(f"Estimated: {estimated} km")

    # In the "Staff Travel Groups" section of the sidebar (where travel_mode is selected)
# Replace the existing travel_mode selectbox with this:

# Expand travel mode options to include flight seat classes
travel_mode_options = [
    "Air - Economy", 
    "Air - Premium Economy", 
    "Air - Business", 
    "Air - First Class",
    "Train", 
    "Car", 
    "Bus", 
    "Other"
]

# Get default mode index (handle old data compatibility)
default_mode = default["Travel Mode"]
if default_mode == "Air":  # Convert old "Air" to "Air - Economy" for compatibility
    default_mode = "Air - Economy"
try:
    mode_index = travel_mode_options.index(default_mode)
except ValueError:
    mode_index = 0  # Fallback to Economy if mode is unknown

travel_mode = st.sidebar.selectbox(
    f"Travel Mode (Group {i+1})", 
    travel_mode_options, 
    index=mode_index, 
    key=f"staff_{i}_mode"
)

# Show seat class info tooltip for flights
if travel_mode.startswith("Air -"):
    st.sidebar.caption("ℹ️ Higher seat classes increase carbon emissions due to greater space per passenger.")
    accommodation = st.sidebar.selectbox(f"Accommodation", ["Budget", "3-star", "4-star", "5-star"], 
                                        ["Budget", "3-star", "4-star", "5-star"].index(default["Accommodation"]), 
                                        key=f"staff_{i}_acc")

    staff_groups.append({
        "Staff Count": staff_count, "Departure": departure, "Destination": destination,
        "Travel Distance (km)": travel_dist, "Travel Mode": travel_mode, "Accommodation": accommodation
    })

# 5. Materials
st.sidebar.subheader("📦 Materials")
col_add_mat, col_remove_mat = st.sidebar.columns(2)
with col_add_mat:
    if st.button("➕ Add Material", "add_mat"):
        update_material_count("add")
with col_remove_mat:
    if st.button("➖ Remove Material", "remove_mat"):
        update_material_count("remove")

materials = []
for i in range(st.session_state["material_count"]):
    default = st.session_state["campaign_data"]["Materials"][i] if i < len(st.session_state["campaign_data"]["Materials"]) else {
        "type": "Brochures", "quantity": 1000, "material_type": "Paper",
        "custom_name": "", "custom_weight": 3, "custom_recyclable": True
    }

    mat_types = [m["name"] for m in PREDEFINED_MATERIALS]
    mat_type = st.sidebar.selectbox(f"Material {i+1}", mat_types, 
                                   mat_types.index(default["type"]) if default["type"] in mat_types else 0, 
                                   key=f"mat_{i}_type")
    quantity = st.sidebar.number_input(f"Quantity", 0, value=default["quantity"], key=f"mat_{i}_qty")

    custom_name, custom_weight, custom_recyclable, material_type = "", 0, False, "Custom"
    # In the "Materials" section of the sidebar (where mat_type == "Other (Custom)")
if mat_type == "Other (Custom)":
    custom_name = st.sidebar.text_input(
        "Custom Material Name", 
        default["custom_name"], 
        key=f"mat_{i}_custom",
        placeholder="e.g., Bamboo Utensils, Biodegradable Cups"  # Add clear placeholder
    )
    # Add validation: Disable AI button if name is empty
    if not custom_name.strip():
        st.sidebar.warning("ℹ️ Enter a material name first (e.g., 'Biodegradable Plates').")
        st.sidebar.button("🤖 AI Impact", key=f"mat_ai_{i}", disabled=True)  # Disable button
    else:
        # Enable button only if name is provided
        if st.sidebar.button("🤖 AI Impact", key=f"mat_ai_{i}") and OPENAI_AVAILABLE:
            with st.spinner("Analyzing material impact..."):
                weight, recyclable = ai_analyze_custom_material(custom_name)
                custom_weight, custom_recyclable = weight, recyclable
else:
    material_type = next((m["type"] for m in PREDEFINED_MATERIALS if m["name"] == mat_type), "Paper")
    materials.append({
        "type": mat_type, "quantity": quantity, "material_type": material_type,
        "custom_name": custom_name, "custom_weight": custom_weight, "custom_recyclable": custom_recyclable
    })

# 6. Governance & Operations Checks
st.sidebar.subheader("📋 Governance Standards")
gov_checks = [st.sidebar.checkbox(c, st.session_state["campaign_data"]["governance_checks"][i], key=f"gov_{i}") 
             for i, c in enumerate(GOVERNANCE_CRITERIA)]

st.sidebar.subheader("⚙️ Operational Efficiency")
ops_checks = [st.sidebar.checkbox(c, st.session_state["campaign_data"]["operations_checks"][i], key=f"ops_{i}") 
             for i, c in enumerate(OPERATIONS_CRITERIA)]

# Save Button
if st.sidebar.button("💾 Save Details", use_container_width=True):
    st.session_state["campaign_data"].update({
        "Campaign Name": campaign_name, "Duration (days)": duration,
        "Staff Groups": staff_groups, "Materials": materials,
        "Local Vendor %": local_vendor_pct,
        "governance_checks": gov_checks, "operations_checks": ops_checks
    })
    st.sidebar.success("✅ Saved!")

# --- Rerun Trigger ---
if st.session_state["rerun_trigger"]:
    st.session_state["rerun_trigger"] = False
    st.rerun()

# --- Main Dashboard ---
data = st.session_state["campaign_data"]
total_carbon = calculate_total_carbon_emission()
total_mat_impact, recyclable_rate, _ = calculate_material_metrics()
scores = calculate_sustainability_scores()
total_score = sum(scores.values())

st.title("🌿 Sustainable Marketing Evaluator")

# 1. Overview
st.subheader("📝 Campaign Overview")
col1, col2, col3 = st.columns(3)
with col1: st.metric("Name", data["Campaign Name"])
with col2: st.metric("Duration", f"{data['Duration (days)']} days")
with col3: st.metric("Total Staff", sum(g["Staff Count"] for g in data["Staff Groups"]))

# 2. Staff Travel
st.subheader("👥 Staff Travel Details")
st.dataframe(pd.DataFrame(data["Staff Groups"]), use_container_width=True)

# 3. Carbon Footprint
st.subheader("🚨 Carbon Footprint")
st.metric("Total CO₂ Emissions", f"{total_carbon} kg")

# Add seat class impact comparison chart (if there are flights)
flight_groups = [g for g in data["Staff Groups"] if g["Travel Mode"].startswith("Air -")]
if flight_groups:
    st.subheader("✈️ Flight Seat Class Impact")
    # Get emission data for each seat class
    seat_class_data = {}
    for group in flight_groups:
        mode = group["Travel Mode"]
        if mode not in seat_class_data:
            seat_class_data[mode] = 0
        # Calculate emissions for this group's seat class
        emissions = group["Travel Distance (km)"] * EMISSION_FACTORS[mode] * group["Staff Count"]
        seat_class_data[mode] += emissions
    
    # Create bar chart
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(seat_class_data.keys(), seat_class_data.values(), color=["#4CAF50", "#FFC107", "#FF9800", "#F44336"])
    ax.set_ylabel("CO₂ Emissions (kg)")
    ax.set_title("Emissions by Flight Seat Class")
    st.pyplot(fig)
else:
    # No flights? Show standard benchmark chart
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
        recyclable = m["custom_recyclable"] if m["type"] == "Other (Custom)" else next(
            (p["recyclable"] for p in PREDEFINED_MATERIALS if p["name"] == m["type"]), False)
        mat_data.append({
            "Material": name, "Quantity": m["quantity"], 
            "Type": m["material_type"], "Recyclable": "✅" if recyclable else "❌"
        })
    st.dataframe(pd.DataFrame(mat_data), use_container_width=True)
    st.metric("Recyclability Rate", f"{recyclable_rate}%")

# 5. Scorecard
st.subheader("📊 Sustainability Scorecard")
st.metric("Overall Score", f"{total_score}/100")
fig, ax = plt.subplots(figsize=(10, 5))
ax.bar(scores.keys(), scores.values(), color=["#4CAF50", "#2196F3", "#FF9800", "#9C27B0"])
ax.set_ylim(0, 40)
st.pyplot(fig)

# 6. AI Recommendations
st.subheader("💡 AI Recommendations")
if st.button("Generate AI Insights", use_container_width=True) and OPENAI_AVAILABLE:
    with st.spinner("Generating insights..."):
        st.session_state["campaign_data"]["ai_recommendations"] = ai_generate_sustainability_tips()

if st.session_state["campaign_data"]["ai_recommendations"]:
    for i, rec in enumerate(st.session_state["campaign_data"]["ai_recommendations"], 1):
        st.write(f"{i}. {rec}")

# 7. PDF Export
st.subheader("📄 Export Report")
if st.button("Generate PDF Report", use_container_width=True):
    try:
        report_prompt = f"Create a professional sustainability report for {data['Campaign Name']} with:\n- Score: {total_score}/100\n- Metrics: {total_carbon}kg CO₂, {recyclable_rate}% recyclable\n- Recommendations: {st.session_state['campaign_data']['ai_recommendations']}\nInclude title, summary, metrics table, recommendations."
        report_content = get_ai_response(report_prompt, "Create a formal sustainability report.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdfkit.from_string(report_content, tmp.name)
            with open(tmp.name, "rb") as f:
                st.download_button("Download PDF", f, f"{data['Campaign Name'].replace(' ', '_')}_report.pdf", use_container_width=True)
        os.unlink(tmp.name)
    except Exception as e:
        st.error(f"PDF generation failed: {e}. Ensure 'wkhtmltopdf' is installed.")
