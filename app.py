import os
import google.generativeai as genai
from google.generativeai import types
from google.api_core import exceptions as google_exceptions # Import exceptions
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
import logging

# --- Basic Configuration ---
load_dotenv() # Load variables from .env file for local development
logging.basicConfig(level=logging.INFO) # Basic logging

app = Flask(__name__)

# --- Gemini API Configuration ---
# !! IMPORTANT !! Get the API key from environment variables for security
# !! Replace 'YOUR_NEW_GEMINI_API_KEY' in your .env file locally
# !! and set it as an environment variable in your deployment (Render)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    logging.error("FATAL ERROR: GEMINI_API_KEY environment variable not set.")
    # In a real app, you might exit or disable API functionality here
    # For now, we'll let it fail later if the API is called without a key.
else:
    logging.info(f"API Key loaded from environment: {GEMINI_API_KEY}")

# Configure the Gemini client (only if key is found)
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Specify the exact model you want to use
        MODEL_NAME = "gemini-pro" # Using gemini-pro as it is more stable and generally available
                                         # UPDATE this if gemini-2.5-pro-exp-03-25 becomes generally available via API Key
        model = genai.GenerativeModel(MODEL_NAME)
        logging.info(f"Gemini client configured with model: {MODEL_NAME}")
    except Exception as e:
        logging.error(f"Failed to configure Gemini client: {e}")
        model = None # Ensure model is None if configuration fails
else:
    model = None # Ensure model is None if API key is missing

# --- System Prompt ---
# This is the core instruction set for the LLM based on your requirements
SYSTEM_PROMPT = """You will be acting as an expert Radiologist. Your primary task is to generate a properly formatted Radiology report based on the provided 'image findings' and 'normal report template'.

Here are the inputs you will receive structured below:
--- START FINDINGS ---
{findings_text}
--- END FINDINGS ---

--- START TEMPLATE ---
{template_text}
--- END TEMPLATE ---

Follow these steps meticulously:

1. Refine Findings: Carefully review the user-provided 'image findings'. Rewrite these findings using precise, standard radiological terminology and phrasing. Correct any grammatical errors, spelling mistakes, or radiologically suboptimal terms to reflect how an experienced radiologist would describe them.

2. Integrate into Template: Merge these refined findings into the appropriate sections of the provided 'normal report template'. If a finding is abnormal, ensure the corresponding normal statement in the template is appropriately modified or replaced.

3. Apply Scoring/Grading Systems (Where Applicable):
   For any positive imaging findings identified using the given imaging modality:
   - Apply Applicable Systems: If established scoring/grading/classification systems (e.g., BI-RADS, PI-RADS, LI-RADS, ASPECTS, etc.) are relevant to the positive findings and the imaging modality, you must include detailed reporting based on the most widely accepted and validated system(s).
   - Handle Missing Components: For any missing components required by the scoring/grading/classification system, assign the lowest possible score/grade/classification for the missing components. Clearly indicate which components were missing and assumed to be minimal. Calculate the final score/grade/classification using these assumed minimal values. Note that the final score represents a "minimum possible score" due to incomplete data.
   - Suggest Alternatives: If no scoring/grading/classification system exists for these specific imaging findings in the requested modality, suggest the most appropriate scoring/grading/classification system available for these same positive findings in other imaging modalities, only if such a system exists.
   - Prioritize: Use scoring/grading/classification systems that are commonly used in clinical practice, well-validated, and have high inter-observer reliability.

4. Generate Impression: Pay special attention to the IMPRESSION section. Synthesize the most critical refined findings into a concise, clinically relevant, bulleted impression. This section should summarize the key points and should not simply reiterate all details from the report body, reflecting the style of an experienced Radiologist. You must generate the impression with corresponding advice/recommendations yourself, ensuring accuracy based on the findings. However, limit advice/recommendations to general statements like 'suggested clinical correlation' or 'suggested further evaluation if clinically indicated', rather than providing specific management plans.

5. Formatting and Final Output Rules:
   - Ensure your final report is free of errors and that all abnormal findings are properly contextualized within the report structure.
   - Your final response must be ONLY the completed Radiology report, without any additional commentary, greetings, or explanations before or after the report.
   - Use BOLD formatting for: Main section headings (e.g., **OBSERVATION**, **TECHNIQUE**, **IMPRESSION**), Organ names (e.g., **Liver**, **Lungs**, **Heart**), Positive (abnormal) imaging findings within the report body and in the **IMPRESSION**, and other significant terms or phrases warranting emphasis for clarity.
   - Use BULLET POINTS ONLY in the **IMPRESSION** section. Do not use numbering. Use a standard bullet like '*'.
   - Strictly adhere to the provided template format. Do not add extra headings, bullet points (outside Impression), colons, or other symbols unless they are part of the original template structure. Present all information in complete sentences.

6. Handling Missing/Vague Input (Internal Instruction for You):
   - If the provided 'image findings' are vague or incomplete, use your expert knowledge to infer likely details or make reasonable assumptions to generate a plausible, detailed report based on the context hinted at.
   - If the 'normal report template' is missing or unusable, generate the report using a standard, common, detailed radiological report template suitable for the likely modality or body part suggested by the findings (e.g., a standard Chest CT template, Abdominal MRI template, etc.).
   - Proceed confidently to generate the best possible report even with suboptimal input. Do not state that the input is insufficient in your final output. Your output must *only* be the report itself.
"""

