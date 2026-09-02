import os
from dotenv import load_dotenv
from sarvamai import SarvamAI
from google import genai
from google.genai.types import HttpOptions
from cartesia import Cartesia

load_dotenv()

# -------------------------
# SARVAM STT
# -------------------------

sarvam = SarvamAI(
    api_subscription_key=os.getenv("SARVAM_API_KEY")
)

with open("test_audio.wav", "rb") as audio_file:
    stt_response = sarvam.speech_to_text.transcribe(
        file=audio_file,
        model="saaras:v3",
        mode="transcribe"
    )

transcript = stt_response.transcript

print("\nUSER SAID:")
print(transcript)


# -------------------------
# GEMINI
# -------------------------

gemini = genai.Client(
    vertexai=True,
    project="minutt-maps-501410",
    location="us-central1",
    http_options=HttpOptions(api_version="v1"),
)

response = gemini.models.generate_content(
    model="gemini-2.5-flash",
    contents=f"""
You are an AI cold-calling assistant.

The prospect said:

"{transcript}"

Reply naturally and briefly. Do not use markdown.
"""
)

ai_reply = response.text

print("\nAI REPLY:")
print(ai_reply)


# -------------------------
# CARTESIA TTS
# -------------------------

cartesia = Cartesia(
    api_key=os.getenv("CARTESIA_API_KEY")
)

tts_response = cartesia.tts.generate(
    model_id="sonic-3",
    transcript=ai_reply,
    voice={
        "mode": "id",
        "id": "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
    },
    output_format={
        "container": "wav",
        "encoding": "pcm_f32le",
        "sample_rate": 44100,
    },
)

tts_response.write_to_file("pipeline_reply.wav")

print("\n✅ COMPLETE!")
print("Audio saved as: pipeline_reply.wav")