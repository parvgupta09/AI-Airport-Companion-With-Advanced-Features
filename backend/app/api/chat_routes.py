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

from app.database.postgres_session import get_db
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

    await manager.connect(user_id, websocket)
    logger.info(f"Active WebSocket established for User {user_id} (Thread: {thread_id})")

    try:
        while True:
            data = await websocket.receive_json()
            user_message_text = data.get("message", "").strip()

            if not user_message_text:
                continue

            logger.info(f"Recieved message from User {user_id}: '{user_message_text}'")

            inputs = {
                "messages" : [HumanMessage(content=user_message_text)],
                "user_id": str(user_id),
                "thread_id": str(thread_id)
            }

            config = {"configurable": {"thread_id": str(thread_id)}}

            graph_response = await asyncio.to_thread(
                airport_graph.invoke,
                inputs,
                config = config
            )

            messages = graph_response.get("messages", [])
            if messages:
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
            speaker=request.speaker
        )

        if not audio_bytes:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Text-to-Speech generation failed.")

        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={"Content-Disposition":"inline; filename=ai_response.wav"}
        )

    except Exception as e:
        logger.error(f"Error generating TTS audio with Sarvam AI: {str(e)}",exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to synthesize speech")