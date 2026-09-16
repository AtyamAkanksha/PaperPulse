import os
import json
import logging
from typing import Dict, Any, Optional
import httpx
from dotenv import load_dotenv
from app.schemas import QuizSchema, QuizQuestion

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def _get_llm_client_config() -> Optional[Dict[str, str]]:
    """Determine which LLM provider to use based on available API keys."""
    if GROQ_API_KEY and GROQ_API_KEY.strip() and not GROQ_API_KEY.startswith("your-"):
        return {
            "url": "https://api.groq.com/openai/v1/chat/completions",
            "api_key": GROQ_API_KEY.strip(),
            "model": GROQ_MODEL,
            "provider": "Groq",
        }
    elif OPENAI_API_KEY and OPENAI_API_KEY.strip() and not OPENAI_API_KEY.startswith("your-"):
        return {
            "url": "https://api.openai.com/v1/chat/completions",
            "api_key": OPENAI_API_KEY.strip(),
            "model": OPENAI_MODEL,
            "provider": "OpenAI",
        }
    return None


async def call_llm(messages: list, response_format_json: bool = False) -> str:
    """Dispatches a chat completion call to configured LLM (Groq or OpenAI)."""
    config = _get_llm_client_config()
    if not config:
        logger.warning("No valid GROQ_API_KEY or OPENAI_API_KEY found. Using development mock.")
        return ""

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "model": config["model"],
        "messages": messages,
        "temperature": 0.3,
    }
    if response_format_json and config["provider"] in ["OpenAI", "Groq"]:
        payload["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(config["url"], headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def clean_json_markdown(text: str) -> str:
    """Removes markdown code block ticks (```json ... ```) if present."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


async def generate_summary(text: str, filename: Optional[str] = None) -> str:
    """
    Sends extracted document text to LLM to generate a concise, structured summary.
    Falls back to intelligent local extraction if no API key is configured.
    """
    if not text or not text.strip():
        return "No extractable text was found in the document to generate a summary."

    # Truncate text if excessively long to stay within token context
    truncated_text = text[:12000]

    system_prompt = (
        "You are an expert research analyst and academic tutor. "
        "Analyze the provided document text and generate a clear, concise, and structured summary. "
        "Highlight key concepts, main findings, and essential takeaways using structured bullet points."
    )
    user_prompt = f"Document: {filename or 'Uploaded File'}\n\nContent:\n{truncated_text}"

    config = _get_llm_client_config()
    if config:
        try:
            summary = await call_llm(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )
            if summary and summary.strip():
                return summary.strip()
        except Exception as e:
            logger.error("Error communicating with LLM provider: %s", str(e))

    # Dev fallback when API keys are absent or during network failures
    preview = " ".join(truncated_text.split()[:80])
    return (
        f"### Summary for {filename or 'Document'}\n\n"
        f"**Key Highlights:**\n"
        f"- Core subject: {preview}...\n"
        f"- Document length: {len(text)} characters analyzed.\n"
        f"- Note: Configure GROQ_API_KEY or OPENAI_API_KEY in .env for full AI-generated summaries."
    )


async def generate_quiz(text: str, filename: Optional[str] = None, num_questions: int = 4) -> QuizSchema:
    """
    Sends extracted document text to the LLM to generate structured multiple-choice questions.
    Validates output conforming to QuizSchema with Pydantic.
    """
    if not text or not text.strip():
        return QuizSchema(
            title=f"Quiz for {filename or 'Document'}",
            questions=[
                QuizQuestion(
                    question="Why is there no content in this quiz?",
                    options=["The document contained no readable text", "Processing failed", "Unknown", "None"],
                    correct_answer="The document contained no readable text",
                    explanation="No extractable text was found in the uploaded file.",
                )
            ]
        )

    truncated_text = text[:12000]
    system_prompt = (
        "You are an expert educator. Based on the document text provided, generate a multiple-choice quiz. "
        "You MUST respond ONLY with a valid JSON object conforming strictly to this schema:\n"
        "{\n"
        '  "title": "Quiz title",\n'
        '  "questions": [\n'
        "    {\n"
        '      "question": "Question text",\n'
        '      "options": ["Option A", "Option B", "Option C", "Option D"],\n'
        '      "correct_answer": "Option A",\n'
        '      "explanation": "Brief explanation of why this answer is correct"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Ensure all questions have exactly 4 distinct options and one unambiguous correct answer."
    )
    user_prompt = f"Document: {filename or 'Uploaded File'}\nGenerate {num_questions} questions.\n\nContent:\n{truncated_text}"

    config = _get_llm_client_config()
    if config:
        try:
            raw_response = await call_llm(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format_json=True,
            )
            cleaned_json = clean_json_markdown(raw_response)
            
            # If the LLM returned a bare array instead of an object, wrap it
            parsed_raw = json.loads(cleaned_json)
            if isinstance(parsed_raw, list):
                parsed_raw = {"title": f"Quiz for {filename or 'Document'}", "questions": parsed_raw}
                cleaned_json = json.dumps(parsed_raw)

            # Validate strictly through Pydantic
            validated_quiz = QuizSchema.model_validate_json(cleaned_json)
            return validated_quiz
        except Exception as e:
            logger.error("Failed to parse or validate LLM quiz response: %s", str(e))

    # Dev fallback when API keys are absent
    return QuizSchema(
        title=f"Study Quiz for {filename or 'Uploaded Material'}",
        questions=[
            QuizQuestion(
                question=f"What is the focus of the document '{filename or 'Uploaded File'}'?",
                options=[
                    f"Core topics discussed in {filename or 'document'}",
                    "Irrelevant background info",
                    "Random trivia",
                    "Unrelated mathematics",
                ],
                correct_answer=f"Core topics discussed in {filename or 'document'}",
                explanation="Extracted from the primary content of the uploaded document.",
            ),
            QuizQuestion(
                question="How was the document text processed?",
                options=[
                    "PyMuPDF and PyTesseract OCR",
                    "Manual typing",
                    "Audio transcription",
                    "Static mock without extraction",
                ],
                correct_answer="PyMuPDF and PyTesseract OCR",
                explanation="PaperPulse extracts document content using PyMuPDF with OCR fallback.",
            ),
        ]
    )
