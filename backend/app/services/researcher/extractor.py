# backend/app/services/researcher/extractor.py

from typing import List, Optional, Dict, Type, Any
import pydantic
from loguru import logger
import sys
from dotenv import load_dotenv

load_dotenv()

# Assuming trustcall is installed: pip install trustcall
try:
    from trustcall import create_extractor

    TRUSTCALL_AVAILABLE = True
except ImportError:
    logger.error(
        "trustcall library not found. Please install it: pip install trustcall"
    )
    TRUSTCALL_AVAILABLE = False

    async def create_extractor(*args, **kwargs):
        raise ImportError("trustcall not installed")


# --- LangChain Core Imports ---
try:
    from langchain_core.language_models import BaseChatModel
    from langchain_openai import ChatOpenAI

    LANGCHAIN_AVAILABLE = True
except ImportError:
    logger.error(
        "LangChain core components (BaseChatModel, ChatOpenAI) not found. "
        "Please install langchain-core and langchain-openai: "
        "pip install langchain-core langchain-openai"
    )
    LANGCHAIN_AVAILABLE = False

    class BaseChatModel:
        pass

    class ChatOpenAI(BaseChatModel):
        pass


# --- Project Specific Imports ---
try:
    from app.api.schemas.company_profile import CompanyProfileSchema

    SCHEMA_AVAILABLE = True
except ImportError:
    logger.error(
        "CompanyProfileSchema not found. Please ensure it exists in app/schemas/company_profile.py"
    )
    SCHEMA_AVAILABLE = False

    class CompanyProfileSchema(pydantic.BaseModel):
        company_name: Optional[str] = None
        company_description: Optional[str] = None


# --- Constants ---
MAX_TEXT_CHARS_FOR_PROMPT = 140000
DEFAULT_EXTRACTION_MODEL = "gpt-4.1-mini"

# --- Helper Functions ---


def _get_schema_description(schema: Type[pydantic.BaseModel]) -> str:
    """
    Generates a simple string description of the schema fields for the prompt.
    (Reinstated from previous version)
    """
    lines = []
    # Use model_fields for Pydantic v2+
    for field_name, field_info in schema.model_fields.items():
        # Attempt to get a cleaner type representation
        field_type_repr = repr(field_info.annotation).replace("typing.", "")
        # Remove Optional wrapper if present for cleaner display
        if field_type_repr.startswith("Optional[") and field_type_repr.endswith("]"):
            field_type_repr = field_type_repr[len("Optional[") : -1]

        description = getattr(
            field_info, "description", ""
        )  # Get description if available
        lines.append(
            f"- {field_name} ({field_type_repr}): {description or 'No description.'}"
        )
    return "\n".join(lines)


def _build_extraction_prompt(website_text: str, schema_description: str) -> str:
    """
    Builds the detailed "business analyst" prompt for the LLM.
    (Reinstated from previous version)

    Args:
        website_text: The text content extracted from the company's website.
        schema_description: A string describing the target schema fields.

    Returns:
        The formatted prompt string.
    """
    truncated_text = website_text[:MAX_TEXT_CHARS_FOR_PROMPT]
    if len(website_text) > MAX_TEXT_CHARS_FOR_PROMPT:
        logger.warning(
            f"Website text truncated to {MAX_TEXT_CHARS_FOR_PROMPT} chars for prompt."
        )

    # Using the detailed prompt structure again
    return f"""
Act as an expert business analyst tasked with extracting structured information about a company from its website text.
Your goal is to populate a Company Profile based *only* on the information provided in the text below.
Do not invent information or make assumptions beyond what's written. If a specific piece of information is not found, use null/None or an empty list as appropriate for the field type based on the target schema.

Target Information Fields (extract into the required JSON schema):
{schema_description}

Website Text to Analyze:
--- START TEXT ---
{truncated_text}
--- END TEXT ---

Now, extract the information and provide it strictly in the JSON format defined by the CompanyProfileSchema.
"""


# --- Core Extraction Function ---


