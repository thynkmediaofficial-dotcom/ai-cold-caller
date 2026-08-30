import asyncio
import json
import os
import re
import threading
import random

import sounddevice as sd
import websockets

from dotenv import load_dotenv
from google import genai
from google.genai.types import HttpOptions, GenerateContentConfig
from cartesia import Cartesia

load_dotenv()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1600
MIC_DEVICE = 2

TTS_SAMPLE_RATE = 44100

VOICE_ID = "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"


# ==========================================
# GEMINI
# ==========================================

gemini = genai.Client(
    vertexai=True,
    project="minutt-maps-501410",
    location="us-central1",
    http_options=HttpOptions(api_version="v1"),
)

conversation = gemini.aio.chats.create(
    model="gemini-2.5-flash-lite",
    config=GenerateContentConfig(
        temperature=0.3,
        max_output_tokens=80,
system_instruction="""
You are Jacqueline, the virtual receptionist for SmileBright Dental Clinic.

Your job is to answer incoming calls from current and prospective patients.
Your goal is to provide information, help with appointment management, and handle common inquiries efficiently, naturally, warmly, and professionally.

========================================
1. IDENTITY & PURPOSE
========================================

- You are the virtual receptionist for SmileBright Dental Clinic.
- You answer incoming calls from patients and prospective patients.
- You help with clinic information, appointment requests, insurance/payment questions, and general dental-practice inquiries.
- You are NOT a dentist, doctor, nurse, or medical professional.

========================================
2. FACTS
========================================

Use these facts when answering questions:

- Clinic hours: Monday to Saturday, 9 AM to 7 PM.
- Clinic is closed on Sundays.
- Services include:
  general dentistry, cleanings, fillings, root canals, crowns,
  extractions, orthodontics, and teeth whitening.
- Appointment slots are NOT available for live lookup.
- Do NOT claim that a specific appointment time is available.
- For appointment requests, collect the patient's details and say that the team will call back to confirm.
- Most major dental insurance plans are accepted.
- Specific insurance coverage must be confirmed by the front desk.
- Accepted payment methods: cash, credit/debit cards, and UPI.
- EMI options are NOT AVAILABLE.
- Prices are NOT AVAILABLE.
- Doctor availability is NOT AVAILABLE.
- For prices or doctor availability, collect the patient's details and offer a callback.
- For detailed insurance questions, collect the patient's details and offer a callback.

========================================
3. ACTIONS & LIMITS
========================================

YOU CAN:

- Answer questions about clinic hours.
- Answer questions about dental services.
- Answer general insurance questions using the provided facts.
- Answer payment-method questions.
- Collect the patient's full name.
- Collect the patient's phone number.
- Collect appointment preferences.
- Collect details for scheduling, rescheduling, or cancellation requests.
- Collect patient contact information for callbacks.
- End the call politely.

YOU CANNOT:

- Confirm or book appointments in real time.
- Claim that a specific appointment slot is available.
- Quote treatment prices.
- Confirm specific insurance coverage.
- Provide medical advice.
- Diagnose medical conditions.
- Recommend medications or treatments.
- Access patient medical records.
- Invent doctor availability.
- Invent information that is not provided in this prompt.

When something cannot be completed directly, collect the necessary details and explain that the team will follow up.

========================================
4. FLOW: GENERAL INQUIRY
========================================

When the caller asks about clinic hours, services, insurance, or payment:

1. Answer directly using the provided facts.
2. If the question requires information that is unavailable, such as prices or specific insurance coverage, offer a callback.
3. Do not make up information.
4. Ask only one question at a time.

Example:

Caller: "Are you open on Sundays?"

Answer naturally:

"We're closed on Sundays, but we're open Monday through Saturday from 9 AM to 7 PM."

========================================
5. FLOW: APPOINTMENT SCHEDULING
========================================

When the caller wants to schedule an appointment:

1. Ask for their full name.
2. Ask for their phone number.
3. Read the phone number back to them and confirm it.
4. Ask what type of dental service they need.
5. Ask for their preferred date and time.
6. Tell them that the team will call back to confirm the appointment.
7. Do NOT claim that the appointment has been booked.

Example:

Caller:
"I want an appointment tomorrow."

Do not say:
"Sure, you're booked tomorrow."

Instead:

"Of course. May I have your full name?"

Then collect the information one piece at a time.

========================================
RESCHEDULING
========================================

When the caller wants to reschedule:

1. Ask for their full name.
2. Ask for their phone number.
3. Ask for the existing appointment date and time if they know it.
4. Ask for their preferred new date and time.
5. Tell them that the team will call back to confirm the change.
6. Never claim the appointment was successfully changed.

========================================
CANCELLATION
========================================

When the caller wants to cancel:

1. Ask for their full name.
2. Ask for their phone number.
3. Ask for the existing appointment date and time if available.
4. Tell them that the team will handle the cancellation and follow up if necessary.
5. Never claim the cancellation was completed unless an actual booking system confirms it.

========================================
6. FLOW: INSURANCE / PAYMENT INQUIRY
========================================

When asked about insurance:

- Say that SmileBright Dental Clinic accepts most major dental insurance plans.
- Explain that the front desk must confirm specific coverage.
- If they need detailed insurance information, offer a callback.
- Collect their name and phone number when a callback is needed.

When asked about payment:

- Say that the clinic accepts cash, credit/debit cards, and UPI.
- Say that EMI options are not available.

When asked about prices:

- Do NOT provide a price.
- Say that pricing information can be provided by the team.
- Offer a callback.
- Collect their name and phone number.

========================================
7. SCOPE & REDIRECTS
========================================

MEDICAL EMERGENCIES:

If the caller describes a serious or potentially life-threatening emergency:

- Do not diagnose.
- Do not provide treatment instructions.
- Do not give medical advice.
- Say:

"I'm not able to provide medical advice. If this is an emergency, please seek immediate emergency medical care."

Keep the response short.

MEDICAL QUESTIONS:

If someone asks for medical advice, diagnosis, treatment recommendations, medication advice, or what their symptoms mean:

- Explain that you are the clinic receptionist and cannot provide medical advice.
- Offer to connect them with the appropriate medical staff or have the team call them back when appropriate.

NON-DENTAL QUESTIONS:

If the caller asks about something unrelated to SmileBright Dental Clinic:

- Politely explain that you can only assist with SmileBright Dental Clinic matters.
- Redirect the conversation back to the dental practice.

========================================
8. GUARDRAILS
========================================

- Never provide medical advice or diagnosis.
- Never recommend medication.
- Never recommend a specific treatment based on symptoms.
- Never quote prices.
- Never confirm specific insurance coverage.
- Never promise that an appointment is booked unless a real booking system confirms it.
- Never invent appointment availability.
- Never invent doctor availability.
- Never invent clinic information.
- Never expose information about another patient.
- Do not ask unnecessary medical questions.
- Ask only one question at a time.
- Remember information the caller has already provided.
- Never ask for the same information twice.
- If the caller corrects you, accept the correction immediately.
- Keep responses short and natural.
- Do not give long explanations.
- Do not sound robotic.
- Do not repeatedly say "Absolutely", "That's fantastic", or "I'd be happy to help."
- Do not overwhelm the caller with multiple questions at once.

========================================
9. FAQ BEHAVIOR
========================================

Use the following answers when applicable:

Q: Are you open on Sundays?
A: We're closed on Sundays, but we're open Monday to Saturday from 9 AM to 7 PM.

Q: Can I book a cleaning for tomorrow?
A: I can take your details and have the team call back to confirm your appointment for tomorrow. May I have your full name and phone number?

Q: Do you accept XYZ insurance?
A: We accept most major dental insurance plans, but the front desk will need to confirm your specific coverage. Would you like a callback for details?

Q: How much does a root canal cost?
A: I don't have pricing information available, but I can have the team call you back with the details. May I have your name and phone number?

Q: Can you give me medical advice?
A: I'm not able to provide medical advice. If this is an emergency, please seek immediate emergency medical care.

========================================
CONVERSATION STYLE
========================================

- Sound like a real American medical receptionist.
- Warm, calm, confident, and professional.
- Speak naturally.
- Keep most responses to one or two short sentences.
- Ask one question at a time.
- Remember the conversation.
- Do not repeat information unnecessarily.
- If the caller already provided their name, do not ask for it again.
- If the caller already provided their phone number, do not ask again.
- If the caller already explained what they need, move to the next relevant step.
- Never confuse scheduling with confirmation.
- Never confuse a callback request with a completed appointment.
- If information is unavailable, say so honestly and offer a callback.
"""
    ),
)

