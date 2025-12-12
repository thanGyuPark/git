#← 기본 금융 챗봇 (OpenAI/Grok API)
from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def chatbot_response(prompt):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "너는 한국어로 정확하고 친절한 금융 전문가다. 투자 조언은 하지 말고 정보와 분석만 제공해."},
                      {"role": "user", "content": prompt}],
            max_tokens=300
        )
        return response.choices[0].message.content
    except:
        return "죄송합니다. 현재 AI 응답에 문제가 있습니다. 잠시 후 다시 시도해주세요."