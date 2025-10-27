import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import openai
import pdfkit
import tempfile
import os
import fitz  # PyMuPDF
import json

# --- Page Config ---
st.set_page_config(page_title="Sustainable Marketing Evaluator", layout="wide")

# --- Load OpenAI Key ---
openai.api_key = st.secrets["OPENAI_API_KEY"]

# --- PDF Upload + Extraction ---
st.sidebar.header("📄 Upload Marketing Plan (PDF)")
uploaded_file = st.sidebar.file_uploader("Upload PDF", type="pdf")

def extract_text_from_pdf(file):
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)

def extract_campaign_data(text):
    prompt = f"""
    You are a sustainability analyst. Extract the following from this marketing plan:
    - Campaign Name
    - Location
    - Duration (in days)
    - Staff Count
    - Travel Mode
    - Materials Used (e.g., brochures, tote bags)
    - Accommodation Type
    - Vendor Type (local or not)

    Text:
    {text}

    Respond in JSON format.
    """
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=500
    )
    return json.loads(response.choices[0].message.content.strip())

# --- Default Values ---
defaults = {
    "Campaign Name": "Green Horizons Launch",
    "Location": "Sydney",
    "Duration": 2,
    "Staff Count": 25,
    "Travel Mode": "Air",
    "Brochures": 2000,
    "Tote Bags": 500,
    "Accommodation": "4-star",
    "Local Vendors": True
}

# --- If PDF Uploaded, Extract and Override Defaults ---
if uploaded_file:
    with st.spinner("Extracting campaign details..."):
        pdf_text = extract_text_from_pdf(uploaded_file)
        try:
            extracted = extract_campaign_data(pdf_text)
            defaults.update({
                "Campaign Name": extracted.get("Campaign Name", defaults["Campaign Name"]),
                "Location": extracted.get("Location", defaults["Location"]),
                "Duration": int(extracted.get("Duration", defaults["Duration"])),
                "Staff Count": int(extracted.get("Staff Count", defaults["Staff Count"])),
                "Travel Mode": extracted.get("Travel Mode", defaults["Travel Mode"]),
                "Brochures": int(extracted.get("Materials Used", {}).get("Brochures", defaults["Brochures"])),
                "Tote Bags": int(extracted.get("Materials Used", {}).get("Tote Bags", defaults["Tote Bags"])),
                "Accommodation": extracted.get("Accommodation Type", defaults["Accommodation"]),
                "Local Vendors": extracted.get("Vendor Type", "local").lower() == "local"
            })
        except Exception as e:
            st.error("⚠️ Failed to extract structured data from PDF. Please check formatting.")

# --- Sidebar Form ---
st.sidebar.header("📋 Review & Edit Campaign Details")
campaign_name = st.sidebar.text_input("Campaign Name", defaults["Campaign Name"])
location = st.sidebar.text_input("Location", defaults["Location"])
duration = st.sidebar.slider("Duration (days)", 1, 10, defaults["Duration"])
staff_count = st.sidebar.number_input("Staff Count", min_value=1, value=defaults["Staff Count"])
travel_mode = st.sidebar.selectbox("Travel Mode", ["Air", "Train", "Car"], index=["Air", "Train", "Car"].index(defaults["Travel Mode"]))
brochures = st.sidebar.number_input("Printed Brochures", min_value=0, value=defaults["Brochures"])
tote_bags = st.sidebar.number_input("Tote Bags", min_value=0, value=defaults["Tote Bags"])
accommodation = st.sidebar.selectbox("Accommodation", ["3-star", "4-star", "5-star"], index=["3-star", "4-star", "5-star"].index(defaults["Accommodation"]))
local_vendors = st.sidebar.checkbox("Using Local Vendors?", value=defaults["Local Vendors"])

# --- Scoring Logic ---
def calculate_scores():
    env_score = 40
    if travel_mode == "Air": env_score -= 12
    elif travel_mode == "Car": env_score -= 6
    else: env_score -= 3
    if brochures > 1000: env_score -= 5
    if tote_bags > 300: env_score -= 4

    social_score = 30
    if not local_vendors: social_score -= 10
    if accommodation == "5-star": social_score -= 5

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

# --- SDG Alignment ---
sdg_status = {
    "SDG 12": "✅ Aligned",
    "SDG 13": "⚠️ Partial",
    "SDG 8": "✅ Aligned",
    "SDG 5 & 11": "⚠️ Partial"
}

