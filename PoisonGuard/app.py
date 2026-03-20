import os
import json
import logging
import asyncio
from typing import Optional, Dict, Any

import streamlit as st
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError
from PIL import Image
from dotenv import load_dotenv

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

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
MAX_TEXT_LENGTH = 2000

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
# 3. CORE LOGIC (CACHED & ASYNC)
# ==========================================
@st.cache_resource
def init_gemini() -> Optional[genai.GenerativeModel]:
    """Caches the Gemini GenerativeModel instance for efficient resource management."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable is missing.")
        return None
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        MODEL_NAME, 
        system_instruction=SYSTEM_PROMPT,
        generation_config={"response_mime_type": "application/json"}
    )
    return model

def validate_inputs(image: Optional[Image.Image], text: str) -> Optional[str]:
    """Robust input validation to ensure scalability and prevent abuse."""
    if not image and not text.strip():
        return "No input provided. Please upload an image or type a description."
    if len(text) > MAX_TEXT_LENGTH:
        return f"Description is too long. Please limit to {MAX_TEXT_LENGTH} characters."
    if image:
        # Validate image format scalability
        if image.format not in ['JPEG', 'PNG', 'JPG', 'WEBP', 'HEIC']:
            logger.warning(f"Unsupported image format: {image.format}")
            return "Unsupported image format. Please upload a JPG or PNG."
    return None

async def analyze_input_async(model: genai.GenerativeModel, image: Optional[Image.Image], text: str) -> Dict[str, Any]:
    """Asynchronous operation to fetch analysis from Gemini API to sustain performance."""
    try:
        contents = []
        if text.strip():
            contents.append(text.strip())
        if image:
            contents.append(image)
            
        logger.info(f"Sending async analysis request to '{MODEL_NAME}'")
        # Async operation for better resource management
        response = await model.generate_content_async(contents)
        
        if not hasattr(response, 'text') or not response.text:
            return {"error": "The AI model returned an empty response."}
            
        return json.loads(response.text)
        
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
# 4. VIEW (UI RENDERING & DEDUPLICATION)
# ==========================================
def render_list(title: str, items: list) -> None:
    """Helper function to reduce duplicate code for rendering lists."""
    if isinstance(items, list) and items:
        st.write(f"**{title}**")
        for item in items:
            st.markdown(f"- {item}")
    else:
        st.write(f"**{title}** None provided. Monitor closely.")

def render_ui():
    """Renders the Streamlit frontend layout."""
    st.title("🛡️ Poison Guard")
    st.subheader("Your AI-Powered Home Safety Assistant")
    st.markdown("Instantly verify potential household hazards, plants, bites, or chemical spills. **Operates dynamically in Emergency or Educational modes.**")

    col1, col2 = st.columns(2)
    with col1:
        uploaded_file = st.file_uploader("Upload an image (plant, bug, chemical...)", type=["jpg", "jpeg", "png"])
    with col2:
        text_input = st.text_area("Describe the item, exposure, or ask a question...", height=130)

    if st.button("Analyze Threat", type="primary", use_container_width=True):
        image_obj = Image.open(uploaded_file) if uploaded_file else None
        
        # Validation
        val_error = validate_inputs(image_obj, text_input)
        if val_error:
            st.warning(val_error)
            return

        model = init_gemini()
        if not model:
            st.error("API configuration error. Ensure the GEMINI_API_KEY is properly set in the server environment.")
            return

        with st.spinner("Analyzing data with Poison Guard..."):
            # Execute async operation
            result = asyncio.run(analyze_input_async(model, image_obj, text_input))
            
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
    is_critical = mode == "EMERGENCY" or result.get("call_911") or result.get("urgency") in ["High", "Critical"]
    
    st.markdown("---")
    if is_critical:
        st.error("🚨 CRITICAL ALERT 🚨")
        if result.get("call_911"):
            st.error("⚠️ IMMEDIATELY CALL 911 OR YOUR LOCAL POISON CONTROL CENTER (1-800-222-1222) ⚠️")
    else:
        st.success(f"✅ Analysis Complete — **{mode} Mode Active**")
    
    st.header(f"Identification: {result.get('identified_threat', 'Unknown')}")
    
    c1, c2 = st.columns(2)
    with c1:
        st.write(f"**Toxicity Level:** {result.get('toxicity_level', 'N/A')}")
    with c2:
        st.write(f"**Urgency:** {result.get('urgency', 'N/A')}")
    
    # Deduplicated list rendering
    st.subheader("First Aid & Immediate Steps")
    render_list("Steps:", result.get("first_aid_steps", []))
    
    st.divider()
    
    st.subheader("📚 Educational Information")
    edu_info = result.get("educational_info", {})
    if isinstance(edu_info, dict) and edu_info:
        st.write(f"**Common Names:** {edu_info.get('common_names', 'N/A')}")
        st.write(f"**Toxicity Profile:** {edu_info.get('toxicity_to_groups', 'N/A')}")
        st.write(f"**Preventative Measures:** {edu_info.get('preventative_measures', 'N/A')}")
        render_list("Symptoms to Watch For:", edu_info.get("symptoms_to_watch", []))

# ==========================================
# 5. ENTRY POINT
# ==========================================
if __name__ == "__main__":
    render_ui()
    st.markdown("---")
    st.warning("**DISCLAIMER:** This is an AI prototype acting as an informational assistant. It does NOT replace professional medical advice.")
