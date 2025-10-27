import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
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
        "Campaign Name": "",
        "Duration (days)": 0,
        "Staff Groups": [],
        "Materials": [],
        "Local Vendor %": 0,
        "governance_checks": [False]*5,
        "operations_checks": [False]*5,
        "ai_recommendations": [],
    }
if "current_step" not in st.session_state:
    st.session_state["current_step"] = 0
if "conversation" not in st.session_state:
    st.session_state["conversation"] = []
if "waiting_for_input" not in st.session_state:
    st.session_state["waiting_for_input"] = True

# --- Constants ---
EMISSION_FACTORS = {
    "Air - Economy": 0.25, "Air - Premium Economy": 0.35, 
    "Air - Business": 0.60, "Air - First Class": 0.90,
    "Train": 0.06, "Car": 0.17, "Bus": 0.08, "Other": 0.12
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
    "Written sustainability goal", "Vendor contracts with sustainability clauses",
    "Eco-certified travel providers", "Certified material suppliers",
    "Planned post-campaign sustainability report"
]
OPERATIONS_CRITERIA = [
    "Campaign duration ≤ 3 days", "Digital alternatives for printed materials",
    "Consolidated staff travel", "Leftover materials donated/recycled",
    "Accommodation near venue"
]

# --- Core AI Functions ---
def get_ai_response(prompt, system_msg="You are a helpful assistant."):
    if not OPENAI_AVAILABLE:
        return "❌ AI requires OPENAI_API_KEY in secrets."
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
            temperature=0.4,  # Lower temp for more consistent factual responses
            timeout=15
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"⚠️ AI error: {str(e)}")
        return "❌ AI response failed. Try again."

# Enhanced distance estimation function
def estimate_distance(departure, destination):
    if not OPENAI_AVAILABLE or not departure or not destination:
        return None
        
    prompt = f"""Estimate the travel distance in kilometers between {departure} and {destination}.
    Consider the most common travel route between these locations.
    Return ONLY a numeric value (no units, no explanations). If you can't estimate, return 0."""
    
    try:
        response = get_ai_response(prompt, "You are a geography expert specializing in travel distances. Return only numbers.")
        return float(response) if response and response.replace('.', '', 1).isdigit() else None
    except:
        return None

def extract_campaign_details(user_input):
    prompt = f"""Extract these fields from the input:
    - Campaign Name (text)
    - Duration (days, number)
    - Local Vendor Percentage (0-100)
    
    Input: {user_input}
    Return as JSON with keys: name, duration, local_vendor_pct. 
    If any field is missing, set to null."""
    
    return json.loads(get_ai_response(prompt, "Extract data accurately. Return only JSON."))

def extract_travel_details(user_input):
    prompt = f"""Extract staff travel groups from input. Each group needs:
    - staff_count (number)
    - departure (location)
    - destination (location)
    - distance_km (number, if provided)
    - travel_mode (choose from: {', '.join(EMISSION_FACTORS.keys())})
    - accommodation (Budget, 3-star, 4-star, 5-star)
    
    Input: {user_input}
    Return as JSON array of objects. If any field missing, set to null."""
    
    return json.loads(get_ai_response(prompt, "Extract travel data. Return only JSON array."))

def extract_material_details(user_input):
    prompt = f"""Extract campaign materials from input. Each material needs:
    - type (choose from: {[m['name'] for m in PREDEFINED_MATERIALS]})
    - custom_name (if type is 'Other (Custom)')
    - quantity (number)
    
    Input: {user_input}
    Return as JSON array of objects. If any field missing, set to null."""
    
    return json.loads(get_ai_response(prompt, "Extract material data. Return only JSON array."))

def extract_checks(user_input, criteria_type):
    criteria = GOVERNANCE_CRITERIA if criteria_type == "governance" else OPERATIONS_CRITERIA
    prompt = f"""Evaluate which of these criteria are met (yes/no) from input:
    {', '.join([f"{i+1}. {c}" for i, c in enumerate(criteria)])}
    
    Input: {user_input}
    Return as JSON array of booleans (true=yes, false=no) in order. 
    If uncertain, set to false."""
    
    return json.loads(get_ai_response(prompt, "Evaluate criteria. Return only JSON array."))

