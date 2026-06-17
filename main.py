import os
import json
import base64
import tempfile
import wave
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from twilio.twiml.voice_response import VoiceResponse, Connect
from twilio.rest import Client
from dotenv import load_dotenv
from groq import Groq
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings
load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
NGROK_URL = "voice-agent-production-5579.up.railway.app"

app = FastAPI()
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY)
eleven_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

AGENTS = {
    "Priya": {"voice_id": "dJW5YPPk3GSnMzHpNSVz", "persona": "You are Priya, a friendly female customer care agent. Be helpful and concise."},
    "Rahul": {"voice_id": "o1cfDx1LMQIpeY2lK3dT", "persona": "You are Rahul, a professional male customer care agent. Be helpful and concise."},
}

conversation_history = {}



def load_previous_transcript(phone: str) -> list:
    try:
        with open(f"history_{phone}.json", "r") as f:
            return json.load(f)
    except:
        return []
    

def save_transcript(call_sid: str, phone: str = None):
    if call_sid in conversation_history:
        # Call SID ke saath save karo
        with open(f"transcript_{call_sid}.json", "w") as f:
            json.dump(conversation_history[call_sid], f, indent=2)
        # Phone number ke saath bhi save karo (next call ke liye)
        if phone:
            with open(f"history_{phone}.json", "w") as f:
                json.dump(conversation_history[call_sid], f, indent=2)
        print(f"✅ Transcript saved!")

def speech_to_text(audio_data: bytes) -> str:
    try:
        import audioop
        pcm_data = audioop.ulaw2lin(audio_data, 2)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            with wave.open(f.name, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(8000)
                wav_file.writeframes(pcm_data)
            with open(f.name, "rb") as audio_file:
                transcription = groq_client.audio.transcriptions.create(
                    file=("audio.wav", audio_file, "audio/wav"),
                    model="whisper-large-v3",
                )
        return transcription.text
    except Exception as e:
        print(f"STT Error: {e}")
        return ""

def get_ai_response(call_sid: str, user_text: str, agent_name: str, previous_history: list = []) -> str:
    agent_config = AGENTS[agent_name]

    if call_sid not in conversation_history:
        conversation_history[call_sid] = []

    system_prompt = agent_config["persona"]

    # Previous call history context add karo
    if previous_history:
        prev_summary = "\n".join([f"{m['role']}: {m['content']}" for m in previous_history[-6:]])
        system_prompt += f"\n\nPrevious call history with this customer:\n{prev_summary}"

    conversation_history[call_sid].append({"role": "user", "content": user_text})
    

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            *conversation_history[call_sid]
        ],
        max_tokens=150
    )

    ai_text = response.choices[0].message.content
    conversation_history[call_sid].append({"role": "assistant", "content": ai_text})
    return ai_text

def text_to_speech(text: str, voice_id: str) -> bytes:
    audio_generator = eleven_client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_turbo_v2_5",
        output_format="ulaw_8000",
        voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.75)
    )
    return b"".join(audio_generator)

@app.get("/test-ws")
async def test_ws():
    return {"status":"websocket route file is loaded"}





@app.get("/")
async def root():
    return {"status": "Voice Agent Running!"}

@app.post("/make-call")
async def make_call(request: Request):
    data = await request.json()
    customer_phone = data.get("phone")

    agent_name = data.get("agent", "Priya")

    call = twilio_client.calls.create(
        to=customer_phone,
        from_=TWILIO_PHONE_NUMBER,
        url=f"https://{NGROK_URL}/voice-connect?agent={agent_name}&phone={customer_phone}"
        
        
    )
    return {"call_sid": call.sid, "agent": agent_name, "status": "calling"}

@app.api_route("/voice-connect", methods=["GET", "POST"])
async def voice_connect(request: Request):
    agent_name = request.query_params.get("agent" , "Priya")
    phone = request.query_paramas.get("phone" , "")
    response = VoiceResponse()
    response.say("Hello , this is the test")
    connect = Connect()
    connect.stream(url=f"wss://voice-agent-production-5579.up.railway.app/media-stream?agent={agent_name}&phone={phone}")
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")
@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    await websocket.accept()
    agent_name = websocket.query_params.get("agent", "Priya")
    phone = websocket.query_params.get("phone", "")
    agent_config = AGENTS[agent_name]
    call_sid = None
    stream_sid = None
    audio_buffer = bytearray()
    # Previous history load karo
    previous_history = load_previous_transcript(phone)
    if previous_history:
        print(f"📖 Previous history loaded for {phone}")

    print(f"📞 Call connected - Agent: {agent_name}")

    try:
        async for message in websocket.iter_text():
            data = json.loads(message)

            if data["event"] == "start":
                call_sid = data["start"]["callSid"]
                stream_sid = data["start"]["streamSid"]
                print(f"📞 Call SID: {call_sid}")


                greeting = text_to_speech(f"Hello! I am {agent_name}, your customer care agent. How can I help you today?", agent_config["voice_id"])
                greeting_b64 = base64.b64encode(greeting).decodee()
                await websocket.send_text(json.dumps({
                    "event": "media",
        "streamSid": stream_sid,
        "media": {"payload": greeting_b64}
                }))
                print(f"✅ Greeting sent!")

            elif data["event"] == "media" and stream_sid:
                chunk = base64.b64decode(data["media"]["payload"])
                audio_buffer.extend(chunk)

                if len(audio_buffer) > 16000:
                    audio_data = bytes(audio_buffer),
                    audio_buffer.clear()

                    try:
                        user_text = speech_to_text(audio_data)
                        if user_text.strip():
                            print(f"👤 Customer: {user_text}")

                            ai_response = get_ai_response(call_sid, user_text, agent_name, previous_history)
                            print(f"🤖 {agent_name}: {ai_response}")

                            audio_response = text_to_speech(ai_response, agent_config["voice_id"])
                            audio_b64 = base64.b64encode(audio_response).decode()

                            await websocket.send_text(json.dumps({
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {"payload": audio_b64}
                            }))
                            print(f"✅ Audio sent!")
                    except Exception as e:
                        print(f"❌ Error: {e}")

            elif data["event"] == "stop":
                print("📞 Call ended")
                if call_sid:
                    save_transcript(call_sid, phone)
                break

    except Exception as e:
        print(f"❌ WebSocket error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), ws="auto")
