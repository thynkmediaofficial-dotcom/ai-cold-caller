import os
from dotenv import load_dotenv
from cartesia import Cartesia

load_dotenv()

client = Cartesia(
    api_key=os.getenv("CARTESIA_API_KEY")
)

response = client.tts.generate(
    model_id="sonic-3",
    transcript="Hello! This is Jacqueline, your AI cold calling assistant.",
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

response.write_to_file("test_voice.wav")

print("Voice generated successfully!")