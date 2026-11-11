"""
Utility that sends a short prompt to Gemini and returns the generated text.
We only feed Gemini **the already‑computed answer**, never the raw query.
"""
import os
import google.generativeai as genai

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

model = genai.GenerativeModel("gemini-1.5-flash-001")  


def polish(text: str) -> str:
    """
    Sends the deterministic response to Gemini for a more natural tone.
    Returns the polished version (or the original text if the call fails).
    """
    try:
        response = model.generate_content(
            f"""Take the following factual answer and rewrite it in a friendly,
            concise tone. Preserve every numeric value, ID and step‑count exactly.
            Do NOT hallucinate any new attribute.

            Answer:
            {text}
            """,
            safety_settings=genai.types.SafetySetting(
                category=genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=genai.types.HarmBlockThreshold.BLOCK_NONE,
            ),
        )
        return response.text.strip()
    except Exception as e:
        return text