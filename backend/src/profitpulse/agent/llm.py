"""LLM provider factory. API keys stay in server-side environment variables."""
import os


class LLMConfigurationError(RuntimeError):
    pass


def build_chat_model():
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise LLMConfigurationError(
                "Gemini is selected but GEMINI_API_KEY is not configured in the API environment."
            )
        from langchain_google_genai import ChatGoogleGenerativeAI

        model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        model = ChatGoogleGenerativeAI(
            model=model_name,
            api_key=api_key,
            max_retries=2,
        )
        return provider, model_name, model

    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise LLMConfigurationError(
                "Groq is selected but GROQ_API_KEY is not configured in the API environment."
            )
        from langchain_groq import ChatGroq

        model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        model = ChatGroq(
            model=model_name,
            api_key=api_key,
            temperature=0.1,
            max_retries=2,
            request_timeout=60,
        )
        return provider, model_name, model

    raise LLMConfigurationError("LLM_PROVIDER must be either 'gemini' or 'groq'.")