# ==========================================
# CARTESIA
# ==========================================

cartesia = Cartesia(
    api_key=CARTESIA_API_KEY
)


# ==========================================
# GEMINI RESPONSE
# ==========================================

async def generate_reply(text):

    print("\n🧠 Gemini thinking...")

    full_reply = ""

    async for chunk in await conversation.send_message_stream(text):

        if chunk.text:

            full_reply += chunk.text

            print(
                chunk.text,
                end="",
                flush=True
            )

    print()

    reply = full_reply.strip()

    print("🤖 AI:", reply)

    return reply


# ==========================================
# TTS TEXT CLEANUP
# ==========================================

def prepare_tts(text):

    # Remove markdown
    text = re.sub(r"[*_#`]", "", text)

    # Remove unnecessary quotation marks
    text = text.replace('"', "")
    
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ==========================================
# CARTESIA STREAMING TTS
# ==========================================

def speak_streaming(text, connection, stop_event):

    print("🔊 Speaking...")

    tts_text = prepare_tts(text)

    print("🗣️ TTS:", tts_text)

    ctx = connection.context(
        model_id="sonic-3",
        voice={
            "mode": "id",
            "id": VOICE_ID,
        },
        output_format={
            "container": "raw",
            "encoding": "pcm_f32le",
            "sample_rate": TTS_SAMPLE_RATE,
        },
        language="en",
    )

    # Keep Jacqueline consistently slower
    ctx.push(
        '<speed ratio="0.92"/> ' + tts_text
    )

    ctx.no_more_inputs()

    try:

        with sd.RawOutputStream(
            samplerate=TTS_SAMPLE_RATE,
            channels=1,
            dtype="float32",
        ) as speaker:

            for response in ctx.receive():

                # User interrupted Jacqueline
                if stop_event.is_set():

                    print("🛑 Interrupted!")

                    break

                if response.type == "chunk" and response.audio:

                    speaker.write(response.audio)

                elif response.done:

                    break

    except Exception as e:

        if not stop_event.is_set():
            print("❌ TTS error:", e)

    print("✅ TTS stopped")

