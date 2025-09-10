from dotenv import load_dotenv
load_dotenv()
from integration_api.routes import file_manager, users
from fastapi import FastAPI, Request, Query, BackgroundTasks
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import requests
import json
import re
import os
import base64

from modules.llm_chatgpt import LLM

org_name = os.getenv("ORG_NAME", "PROCON")
app = FastAPI(title=f"Chatbot {org_name} - Evolution API", version="1.0.0")
llm = LLM()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)

app.include_router(file_manager.router)
app.include_router(users.router)


def _log_event(message: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{now} - {message}")

def correct_audio_transcription(text):
    substitutions = {

    "ascom": org_name,
    "poscon": org_name,
    "proton": org_name,
    "cupom": org_name,
    "compom": org_name
}

    for wrong, right in substitutions.items():
        text = re.sub(re.escape(wrong), right, text, flags=re.IGNORECASE)

    return text


def get_transcription(output_file_path):
    return llm.to_transcribe(output_file_path)

def mp3_to_base64(file_path):
    with open(file_path, "rb") as audio_file:
        encoded_string = base64.b64encode(audio_file.read()).decode('utf-8')
    return encoded_string

def send_audio_to_whatsapp(recipient_phone_number):
    evolution_url = os.getenv("EVOLUTION_API_URL")
    evolution_key = os.getenv("EVOLUTION_API_KEY")
    instance_name = os.getenv("EVOLUTION_INSTANCE_ID")

    if not all([evolution_url, evolution_key, instance_name]):
        _log_event("Variáveis de ambiente Evolution API ausentes ou inválidas.")
        return {"status": 500, "message": "Erro interno de configuração"}
    
    llm_response = llm.to_respond(recipient_phone_number, correct_audio_transcription(get_transcription(f"media/{recipient_phone_number}_audio_message.ogg")))

    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        audio_path = llm.generate_audio(recipient_phone_number, llm_response)
        _log_event("Usando síntese de voz local (gTTS)")
    else:
        audio_path = llm.generate_audio_via_openai(recipient_phone_number, llm_response) 
        _log_event("Usando síntese de voz via OpenAI")

    audio = mp3_to_base64(audio_path)

    final_api_url = f"{evolution_url}/message/sendWhatsAppAudio/{instance_name}"
    payload = {
        "number": recipient_phone_number,
        "audio": audio,
        "encoding": False,  # Exemplo de arquivo de áudio
    }

    headers = {
        "Content-Type": "application/json",
        "apikey": evolution_key
    }

    try:
        response = requests.post(final_api_url, headers=headers, json=payload)

        if response.status_code == 201:
            _log_event(f"Mensagem de audio enviada para: {recipient_phone_number}")
            return {"status": 201, "message": "success"}
        else:
            _log_event(
                f"Erro ao enviar mensagem de audio: {response.status_code} {response.text}"
            )
            return {"status": response.status_code, "message": response.text}
    except Exception as e:
        _log_event(f"Erro ao enviar mensagem de audio via Evolution API: {str(e)}")
        return {"status": 500, "message": "Erro ao enviar mensagem"}

def send_response_to_whatsapp(recipient_phone_number, text_message_content):
    """Envia mensagem de texto via Evolution API"""
    evolution_url = os.getenv("EVOLUTION_API_URL")
    evolution_key = os.getenv("EVOLUTION_API_KEY")
    instance_name = os.getenv("EVOLUTION_INSTANCE_ID")

    if not all([evolution_url, evolution_key, instance_name]):
        _log_event("Variáveis de ambiente Evolution API ausentes ou inválidas.")
        return {"status": 500, "message": "Erro interno de configuração"}

    final_api_url = f"{evolution_url}/message/sendText/{instance_name}"

    payload = {
        "number": recipient_phone_number,
        "text": text_message_content
    }

    headers = {
        "Content-Type": "application/json",
        "apikey": evolution_key
    }

    try:
        response = requests.post(final_api_url, headers=headers, json=payload)

        if response.status_code == 201:
            _log_event(f"Mensagem de texto enviada para: {recipient_phone_number}")
            return {"status": 201, "message": "success"}
        else:
            _log_event(
                f"Erro ao enviar mensagem de texto: {response.status_code} {response.text}"
            )
            return {"status": response.status_code, "message": response.text}
    except Exception as e:
        _log_event(f"Erro ao enviar mensagem de texto via Evolution API: {str(e)}")
        return {"status": 500, "message": "Erro ao enviar mensagem"}


def get_final_response(number, question):
    """Processa pergunta e retorna resposta via LLM"""
    question_sanitized = re.sub(r"(--|\||;|--|#|/\*|\*/|')", "", question)
    return llm.to_respond(number, question_sanitized, 1)


def send_typing_indicator(number_sender, message_type):
    """Envia indicador de digitando..."""
    evolution_url = os.getenv("EVOLUTION_API_URL")
    evolution_key = os.getenv("EVOLUTION_API_KEY")
    instance_name = os.getenv("EVOLUTION_INSTANCE_ID")

    if not all([evolution_url, evolution_key, instance_name]):
        _log_event("Variáveis de ambiente Evolution API ausentes ou inválidas.")
        return {"status": 500, "message": "Erro interno de configuração"}

    url = f"{evolution_url}/chat/sendPresence/{instance_name}"

    if message_type == "text":
        delay = 5000
        presence = "composing"
    elif message_type == "audio":
        delay = 1000
        presence = "recording"

    payload = {
        "number": number_sender,
        "delay": delay,
        "presence": presence
    }

    headers = {
        "Content-Type": "application/json",
        "apikey": evolution_key
    }

    try:
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code != 201:
            _log_event(
                f"Erro ao enviar indicador de presença: {response.status_code} - {response.text}"
            )
        else:
            _log_event("Indicador de 'digitando...' enviado com sucesso")
    except Exception as e:
        _log_event(f"Erro na requisição ao enviar indicador de presença: {str(e)}")


def mark_message_as_read(number_sender):
    """Marca mensagem como lida"""
    evolution_url = os.getenv("EVOLUTION_API_URL")
    evolution_key = os.getenv("EVOLUTION_API_KEY")
    instance_name = os.getenv("EVOLUTION_INSTANCE_ID")

    if not all([evolution_url, evolution_key, instance_name]):
        _log_event("Variáveis de ambiente Evolution API ausentes ou inválidas.")
        return {"status": 500, "message": "Erro interno de configuração"}

    url = f"{evolution_url}/chat/sendPresence/{instance_name}"

    payload = {
        "number": number_sender,
        "presence": "available",
        "delay": 1000
    }

    headers = {
        "Content-Type": "application/json",
        "apikey": evolution_key
    }

    try:
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code != 201:
            _log_event(
                f"Erro ao enviar presença: {response.status_code} - {response.text}"
            )
        else:
            _log_event(f"Presença enviada para {number_sender}")
    except Exception as e:
        _log_event(f"Erro ao enviar presença: {str(e)}")


def flow_audio(number_sender):
    """Processa mensagem de audio e envia resposta"""
    try:
        # Marca mensagem como lida
        mark_message_as_read(number_sender)
        
        # Envia indicador de "digitando..."
        send_typing_indicator(number_sender, "audio")
        
        # Processa resposta
        # answer = get_final_response(number_sender, message)
        
        # Envia resposta
        send_audio_to_whatsapp(number_sender)

        return {"status": "success"}
    except Exception as e:
        _log_event(f"Erro ao processar mensagem de audio: {e}")
        return {"status": "error", "message": str(e)}


def flow_conversation(number_sender, message):
    """Processa mensagem de texto e envia resposta"""
    try:
        # Marca mensagem como lida
        mark_message_as_read(number_sender)
        
        # Envia indicador de "digitando..."
        send_typing_indicator(number_sender, "text")
        
        # Processa resposta
        answer = get_final_response(number_sender, message)
        
        # Envia resposta
        send_response_to_whatsapp(number_sender, answer)

        return {"status": "success"}
    except Exception as e:
        _log_event(f"Erro ao processar mensagem de texto: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/")
def read_root():
    return {"message": f"Chatbot {org_name} - Evolution API (Texto)", "status": "running"}


@app.get("/status")
def check_evolution_status():
    """Verifica o status da instância da Evolution API"""
    evolution_url = os.getenv("EVOLUTION_API_URL")
    evolution_key = os.getenv("EVOLUTION_API_KEY")
    instance_name = os.getenv("EVOLUTION_INSTANCE_ID")

    if not all([evolution_url, evolution_key, instance_name]):
        return {"status": "error", "message": "Variáveis de ambiente não configuradas"}

    try:
        url = f"{evolution_url}/instance/connectionState/{instance_name}"
        headers = {"apikey": evolution_key}
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return {
                "status": "success",
                "evolution_api": "connected",
                "instance": instance_name,
                "details": response.json()
            }
        else:
            return {
                "status": "error",
                "evolution_api": "connection_failed",
                "instance": instance_name,
                "error": response.text
            }
    except Exception as e:
        return {
            "status": "error",
            "evolution_api": "unreachable",
            "instance": instance_name,
            "error": str(e)
        }


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """Verifica webhook do WhatsApp"""
    verify_token = os.getenv("EVOLUTION_WEBHOOK_TOKEN")

    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        _log_event("Webhook verificado com sucesso")
        return Response(content=hub_challenge, media_type="text/plain")
    
    _log_event("Falha na verificação do webhook")
    return Response(status_code=400)


@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """Recebe e processa mensagens do WhatsApp (apenas texto)"""
    try:
        body = await request.body()
        json_body = json.loads(body)
        
        _log_event(f"Webhook recebido: {json_body}")
        
        # Evolution API webhook structure
        if "instance" in json_body:
            instance = json_body["instance"]
            event_type = json_body.get("event", "")
            data = json_body.get("data", [])
            
            _log_event(f"Processando webhook para instância: {instance}")
            _log_event(f"Tipo de evento: {event_type}")
            
            # Verifica se é um evento de mensagem
            if event_type == "messages.upsert":
                _log_event("Evento de mensagem detectado!")
                
                # Processa lista de mensagens
                if isinstance(data, list) and len(data) > 0:
                    _log_event(f"Processando lista com {len(data)} itens")
                    
                    for i, item in enumerate(data):
                        _log_event(f"Processando item {i}: {item}")
                        
                        if isinstance(item, dict) and "message" in item and "key" in item:
                            message_data = item.get("message", {})
                            key_data = item.get("key", {})
                            
                            # Extrai informações da mensagem
                            number_sender = key_data.get("remoteJid", "").replace("@s.whatsapp.net", "")

                            message_id = key_data.get("id", "")
                            
                            _log_event(f"Remetente: {number_sender}, Message ID: {message_id}")
                            
                            # Determina o tipo de mensagem
                            if "conversation" in message_data:
                                message = message_data["conversation"]
                                _log_event(f"Mensagem de conversa recebida: '{message}'")
                                
                                # Processa a mensagem de conversa
                                background_tasks.add_task(
                                    flow_conversation, number_sender, message
                                )
                                
                            elif "textMessage" in message_data:
                                message = message_data["textMessage"]["text"]
                                _log_event(f"Mensagem de texto recebida: '{message}'")
                                
                                # Processa a mensagem de texto
                                background_tasks.add_task(
                                    flow_conversation, number_sender, message
                                )
                                
                            elif "imageMessage" in message_data:
                                _log_event(f"Mensagem de imagem recebida de {number_sender}")
                                send_response_to_whatsapp(
                                    number_sender, 
                                    "Desculpe, no momento só consigo responder mensagens de texto."
                                )
                                
                            elif "documentMessage" in message_data:
                                _log_event(f"Mensagem de documento recebida de {number_sender}")
                                send_response_to_whatsapp(
                                    number_sender, 
                                    "Desculpe, no momento só consigo responder mensagens de texto."
                                )
                                
                            elif "videoMessage" in message_data:
                                _log_event(f"Mensagem de vídeo recebida de {number_sender}")
                                send_response_to_whatsapp(
                                    number_sender, 
                                    "Desculpe, no momento só consigo responder mensagens de texto."
                                )
                                
                            elif "audioMessage" in message_data:
                                _log_event(f"Mensagem de áudio recebida de {number_sender}")
                                send_response_to_whatsapp(
                                    number_sender, 
                                    "Desculpe, no momento só consigo responder mensagens de texto."
                                )
                                
                            else:
                                _log_event(f"Tipo de mensagem desconhecido de {number_sender}")
                                
                elif isinstance(data, dict):
                    _log_event("Processando data como dicionário (formato antigo)")
                    
                    # Verificar se é uma mensagem válida
                    if "message" in data and "key" in data:
                        message_data = data.get("message", {})
                        key_data = data.get("key", {})
                        
                        # Extrai informações da mensagem
                        number_sender = key_data.get("remoteJid", "").replace("@s.whatsapp.net", "")
                        message_id = key_data.get("id", "")
                        
                        _log_event(f"Remetente: {number_sender}, Message ID: {message_id}")
                        
                        # Determina o tipo de mensagem
                        if "conversation" in message_data:
                            message = message_data["conversation"]
                            _log_event(f"Mensagem de conversa recebida: '{message}'")
                            
                            # Processa a mensagem de conversa
                            background_tasks.add_task(
                                flow_conversation, number_sender, message
                            )
                            
                        elif "textMessage" in message_data:
                            message = message_data["textMessage"]["text"]
                            _log_event(f"Mensagem de texto recebida: '{message}'")
                            
                            # Processa a mensagem de texto
                            background_tasks.add_task(
                                flow_conversation, number_sender, message
                            )
                        
                        elif "audioMessage" in message_data:
                            base64_audio = message_data["base64"]
                            audio_bytes = base64.b64decode(base64_audio)
                            output_file_path = f"media/{number_sender}_audio_message.ogg"
                            with open(output_file_path, "wb") as audio_file:
                                audio_file.write(audio_bytes)
                            _log_event(f"Mensagem de áudio recebida de {number_sender}")
                            # Processa a mensagem de áudio
                            background_tasks.add_task(
                                flow_audio, number_sender
                            )

                        else:
                            _log_event(f"Tipo de mensagem não suportado de {number_sender}")
                    else:
                        _log_event(f"Data não contém mensagem válida: {data}")
                else:
                    _log_event(f"Data não é lista nem dicionário: {type(data)}")
            else:
                _log_event(f"Evento não é de mensagem: {event_type}")
        else:
            _log_event("Webhook não contém campo 'instance'")

        return JSONResponse(content={"status": "ok"}, status_code=200)

    except Exception as e:
        _log_event(f"Erro ao processar webhook: {e}")
        import traceback
        _log_event(f"Traceback completo: {traceback.format_exc()}")
        return JSONResponse(
            content={"detail": "Erro interno no servidor"}, status_code=500
        )