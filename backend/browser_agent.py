import os
import json
import base64
import asyncio
import random
import re
import time

import websockets

from dotenv import load_dotenv

from google import genai
from google.genai.types import GenerateContentConfig

from cartesia import AsyncCartesia


# ==================================================
# ENVIRONMENT
# ==================================================

load_dotenv()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")


# ==================================================
# AUDIO SETTINGS
# ==================================================

SAMPLE_RATE = 16000
TTS_SAMPLE_RATE = 44100

VOICE_ID = "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"


# ==================================================
# SETTINGS
# ==================================================

# Ignore the same Sarvam final transcript if it
# arrives again within this time window.
DUPLICATE_FINAL_WINDOW = 2.5

# End demo call after this much inactivity.
SILENCE_TIMEOUT = 30


# ==================================================
# GEMINI
# ==================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

gemini = genai.Client(
    api_key=GEMINI_API_KEY
),


# ==================================================
# CARTESIA
# ==================================================

cartesia = AsyncCartesia(
    api_key=CARTESIA_API_KEY
)


# ==================================================
# FILLER PHRASES
# ==================================================

GENERAL_FILLERS = [
    "Okay.",
    "Hmm.",
    "Uh-huh.",
    "Ah, okay.",
    "I see.",
    "Got it.",
    "Alright.",
    "Hmm, okay.",
    "Ah, got it.",
    "Okay, I understand.",
    "Right, got it.",
]

APPOINTMENT_FILLERS = [
    "Okay.",
    "Hmm, sure.",
    "Ah, okay.",
    "Alright.",
    "Okay, got it.",
]

PRICE_INSURANCE_FILLERS = [
    "Hmm.",
    "Ah, okay.",
    "Let me see.",
    "Hmm, okay.",
]

CLINIC_INFO_FILLERS = [
    "Oh, okay.",
    "Hmm.",
    "Alright.",
    "Okay.",
]

SERVICE_FILLERS = [
    "Ah, sure.",
    "Hmm, okay.",
    "Oh, got it.",
    "Alright.",
]


# ==================================================
# TTS TEXT CLEANUP
# ==================================================

def prepare_tts(text):

    text = re.sub(
        r"[*_#`]",
        "",
        text
    )

    text = text.replace('"', "")
    text = text.replace("“", "")
    text = text.replace("”", "")

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ==================================================
# SMART FILLER SELECTION
# ==================================================

def choose_filler(text, previous_filler=None):

    normalized = text.lower().strip()

    phrases = GENERAL_FILLERS


    if any(
        word in normalized
        for word in [
            "appointment",
            "book",
            "booking",
            "schedule",
            "reschedule",
            "cancel",
            "date",
            "time",
        ]
    ):

        phrases = APPOINTMENT_FILLERS


    elif any(
        word in normalized
        for word in [
            "price",
            "cost",
            "insurance",
            "payment",
            "emi",
            "pay",
            "coverage",
        ]
    ):

        phrases = PRICE_INSURANCE_FILLERS


    elif any(
        word in normalized
        for word in [
            "hour",
            "open",
            "close",
            "closed",
            "timing",
            "monday",
            "sunday",
            "saturday",
        ]
    ):

        phrases = CLINIC_INFO_FILLERS


    elif any(
        word in normalized
        for word in [
            "cleaning",
            "filling",
            "crown",
            "root canal",
            "whitening",
            "braces",
            "orthodont",
            "extraction",
            "tooth",
            "teeth",
            "dentist",
        ]
    ):

        phrases = SERVICE_FILLERS


    available = [
        phrase
        for phrase in phrases
        if phrase != previous_filler
    ]

    if not available:
        available = phrases

    return random.choice(available)


# ==================================================
# GOODBYE DETECTION
# ==================================================

