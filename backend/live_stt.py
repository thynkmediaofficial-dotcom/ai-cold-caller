import asyncio
import json
import os

import sounddevice as sd
import websockets
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("SARVAM_API_KEY")

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1600
MIC_DEVICE = 2


async def main():
    url = (
        "wss://api.sarvam.ai/speech-to-text-realtime/ws"
        "?sample_rate=16000"
        "&language_code=en-IN"
        "&encoding=linear16"
    )

    headers = {
        "API-Subscription-Key": API_KEY
    }

    print("Connecting to Sarvam Realtime STT...")

    async with websockets.connect(
        url,
        additional_headers=headers
    ) as ws:

        print("✅ Connected!")
        print("🎤 Speak into your microphone.")
        print("Press Ctrl+C to stop.\n")

        loop = asyncio.get_running_loop()
        audio_queue = asyncio.Queue()

        def audio_callback(indata, frames, time, status):
            if status:
                print("Audio:", status)

            audio = bytes(indata)

            samples = memoryview(audio).cast("h")
            volume = max(abs(x) for x in samples) if samples else 0

            print(
                "🎙️ MIC:",
                len(audio),
                "bytes | volume:",
                volume
            )

            asyncio.run_coroutine_threadsafe(
                audio_queue.put(audio),
                loop
            )

        async def send_audio():
            with sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                blocksize=CHUNK_SIZE,
                dtype="int16",
                channels=CHANNELS,
                device=MIC_DEVICE,
                callback=audio_callback,
            ):
                while True:
                    audio = await audio_queue.get()
                    await ws.send(audio)

        async def receive_results():
            async for message in ws:
                try:
                    data = json.loads(message)
                    print("\nSARVAM:", data)
                except Exception:
                    print("\nSARVAM:", message)

        await asyncio.gather(
            send_audio(),
            receive_results()
        )


if __name__ == "__main__":
    asyncio.run(main())