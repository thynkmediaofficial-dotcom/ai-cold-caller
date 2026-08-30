from fastapi import FastAPI
from google import genai
from google.genai.types import HttpOptions

app = FastAPI()

client = genai.Client(
    vertexai=True,
    project="minutt-maps-501410",
    location="us-central1",
    http_options=HttpOptions(api_version="v1"),
)


@app.get("/")
def home():
    return {"message": "AI Cold Caller is running 🚀"}


@app.get("/ask")
def ask():
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Reply with exactly: Gemini Connected Successfully",
    )

    return {"response": response.text}