# --- AI Recommendations ---
def generate_ai_recommendations(description):
    prompt = f"""
    You are a sustainability expert. Based on the following campaign, suggest 3 ways to reduce environmental impact and improve SDG alignment.

    Campaign Description:
    {description}

    Recommendations:
    """
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=300
    )
    return response.choices[0].message.content.strip()

# --- ESG Report HTML ---
def generate_html_report():
    html = f"""
    <html><head><style>
    body {{ font-family: Arial; padding: 20px; }}
    h1 {{ color: #2E8B57; }}
    </style></head><body>
    <h1>ESG Sustainability Report</h1>
    <p><strong>Campaign:</strong> {campaign_name}</p>
    <p><strong>Location:</strong> {location}</p>
    <p><strong>Duration:</strong> {duration} days</p>
    <p><strong>Staff Count:</strong> {staff_count}</p>
    <p><strong>Travel Mode:</strong> {travel_mode}</p>
    <p><strong>Total Score:</strong> {total_score}/100</p>
    <h2>SDG Contributions</h2>
    <ul>{''.join(f"<li>{sdg}: {status}</li>" for sdg, status in sdg_status.items())}</ul>
    <h2>Recommendations</h2>
    <ul>{''.join(f"<li>{rec}</li>" for rec in ai_recommendations.split('\n') if rec.strip())}</ul>
    </body></html>
    """
    return html

# --- Main Page ---
st.title("🌿 Sustainable Marketing Evaluator Dashboard")
st.subheader("Campaign Summary")
st.write(f"**Campaign Name:** {campaign_name}")
st.write(f"**Location:** {location}")
st.write(f"**Duration:** {duration} days")
st.write(f"**Staff Count:** {staff_count}")
st.write(f"**Travel Mode:** {travel_mode}")
st.write(f"**Materials:** {brochures} brochures, {tote_bags} tote bags")
st.write(f"**Accommodation:** {accommodation}")
st.write(f"**Local Vendors:** {'Yes' if local_vendors else 'No'}")

# --- Scorecard ---
st.subheader("📊 Sustainability Scorecard")
st.metric("Overall Sustainability Score", f"{total_score}/100")
fig, ax = plt.subplots()
ax.bar(scores.keys(), scores.values(), color=["green", "blue", "orange", "purple"])
ax.set_ylim(0, 40)
ax.set_ylabel("Score")
st.pyplot(fig)

# --- SDG Alignment ---
st.subheader("🌍 SDG Alignment")
for sdg, status in sdg_status.items():
    st.write(f"{sdg}: {status}")

# --- AI Recommendations ---
st.subheader("🧠 AI Recommendations")
description = f"{campaign_name} in {location} with {staff_count} staff traveling by {travel_mode}, using {brochures} brochures and {tote_bags} tote bags."
if st.button("Generate AI Recommendations"):
    with st.spinner("Thinking..."):
        ai_recommendations = generate_ai_recommendations(description)
        st.session_state["ai_recommendations"] = ai_recommendations
else:
    ai_recommendations = st.session_state.get("ai_recommendations", "")
if ai_recommendations:
    st.markdown(ai_recommendations)

# --- ESG Report Preview ---
st.subheader("📄 ESG Report Preview")
with st.expander("View ESG Summary"):
    st.write(f"**Campaign:** {campaign_name}")
    st.write(f"**Location:** {location}")
    st.write(f"**Duration:** {duration} days")
    st.write(f"**Staff Count:** {staff_count}")
    st.write(f"**Travel Mode:** {travel_mode}")
    st.write(f"**Total Score:** {total_score}/100")
    st.write("**SDG Contributions:**")
    for sdg, status in sdg_status.items():
        st.write(f"- {sdg}: {status}")
    st.write("**Recommendations:**")
    for rec in ai_recommendations.split("\n"):
        st.write(f"- {rec}")

# --- PDF Export ---
if st.button("📄 Export ESG Report as PDF"):
    html = generate_html_report()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
        pdfkit.from_string(html, tmpfile.name)
        with open(tmpfile.name, "rb") as f:
            st.download_button(
                label="Download ESG Report PDF",
                data=f,
                file_name=f"{campaign_name}_ESG_Report.pdf",
                mime="application/pdf"
            )
        os.unlink(tmpfile.name)