def is_goodbye(text):

    normalized = text.lower().strip()

    goodbye_phrases = [
        "goodbye",
        "bye",
        "bye bye",
        "that's all",
        "thats all",
        "that's it",
        "thats it",
        "nothing else",
        "i'm done",
        "im done",
        "no that's all",
        "no thats all",
        "thank you bye",
        "thank you goodbye",
        "thanks bye",
        "thanks goodbye",
        "thank you that's all",
        "thank you thats all",
        "thanks that's all",
        "thanks thats all",
    ]

    return any(
        phrase in normalized
        for phrase in goodbye_phrases
    )


# ==================================================
# TRANSCRIPT NORMALIZATION
# ==================================================

def normalize_transcript(text):

    text = text.lower().strip()

    text = re.sub(
        r"[^\w\s]",
        "",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ==================================================
# BROWSER AGENT
# ==================================================

async def handle_browser(websocket):

    print("\n🌐 Browser connected")


    # ==============================================
    # PER-CALL GEMINI CONVERSATION
    # ==============================================

    conversation = gemini.aio.chats.create(
        model="gemini-2.5-flash-lite",

        config=GenerateContentConfig(
            temperature=0.35,

            max_output_tokens=120,

            system_instruction="""
You are Jacqueline, the virtual receptionist for SmileBright Dental Clinic.

You answer incoming calls from current and prospective patients.

Your goal is to provide information, handle common receptionist requests,
and collect details when the clinic team needs to follow up.

========================================
IDENTITY
========================================

You are a virtual receptionist.

You are NOT a dentist, doctor, nurse, or medical professional.

Sound like a real, warm, friendly American receptionist having a natural
phone conversation.

Do not sound robotic, scripted, overly formal, or corporate.

Use natural contractions such as:
"I'm", "we're", "that's", "I'll", "don't", and "can't".

Do not use filler words excessively because the system already plays
a short natural filler while you generate your response.

========================================
CLINIC FACTS
========================================

Clinic hours:

Monday to Saturday:
9 AM to 7 PM.

Closed Sundays.

Services:

- General dentistry
- Cleanings
- Fillings
- Root canals
- Crowns
- Extractions
- Orthodontics
- Teeth whitening

Insurance:

Most major dental insurance plans are accepted.

Specific insurance coverage must be confirmed by the front desk.

Payments:

- Cash
- Credit cards
- Debit cards
- UPI

EMI is not available.

Prices are not available.

Live doctor availability is not available.

Live appointment availability is not available.

========================================
GENERAL INQUIRIES
========================================

For clinic hours, services, general insurance, or payment questions:

1. Answer directly using the provided information.
2. Do not invent missing information.
3. If detailed information is unavailable, offer a callback.
4. Ask only one question at a time.

========================================
APPOINTMENT SCHEDULING FLOW
========================================

When the caller wants to schedule an appointment:

1. Ask for their full name.
2. Ask for their phone number.
3. Read the phone number back and confirm it.
4. Ask what dental service they need.
5. Ask for their preferred date.
6. Ask for their preferred time.
7. Explain that the team will call back to confirm.

Ask only ONE question at a time.

Never ask for information that the caller has already provided.

Never claim that an appointment is booked.

Never claim that a specific appointment slot is available.

========================================
RESCHEDULING FLOW
========================================

When the caller wants to reschedule:

1. Ask for their full name.
2. Ask for their phone number.
3. Ask for the existing appointment date and time if known.
4. Ask for their preferred new date.
5. Ask for their preferred new time.
6. Explain that the team will call back to confirm the change.

Never claim that the appointment was successfully changed.

========================================
CANCELLATION FLOW
========================================

When the caller wants to cancel:

1. Ask for their full name.
2. Ask for their phone number.
3. Ask for the existing appointment date and time if available.
4. Explain that the team will handle the cancellation.
5. Say the team will follow up if necessary.

Never claim that the cancellation is already completed.

========================================
INSURANCE
========================================

Say that the clinic accepts most major dental insurance plans.

Explain that specific coverage must be confirmed by the front desk.

If detailed insurance information is needed, offer a callback.

========================================
PAYMENT
========================================

The clinic accepts:

- Cash
- Credit cards
- Debit cards
- UPI

EMI is not available.

========================================
PRICES
========================================

If asked about a treatment price:

Do NOT invent or estimate a price.

Say that you do not have pricing information available.

Offer to have the clinic team call them back.

Collect their name and phone number if they want a callback.

========================================
DOCTOR AVAILABILITY
========================================

Do not invent doctor availability.

Explain that you do not have live doctor availability.

Offer to take the caller's details and have the clinic team follow up.

========================================
MEDICAL QUESTIONS
========================================

Do not provide:

- medical advice
- diagnosis
- medication recommendations
- treatment recommendations

Explain that you are the clinic receptionist and cannot provide medical
advice.

========================================
MEDICAL EMERGENCY
========================================

If the caller describes a serious or potentially life-threatening
emergency:

Do not diagnose.

Do not provide treatment instructions.

Say:

"I'm not able to provide medical advice. If this is an emergency,
please seek immediate emergency medical care."

========================================
UNRELATED QUESTIONS
========================================

If the caller asks something unrelated to SmileBright Dental Clinic:

Politely explain that you can help with clinic-related matters such as:

- appointments
- clinic hours
- services
- insurance
- payment questions

Then redirect naturally.

========================================
CONVERSATION RULES
========================================

- Keep responses concise and natural.
- Usually use one or two sentences.
- Ask only one question at a time.
- Remember information already provided.
- Never ask for the same information twice.
- Accept corrections immediately.
- Do not repeat yourself unnecessarily.
- Never invent information.
- Never claim an appointment is booked.
- Never claim an appointment time is available.
- Never quote a treatment price.
- Never confirm specific insurance coverage.
- Never provide medical advice.
"""
        ),
    )


    # ==============================================
    # SARVAM CONFIGURATION
    # ==============================================

    sarvam_url = (
        "wss://api.sarvam.ai/"
        "speech-to-text-realtime/ws"
        "?sample_rate=16000"
        "&language_code=en-IN"
        "&encoding=linear16"
    )

    sarvam_headers = {
        "API-Subscription-Key": SARVAM_API_KEY
    }


    # ==============================================
    # CALL STATE
    # ==============================================

    call_active = True

    speaking_task = None
    processing_task = None

    stop_event = asyncio.Event()

    assistant_active = False

    last_user_activity = (
        asyncio.get_running_loop().time()
    )

    last_final_text = ""
    last_final_time = 0.0

    last_filler = None


    # ==============================================
    # GEMINI
    # ==============================================

    async def generate_reply(text):

        response = await conversation.send_message(
            text
        )

        return response.text.strip()


    # ==============================================
    # STREAM AUDIO
    # ==============================================

    async def stream_audio(text):

        tts_text = prepare_tts(text)

        if not tts_text:
            return


        try:

            async with (
                cartesia.tts.websocket_connect()
                as cartesia_ws
            ):

                ctx = cartesia_ws.context(
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


                await ctx.push(
                    '<speed ratio="0.82"/> '
                    + tts_text
                )

                await ctx.no_more_inputs()


                async for response in ctx.receive():

                    if stop_event.is_set():

                        break


                    if (
                        response.type == "chunk"
                        and response.audio
                    ):

                        encoded = (
                            base64.b64encode(
                                response.audio
                            )
                            .decode("utf-8")
                        )


                        await websocket.send_json({
                            "type": "audio",
                            "data": encoded,
                            "sample_rate":
                            TTS_SAMPLE_RATE
                        })


                    elif response.type == "error":

                        print(
                            "❌ Cartesia error:",
                            getattr(
                                response,
                                "message",
                                "Unknown error"
                            )
                        )

                        break


                    elif response.done:

                        break


        except asyncio.CancelledError:

            raise


        except Exception as e:

            if not stop_event.is_set():

                print(
                    "❌ Cartesia error:",
                    e
                )


    # ==============================================
    # STOP CURRENT AUDIO
    # ==============================================

    async def stop_speaking():

        nonlocal speaking_task
        nonlocal assistant_active


        stop_event.set()


        if (
            speaking_task is not None
            and not speaking_task.done()
        ):

            speaking_task.cancel()

            try:

                await speaking_task

            except asyncio.CancelledError:

                pass

            except Exception:

                pass


        try:

            await websocket.send_json({
                "type":
                "assistant_interrupt"
            })

        except Exception:

            pass


        speaking_task = None

        assistant_active = False

        stop_event.clear()


    # ==============================================
    # PLAY FILLER
    #
    # This returns the actual filler task so we can
    # wait for it to finish before playing the answer.
    # ==============================================

    async def start_filler(filler):

        nonlocal speaking_task
        nonlocal assistant_active


        stop_event.clear()

        assistant_active = True


        filler_task = asyncio.create_task(
            stream_audio(filler)
        )


        speaking_task = filler_task


        return filler_task


    # ==============================================
    # SPEAK REAL RESPONSE
    #
    # IMPORTANT:
    #
    # We do NOT call stop_speaking() here when the
    # filler has already finished naturally.
    #
    # That prevents assistant_interrupt from clearing
    # the filler audio that the browser may still have
    # queued for playback.
    # ==============================================

    async def speak_reply(reply):

        nonlocal speaking_task
        nonlocal assistant_active
        nonlocal last_user_activity


        stop_event.clear()

        assistant_active = True


        await websocket.send_json({
            "type": "assistant_text",
            "text": reply
        })


        await websocket.send_json({
            "type": "assistant_start"
        })


        async def run_tts():

            nonlocal assistant_active
            nonlocal last_user_activity

            try:

                await stream_audio(reply)

            except asyncio.CancelledError:

                raise

            finally:

                if not stop_event.is_set():

                    try:

                        await websocket.send_json({
                            "type":
                            "assistant_end"
                        })

                    except Exception:

                        pass


                    last_user_activity = (
                        asyncio.get_running_loop().time()
                    )


                    assistant_active = False


        speaking_task = asyncio.create_task(
            run_tts()
        )


    # ==============================================
    # CANCEL PROCESSING
    # ==============================================

    async def cancel_processing():

        nonlocal processing_task

        current_task = asyncio.current_task()


        if (
            processing_task is not None
            and not processing_task.done()
            and processing_task is not current_task
        ):

            processing_task.cancel()


            try:

                await processing_task

            except asyncio.CancelledError:

                pass

            except Exception:

                pass


        if (
            processing_task is not None
            and processing_task.done()
        ):

            processing_task = None


    # ==============================================
    # END CALL
    # ==============================================

    async def end_call(reason):

        nonlocal call_active

        if not call_active:
            return


        call_active = False

        print(
            f"📞 Ending call: {reason}"
        )


        await stop_speaking()


        try:

            await websocket.close()

        except Exception:

            pass


    # ==============================================
    # PROCESS FINAL USER TEXT
    #
    # NEW GUARANTEED FILLER FLOW:
    #
    # FINAL USER TRANSCRIPT
    #          ↓
    # START FILLER
    #          +
    # START GEMINI AT SAME TIME
    #          ↓
    # GEMINI MAY FINISH EARLY
    #          ↓
    # WAIT FOR FILLER TASK TO FINISH
    #          ↓
    # START ACTUAL RESPONSE
    # ==============================================

    async def process_user_text(text):

        nonlocal last_user_activity
        nonlocal last_filler
        nonlocal speaking_task
        nonlocal assistant_active


        if not text:
            return


        last_user_activity = (
            asyncio.get_running_loop().time()
        )


        print(
            "\n👤 USER:",
            text
        )


        await websocket.send_json({
            "type": "user_text",
            "text": text
        })


        # ==========================================
        # GOODBYE
        # ==========================================

        if is_goodbye(text):

            goodbye_message = (
                "Thanks for calling SmileBright Dental Clinic. "
                "Have a great day!"
            )


            await speak_reply(
                goodbye_message
            )


            if speaking_task is not None:

                try:

                    await speaking_task

                except asyncio.CancelledError:

                    pass


            await end_call(
                "caller said goodbye"
            )

            return


        # ==========================================
        # FAST GREETING
        # ==========================================

        normalized_text = (
            text.lower()
            .strip()
            .strip(".,!?")
        )


        simple_greetings = {
            "hi",
            "hello",
            "hey",
            "hi there",
            "hello there",
            "hey there",
            "good morning",
            "good afternoon",
            "good evening",
        }


        if (
            normalized_text
            in simple_greetings
        ):

            reply = (
                "Hi! I'm Jacqueline. "
                "How can I help you today?"
            )


            print(
                "⚡ Fast greeting response"
            )


            await speak_reply(reply)

            return


        # ==========================================
        # CHOOSE FILLER
        # ==========================================

        filler = choose_filler(
            text,
            last_filler
        )

        last_filler = filler


        print(
            "💬 Filler:",
            filler
        )


        # ==========================================
        # START FILLER IMMEDIATELY
        # ==========================================

        filler_task = await start_filler(
            filler
        )


        # ==========================================
        # START GEMINI IMMEDIATELY
        #
        # Gemini does NOT wait for filler.
        # ==========================================

        print(
            "🧠 Gemini thinking..."
        )


        gemini_task = asyncio.create_task(
            generate_reply(text)
        )


        # ==========================================
        # WAIT FOR GEMINI RESPONSE
        # ==========================================

        try:

            reply = await gemini_task


        except asyncio.CancelledError:

            gemini_task.cancel()

            try:

                await gemini_task

            except Exception:

                pass

            raise


        except Exception as e:

            print(
                "❌ Gemini error:",
                e
            )


            reply = (
                "I'm sorry, I had a little trouble with that. "
                "Could you please say that again?"
            )


        # ==========================================
        # GUARANTEE THE FILLER FINISHES
        #
        # Even if Gemini finished immediately,
        # wait for the filler task before moving on.
        # ==========================================

        try:

            if not filler_task.done():

                await filler_task

        except asyncio.CancelledError:

            raise

        except Exception as e:

            print(
                "⚠️ Filler error:",
                e
            )


        # ==========================================
        # FILLER FINISHED NATURALLY
        #
        # Do NOT send assistant_interrupt here.
        #
        # The browser can continue its queued audio
        # naturally and then play the real answer.
        # ==========================================

        if speaking_task is filler_task:

            speaking_task = None


        assistant_active = False


        print(
            "🤖 JACQUELINE:",
            reply
        )


        print(
            "🔊 Cartesia speaking..."
        )


        await speak_reply(
            reply
        )


    # ==============================================
    # SILENCE MONITOR
    # ==============================================

    async def monitor_silence():

        while call_active:

            await asyncio.sleep(1)


            # Do not end while Gemini is processing.
            if (
                processing_task is not None
                and not processing_task.done()
            ):

                continue


            # Do not end while TTS is active.
            if (
                speaking_task is not None
                and not speaking_task.done()
            ):

                continue


            silence = (
                asyncio.get_running_loop().time()
                - last_user_activity
            )


            if silence >= SILENCE_TIMEOUT:

                print(
                    f"⏰ {SILENCE_TIMEOUT} seconds "
                    "of inactivity"
                )


                await end_call(
                    f"{SILENCE_TIMEOUT} seconds of inactivity"
                )

                break


    # ==============================================
    # CONNECT TO SARVAM
    # ==============================================

    try:

        async with websockets.connect(
            sarvam_url,
            additional_headers=sarvam_headers
        ) as sarvam_ws:


            print(
                "✅ Sarvam connected"
            )


            # ==========================================
            # BROWSER → SARVAM
            # ==========================================

            async def browser_to_sarvam():

                nonlocal last_user_activity


                try:

                    while call_active:

                        message = (
                            await websocket.receive()
                        )


                        if (
                            message.get("type")
                            == "websocket.disconnect"
                        ):

                            print(
                                "🌐 Browser disconnected"
                            )

                            break


                        text_message = (
                            message.get("text")
                        )


                        if not text_message:

                            continue


                        try:

                            data = json.loads(
                                text_message
                            )


                            if (
                                data.get("type")
                                == "audio"
                            ):

                                audio = (
                                    base64.b64decode(
                                        data["data"]
                                    )
                                )


                                await sarvam_ws.send(
                                    audio
                                )


                        except Exception as e:

                            print(
                                "❌ Browser audio error:",
                                e
                            )


                except asyncio.CancelledError:

                    pass


                except Exception as e:

                    print(
                        "❌ Browser receive error:",
                        e
                    )


            # ==========================================
            # SARVAM → AGENT
            #
            # PARTIAL TRANSCRIPTS ARE IGNORED.
            #
            # ONLY transcript.final IS PROCESSED.
            # ==========================================

            async def sarvam_to_agent():

                nonlocal processing_task
                nonlocal last_final_text
                nonlocal last_final_time
                nonlocal last_user_activity


                try:

                    async for message in sarvam_ws:

                        if not call_active:

                            break


                        try:

                            data = json.loads(
                                message
                            )

                        except Exception:

                            continue


                        event = data.get(
                            "event"
                        )


                        # ==================================
                        # IGNORE EVERYTHING EXCEPT FINAL
                        # ==================================

                        if (
                            event
                            != "transcript.final"
                        ):

                            continue


                        # ==================================
                        # FINAL TRANSCRIPT
                        # ==================================

                        final_text = (
                            data.get(
                                "text",
                                ""
                            )
                            .strip()
                        )


                        if not final_text:

                            continue


                        last_user_activity = (
                            asyncio.get_running_loop().time()
                        )


                        # ==================================
                        # DUPLICATE PROTECTION
                        # ==================================

                        normalized_final = (
                            normalize_transcript(
                                final_text
                            )
                        )


                        now = time.monotonic()


                        if (
                            normalized_final
                            == last_final_text
                            and (
                                now
                                - last_final_time
                            )
                            < DUPLICATE_FINAL_WINDOW
                        ):

                            print(
                                "🔁 Duplicate final ignored:",
                                final_text
                            )

                            continue


                        last_final_text = (
                            normalized_final
                        )

                        last_final_time = now


                        # ==================================
                        # CANCEL OLD GEMINI PROCESSING
                        # ==================================

                        await cancel_processing()


                        # ==================================
                        # STOP OLD ASSISTANT AUDIO
                        #
                        # Because partial transcripts are
                        # disabled, interruption happens
                        # after a new FINAL transcript.
                        # ==================================

                        if assistant_active:

                            print(
                                "🛑 New user speech received"
                            )

                            await stop_speaking()


                        # ==================================
                        # PROCESS NEW REQUEST
                        # ==================================

                        processing_task = (
                            asyncio.create_task(
                                process_user_text(
                                    final_text
                                )
                            )
                        )


                except asyncio.CancelledError:

                    pass


                except Exception as e:

                    print(
                        "❌ Sarvam receive error:",
                        e
                    )


            # ==========================================
            # RUN EVERYTHING
            # ==========================================

            await asyncio.gather(

                browser_to_sarvam(),

                sarvam_to_agent(),

                monitor_silence(),

                return_exceptions=True
            )


    except Exception as e:

        print(
            "❌ Browser agent error:",
            e
        )


    finally:

        call_active = False

        stop_event.set()


        if (
            processing_task is not None
            and not processing_task.done()
        ):

            processing_task.cancel()


        if (
            speaking_task is not None
            and not speaking_task.done()
        ):

            speaking_task.cancel()


        print(
            "🌐 Browser agent stopped"
        )