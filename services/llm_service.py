from __future__ import annotations
import json, os, re, requests
import math
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from dotenv import load_dotenv

load_dotenv()


class InvalidLLMResponse(ValueError):
    """The provider returned an incomplete or unusable generation."""


class RateLimitError(RuntimeError):
    """The provider's quota is still unavailable after bounded retries."""


def retry_delay(value: str | None, default: float) -> float:
    """Parse Retry-After seconds or HTTP date without retrying prematurely."""
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        try:
            seconds = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return default
    return max(0, seconds) if math.isfinite(seconds) else default


class LLMService:
    def __init__(self):
        self.api_key = os.getenv('GROQ_API_KEY','')
        self.model = os.getenv('GROQ_MODEL','openai/gpt-oss-20b')
        self.base_url = os.getenv('GROQ_BASE_URL','https://api.groq.com/openai/v1').rstrip('/')
        self.ca_bundle = (
            os.getenv('REQUESTS_CA_BUNDLE')
            or os.getenv('CURL_CA_BUNDLE')
            or os.getenv('GROQ_CA_CERT')
        )

    def configured(self) -> bool:
        return bool(self.api_key)

    def chat(self, system: str, user: str, temperature: float = 0.1) -> str:
        return self.chat_messages([
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ], temperature)

    def chat_messages(self, messages: list[dict], temperature: float = 0.1,
                      *, response_format: dict | None = None,
                      max_completion_tokens: int | None = None) -> str:
        if not self.api_key:
            raise RuntimeError('GROQ_API_KEY is not configured. Copy .env.example to .env and add your key.')
        payload = {'model': self.model, 'messages': messages, 'temperature': temperature}
        if response_format is not None:
            payload['response_format'] = response_format
        if max_completion_tokens is not None:
            payload['max_completion_tokens'] = max_completion_tokens
        total_wait = 0.0
        for attempt in range(3):
            try:
                r = requests.post(
                    f'{self.base_url}/chat/completions',
                    headers={'Authorization': f'Bearer {self.api_key}','Content-Type':'application/json'},
                    json=payload,
                    timeout=120,
                    verify=self.ca_bundle or True,
                )
            except requests.exceptions.SSLError:
                raise RuntimeError('Could not verify the AI endpoint certificate. Check the configured CA certificate.') from None
            except (requests.ConnectionError, requests.Timeout):
                if attempt == 2:
                    raise RuntimeError('The AI connection failed after three attempts. Please check your network or proxy and try again.') from None
                time.sleep(2 ** attempt)
                continue
            if r.status_code != 429:
                break
            delay = retry_delay(r.headers.get('retry-after'), default=5 * (2 ** attempt))
            if attempt == 2 or total_wait + delay > 60:
                wait_hint = f' Wait at least {math.ceil(delay)} seconds before retrying.' if delay else ' Please try again later.'
                raise RateLimitError(
                    'Groq has reached a request or token quota for this account/model.'
                    + wait_hint + ' All app features share this quota. '
                    'Check Groq account Limits if it persists; a daily quota requires waiting for reset. '
                    'Your saved results have not changed.'
                )
            time.sleep(delay)
            total_wait += delay
        if r.status_code == 400 and response_format is not None:
            try:
                error = r.json().get('error', {})
            except ValueError:
                error = {}
            if error.get('code') == 'json_validate_failed':
                raise InvalidLLMResponse('The AI provider could not generate valid JSON.')
        r.raise_for_status()
        choice = r.json()['choices'][0]
        if choice.get('finish_reason') == 'length':
            raise InvalidLLMResponse('The AI response exceeded its output limit. Try a smaller set of documents.')
        content = choice['message'].get('content')
        if not isinstance(content, str) or not content.strip():
            raise InvalidLLMResponse('The AI returned an empty response. Please try again.')
        return content

    def json_chat(self, system: str, user: str) -> dict:
        messages = [
            {'role': 'system', 'content': system + '\nReturn one complete JSON object only. Do not use markdown fences.'},
            {'role': 'user', 'content': user},
        ]
        for attempt in range(2):
            try:
                text = self.chat_messages(
                    messages, temperature=0, response_format={'type': 'json_object'},
                    max_completion_tokens=4096,
                ).strip()
                # Tolerate a complete Markdown fence from compatible endpoints.
                fenced = re.fullmatch(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.S | re.I)
                result = json.loads(fenced.group(1) if fenced else text)
                if not isinstance(result, dict):
                    raise InvalidLLMResponse('Expected a JSON object.')
                return result
            except (json.JSONDecodeError, InvalidLLMResponse) as exc:
                if attempt == 1:
                    raise ValueError(
                        'The AI could not return a complete, valid analysis after two attempts. '
                        'Your saved analysis has not changed. Please run analysis again; '
                        'if this continues, try a smaller set of documents.'
                    ) from exc
                messages.append({
                    'role': 'user',
                    'content': 'The previous attempt was invalid or incomplete. Regenerate the complete JSON object from the original material. Keep descriptions concise, include all required fields, and check commas, quotes and closing brackets.',
                })
