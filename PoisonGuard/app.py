import os
import json
import logging
from typing import Optional, Dict, Any

import streamlit as st
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError
from PIL import Image
from dotenv import load_dotenv

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================
# Configure logging for better observability and security tracking
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables securely
load_dotenv()

# Configure page explicitly with accessibility in mind (clear title and layout)
st.set_page_config(
    page_title="Poison Guard",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ==========================================
# 2. CONSTANTS & SYSTEM PROMPTS
# ==========================================
MODEL_NAME = 'gemini-2.5-flash'

SYSTEM_PROMPT = """You are 'Poison Guard', a highly advanced AI system with two distinct personas:
1. Emergency Mode (Poison Control Specialist): When the input describes a potential poisoning, immediate threat, or panic, act authoritatively. Identify the threat and prioritize first aid.
2. Educational Mode (Health Educator): When the user explores potential household hazards or inquires about toxicity, provide informative, preventative advice.

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
If a field is not applicable based on the mode, provide an empty string or empty list, but DO NOT OMIT the key.
Do not provide any markdown formatting around the JSON, just output the raw JSON string.
"""

# ==========================================
# 3. CORE LOGIC (CACHED FOR EFFICIENCY)
# ==========================================
@st.cache_resource
def init_gemini() -> Optional[genai.GenerativeModel]:
    """
    Initializes and caches the Gemini GenerativeModel instance.
    This improves app efficiency by not rebuilding the model object on every run.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable is missing.")
        return None
    
    # Configure the global genai library
    genai.configure(api_key=api_key)
    
    # Instantiate the model with structured output rules
    model = genai.GenerativeModel(
        MODEL_NAME, 
        system_instruction=SYSTEM_PROMPT,
        generation_config={"response_mime_type": "application/json"}
    )
    return model

def analyze_input(model: genai.GenerativeModel, image: Optional[Image.Image], text: str) -> Dict[str, Any]:
    """
    Sends the user text and/or image to the Gemini API and parses the JSON response.
    
    Args:
        model: The initialized GenerativeModel.
        image: A PIL Image object if provided by the user.
        text: A string description provided by the user.
        
    Returns:
        dict: The structured JSON response payload, or a dictionary containing an 'error' key.
    """
    try:
        if not image and not text.strip():
            return {"error": "No input provided. Please upload an image or type a description."}
            
        contents = []
        if text.strip():
            contents.append(text.strip())
        if image:
            contents.append(image)
            
        logger.info(f"Sending analysis request to '{MODEL_NAME}'")
        response = model.generate_content(contents)
        
        # Validating API actual text property exists to avoid unhandled exceptions
        if not hasattr(response, 'text') or not response.text:
            logger.error("Empty response from API")
            return {"error": "The AI model returned an empty response."}
            
        parsed_json = json.loads(response.text)
        return parsed_json
        
    except json.JSONDecodeError as de:
        logger.error(f"JSON Parsing Error: {de}")
        return {"error": "The AI model returned malformed data. Please try again."}
    except GoogleAPIError as gae:
        logger.error(f"Google API Error: {gae}")
        return {"error": "There was an issue communicating with the Google API. Please try again later."}
    except Exception as e:
        logger.error(f"Unexpected error in analyze_input: {e}")
        return {"error": "An unexpected server error occurred during analysis."}

# ==========================================
# 4. VIEW (UI RENDERING)
# ==========================================
def render_ui():
    """Renders the Streamlit frontend layout."""
    # Semantic Titles
    st.title("🛡️ Poison Guard")
    st.subheader("Your AI-Powered Home Safety Assistant")
    st.markdown("Instantly verify potential household hazards, plants, bites, or chemical spills. **Operates dynamically in Emergency or Educational modes.**")

    # Layout for inputs
    col1, col2 = st.columns(2)
    with col1:
        # Accessible label provided internally by Streamlit logic
        uploaded_file = st.file_uploader(
            "Upload an image (plant, bug, chemical...)", 
            type=["jpg", "jpeg", "png"],
            help="Upload a clear photo of the substance or item in question."
        )
    with col2:
        text_input = st.text_area(
            "Describe the item, exposure, or ask a question...", 
            height=130,
            help="Provide as much context as possible (e.g., 'Toddler drank a sip of cleaning fluid')"
        )

    # Submission Action
    if st.button("Analyze Threat", type="primary", use_container_width=True):
        if not uploaded_file and not text_input.strip():
            st.warning("Please upload an image or provide a description to proceed.")
            return

        # Initialize the cached model
        model = init_gemini()
        if not model:
            st.error("API configuration error. Ensure the GEMINI_API_KEY is properly set in the server environment.")
            return

        # Execute analysis efficiently with a spinner
        with st.spinner("Analyzing data with Poison Guard..."):
            image_obj = Image.open(uploaded_file) if uploaded_file else None
            result = analyze_input(model, image_obj, text_input)
            
        render_results(result)

def render_results(result: Dict[str, Any]):
    """Renders the AI JSON payload into readable, conditional Streamlit UI components."""
    if not result:
        st.error("Could not process input. Please try again.")
        return
        
    if "error" in result:
        st.error(f"⚠️ {result['error']}")
        return

    mode = result.get("mode", "EDUCATION")
    
    # --- Dynamic Styling based on Urgency ---
    st.markdown("---")
    is_critical = mode == "EMERGENCY" or result.get("call_911") or result.get("urgency") in ["High", "Critical"]
    
    if is_critical:
        st.error("🚨 CRITICAL ALERT 🚨")
        if result.get("call_911"):
            st.error("⚠️ IMMEDIATELY CALL 911 OR YOUR LOCAL POISON CONTROL CENTER (1-800-222-1222) ⚠️")
    else:
        st.success(f"✅ Analysis Complete — **{mode} Mode Active**")
    
    # --- Core Identification ---
    st.header(f"Identification: {result.get('identified_threat', 'Unknown')}")
    
    c1, c2 = st.columns(2)
    with c1:
        st.write(f"**Toxicity Level:** {result.get('toxicity_level', 'N/A')}")
    with c2:
        st.write(f"**Urgency:** {result.get('urgency', 'N/A')}")
    
    # --- First Aid Steps ---
    st.subheader("First Aid & Immediate Steps")
    first_aid = result.get("first_aid_steps", [])
    if isinstance(first_aid, list) and first_aid:
        for step in first_aid:
            st.markdown(f"- {step}")
    else:
        st.write("No specific immediate steps provided. Monitor closely.")
    
    st.divider()
    
    # --- Educational Safe Mode Display ---
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

# ==========================================
# 5. ENTRY POINT
# ==========================================
if __name__ == "__main__":
    render_ui()
    
    st.markdown("---")
    st.warning(
        "**DISCLAIMER:** This is an AI prototype acting as an informational assistant. "
        "It does NOT replace professional medical advice. Always consult a medical professional or "
        "contact your local Poison Control Center in case of actual poisoning."
    )
