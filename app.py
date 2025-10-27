import openai
import streamlit as st

# Set your OpenAI API key securely
openai.api_key = st.secrets["OPENAI_API_KEY"]  # Or use os.environ["OPENAI_API_KEY"]

# --- AI Recommendation Function ---
def generate_ai_recommendations(campaign_description):
    prompt = f"""
    You are a sustainability expert. Based on the following marketing campaign description, suggest 3 ways to reduce its environmental impact and improve its alignment with SDG 12 and SDG 13.

    Campaign Description:
    {campaign_description}

    Recommendations:
    """
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=300
    )
    return response.choices[0].message.content.strip()

# --- Streamlit UI ---
st.subheader("🧠 AI-Powered Sustainability Recommendations")
campaign_description = st.text_area("Describe your campaign", "We are launching a 2-day product event in Sydney with 25 staff flying in from Melbourne...")
if st.button("Generate Recommendations"):
    with st.spinner("Thinking..."):
        ai_output = generate_ai_recommendations(campaign_description)
        st.markdown(ai_output)
