import logging
from datetime import datetime, timezone
import asyncio
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    WebSocket,
    WebSocketDisconnect,
    status
)
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage

from app.database.postgres_session import get_db, SessionLocal
from app.database.postgres_models import Flight
from app.core.security import verify_token
from app.core.websocket_manager import manager
from app.graph.graph import airport_graph
from app.services.stt_service import stt_service
from app.services.tts_service import tts_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix = "/api/chat", tags=["Chat & Websocket"])


class ChatMessageRequest(BaseModel):
    message: str = Field(..., description="Passengers's text query to the AI companion")

class ChatMessageResponse(BaseModel):
    sender: str = Field(default="assistant", description="'user' or 'assistant'")
    content: str = Field(..., description="AI response text")
    timestamp: str = Field(..., description="ISO timestamp of the response")

class VoiceTranscriptionResponse(BaseModel):
    success: bool
    text: str = Field(..., description="Transcribed text from Sarvam STT")
    error: str | None = None

class TTSRequest(BaseModel):
    text: str = Field(..., description="AI response text to convert to speech")
    speaker: str = Field(default="shubh", description="Sarvam speaker voice name")
    language_code: str = Field(default = "en-IN", description="Sarvam target language code (e.g., 'hi-IN', 'ta-IN')")

class HeadlessChatRequest(BaseModel):
    token: str = Field(..., description="Your active session token")
    message: str = Field(..., description="The STT text to send to the the AI")