# --- Default Values (if user provides empty inputs) ---
# You can make these more detailed or modality-specific if desired
DEFAULT_FINDINGS = "Routine chest CT requested for cough. Findings show a small opacity in the right upper lobe, measuring 5mm. Otherwise unremarkable."
DEFAULT_TEMPLATE = """**EXAMINATION:** Computed Tomography of the Chest

**CLINICAL HISTORY:** [Insert Clinical History Here, e.g., Cough]

**COMPARISON:** [Insert Comparison Study Here, e.g., None available]

**TECHNIQUE:** Axial images were acquired through the chest following the administration of intravenous contrast. Coronal and sagittal reconstructions were performed.

**FINDINGS:**

**Lungs and Airways:** The trachea and central airways are patent. The lungs are clear bilaterally. No consolidation, effusion, or pneumothorax.

**Mediastinum and Hila:** The heart is normal in size. No mediastinal or hilar lymphadenopathy. The thoracic aorta and pulmonary arteries are unremarkable.

**Pleura:** No pleural thickening or effusion.

**Chest Wall and Soft Tissues:** Unremarkable.

**Upper Abdomen (limited view):** Visualized portions of the liver, spleen, adrenal glands, and kidneys are unremarkable.

**Bones:** No acute osseous abnormalities identified.

**IMPRESSION:**

*   Normal CT scan of the chest.
"""


# --- Flask Routes ---

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/generate_report', methods=['POST'])
def generate_report_api():
    """API endpoint to generate the radiology report."""
    if not model:
        logging.error("Attempted to call /generate_report but Gemini model is not configured (check API key and initialization).")
        return jsonify({"error": "Report generation service is currently unavailable. Missing API configuration."}), 500

    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    user_findings = data.get('findings', '').strip()
    user_template = data.get('template', '').strip()

    # Use defaults if inputs are empty (as per instructions)
    final_findings = user_findings if user_findings else DEFAULT_FINDINGS
    final_template = user_template if user_template else DEFAULT_TEMPLATE

    # Construct the final prompt for the LLM
    prompt_for_llm = SYSTEM_PROMPT.format(
        findings_text=final_findings,
        template_text=final_template
    )

    logging.info("Generating report...")
    # print(f"--- PROMPT SENT TO GEMINI ---\n{prompt_for_llm}\n--- END PROMPT ---") # Uncomment for debugging

    try:
        # Set up generation config - ensure text output
        generation_config = types.GenerationConfig(
            # response_mime_type="text/plain", # Use default or remove if causing issues
            temperature=0.5, # Adjust temperature for creativity vs consistency
            # Add other parameters if needed (top_p, top_k, max_output_tokens)
        )

        # Call the Gemini API
        response = model.generate_content(
            prompt_for_llm,
            generation_config=generation_config,
             # Add safety settings if needed, e.g., block harmful content
            # safety_settings=[
            #     {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            #     {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            # ]
            )

        # Extract the text report
        # Accessing response.text directly is common for simple text models/responses
        # If the response structure is more complex, you might need response.parts[0].text
        generated_report = response.text
        logging.info("Report generated successfully.")
        # print(f"--- REPORT RECEIVED FROM GEMINI ---\n{generated_report}\n--- END REPORT ---") # Uncomment for debugging
        return jsonify({"report": generated_report})

    except google_exceptions.PermissionDenied as e:
         logging.error(f"Gemini API Permission Denied: {e}. Check your API key and permissions.")
         return jsonify({"error": f"API Permission Denied. Please check API key configuration. Details: {e}"}), 403 # Forbidden
    except google_exceptions.ResourceExhausted as e:
         logging.error(f"Gemini API Quota Exceeded: {e}")
         return jsonify({"error": "API quota exceeded. Please try again later or check your usage limits."}), 429 # Too Many Requests
    except google_exceptions.InvalidArgument as e:
         logging.error(f"Gemini API Invalid Argument: {e}. This might be due to the prompt or model parameters.")
         # Check if it's related to safety settings
         if "candidate.safety_ratings" in str(e) or "blocked due to safety" in str(e):
             logging.warning("Report generation blocked due to safety filters.")
             return jsonify({"error": "Report generation failed due to safety filters. The content may have been flagged as potentially harmful."}), 400
         else:
             return jsonify({"error": f"Invalid request sent to API. Details: {e}"}), 400 # Bad Request
    except AttributeError as e:
         # Handle cases where the response structure might be unexpected
         # For example, if response.text doesn't exist because of an error or different structure
         logging.error(f"Error processing Gemini response: {e}. Response object: {response}")
         # Try accessing parts if available and text fails
         try:
             generated_report = response.parts[0].text
             logging.info("Report extracted using response.parts[0].text")
             return jsonify({"report": generated_report})
         except Exception as inner_e:
             logging.error(f"Could not extract text using response.parts either: {inner_e}")
             return jsonify({"error": "Failed to process the response from the report generation service."}), 500
    except Exception as e:
        # Catch any other unexpected errors
        logging.error(f"An unexpected error occurred during report generation: {e}", exc_info=True) # Log traceback
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

# --- Run the App ---
if __name__ == '__main__':
    # Use port defined by environment variable (for Render) or default to 5001 locally
    port = int(os.environ.get('PORT', 5001))
    # Run with host='0.0.0.0' to be accessible externally (needed for Render)
    # debug=False for production/deployment
    app.run(host='0.0.0.0', port=port, debug=False)