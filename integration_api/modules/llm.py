from openai import OpenAI
from modules.db import DB
from time import sleep
import chromadb
import random
import os
from rapidfuzz import fuzz
from num2words import num2words
from google.cloud import texttospeech


class LLM:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPEN_AI_API_KEY"))
        self.collection = chromadb.HttpClient(
            host=os.getenv("CHROMADB_HOST"), port=os.getenv("CHROMADB_PORT")
        ).get_or_create_collection(name=os.getenv("CHROMADB_COLLECTION"))
        self.db = DB()
        # Organização alvo
        self.org_name = os.getenv("ORG_NAME", "PROCON")

        # Arquivo de serviços por órgão (permite trocar para PROCON sem alterar código)
        services_file_path = os.getenv("ORG_SERVICES_FILE", os.path.join("utils", "servicos.txt"))
        with open(services_file_path, "r", encoding="utf-8") as file:
            self.services_context = file.read()

    def __to_recognize__(self, number, question, attempt=1):
        client = self.client

        foreknowledge = self.db.get_foreknowledge(number)

        if attempt == 4:
            return foreknowledge
        if attempt > 1:
            sleep(2)

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": """
                        Você é um agente especialista em classificação de dados relevantes sobre pessoas. 
                        Sua missão é, dada uma mensagem, extrair dela ( se for possível e pertinente ), informações relevantes sobre a pessoa.
                        Sua resposta deve apenas o resumo do perfil da pessoa atualizado.
                        O resumo deve sempre ser o mais objetivo possível, pois ele deve ser curto ( não exceder, 300 palavras ).
                        Se não houver dados relevantes, apenas responda com o resumo já construído até o momento.
                        A resposta não deve conter caracteres como aspas ( de nenhum tipo ) ou parêntes.
                    """,
                },
                {
                    "role": "user",
                    "content": f"""
                        A mensagem de interação com a pessoa é: "{question}"
                        Abaixo, está o que se sabe até o momento sobre a pessoa. Agregue mais informações, se houver algo relevante para que possa ser criado um pequeno resumo do perfil dessa pessoa:
                        
                        {foreknowledge}
                    """,
                },
            ],
            model="gpt-3.5-turbo",
        )

        try:
            new_summary = chat_completion.choices[0].message.content
            self.db.update_foreknowledge(number, new_summary)
            return new_summary
        except:
            return self.__to_recognize__(number, question, attempt + 1)

    def __rate_question__(self, questions):
        results = self.collection.query(query_texts=questions, n_results=30)
        return (
            " ".join(results["documents"][0])
            if results["documents"]
            else "Nenhum resultado encontrado."
        )

    def to_transcribe(self, filename):
        client = self.client

        transcription_text = ""
        with open(filename, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(filename, file.read()),
                model="whisper-1",
                language="pt",
            )
            transcription_text = transcription.text
        
        import re
        def replace_procon(match):
            word = match.group(0)
            target = self.org_name
            if fuzz.ratio(word.lower(), target.lower()) > 65 and word.lower() != target.lower():
                print(f"Correção aplicada: '{word}' para '{target}'")
                return target
            return word

        transcription_text = re.sub(r'\b\w+\b', replace_procon, transcription_text)
        print("Transcrição:", transcription_text)
        return transcription_text

    def generate_audio_via_openai(self, number, text):
        client = self.client

        target_file = f"{number}_audio_answer.ogg"
        path_file = os.path.join("media", target_file)
        with client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice="nova",
            input=text,
            response_format="opus",  # onyx; nova; shimmer
        ) as answer:
            answer.stream_to_file(path_file)

    def generate_audio(self, number, text):
        """
        Gera áudio usando a API do Google Text-to-Speech com a voz Zephir
        """
        #### Configurações da voz Zephir
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        # ##Inicializa o cliente do Google Text-to-Speech
        client = texttospeech.TextToSpeechClient()

        # ##Configura o texto para síntese
        synthesis_input = texttospeech.SynthesisInput(
            text=text
        )

        # ##Configura a voz Zephir (pt-BR)
        voice = texttospeech.VoiceSelectionParams(
            language_code="pt-BR",
            name="pt-BR-Chirp3-HD-Zephyr",  # Voz Zephir feminina
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.OGG_OPUS,
            speaking_rate=1  # Velocidade similar à anterior
        )

        # ##Gera a síntese de fala
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        target_file = f"{number}_audio_answer.ogg"
        path_file = os.path.join("media", target_file)

        with open(path_file, "wb") as out:
            out.write(response.audio_content)

        print(f"Áudio gerado com sucesso: {text}")
        return path_file
                
    def to_respond(self, number, question, attempt=1):
        if attempt == 4:
            return "Não consegui compreender bem a sua mensagem... Poderia reformulá-la, por favor?"
        try:

            client = self.client
            services_context = self.services_context

            new_summary = self.__to_recognize__(number, question)

            history_messages = self.db.get_messages(number)

            questions = []
            if history_messages:
                questions = [question, history_messages[1][1]]
            else:
                questions = [question]

            print(questions)
            context = self.__rate_question__(questions)
            # constroi a ordem de mensagens para a memorizacao
            messages = [
                {
                    "role": "system",
                    "content": f"""
                        Você é um assistente virtual da {self.org_name}, desenvolvido pelo willian, treinado exclusivamente para responder dúvidas sobre os serviços públicos oferecidos pela {self.org_name}.

                        Você foi projetado para responder perguntas com base exclusiva no conteúdo dos arquivos do contexto adicional.

                        Esses arquivos contêm informações relevantes que foram processadas e armazenadas com o objetivo de fornecer respostas precisas e baseadas em evidências.

                        As informações disponíveis incluem:
                        - Dados do perfil do usuário com quem você está interagindo, que devem ser usados para personalizar a resposta, quando relevante.
                        - Contexto adicional, que serve de base para construir suas respostas com mais precisão.

                        Restrições obrigatórias:
                        - Use o contexto adicional como base principal para suas respostas.
                        - Se a informação exata não estiver presente, construa uma resposta informativa baseada no que está disponível no contexto.
                        - Analise o contexto para extrair informações relevantes e responda de forma útil.
                        - Se o usuário fizer perguntas completamente fora do escopo do contexto — como piadas, política, receitas, hobbies — responda educadamente que você é especializado em assuntos da {self.org_name}.
                        - Sempre que possível, forneça informações específicas extraídas do contexto.

                        Responda de forma cordial, mas firme, com uma frase como:
                        "Olá, eu sou um assistente virtual da {self.org_name} e fui desenvolvido apenas para ajudar com dúvidas sobre os serviços da {self.org_name}."

                        Estilo de resposta:
                        - Sempre que for dito um número de telefone, coloque essas tags ao redor do número: <speak><say-as interpret-as='telephone'>8530042840</say-as></speak>
                        - Seja sempre objetivo, acolhedor e respeitoso. **Vá direto ao ponto.**
                        - **Suas respostas devem ser concisas, focando apenas na informação mais importante para o usuário.**
                        - Sempre que possível, utilize o nome ou outros dados relevantes do perfil do usuário, se tiverem sido fornecidos.
                        - Suas respostas devem ser fáceis de entender por pessoas com baixa escolaridade.
                        - Formate suas respostas de forma apropriada para o WhatsApp, com parágrafos curtos e linguagem clara. No máximo 300 caracteres.
                        - **Se uma resposta exigir vários passos ou detalhes, use uma lista simples com marcadores (•) em vez de um parágrafo longo.**
                        - Caso a informação esteja disponível, responda com base no trecho mais relevante e, se possível, mencione a fonte ou nome do arquivo de onde a informação foi extraída.

                        ##### Início do Perfil do usuário #####
                        {new_summary}
                        ##### Fim do perfil do usuário #####

                        ##### Início de informações sobre os serviços oferecidos pela {self.org_name} #####
                        {services_context}
                        ##### Fim de informações sobre os serviços oferecidos pela {self.org_name} #####

                        ##### Início de contexto adicional #####
                        {context}
                        ##### Fim de contexto adicional #####
                    """,
                }
            ]
            for role, message in history_messages[::-1]:
                messages += [{"role": role, "content": message}]
            messages += [{"role": "user", "content": question}]

            chat_completion = client.chat.completions.create(
                messages=messages,
                model="gpt-3.5-turbo",
            )

            reply_message = chat_completion.choices[0].message.content
        except Exception as e:
            print(e)
            return self.to_respond(number, question, attempt=attempt + 1)
        
        self.db.insert_message(number, "user", question)
        # Truncate the reply to a maximum of 300 characters as instructed in the system prompt
        truncated_reply = reply_message[:300]
        self.db.insert_message(number, "assistant", truncated_reply)

        return truncated_reply
