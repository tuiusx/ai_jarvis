# 🧠 AI Jarvis – Assistente de IA Inteligente

AI Jarvis é um projeto de **assistente de Inteligência Artificial inteligente**, com foco em:

- **LLM Integrado**: Usa OpenAI GPT para análise inteligente de comandos
- **Interface Multimodal**: Reconhecimento de voz + texto com wake word "jarvis"
- **Memória Persistente**: Memória curta e longa prazo com salvamento em arquivo
- **Ferramentas Avançadas**: Detecção de pessoas, gravação de vídeo
- **Interface Rica**: Interface de texto colorida com comandos interativos

## 🚀 Funcionalidades

### 🤖 Agente Inteligente
- Análise de intenção com LLM (OpenAI GPT)
- Planejamento automático de ações
- Memória contextual inteligente
- Execução de ferramentas integrada

### 🎤 Interface Multimodal
- Reconhecimento de voz em português brasileiro
- Wake word "jarvis" para ativação
- Síntese de voz com pyttsx3
- Timeout configurável para comandos

### 🧠 Sistema de Memória
- **Memória Curta**: Últimas 10 interações
- **Memória Longa**: Salvamento persistente em JSON
- Busca contextual inteligente

### 🛠️ Ferramentas Disponíveis
- `detect_people`: Detecção de pessoas via câmera
- `start_recording`: Gravação automática de vídeo
- Sistema extensível para novas ferramentas

### 💻 Interface de Texto
- Interface colorida e intuitiva
- Comandos especiais: `ajuda`, `limpar`, `memoria`, `sair`
- Formatação rica com cores

## 🛠️ Tecnologias

- **Python 3.11+**
- **OpenAI GPT** (análise inteligente)
- **OpenCV** (visão computacional)
- **SpeechRecognition** (reconhecimento de voz)
- **PyYAML** (configurações)
- **Colorama** (interface colorida)

## 📋 Instalação e Configuração

### 1. Instalar Dependências
```bash
pip install -r requirements.txt
```

### 2. Configurar API da OpenAI
Edite `config/settings.yaml`:
```yaml
openai:
  api_key: "sk-sua-chave-aqui"
  model: "gpt-3.5-turbo"
```

Ou defina a variável de ambiente:
```bash
export OPENAI_API_KEY="sk-sua-chave-aqui"
```

### 3. Executar
```bash
# Interface multimodal (voz + vídeo)
python main.py

# Interface de texto apenas
python -c "from interfaces.text import chat; chat()"
```

## 🎯 Como Usar

### Interface Multimodal
1. Execute `python main.py`
2. Diga "jarvis" para ativar
3. Dê comandos como:
   - "Olá" → Saudação
   - "Gravar vídeo" → Inicia gravação
   - "Detectar pessoas" → Análise de câmera

### Interface de Texto
1. Execute `python -c "from interfaces.text import chat; chat()"`
2. Digite comandos ou use comandos especiais:
   - `ajuda` - Mostra ajuda
   - `limpar` - Limpa tela
   - `memoria` - Mostra memória recente
   - `sair` - Encerra

## ⚙️ Configurações

O arquivo `config/settings.yaml` permite personalizar:

```yaml
openai:
  api_key: "sk-..."
  model: "gpt-3.5-turbo"

voice:
  wake_word: "jarvis"
  language: "pt-BR"
  timeout: 8

memory:
  short_term_limit: 10
  long_term_file: "memory.json"
  long_term_limit: 100

camera:
  default_index: 0
  detection_duration: 5

recording:
  default_duration: 10
  output_dir: "recordings"
```

## 📂 Estrutura do Projeto

```
ai_jarvis/
├── config/
│   └── settings.yaml          # Configurações
├── core/
│   ├── agent.py               # Agente principal
│   ├── llm.py                 # Integração com OpenAI
│   ├── memory.py              # Sistema de memória
│   └── planner.py             # Planejamento de ações
├── interfaces/
│   ├── multimodal.py          # Voz + texto
│   └── text.py                # Interface de texto
├── tools/
│   ├── base.py                # Classe base para ferramentas
│   ├── camera.py              # Detecção de pessoas
│   ├── recorder.py            # Gravação de vídeo
│   └── manager.py             # Gerenciador de ferramentas
├── faces/                     # Dados de reconhecimento facial
├── recordings/                # Vídeos gravados
├── memory.json                # Memória de longo prazo
└── main.py                    # Ponto de entrada
```

## 🔧 Desenvolvimento

### Adicionando Novas Ferramentas
1. Crie uma classe herdando de `Tool` em `tools/`
2. Implemente o método `run()`
3. Registre no `ToolManager` em `main.py`

### Melhorando o LLM
- Modifique prompts em `core/llm.py`
- Adicione novos intents no método `think()`
- Configure diferentes modelos no `settings.yaml`

## 🔐 Privacidade e Segurança

- **Totalmente Local**: LLM roda via API, mas dados ficam locais
- **Sem Telemetria**: Não envia dados para terceiros
- **Controle Total**: Você controla todas as configurações
- **Licença Proprietária**: Todos os direitos reservados

## 📈 Roadmap

- [ ] Interface web moderna
- [ ] Suporte a múltiplos LLMs (Ollama, Claude)
- [ ] Reconhecimento facial avançado
- [ ] Integração com dispositivos IoT
- [ ] Modo offline completo
- [ ] Plugins extensíveis

## 🤝 Contribuição

Contribuições são bem-vindas! Sinta-se à vontade para:

- Reportar bugs
- Sugerir funcionalidades
- Enviar pull requests
- Melhorar documentação

## 📞 Suporte

Para dúvidas ou sugestões:
- Abra uma issue no GitHub
- Consulte a documentação
- Verifique os logs de erro

---

**Desenvolvido com ❤️ para tornar a IA mais acessível e privada.**


## 🔐 Licença

Este projeto é de propriedade exclusiva do autor e está sob licença proprietária (**All Rights Reserved**).

### O que isso significa?

- ❗ Não é permitido usar, copiar, modificar, redistribuir ou vender sem autorização prévia por escrito.
- ❗ Não há concessão de licença implícita sobre o código-fonte.

## 💼 Licenciamento Comercial

Caso você queira usar este projeto comercialmente ou em produto fechado:

👉 **É necessária autorização formal do autor**.
Entre em contato para obter licença comercial personalizada.

📧 Contato: **[SEU EMAIL AQUI]**

## ⚠️ Aviso Legal

Este software é fornecido **“como está”**, sem garantias.
O uso é de inteira responsabilidade do usuário.

Este projeto **não deve ser utilizado para vigilância ilegal** ou violação de privacidade.
Sempre respeite as leis locais.

---

## 🌱 Contribuições

Contribuições são bem-vindas!
Ao contribuir, você concorda com os termos da licença proprietária deste repositório.

---

## 🧠 Visão do Projeto

O objetivo do AI Jarvis é evoluir para um assistente local completo, com:

- Visão computacional avançada
- Processamento de voz
- Tomada de decisão autônoma
- Integração com hardware e sistemas reais
