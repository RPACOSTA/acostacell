---
title: Rick's Voice Studio V001
emoji: 🎙️
colorFrom: green
colorTo: gray
sdk: gradio
sdk_version: 6.32.0
python_version: "3.12"
app_file: app.py
short_description: Narração e diálogos em português com Pocket TTS
---

# Rick's Voice Studio V001

Estúdio Gradio em português brasileiro para narrações e diálogos com [Pocket TTS da Kyutai](https://huggingface.co/kyutai/pocket-tts). A síntese roda em CPU.

- **Narração** aceita até 16.000 caracteres por geração. Escolha uma voz, ajuste a temperatura e gere o áudio.
- **Diálogo** usa linhas iniciadas com `[personagem]`. Clique em **Detectar personagens**, atribua as vozes e gere o roteiro. O estúdio junta as falas na ordem original, com uma pausa curta entre elas.
- **Vozes** incluem Rafael, a voz oficial em português, e as demais entradas do catálogo da versão instalada para experimentar com texto em PT-BR. As vozes experimentais podem manter o sotaque de origem.
- **Qualidade** usa as variantes oficiais `portuguese` e `portuguese_24l` e o parâmetro `sampler_decode_steps`. A variante de 24 camadas e mais passos de decodificação aumentam o tempo de CPU.
- **Biblioteca** aceita até seis amostras autorizadas por sessão. A biblioteca é temporária. A interface permite pré-escutar cada voz com uma frase em português.
- **Exportação** oferece WAV e MP3 e um player para reprodução no navegador.

## Usar pelo GitHub Codespaces

[Crie um Codespace na branch `main`](https://codespaces.new/RPACOSTA/acostacell?ref=main). O Codespace instala as dependências, incluindo FFmpeg e FFprobe, e abre o estúdio no navegador pela porta **7860**. Se a aba do estúdio não abrir automaticamente, selecione **Ports → Rick's Voice Studio → Open in Browser**.

A porta é privada por padrão. Pare o Codespace ao terminar para conservar a cota da conta. Caso o servidor precise ser iniciado manualmente, execute `bash .devcontainer/start.sh`. O log fica em `.venv-codespaces/voice-studio.log`.

Se o terminal estiver usando Alpine/musl, abra a paleta de comandos do VS Code e selecione **Codespaces: Rebuild Container** para carregar a imagem Debian com Python 3.12 definida no projeto. As dependências do Codespace ficam em `.venv-codespaces`.

Para habilitar a clonagem de voz, aceite os termos do modelo e adicione um [segredo do Codespaces](https://github.com/settings/codespaces) chamado `HF_TOKEN` com permissão de leitura para `kyutai/pocket-tts` e acesso a este repositório GitHub. Depois de adicionar o segredo, reinicie o Codespace para carregar a credencial.

## Desenvolvimento

Com Python 3.12 e FFmpeg disponíveis em Linux:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install gradio==6.32.0 -r requirements.txt
python app.py
```

Execute os testes locais com `python -m unittest discover -s tests -v`. Os testes usam uma síntese de referência e verificam a preparação dos roteiros, o upload de amostras e os arquivos de saída sem baixar pesos.

Para clonagem local, aceite as condições de acesso na página do [modelo](https://huggingface.co/kyutai/pocket-tts) e autentique-se com `hf auth login`. No Space, configure o segredo `HF_TOKEN` com permissão de leitura dos pesos após aceitar as condições. Gradio e a versão do Python são configurados no cabeçalho deste arquivo. O Space usa o hardware **CPU Basic**, sem cobrança por hora. O Hugging Face exige um plano habilitado para criar um Space Gradio com esse hardware.

Documentação e catálogo do modelo em [kyutai-labs/pocket-tts](https://github.com/kyutai-labs/pocket-tts).
