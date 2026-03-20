import streamlit as st
import google.generativeai as genai
from PIL import Image
import os
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Configure page
st.set_page_config(page_title="Poison Guard", page_icon="🛡️", layout="centered")

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY", "").strip()
if not api_key:
    st.error("Please set your GEMINI_API_KEY in the .env file in the project root directory.", icon="⚠️")
    st.stop()
else:
    genai.configure(api_key=api_key)

# The Brain: System Prompt
SYSTEM_PROMPT = """You are 'Poison Guard', a highly advanced AI system with two distinct personas:
1. Emergency Mode (Poison Control Specialist): When the user input describes a potential poisoning, immediate threat, or panic, act authoritatively and clearly. Identify the threat and prioritize first aid.
2. Educational Mode (Health Educator): When the user is asking general questions, exploring potential household hazards, or inquiring about toxicity profiles, provide detailed, informative, and preventative advice.

Analyze the given image and/or text carefully.

You MUST respond strictly in the following JSON schema:
{
  "mode": "EMERGENCY" or "EDUCATION",
  "identified_threat": "Name of the substance, plant, pest, or product",
  "toxicity_level": "None", "Mild", "Moderate", "Severe", or "Lethal",
  "first_aid_steps": ["Step 1", "Step 2", ...],
  "urgency": "Low", "Medium", "High", or "Critical",
  "call_911": true or false,
  "educational_info": {
     "common_names": "Common names",
     "toxicity_to_groups": "Information regarding pets, children, adults",
     "preventative_measures": "How to prevent exposure",
     "symptoms_to_watch": ["Symptom 1", "Symptom 2", ...]
  }
}
If a field is not applicable based on the mode, provide an empty string or empty list, but DO NOT OMIT the key. Do not provide any markdown formatting around the JSON, just output the raw JSON string.
"""

def analyze_input(image, text):
    try:
        # Use gemini-2.0-flash for speed and multimodal capability
        model = genai.GenerativeModel('gemini-2.0-flash', 
                                      system_instruction=SYSTEM_PROMPT,
                                      generation_config={"response_mime_type": "application/json"})
        
        contents = []
        if text:
            contents.append(text)
        if image:
            contents.append(image)
            
        if not contents:
            return None
            
        response = model.generate_content(contents)
        return json.loads(response.text)
    except Exception as e:
        return {"error": str(e)}

# --- UI Layout ---
st.title("🛡️ Poison Guard")
st.subheader("Your Home Safety Assistant")
st.markdown("This app operates in two modes: **Emergency Response** for immediate threats and **Educational Mode** for proactive learning about household hazards.")

col1, col2 = st.columns(2)
with col1:
    uploaded_file = st.file_uploader("Upload an image (plant, bug, chemical...)", type=["jpg", "jpeg", "png"])
with col2:
    text_input = st.text_area("Describe the item, exposure, or ask a question...", height=130)

if st.button("Analyze Now!", type="primary", use_container_width=True):
    if not uploaded_file and not text_input:
        st.warning("Please upload an image or provide a description to analyze.")
    else:
        with st.spinner("Analyzing with Poison Guard..."):
            image = Image.open(uploaded_file) if uploaded_file else None
            result = analyze_input(image, text_input)
            
            if not result:
                st.error("Could not process input.")
            elif "error" in result:
                st.error(f"An error occurred: {result['error']}")
            else:
                mode = result.get("mode", "EDUCATION")
                
                # --- Dynamic Styling based on Urgency/Mode ---
                st.markdown("---")
                if mode == "EMERGENCY" or result.get("call_911") or result.get("urgency") in ["High", "Critical"]:
                    st.error("🚨 CRITICAL ALERT 🚨")
                    if result.get("call_911"):
                        st.error("⚠️ IMMEDIATELY CALL 911 OR YOUR LOCAL POISON CONTROL CENTER (1-800-222-1222) ⚠️")
                else:
                    st.info(f"✅ Analysis Complete — {mode} Mode Active")
                
                # --- Core Info Display ---
                st.header(f"Identification: {result.get('identified_threat', 'Unknown')}")
                
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**Toxicity Level:** {result.get('toxicity_level', 'N/A')}")
                with c2:
                    st.write(f"**Urgency:** {result.get('urgency', 'N/A')}")
                
                st.subheader("First Aid & Immediate Steps")
                first_aid = result.get("first_aid_steps", [])
                if first_aid:
                    for step in first_aid:
                        st.markdown(f"- {step}")
                else:
                    st.write("No specific immediate steps provided. Monitor closely.")
                
                st.divider()
                
                # --- Educational Info Display ---
                st.subheader("📚 Educational Information")
                edu_info = result.get("educational_info", {})
                if isinstance(edu_info, dict) and edu_info:
                    st.write(f"**Common Names:** {edu_info.get('common_names', 'N/A')}")
                    st.write(f"**Toxicity Profile (Groups):** {edu_info.get('toxicity_to_groups', 'N/A')}")
                    st.write(f"**Preventative Measures:** {edu_info.get('preventative_measures', 'N/A')}")
                    
                    symptoms = edu_info.get("symptoms_to_watch", [])
                    if isinstance(symptoms, list) and symptoms:
                        st.write("**Symptoms to Watch For:**")
                        for symp in symptoms:
                            st.markdown(f"- {symp}")

st.markdown("---")
st.warning("⚠️ **DISCLAIMER:** This is an AI prototype acting as an informational assistant. It does NOT replace professional medical advice. Always consult a medical professional or contact your local Poison Control Center in case of actual poisoning.")
