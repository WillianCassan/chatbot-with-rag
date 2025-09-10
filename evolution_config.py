import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

class EvolutionConfig:
    """Configurações para Evolution API"""
    
    # URLs e endpoints
    BASE_URL = os.getenv("EVOLUTION_API_URL")
    API_KEY = os.getenv("EVOLUTION_API_KEY")
    INSTANCE_ID = os.getenv("EVOLUTION_INSTANCE_ID")
    INSTANCE_TOKEN = os.getenv("EVOLUTION_INSTANCE_TOKEN")

    
    # Endpoints
    SEND_TEXT_ENDPOINT = f"{BASE_URL}message/sendText/{INSTANCE_ID}"
    PRESENCE_ENDPOINT = f"{BASE_URL}chat/sendPresence/{INSTANCE_ID}"
    CONNECTION_STATUS_ENDPOINT = f"{BASE_URL}instance/connectionState/{INSTANCE_ID}"
    
    @classmethod
    def is_configured(cls):
        """Verifica se todas as variáveis necessárias estão configuradas"""
        required_vars = [
            cls.API_KEY,
            cls.INSTANCE_ID,
            cls.INSTANCE_TOKEN,
        ]
        return all(required_vars)
    
    @classmethod
    def get_headers(cls):
        """Retorna headers padrão para requisições"""
        return {
            "Content-Type": "application/json",
            "apikey": cls.API_KEY
        }
    
    @classmethod
    def validate_config(cls):
        """Valida a configuração e retorna erros se houver"""
        errors = []
        
        if not cls.API_KEY:
            errors.append("EVOLUTION_API_KEY não configurada")
        if not cls.INSTANCE_ID:
            errors.append("EVOLUTION_INSTANCE_ID não configurada")
        if not cls.INSTANCE_TOKEN:
            errors.append("EVOLUTION_INSTANCE_TOKEN não configurada")
        if not cls.BASE_URL:
            errors.append("EVOLUTION_API_URL não configurada")
            
        return errors

def print_evolution_status():
    """Imprime status da configuração do Evolution API"""
    print("🔧 Configuração Evolution API (Apenas Texto):")
    print(f"   Base URL: {EvolutionConfig.BASE_URL}")
    print(f"   Instance ID: {EvolutionConfig.INSTANCE_ID}")
    print(f"   API Key: {'✅ Configurada' if EvolutionConfig.API_KEY else '❌ Não configurada'}")
    print(f"   Instance Token: {'✅ Configurado' if EvolutionConfig.INSTANCE_TOKEN else '❌ Não configurado'}")
    
    errors = EvolutionConfig.validate_config()
    if errors:
        print("\n❌ Erros de configuração:")
        for error in errors:
            print(f"   - {error}")
    else:
        print("\n✅ Configuração válida!")
        print("📱 Sistema configurado para processar apenas mensagens de texto")

if __name__ == "__main__":
    print_evolution_status()