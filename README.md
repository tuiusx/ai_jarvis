# AI Jarvis - Assistente Local

AI Jarvis e um projeto de assistente local, offline-first, com foco em vigilancia, memoria simples e automacoes de camera.

## Estado atual

- Interface de texto local
- Vigilancia em background com deteccao de pessoas via YOLO
- Gravacao automatica usando o mesmo stream da camera
- Deteccao e cadastro de rostos com OpenCV
- Memoria curta em conversa e memoria longa persistida em `state/long_term_memory.json`
- Arquitetura modular pronta para receber um LLM local real no futuro

## O que ainda nao existe

- Um LLM generativo integrado por padrao
- Interface de voz ou web
- Suite de testes ampla para camera e visao computacional

## Estrutura

```text
ai_jarvis/
|-- core/        # agente, memoria, planner, vigilancia
|-- tools/       # ferramentas como gravacao
|-- interfaces/  # interface de texto
|-- config/      # configuracoes estaticas
|-- tests/       # testes unitarios leves
|-- main.py
```

## Como executar

1. Instale as dependencias com `pip install -r requirements.txt`.
2. Garanta acesso a um peso YOLO compativel com `yolov8n.pt`, seja localmente ou pela resolucao automatica do Ultralytics.
3. Rode `python main.py`.

## Comandos de exemplo

- `vigiar ambiente`
- `parar vigilancia`
- `esse rosto e ricardo`
- `lembre que a chave reserva esta na gaveta`
- `o que voce sabe sobre chave reserva`
- `quais rostos conhecidos voce tem`

## Dados locais

Arquivos gerados em runtime ficam em `faces/`, `recordings/`, `runs/` e `state/` e nao devem ser versionados.

## Licenca

Este projeto esta licenciado sob a GNU General Public License v3 (GPLv3).
