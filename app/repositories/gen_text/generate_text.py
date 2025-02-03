import json
import logging
import re
from typing import List

from loguru import logger
from openai import OpenAI
from openai.types.chat import ChatCompletion

from app.core.settings import settings
from app.repositories.gen_text.promp import GEN_VIDEO_SCRIPT, GEN_VIDEO_TERM

_max_retries = 5


def _generate_response(
    prompt: str,
    ) -> str:
    """
    Generates a response from the LLM provider (OpenAI or Gemini) based on the provided prompt.

    Args:
        prompt (str): The prompt that will be sent to the LLM provider.

    Returns:
        str: The generated response from the LLM provider or an error message.
    """  # noqa: E501
    try:
        content = ""
        llm_provider = settings.llm_provider
        logger.info(f"llm provider: {llm_provider}")

        if llm_provider == "openai":
            api_key = settings.open_api_key
            model_name = settings.openai_model_name
            base_url = settings.openai_base_url
            if not base_url:
                base_url = "https://api.openai.com/v1"
        elif llm_provider == "gemini":
            api_key = settings.gemini_api_key
            model_name = settings.gemini_model_name
            base_url = "***"
        else:
            raise ValueError(
                "llm_provider is not set, please set it in the config.toml file."
            )

        if not api_key:
            raise ValueError(
                f"{llm_provider}: api_key is not set.",
            )
        if not model_name:
            raise ValueError(
                f"{llm_provider}: model_name is not set .",
            )
        if not base_url:
            raise ValueError(
                f"{llm_provider}: base_url is not set.",
            )

        if llm_provider == "gemini":
            import google.generativeai as genai

            genai.configure(api_key=api_key, transport="rest")

            generation_config = {
                "temperature": 0.5,
                "top_p": 1,
                "top_k": 1,
                "max_output_tokens": 2048,
            }

            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_ONLY_HIGH",
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_ONLY_HIGH",
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_ONLY_HIGH",
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_ONLY_HIGH",
                },
            ]

            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config,
                safety_settings=safety_settings,
            )

            try:
                response = model.generate_content(prompt)
                candidates = response.candidates
                generated_text = candidates[0].content.parts[0].text
            except (AttributeError, IndexError) as e:
                logger.error("Gemini Error:", e)

            return generated_text

        else:
            client = OpenAI(
                api_key=api_key,
                base_url=base_url,
            )

        response = client.chat.completions.create(
            model=model_name, messages=[{"role": "user", "content": prompt}]
        )
        if response:
            if isinstance(response, ChatCompletion):
                content = response.choices[0].message.content
            else:
                raise Exception(
                    f'[{llm_provider}] returned an invalid response: "{response}", please check your network '  # noqa: E501
                    f"connection and try again.",
                )
        else:
            raise Exception(
                f"[{llm_provider}] returned an empty response, please check your network connection and try again.",  # noqa: E501
            )

        return content.replace("\n", "")
    except Exception as e:
        return f"Error: {e!s}"


def generate_script(
    video_subject: str, language: str = "", paragraph_number: int = 1,
) -> str:
    """
    Generates a video script based on the provided video subject, language, and paragraph count.

    Args:
        video_subject (str): The subject of the video.
        language (str, optional): The language in which the script should be generated. Defaults to "".
        paragraph_number (int, optional): The number of paragraphs in the script. Defaults to 1.

    Returns:
        str: The generated video script.
    """  # noqa: E501

    prompt = GEN_VIDEO_SCRIPT.format(video_subject = video_subject,paragraph_number = paragraph_number)

    if language:
        prompt += f"\n- language: {language}"

    final_script = ""
    logger.info(f"subject: {video_subject}")

    def format_response(response:str) ->str:
        """
        Cleans up the response by removing unnecessary formatting and splitting it into paragraphs.

        Args:
            response (str): The raw response from the LLM provider.

        Returns:
            str: The cleaned response split into paragraphs.
        """
       # Remove asterisks, hashes, and markdown syntax
        response = response.replace("*", "").replace("#", "")
        response = re.sub(r"\[.*\]", "", response)
        response = re.sub(r"\(.*\)", "", response)

        # Split the script into paragraphs and return the first few paragraphs
        paragraphs = response.split("\n\n")

        return "\n\n".join(paragraphs)

    for i in range(_max_retries):
        try:
            response = _generate_response(prompt=prompt)
            if response:
                final_script = format_response(response)
            else:
                logging.error("gpt returned an empty response")


            if final_script:
                break
        except Exception as e:
            logger.error(f"failed to generate script: {e}")

        if i < _max_retries:
            logger.warning(f"failed to generate video script, trying again... {i + 1}")
    if "Error: " in final_script:
        logger.error(f"failed to generate video script: {final_script}")
    else:
        logger.success(f"completed: \n{final_script}")
    return final_script.strip()


def generate_terms(video_subject: str, video_script: str, amount: int = 5) -> List[str]:
    """
    Generates a list of search terms for stock videos based on the provided video subject and script.

    Args:
        video_subject (str): The subject of the video.
        video_script (str): The script of the video.
        amount (int, optional): The number of search terms to generate. Defaults to 5.

    Returns:
        List[str]: A list of search terms.
    """  # noqa: E501


    prompt =  GEN_VIDEO_TERM.format(amount= amount,video_subject = video_subject,
                                    video_script = video_script)

    logger.info(f"subject: {video_subject}")

    search_terms = []
    response = ""
    for i in range(_max_retries):
        try:
            response = _generate_response(prompt)
            if "Error: " in response:
                logger.error(f"failed to generate video script: {response}")
                return response
            search_terms = json.loads(response)
            if not isinstance(search_terms, list) or not all(
                isinstance(term, str) for term in search_terms
            ):
                logger.error("response is not a list of strings.")
                continue

        except Exception as e:
            logger.warning(f"failed to generate video terms: {e!s}")
            if response:
                match = re.search(r"\[.*]", response)
                if match:
                    try:
                        search_terms = json.loads(match.group())
                    except Exception as e:
                        logger.warning(f"failed to generate video terms: {e!s}")
                        pass

        if search_terms and len(search_terms) > 0:
            break
        if i < _max_retries:
            logger.warning(f"failed to generate video terms, trying again... {i + 1}")

    logger.success(f"completed: \n{search_terms}")
    return search_terms