# --- Calculation Functions ---
def calculate_total_carbon_emission():
    total_emission = 0
    for group in st.session_state["campaign_data"]["Staff Groups"]:
        distance = group.get("Travel Distance (km)", 0)
        if distance <= 0: continue
        
        travel_mode = group.get("Travel Mode", "Other")
        emission_factor = EMISSION_FACTORS.get(travel_mode, 0.12)
        total_emission += distance * emission_factor * group.get("Staff Count", 0)
    
    return round(total_emission, 1)
    
def calculate_material_metrics():
    total_impact, total_recyclable, total_qty, total_plastic = 0, 0, 0, 0
    for mat in st.session_state["campaign_data"]["Materials"]:
        qty = mat.get("quantity", 0)
        if qty <= 0: continue
        total_qty += qty
        if mat.get("material_type") == "Plastic": total_plastic += qty
        
        if mat["type"] == "Other (Custom)":
            weight = mat.get("custom_weight", 5)
            recyclable = mat.get("custom_recyclable", False)
        else:
            match = next((m for m in PREDEFINED_MATERIALS if m["name"] == mat["type"]), None)
            weight = match["weight"] if match else 5
            recyclable = match["recyclable"] if match else False
        
        total_impact += (qty // 100) * weight
        if recyclable: total_recyclable += qty
    
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
    total_staff = sum(g.get("Staff Count", 0) for g in data["Staff Groups"])
    acc_score_map = {"Budget": 15, "3-star": 15, "4-star": 10, "5-star": 5}
    total_acc_score = sum(acc_score_map.get(g.get("Accommodation"), 0) * g.get("Staff Count", 0) for g in data["Staff Groups"])
    accommodation_score = total_acc_score // total_staff if total_staff > 0 else 0
    social_score = local_score + accommodation_score

    # Governance (20 pts) + Operations (10 pts)
    gov_score = sum(data["governance_checks"]) * 4
    ops_score = sum(data["operations_checks"]) * 2

    return {
        "Environmental Impact": env_score,
        "Social Responsibility": social_score,
        "Governance": gov_score,
        "Operations": ops_score
    }

# --- Chat Flow Functions ---
def start_conversation():
    st.session_state["conversation"].append({
        "role": "assistant",
        "content": "👋 Welcome to the Sustainable Marketing Evaluator! Let's start with basics. Please share:\n- Campaign name\n- Duration (days)\n- Percentage of local vendors (0-100)"
    })
    st.session_state["current_step"] = 1
    st.session_state["waiting_for_input"] = True

def process_step(step, user_input):
    st.session_state["conversation"].append({"role": "user", "content": user_input})
    data = st.session_state["campaign_data"]
    response = ""

    if step == 1:  # Basic campaign info
        details = extract_campaign_details(user_input) if OPENAI_AVAILABLE else {}
        
        # Validate and collect data
        missing = []
        if details.get("name"):
            data["Campaign Name"] = details["name"]
        else:
            missing.append("campaign name")
        
        if details.get("duration") and isinstance(details["duration"], (int, float)):
            data["Duration (days)"] = int(details["duration"])
        else:
            missing.append("duration (days)")
        
        if details.get("local_vendor_pct") and 0 <= details["local_vendor_pct"] <= 100:
            data["Local Vendor %"] = int(details["local_vendor_pct"])
        else:
            missing.append("local vendor percentage (0-100)")

        if not missing:
            response = "Thanks! Next, tell me about staff travel. For each group (teams from same origin), include:\n- Number of staff\n- Departure/destination locations\n- Travel mode (Air Economy, Train, Car, etc.)\n- Accommodation type (Budget, 3-star, 4-star, 5-star)\nI'll estimate distances automatically if you don't provide them!"
            st.session_state["current_step"] = 2
        else:
            response = f"Could you provide: {', '.join(missing)}?"

    elif step == 2:  # Staff travel info with distance estimation
        travel_groups = extract_travel_details(user_input) if OPENAI_AVAILABLE else []
        valid_groups = []
        estimation_notes = []
        
        for i, group in enumerate(travel_groups, 1):
            # Check for required base fields
            if not all(k in group for k in ["staff_count", "departure", "destination", "travel_mode", "accommodation"]):
                estimation_notes.append(f"Group {i} is missing basic information (staff count, locations, travel mode, or accommodation)")
                continue

            # Handle distance - use provided if available, estimate if missing
            distance = group.get("distance_km")
            if distance is None or not isinstance(distance, (int, float)) or distance <= 0:
                # Attempt AI estimation
                estimated = estimate_distance(group["departure"], group["destination"])
                if estimated and estimated > 0:
                    distance = estimated
                    estimation_notes.append(f"Estimated distance for Group {i} ({group['departure']} to {group['destination']}): {distance} km")
                else:
                    estimation_notes.append(f"Could not estimate distance for Group {i} - please provide it")
                    continue  # Skip group if we can't get distance
            
            # Add valid group
            valid_groups.append({
                "Staff Count": int(group["staff_count"]),
                "Departure": group["departure"],
                "Destination": group["destination"],
                "Travel Distance (km)": float(distance),
                "Travel Mode": group["travel_mode"],
                "Accommodation": group["accommodation"]
            })

        if valid_groups:
            data["Staff Groups"] = valid_groups
            response = "Got it! "
            if estimation_notes:
                response += "\n".join(estimation_notes) + "\n\n"
            response += "Now materials. List each type with quantity. Options: Brochures, Flyers, Plastic Tote Bags, Cotton Tote Bags, Metal Badges, or Custom (specify name)."
            st.session_state["current_step"] = 3
        else:
            response = "I didn't get valid travel details. Please include for each group: staff count, departure, destination, travel mode, and accommodation."

    elif step == 3:  # Materials info
        materials = extract_material_details(user_input) if OPENAI_AVAILABLE else []
        valid_materials = []
        
        for mat in materials:
            if "type" in mat and "quantity" in mat:
                mat_data = {"type": mat["type"], "quantity": int(mat["quantity"])}
                if mat["type"] == "Other (Custom)":
                    mat_data["custom_name"] = mat.get("custom_name", "Custom Material")
                    mat_data["material_type"] = "Custom"
                    mat_data["custom_weight"] = 5
                    mat_data["custom_recyclable"] = False
                else:
                    match = next((m for m in PREDEFINED_MATERIALS if m["name"] == mat["type"]), None)
                    if match:
                        mat_data["material_type"] = match["type"]
                valid_materials.append(mat_data)

        if valid_materials:
            data["Materials"] = valid_materials
            response = "Thanks! Now governance: Do you have these? (yes/no for each)\n1. Written sustainability goal\n2. Vendor contracts with sustainability clauses\n3. Eco-certified travel providers\n4. Certified material suppliers\n5. Planned post-campaign report"
            st.session_state["current_step"] = 4
        else:
            response = "Please list materials with types and quantities (e.g., '100 Brochures, 50 Cotton Tote Bags')."

    elif step == 4:  # Governance checks
        checks = extract_checks(user_input, "governance") if OPENAI_AVAILABLE else [False]*5
        if len(checks) == 5:
            data["governance_checks"] = checks
            response = "Last one! Operations: Do you have these? (yes/no)\n1. Campaign ≤3 days\n2. Digital alternatives for printing\n3. Consolidated staff travel\n4. Leftover materials recycled/donated\n5. Accommodation near venue"
            st.session_state["current_step"] = 5
        else:
            response = "Please answer yes/no for all 5 governance criteria (e.g., 'yes,no,yes,yes,no')."

    elif step == 5:  # Operations checks + Report
        checks = extract_checks(user_input, "operations") if OPENAI_AVAILABLE else [False]*5
        if len(checks) == 5:
            data["operations_checks"] = checks
            response = "Generating your sustainability report..."
            st.session_state["current_step"] = 6
            st.session_state["waiting_for_input"] = False
            generate_report()
        else:
            response = "Please answer yes/no for all 5 operations criteria (e.g., 'yes,no,yes,yes,no')."

    st.session_state["conversation"].append({"role": "assistant", "content": response})

def generate_report():
    data = st.session_state["campaign_data"]
    total_carbon = calculate_total_carbon_emission()
    total_mat_impact, recyclable_rate, _ = calculate_material_metrics()
    scores = calculate_sustainability_scores()
    total_score = sum(scores.values())
    
    # AI Recommendations
    if OPENAI_AVAILABLE:
        prompt = f"""Recommend 3 sustainability improvements for {data['Campaign Name']} (Score: {total_score}/100). 
        Weak areas: {[k for k, v in scores.items() if v < 10]}.
        Metrics: {total_carbon}kg CO₂ | {recyclable_rate}% recyclable | {data['Local Vendor %']}% local vendors."""
        data["ai_recommendations"] = get_ai_response(prompt).split("\n")[:3]
    
    # Report content
    report = f"# 🌿 Sustainability Report: {data['Campaign Name']}\n\n"
    
    report += "## 📝 Overview\n"
    report += f"- **Duration**: {data['Duration (days)']} days\n"
    report += f"- **Total Staff**: {sum(g['Staff Count'] for g in data['Staff Groups'])}\n"
    report += f"- **Local Vendors**: {data['Local Vendor %']}%\n\n"
    
    report += "## 👥 Staff Travel & Carbon Footprint\n"
    for i, group in enumerate(data['Staff Groups'], 1):
        report += f"- Group {i}: {group['Staff Count']} people from {group['Departure']} to {group['Destination']} ({group['Travel Distance (km)']}km via {group['Travel Mode']})\n"
    report += f"\n**Total Carbon Emission**: {total_carbon} kg CO₂\n\n"
    
    report += "## 📦 Materials\n"
    for i, mat in enumerate(data['Materials'], 1):
        name = mat["custom_name"] if mat["type"] == "Other (Custom)" else mat["type"]
        recyclable = "✅" if (mat.get("custom_recyclable") if mat["type"] == "Other (Custom)" else next((p["recyclable"] for p in PREDEFINED_MATERIALS if p["name"] == mat["type"]), False)) else "❌"
        report += f"- {name}: {mat['quantity']} units ({recyclable} recyclable)\n"
    report += f"- **Recyclability Rate**: {recyclable_rate}%\n\n"
    
    report += "## 📊 Sustainability Scorecard\n"
    report += f"- **Overall Score**: {total_score}/100\n"
    for category, score in scores.items():
        max_score = 40 if category == "Environmental Impact" else 30 if category == "Social Responsibility" else 20 if category == "Governance" else 10
        report += f"- {category}: {score}/{max_score}\n"
    
    if data["ai_recommendations"]:
        report += "\n## 💡 Recommendations\n"
        for i, rec in enumerate(data["ai_recommendations"], 1):
            report += f"- {i}. {rec}\n"
    
    st.session_state["conversation"].append({"role": "assistant", "content": report})

# --- UI Rendering ---
st.title("🌿 Sustainable Marketing Evaluator")

if not st.session_state["conversation"]:
    start_conversation()

# Display conversation
for message in st.session_state["conversation"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle user input
if st.session_state["waiting_for_input"] and st.session_state["current_step"] < 6:
    user_input = st.chat_input("Enter your response here...")
    if user_input:
        process_step(st.session_state["current_step"], user_input)
        st.rerun()
elif st.session_state["current_step"] == 6:
    st.chat_input("Ask follow-up questions about your report...")