# ==========================================
# FILLER PHRASES
# ==========================================

FILLER_PHRASES = [
    "Let me check that for you.",
    "Just a moment.",
    "Let me see.",
    "I'm thinking.",
]

# ==========================================
# MAIN
# ==========================================

# ==========================================
# OFFICE AMBIENCE
# ==========================================

import os
import threading
import time

AMBIENCE_FILE = os.path.join(
    os.path.dirname(__file__),
    "office_ambience.wav"
)

AMBIENCE_VOLUME = 0.45


def play_office_ambience(stop_event):

    import wave
    import numpy as np

    try:
        with wave.open(AMBIENCE_FILE, "rb") as wav:

            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            chunk_frames = 4096

            print("🔊 Office ambience started.")

            with sd.RawOutputStream(
                samplerate=sample_rate,
                channels=channels,
                dtype="int16",
            ) as speaker:

                while not stop_event.is_set():

                    data = wav.readframes(chunk_frames)

                    if not data:
                        wav.rewind()
                        continue

                    audio_data = np.frombuffer(
                        data,
                        dtype=np.int16
                    )

                    # 1.8x volume boost
                    audio_data = np.clip(
                        audio_data * 1.8,
                        -32768,
                        32767
                    ).astype(np.int16)

                    speaker.write(
                        audio_data.tobytes()
                    )

    except Exception as e:
        print("❌ Ambience error:", e)

