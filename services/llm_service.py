from __future__ import annotations
import json, os, re, requests
from dotenv import load_dotenv

load_dotenv()

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
        if not self.api_key:
            raise RuntimeError('GROQ_API_KEY is not configured. Copy .env.example to .env and add your key.')
        r = requests.post(
            f'{self.base_url}/chat/completions',
            headers={'Authorization': f'Bearer {self.api_key}','Content-Type':'application/json'},
            json={'model': self.model,'messages':[{'role':'system','content':system},{'role':'user','content':user}], 'temperature':temperature},
            timeout=120,
            verify=self.ca_bundle or True,
        )
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content']

    def json_chat(self, system: str, user: str) -> dict:
        text = self.chat(system + '\nReturn valid JSON only. Do not use markdown fences.', user)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r'\{.*\}', text, re.S)
            if not m:
                raise ValueError(f'LLM did not return JSON: {text[:500]}')
            return json.loads(m.group(0))
