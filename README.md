# AI Jarvis - Assistente Local

AI Jarvis e um assistente local com foco em vigilancia, memoria simples e automacao residencial.

## Estado atual

- Interface de texto local
- Interface multimodal em desenvolvimento
- Vigilancia em background com deteccao de pessoas
- Gravacao automatica do stream atual
- Deteccao e cadastro de rostos com OpenCV
- Memoria curta em conversa e memoria longa persistida em `state/long_term_memory.json`
- Controle de `luz`, `tomada` e `fechadura` em modo simulado
- Suite de testes automatizados para os modulos centrais

## Como executar

1. Instale as dependencias com `pip install -r requirements.txt`.
2. Configure `OPENAI_API_KEY` ou edite `config/settings.yaml` se quiser fallback via OpenAI.
3. Rode `python main.py` para a interface principal.
4. Rode `python -m unittest discover -s tests -v` para executar os testes.

## Comandos de exemplo

- `vigiar ambiente`
- `parar vigilancia`
- `ligar a luz da casa`
- `desligar a tomada`
- `trancar a fechadura da casa`
- `lembre que a chave reserva esta na gaveta`
- `o que voce sabe sobre chave reserva`

## Estrutura

```text
ai_jarvis/
|-- config/
|-- core/
|-- interfaces/
|-- tests/
|-- tools/
`-- main.py
```

## Observacoes

- Arquivos gerados em runtime ficam em `faces/`, `recordings/`, `runs/` e `state/`.
- Esses artefatos nao devem ser versionados.
- A interface multimodal ainda precisa de ajuste de sintaxe antes de ficar estavel.

## Licenca

Este projeto esta licenciado sob a GNU General Public License v3 (GPLv3).