async def main():

    sarvam_url = (
        "wss://api.sarvam.ai/speech-to-text-realtime/ws"
        "?sample_rate=16000"
        "&language_code=en-IN"
        "&encoding=linear16"
    )

    sarvam_headers = {
        "API-Subscription-Key": SARVAM_API_KEY
    }

    print("Connecting to Sarvam...")

    async with websockets.connect(
        sarvam_url,
        additional_headers=sarvam_headers
    ) as sarvam_ws:

        print("✅ Sarvam connected!")

        print("Connecting to Cartesia...")

        with cartesia.tts.websocket_connect() as cartesia_ws:

            print("✅ Cartesia connected!")
            print("🎤 Jacqueline is ready.")
            print("Press Ctrl+C to stop.\n")

            loop = asyncio.get_running_loop()

            audio_queue = asyncio.Queue()

            speaking_task = None

            stop_event = threading.Event()

            call_active = True

            # ======================================
            # SILENCE CONTROL
            # ======================================

            
            last_user_activity = loop.time()

            # ======================================
            # CALL END
            # ======================================

            async def end_call(reason="normal"):

                nonlocal call_active

                if not call_active:
                    return

                call_active = False

                print(f"\n📞 Ending call: {reason}")

                if silence_task and not silence_task.done():
                    silence_task.cancel()

                if speaking_task and not speaking_task.done():

                    stop_event.set()

                    try:
                        await speaking_task
                    except Exception:
                        pass

                sd.stop()

                print("📞 Call ended.")

            # ======================================
            # DYNAMIC GOODBYE
            # ======================================

            async def say_goodbye():

                nonlocal speaking_task

                stop_event.clear()

                goodbye_prompt = """
The caller has indicated that they are finished with the conversation.

Generate a very short, warm, natural receptionist goodbye.

Rules:
- One short sentence only.
- Do not ask another question.
- Do not introduce new information.
- Sound like a real American receptionist.
"""

                try:

                    response = await asyncio.to_thread(
                        conversation.send_message,
                        goodbye_prompt
                    )

                    goodbye = response.text.strip()

                    print("👋 Goodbye:", goodbye)

                    speaking_task = asyncio.create_task(
                        asyncio.to_thread(
                            speak_streaming,
                            goodbye,
                            cartesia_ws,
                            stop_event
                        )
                    )

                    await speaking_task

                except Exception as e:

                    print("Goodbye error:", e)

            # ======================================
            # GOODBYE DETECTION
            # ======================================

            def is_goodbye(text):

                text = text.lower().strip()

                goodbye_phrases = [
                    "goodbye",
                    "bye",
                    "bye bye",
                    "that's all",
                    "thats all",
                    "i'm done",
                    "im done",
                    "that's it",
                    "thats it",
                    "nothing else",
                    "no that's all",
                    "no thats all",
                    "thank you that's all",
                    "thank you thats all",
                    "thanks that's all",
                    "thanks thats all",
                ]

                return any(
                    phrase in text
                    for phrase in goodbye_phrases
                )

            # ======================================
            # DYNAMIC SILENCE NUDGE
            # ======================================

            async def generate_silence_nudge(stage):

                if stage == 1:

                    instruction = """
The patient has been silent for about 10 seconds.

Generate a very short natural receptionist nudge to check whether they are still there.

One short sentence.
Do not say "Are you still there?" every time.
Sound natural.
"""

                elif stage == 2:

                    instruction = """
The patient has remained silent for another 10 seconds.

Generate a short, polite receptionist nudge.

One short sentence.
Do not sound robotic.
Do not repeat the previous nudge.
"""

                else:

                    instruction = """
The patient has been silent for about 30 seconds.

Generate a short final receptionist message explaining that you will end the call for now.

One short sentence.
Do not ask another question.
Sound warm and professional.
"""

                try:

                    response = await conversation.send_message(
                        instruction
                    )

                    return response.text.strip()

                except Exception as e:

                    print("Silence nudge error:", e)

                    if stage == 1:
                        return "Hi, are you still there?"

                    if stage == 2:
                        return "I just wanted to make sure we didn't lose you."

                    return "I'll end the call for now, but please feel free to call us back."
            # ======================================


                except asyncio.CancelledError:
                    pass

            # ======================================
            # MICROPHONE
            # ======================================

            def audio_callback(
                indata,
                frames,
                time,
                status
            ):

                if status:
                    print("Audio:", status)

                audio = bytes(indata)

                asyncio.run_coroutine_threadsafe(
                    audio_queue.put(audio),
                    loop
                )

            # ======================================
            # SEND MICROPHONE AUDIO
            # ======================================

            async def send_audio():

                with sd.RawInputStream(
                    samplerate=SAMPLE_RATE,
                    blocksize=CHUNK_SIZE,
                    dtype="int16",
                    channels=CHANNELS,
                    device=MIC_DEVICE,
                    callback=audio_callback,
                ):

                    while call_active:

                        audio = await audio_queue.get()

                        if not call_active:
                            break

                        # Don't send microphone audio to Sarvam
                        # while Jacqueline is speaking.
                        # This prevents her own voice from being
                        # transcribed as the user's voice.
                        if speaking_task and not speaking_task.done():
                            continue

                        await sarvam_ws.send(audio)

            # ======================================
            # RECEIVE SARVAM
            # ======================================

            async def receive_results():

                nonlocal speaking_task
                nonlocal last_user_activity
                

                async for message in sarvam_ws:

                    if not call_active:
                        break

                    try:
                        data = json.loads(message)

                    except Exception:
                        continue

                    event = data.get("event")

                    # ==================================
                    # USER STARTED SPEAKING
                    # ==================================

                    if event == "transcript.partial":

                        text = data.get(
                            "text",
                            ""
                        ).strip()

                        if text:

                            last_user_activity = loop.time()

                            # User interrupted Jacqueline
                            if (
                                speaking_task
                                and not speaking_task.done()
                            ):

                                print(
                                    "\n🗣️ User interrupted!"
                                )

                                stop_event.set()

                                sd.stop()

                    # ==================================
                    # FINAL USER SPEECH
                    # ==================================

                    elif event == "transcript.final":

                        text = data.get(
                            "text",
                            ""
                        ).strip()

                        if not text:
                            continue

                        last_user_activity = loop.time()

                        print(
                            "\n👤 You:",
                            text
                        )

                        # ==================================
                        # GOODBYE
                        # ==================================

                        if is_goodbye(text):

                            print(
                                "👋 Goodbye detected."
                            )

                            if (
                                speaking_task
                                and not speaking_task.done()
                            ):

                                stop_event.set()

                                try:
                                    await speaking_task
                                except Exception:
                                    pass

                            stop_event.clear()

                            await say_goodbye()

                            await end_call(
                                "caller goodbye"
                            )

                            break

                        # ==================================
                        # STOP PREVIOUS RESPONSE
                        # ==================================

                        if (
                            speaking_task
                            and not speaking_task.done()
                        ):

                            stop_event.set()

                            try:
                                await speaking_task
                            except Exception:
                                pass

                        stop_event.clear()

                        # ==================================
                        # GEMINI RESPONSE
                        # ==================================

                        # ==================================
                        # ==================================
                        # GEMINI RESPONSE
                        # ==================================

                        reply = await generate_reply(text)

                        stop_event.clear()

                        if not call_active:
                            break



                        # ==================================
                        # TTS
                        # ==================================

                        speaking_task = asyncio.create_task(
                            asyncio.to_thread(
                                speak_streaming,
                                reply,
                                cartesia_ws,
                                stop_event
                            )
                        )

                        # Reset silence timer after AI response
                        last_user_activity = loop.time()

            # ======================================
            # START SILENCE MONITOR
            # ======================================

          

            # ======================================
            # RUN AGENT
            # ======================================

            try:

                await asyncio.gather(
                    send_audio(),
                    receive_results()
                )

            except asyncio.CancelledError:
                pass

            finally:

                call_active = False

                if silence_task and not silence_task.done():
                    silence_task.cancel()

                if speaking_task and not speaking_task.done():

                    stop_event.set()

                    try:
                        await speaking_task
                    except Exception:
                        pass

                sd.stop()

                print("\n✅ Jacqueline stopped.")


# ==========================================
# START
# ==========================================

if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print("\n🛑 Stopped by user.")