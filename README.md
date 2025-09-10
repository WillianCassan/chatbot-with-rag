# 🤖 Chatbot WhatsApp - Evolution API

Um chatbot inteligente para WhatsApp desenvolvido em Python com FastAPI, integrado à Evolution API para processamento de mensagens de texto e áudio. O sistema utiliza IA para fornecer respostas personalizadas baseadas em contexto e histórico de conversas.

## 📋 Funcionalidades

- **Processamento de Mensagens**: Suporte a mensagens de texto e áudio via WhatsApp
- **Transcrição de Áudio**: Conversão de mensagens de voz em texto usando Whisper [[memory:7331078]]
- **Síntese de Voz**: Geração de respostas em áudio usando OpenAI TTS ou Google Text-to-Speech
- **IA Contextual**: Respostas inteligentes baseadas em contexto e histórico de conversas
- **Gerenciamento de Usuários**: Sistema de autenticação e perfil de usuários
- **Gerenciamento de Arquivos**: Upload e organização de documentos
- **Banco de Dados**: Integração com PostgreSQL e ChromaDB para armazenamento
- **Armazenamento de Arquivos**: Integração com MinIO para gerenciamento de arquivos

## 🏗️ Arquitetura

```
chatbot/
├── main.py                          # Aplicação principal FastAPI
├── evolution_config.py              # Configurações da Evolution API
├── requirements.txt                 # Dependências Python
├── integration_api/                 # Módulos de integração
│   ├── modules/
│   │   ├── llm.py                  # Módulo de IA e processamento
│   │   └── db.py                   # Conexão com banco de dados
│   ├── routes/                     # Endpoints da API
│   │   ├── users.py               # Rotas de usuários
│   │   └── file_manager.py        # Rotas de gerenciamento de arquivos
│   ├── services/                   # Lógica de negócio
│   ├── repository/                 # Camada de acesso a dados
│   └── security/                   # Autenticação e segurança
├── models/                         # Modelos Pydantic
├── utils/                          # Utilitários e configurações
└── media/                          # Arquivos de mídia temporários
```

## 🚀 Instalação

### Pré-requisitos

- Python 3.8+
- PostgreSQL
- ChromaDB
- MinIO (opcional)
- Evolution API configurada

### 1. Clone o repositório

```bash
git clone <url-do-repositorio>
cd chatbot
```

### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

### 3. Configure as variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
# Evolution API
EVOLUTION_API_URL=https://sua-evolution-api.com
EVOLUTION_API_KEY=sua_api_key
EVOLUTION_INSTANCE_ID=sua_instance_id
EVOLUTION_INSTANCE_TOKEN=seu_token
EVOLUTION_WEBHOOK_TOKEN=seu_webhook_token

# OpenAI
OPEN_AI_API_KEY=sua_openai_api_key

# Banco de Dados
DATABASE_URL=postgresql://usuario:senha@localhost:5432/chatbot_db
CHROMADB_HOST=localhost
CHROMADB_PORT=8000
CHROMADB_COLLECTION=chatbot_collection

# MinIO (opcional)
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=chatbot-files

# Google Cloud (opcional - para síntese de voz)
GOOGLE_APPLICATION_CREDENTIALS=caminho/para/service-account.json

# Configurações da Organização
ORG_NAME=PROCON
ORG_SERVICES_FILE=utils/servicos.txt
```

### 4. Execute a aplicação

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 📱 Configuração do WhatsApp

### 1. Configure o webhook na Evolution API

- URL do webhook: `https://seu-dominio.com/webhook`
- Token de verificação: Use o valor de `EVOLUTION_WEBHOOK_TOKEN`

### 2. Teste a conexão

```bash
curl http://localhost:8000/status
```

## 🔧 Uso da API

### Endpoints Principais

#### Status do Sistema
```http
GET /status
```

#### Webhook do WhatsApp
```http
GET /webhook?hub.mode=subscribe&hub.challenge=CHALLENGE&hub.verify_token=TOKEN
POST /webhook
```

#### Gerenciamento de Usuários
```http
POST /users/token
```

#### Gerenciamento de Arquivos
```http
POST /files/upload
GET /files
GET /files/{file_id}
PUT /files/{file_id}/metadata
DELETE /files/{file_id}
```

## 🤖 Funcionalidades do Chatbot

### Processamento de Mensagens

- **Mensagens de Texto**: Processamento direto via LLM
- **Mensagens de Áudio**: Transcrição com Whisper + processamento
- **Respostas Personalizadas**: Baseadas no perfil e histórico do usuário
- **Contexto Inteligente**: Uso de ChromaDB para busca semântica

### Recursos de IA

- **Modelo**: GPT-3.5-turbo
- **Transcrição**: Whisper-1 (português)
- **Síntese de Voz**: OpenAI TTS ou Google Text-to-Speech
- **Memória de Conversa**: Histórico persistente por usuário
- **Perfil de Usuário**: Construção automática de perfil baseado nas interações

## 🛠️ Desenvolvimento

### Estrutura de Dados

#### Usuário
```python
class UserModel(BaseModel):
    cpf: str
    senha: str
    responsavel: str
```

#### Arquivo
```python
class ArquivoEnviado(BaseModel):
    file_id: str
    titulo_documento: str
    subgrupo: str
    grupo: str
    responsavel: str
    descricao: str
    status: str
    data_envio: datetime
```

### Adicionando Novos Serviços

1. Edite o arquivo `utils/servicos.txt`
2. Adicione informações sobre os novos serviços
3. Reinicie a aplicação

### Personalizando Respostas

Modifique o prompt do sistema em `integration_api/modules/llm.py` na função `to_respond()`.

## 📊 Monitoramento

### Logs

O sistema gera logs detalhados para:
- Mensagens recebidas
- Processamento de áudio
- Erros de API
- Status de conexão

### Métricas

- Status da Evolution API
- Conexão com banco de dados
- Processamento de mensagens

## 🔒 Segurança

- Autenticação JWT para endpoints protegidos
- Validação de webhook do WhatsApp
- Sanitização de entrada de dados
- Criptografia de senhas com bcrypt

## 🐛 Solução de Problemas

### Problemas Comuns

1. **Erro de conexão com Evolution API**
   - Verifique as variáveis de ambiente
   - Confirme se a instância está ativa

2. **Falha na transcrição de áudio**
   - Verifique se o arquivo de áudio existe
   - Confirme as credenciais da OpenAI

3. **Erro de banco de dados**
   - Verifique a conexão com PostgreSQL
   - Confirme se o ChromaDB está rodando

### Logs de Debug

```bash
# Ativar logs detalhados
export LOG_LEVEL=DEBUG
uvicorn main:app --reload
```

## 📝 Licença

Este projeto é de uso interno e proprietário.

## 👥 Contribuição

Para contribuir com o projeto:

1. Faça um fork do repositório
2. Crie uma branch para sua feature
3. Faça commit das mudanças
4. Abra um Pull Request

## 📞 Suporte

Para suporte técnico, entre em contato com a equipe de desenvolvimento.

---

**Desenvolvido por Willian** 🚀