async def extract_profile_from_text(
    website_text: str,
    llm: BaseChatModel,  # Expect a LangChain LLM instance
    target_schema: Type[CompanyProfileSchema] = CompanyProfileSchema,
) -> Optional[CompanyProfileSchema]:
    """
    Extracts company profile information from website text using trustcall.

    Uses trustcall's `create_extractor` to bind the LLM to the target schema
    and handle reliable extraction with internal retries, using a detailed prompt.

    Args:
        website_text: The text content extracted from the company's website.
        llm: An instance of a LangChain BaseChatModel (e.g., ChatOpenAI).
        target_schema: The Pydantic schema to extract data into.

    Returns:
        An instance of the target_schema populated with extracted information,
        or None if extraction fails or prerequisites are missing.
    """
    if not TRUSTCALL_AVAILABLE:
        logger.error("Cannot extract profile: trustcall library is not available.")
        return None
    if not LANGCHAIN_AVAILABLE:
        logger.error("Cannot extract profile: LangChain core library is not available.")
        return None
    if not SCHEMA_AVAILABLE:
        logger.error("Cannot extract profile: CompanyProfileSchema is not available.")
        return None

    if not isinstance(llm, BaseChatModel):
        logger.error(
            f"Invalid llm provided. Expected instance inheriting from BaseChatModel, got {type(llm)}"
        )
        return None

    if not website_text:
        logger.warning("Website text is empty. Cannot extract profile.")
        return None

    # Generate schema description for the prompt
    schema_description = _get_schema_description(target_schema)

    # Build the detailed prompt
    prompt = _build_extraction_prompt(website_text, schema_description)

    logger.info(
        f"Attempting profile extraction using LLM: {llm.__class__.__name__}. Text length: {len(website_text)}"
    )
    logger.debug(f"Extraction prompt (schema description):\n{schema_description}")
    logger.debug(f"Extraction prompt (truncated text start): {website_text[:200]}...")

    try:
        # Create the extractor agent using trustcall
        extractor_agent = create_extractor(
            llm=llm,
            tools=[target_schema],
            tool_choice=target_schema.__name__,
        )

        # Invoke the agent with the detailed prompt
        result: Dict[str, Any] = await extractor_agent.ainvoke(prompt)

        # Process the result
        responses = result.get("responses")
        if isinstance(responses, list) and len(responses) > 0:
            extracted_profile = responses[0]
            if isinstance(extracted_profile, target_schema):
                logger.success(
                    f"Successfully extracted profile. Company Name: {getattr(extracted_profile, 'company_name', 'N/A')}"
                )
                return extracted_profile
            else:
                logger.error(
                    f"Extraction result is not of the expected type '{target_schema.__name__}'. Got: {type(extracted_profile)}"
                )
                return None
        else:
            # Log the actual result structure if it's unexpected
            logger.error(f"Extraction failed. Unexpected result structure: {result}")
            # You might want to inspect result['messages'] or other keys for error details from trustcall/LLM
            return None

    except Exception as e:
        logger.exception(f"An unexpected error occurred during profile extraction: {e}")
        return None


# --- Example Usage (for quick testing) ---
# (Remains the same as the previous version)
async def main_test():
    """Runs a quick test of the extract_profile_from_text function."""
    logger.remove()
    logger.add(sys.stderr, level="INFO")  # Use INFO or DEBUG

    if not all([TRUSTCALL_AVAILABLE, LANGCHAIN_AVAILABLE, SCHEMA_AVAILABLE]):
        logger.error(
            "Cannot run test due to missing dependencies (trustcall, langchain, schema)."
        )
        return

    # --- LLM Setup (Replace with your actual setup) ---
    try:
        llm = ChatOpenAI(model=DEFAULT_EXTRACTION_MODEL, temperature=0.0)
        await llm.ainvoke("test")  # Basic check
        logger.info(f"Using actual ChatOpenAI model: {DEFAULT_EXTRACTION_MODEL}")
    except Exception as llm_exc:
        logger.error(
            f"Failed to initialize or test ChatOpenAI. Ensure API key is set and valid. Error: {llm_exc}"
        )
        logger.warning("Skipping extraction test.")
        return
    # --- End LLM Setup ---

    sample_website_text = """
    Welcome to The Real Bakery! We are passionate about creating the most delicious cakes and pastries
    using locally sourced ingredients. Our specialties include custom cakes, fresh cookies, and artisanal bread.
    We cater to everyone who enjoys high-quality baked goods. Find us at 456 Main Street, Anytown.
    Contact us via email at info@realbakery.local or call us at 987-654-3210.
    We offer local delivery! Pay with Visa, Mastercard, or Cash. Open Tue-Sun 8am-6pm.
    Follow us on Instagram: https://instagram.com/realbakery. Our sourdough is renowned!
    Our website is https://realbakery.local. We pride ourselves on a warm, welcoming tone.
    """

    print("\n--- Testing Profile Extraction ---")
    extracted_profile = await extract_profile_from_text(
        website_text=sample_website_text, llm=llm, target_schema=CompanyProfileSchema
    )

    if extracted_profile:
        print("\nExtraction Successful! Profile:")
        print(extracted_profile.model_dump_json(indent=2))
    else:
        print("\nExtraction Failed.")
    print("--- End Test ---")


if __name__ == "__main__":
    import asyncio
    import os

    if "OPENAI_API_KEY" not in os.environ:
        logger.warning(
            "OPENAI_API_KEY environment variable not set. The test might fail if using ChatOpenAI."
        )

    try:
        asyncio.run(main_test())
    except ImportError as e:
        print(
            f"ERROR: Missing required library for test (e.g., pydantic, langchain?): {e}"
        )
    except Exception as main_exc:
        logger.exception(
            f"An error occurred during the main test execution: {main_exc}"
        )
