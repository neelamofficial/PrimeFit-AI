import os, json, re
import streamlit as st
from groq import Groq

# Page Config
st.set_page_config(page_title="PrimeFit AI", page_icon="🏋️", layout="wide")

# Custom CSS for Modern Minimalist Look
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background-color: #0F172A; color: #F8FAFC; }
.pf-card { background: #1E293B; padding: 24px; border-radius: 16px; border: 1px solid #334155; margin-bottom: 20px; }
.grad-text { background: linear-gradient(90deg, #38BDF8, #8B5CF6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800; }
div.stButton>button { border-radius: 12px; background: linear-gradient(90deg, #0EA5E9, #6366F1); color: white; border: none; font-weight: 600; height: 48px; }
</style>
""", unsafe_allow_html=True)

# GROQ Client Setup
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")

@st.cache_resource
def get_groq():
    if GROQ_API_KEY:
        return Groq(api_key=GROQ_API_KEY)
    return None

groq_client = get_groq()

# Title
st.markdown("<h1 style='text-align: center;'><span class='grad-text'>PrimeFit AI</span> 🏋️</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #94A3B8;'>Instant Personal Workouts & Budget-Friendly Nutrition Plans — No Account Needed!</p>", unsafe_allow_html=True)
st.divider()

if not groq_client:
    st.error("⚠️ GROQ API Key missing! Streamlit secrets mein `GROQ_API_KEY` add karein.")
    st.stop()

# User Input Form
with st.form("planner_form"):
    st.subheader("📋 Enter Your Details")
    
    col1, col2 = st.columns(2)
    with col1:
        age = st.number_input("Age", 12, 90, 22)
        gender = st.selectbox("Gender", ["Male", "Female", "Other"])
        weight = st.number_input("Weight (kg)", 30.0, 200.0, 70.0)
        height = st.number_input("Height (cm)", 100, 230, 172)
        goal = st.selectbox("Primary Goal", ["Fat Loss / Weight Loss", "Muscle Building", "Strength & Conditioning", "General Fitness"])
    
    with col2:
        level = st.selectbox("Fitness Level", ["Beginner", "Intermediate", "Advanced"])
        location = st.selectbox("Workout Place", ["Home (Bodyweight/Bands)", "Gym (Full Equipment)"])
        budget = st.number_input("Daily Food Budget (PKR)", 100, 5000, 400, step=50)
        meals_per_day = st.slider("Meals per day", 2, 6, 3)
        diet_pref = st.text_input("Dietary Preferences / Restrictions", placeholder="e.g. Vegetarian, High Protein, Eggs allowed, No Seafood")

    submit = st.form_submit_button("🔥 Generate My Fitness & Diet Plan", use_container_width=True)

# Plan Generation Logic
if submit:
    prompt = f"""
    You are an expert personal trainer and nutritionist. Create a complete, highly structured 7-day workout and budget-friendly Pakistani meal plan for this user:
    - Age: {age}, Gender: {gender}, Weight: {weight}kg, Height: {height}cm
    - Goal: {goal}, Level: {level}, Place: {location}
    - Food Budget: Rs. {budget} PKR/day, Meals/day: {meals_per_day}
    - Dietary Preferences: {diet_pref}

    Provide the output in clean Markdown formatting:
    1. **Workout Plan**: List daily split, main exercises, sets, reps, and rest duration.
    2. **Nutrition Plan**: Practical daily meal breakdown using local Pakistani foods (Eggs, Roti, Daal, Chana, Milk, Chicken, Rice) within the Rs. {budget}/day budget.
    3. **Key Tips**: 3 quick actionable lifestyle tips for consistency.
    """

    with st.spinner("⚡ PrimeFit AI is crafting your customized plan..."):
        try:
            response = groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=2000
            )
            plan_output = response.choices[0].message.content
            
            st.success("✨ Your Personalized Plan is Ready!")
            st.markdown(f"<div class='pf-card'>{plan_output}</div>", unsafe_allow_html=True)
            
            # Download Button
            st.download_button(
                label="📥 Download My Plan (TXT)",
                data=plan_output,
                file_name="PrimeFit_AI_Plan.txt",
                mime="text/plain"
            )
        except Exception as e:
            st.error(f"Error generating plan: {e}")

st.divider()
st.caption("<p style='text-align: center; color: #64748B;'>PrimeFit AI — Simple, Fast & Free for Everyone 🇵🇰</p>", unsafe_allow_html=True)