@router.websocket("/ws")
async def websocket_chat_endpoint(websocket: WebSocket, token: str):
    """
    Establishes a pesistent WebSocket connection for interactive AI chat, and background push notifications (flight delays, gate changes, reminder)
    """

    auth_result = verify_token(token, expected_type="session")
    if not auth_result["valid"]:
        logger.warning(f"WebSocket connection rejected: {auth_result['error']}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    payload = auth_result["payload"]
    user_id = payload.get("sub")
    flight_id = payload.get("flight_id")
    thread_id = payload.get("thread_id")

    if not user_id or not flight_id or not thread_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    db: Session = SessionLocal()
    try:
        flight = db.query(Flight).filter(Flight.id==flight_id).first()
        if not flight:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        flight_state = {
            "user_name": flight.user.name if flight.user else "Passenger",
            "pnr": flight.pnr,
            "flight_number": flight.flight_number,
            "source": flight.source,
            "destination": flight.destination,
            "terminal": flight.terminal.value if flight.terminal else "Unknown",
            "gate": flight.gate.value if flight.gate else "Unknown",
            "is_layover": flight.has_layover,
            "layover_airport": flight.layover_airport or "None"
        }
    finally:
        db.close()

    await manager.connect(user_id, websocket)
    logger.info(f"Active WebSocket established for User {user_id} (Thread: {thread_id})")

    try:
        while True:
            try:
                data = await websocket.receive_json()
                user_message_text = data.get("message", "").strip()
    
                if not user_message_text:
                    continue
    
                logger.info(f"Recieved message from User {user_id}: '{user_message_text}'")
    
                inputs = {
                    "messages" : [HumanMessage(content=user_message_text)],
                    "user_id": str(user_id),
                    "thread_id": str(thread_id),
                    **flight_state
                }
    
                config = {
                    "configurable": {
                        "thread_id": str(thread_id),
                        "user_id":str(user_id)
                    }
                }
    
                graph_response = await airport_graph.ainvoke(inputs, config=config)
    
                messages = graph_response.get("messages", [])



                print("\n--- GRAPH FINISHED. MESSAGE HISTORY: ---")
                for m in messages:
                    print(f"Type: {m.type} | Content: {m.content}")
                print("----------------------------------------\n")




                if messages:
                    raw_content = messages[-1].content
    
                    if isinstance(raw_content, list):
                        ai_reply = " ".join([part.get("text","") for part in raw_content if "text" in part])
                    else:
                        ai_reply = messages[-1].content
                else:
                    ai_reply = "I apologize, but i am unable to process your request right now."
    
                response_payload = {
                    "type": "chat_response",
                    "sender": "assistant",
                    "message": ai_reply,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
    
                await websocket.send_json(response_payload)

            except Exception as e:
                logger.error(f"Internal graph error processing message: {str(e)}", exc_info=True)
                await websocket.send_json({
                    "type":"chat_response",
                    "sender" : "assistant",
                    "message": "I encountered an internal system error, please try asking again.",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for User {user_id}")
        manager.disconnect(user_id)

    except Exception as e:
        logger.info(f"Error in WebSocket session for User {user_id}: {str(e)}", exc_info=True)


@router.post("/voice-input", response_model = VoiceTranscriptionResponse)
async def transcribe_voice_input(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Accepts recorded audio blob from MicButon.tsx, passes it through Sarvam STT (Saaras model for Indian accents and code mixed Hinglish), and returns the transcribed string to insert into the chat UI
    """

    if not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file type. Please upload a valid audio recording.")

    try:
        audio_bytes = await file.read()

        transcribed_text = await asyncio.to_thread(
            stt_service.transcribe_audio,
            audio_bytes,
            filename=file.filename or "recording.wav"
        )

        if not transcribed_text:
            return VoiceTranscriptionResponse(
                success = True,
                text = "",
                error = "Could not clearly transcribe the audio recording. Please try speaking again."
            )

        logger.info(f"Sarvam AI voice transcribed successfully: ''{transcribed_text}")

        return VoiceTranscriptionResponse(
            success = True,
            text = transcribed_text,
            error = None
        )

    except Exception as e:
        logger.info(f"Error transcribing voice input with Sarvam AI: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process recording.")

@router.post("/tts", summary="Convert AI text response to audio using Sarvam AI Bulbul")
async def generate_speech_response(request: TTSRequest):
    """
    Accepts text generated by the Langgraph AI Assistant and streams back WAV audio bytes for immediate palyback in the react frontend.
    """

    try:
        audio_bytes = await asyncio.to_thread(
            tts_service.text_to_speech,
            text=request.text,
            speaker=request.speaker,
            language_code = request.language_code
        )

        if not audio_bytes:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Text-to-Speech generation failed.")

        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={"Content-Disposition":"attachment; filename=ai_response.wav"}
        )

    except Exception as e:
        logger.error(f"Error generating TTS audio with Sarvam AI: {str(e)}",exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to synthesize speech")


@router.post("/message", response_model=ChatMessageResponse, summary="Headless AI Generation")
async def generate_ai_message(request: HeadlessChatRequest):
    """
    
    """

    auth_result = verify_token(request.token, expected_type="session")
    if not auth_result["valid"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")

    payload = auth_result["payload"]
    user_id = payload.get("sub")
    flight_id = payload.get("flight_id")
    thread_id = payload.get("thread_id")

    db: Session = SessionLocal()
    try:
        flight = db.query(Flight).filter(Flight.id == flight_id).first()
        if not flight:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flight not found")

        flight_state = {
            "user_name": flight.user.name if flight.user else "Passenger",
            "pnr" : flight.pnr,
            "flight_number": flight.flight_number,
            "source": flight.source,
            "destination": flight.destination,
            "terminal": flight.terminal.value if flight.terminal else "Unknown",
            "gate": flight.gate.value if flight.gate else "Unknown",
            "is_layover": flight.has_layover,
            "layover_airport": flight.layover_airport or "None"
        }

    finally:
        db.close()

    inputs = {
        "messages": [HumanMessage(content=request.message)],
        "user_id": str(user_id),
        "thread_id": str(thread_id),
        **flight_state
    }

    config = {"configurable": {"thread_id" : str(thread_id), "user_id": str(user_id)}}

    try:
        graph_response = await airport_graph.ainvoke(inputs, config=config)
        messages = graph_response.get("messages", [])

        if messages and messages[-1].type=="ai":
            raw_content = messages[-1].content
            ai_reply = " ".join([part.get("text", "") for part in raw_content if "text" in part]) if isinstance(raw_content, list) else str(raw_content)
        else:
            ai_reply = "I apologize, but I am unable to process your request right now."

        return ChatMessageResponse(
            sender="assistant",
            content=ai_reply,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    except Exception as e:
        logger.info(f"Headless graph error : {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI processing failed")