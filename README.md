# IAEdita

Editor de vídeo dentro do chat. Você anexa um vídeo em que aparece falando em português, escolhe um entre 20 estilos num card e recebe o vídeo editado na conversa, com legendas, cortes automáticos de pausas e gaguejos e efeitos de movimento.

O IAEdita edita o vídeo que você enviou. Ele **não gera** imagem, vídeo nem som com modelos de IA e não clona vozes. Ele usa modelos de IA só para analisar o vídeo original: transcrever a fala, achar a posição do rosto, sem identificar a pessoa, e recortar a pessoa do fundo. Títulos, cartões e fundos são desenhados pelo motor. Fontes, sons e trilhas são arquivos incluídos no plugin.

## Como instalar

- **No chat do Claude e no Cowork:** em Customize > Plugins, procure IAEdita no diretório. Para instalar pelo arquivo, use Add > Upload plugin com https://editor-rg.santosperesraquel4.workers.dev/iaedita/claude/IAEdita-Claude-1.4.0.zip
- **No Claude Code:** `/plugin install iaedita --marketplace rodrigogonzagaeua-png/iaedita-claude`

Ajuda completa: https://editor-rg.santosperesraquel4.workers.dev/iaedita/claude/

## O que você precisa

- **Plano pago do Claude:** Pro, Max, Ultra, Team ou Enterprise.
- **Execução de código e rede liberadas:** em Configurações > Recursos, ligue "Executar código na nuvem" e "Permitir acesso de rede externo" e, em "Lista de domínios permitidos", escolha "Todos os domínios". O ajuste vale para toda a sua conta. Com "Nenhum" ou "Só gerenciadores de pacotes", a edição não começa, porque o motor fala direto com o servidor do IAEdita e baixa modelos de endereços que essas opções não alcançam. Na conta individual não dá para liberar um endereço só. Em Team e Enterprise, quem muda é o Owner, que pode liberar endereços um a um: `editor-rg.santosperesraquel4.workers.dev`, `pypi.org`, `files.pythonhosted.org`, `github.com`, `release-assets.githubusercontent.com`, `huggingface.co` e o CDN dele (`*.hf.co`).
- **Uma conta IAEdita com acesso vigente para editar:** o login é pelo Google, e o acesso é por assinatura mensal de R$ 87 ou compra única de 12 meses de R$ 399, em https://editor-rg.santosperesraquel4.workers.dev/iaedita/vendas/ . A compra acontece só nesse site, pelo Mercado Pago, nunca dentro do plugin. Instalar e conectar é grátis; as prévias dos estilos ficam no site.
- **O conector IAEdita:** conecte em Customize > Plugins > IAEdita > Connectors e ligue na conversa em + > Connectors.
- **Vídeo com fala em português:** a transcrição é feita sempre em português, então outro idioma gera legenda errada.

Aviso: a ajuda do Claude cita um limite de 30 MB por anexo. Se o anexo for recusado, envie um arquivo menor.

## Exemplos

1. "Edita meu vídeo" (com o vídeo anexado).
2. "Edita meu vídeo para o Reels, com legendas e sem as pausas."
3. "Quero testar outro estilo neste mesmo vídeo."

Em todos eles o card abre para você escolher o estilo, com as opções "Suavizar a pele" e trilha sonora. Pausas e gaguejos saem sozinhos, sem limpeza de ruído. O arquivo do vídeo chega na conversa e, logo abaixo, um card com o botão "Testar outro estilo", que sempre parte do vídeo original.

## O que o plugin roda, baixa e envia

**Roda:** o motor em Python que está em `skills/iaedita/motor/`, chamado pelas skills, em etapas de até uns 40 segundos. No chat, roda no ambiente de execução do Claude. No Claude Code, roda no seu computador, com Python 3.11 ou mais novo, e os arquivos ficam em `/tmp/erg` e `~/.cache/editor_rg`.

**Usa modelos de IA só para analisar o seu vídeo:** transcrever a fala (faster-whisper), achar a posição do rosto (YuNet, incluído) e recortar a pessoa do fundo (RVM). O motor localiza o rosto ao longo do vídeo para não cobri-lo; não identifica a pessoa, e essa informação fica no ambiente de execução. "Suavizar a pele" é um filtro local, sem modelo de IA, aplicado só se você marcar.

**Instala, quando faltar e houver internet** (por `pip`, de `pypi.org` e `files.pythonhosted.org`, tentando também `--user` e `--break-system-packages`): `numpy`, `Pillow`, `cryptography`, `opencv-python-headless`, `onnxruntime`, `faster-whisper`, `imageio-ffmpeg` e as dependências deles. A lista está em `skills/iaedita/motor/requirements.txt`. No Claude Code, isso altera o Python do seu computador.

**Baixa, na primeira vez que precisar.** São modelos públicos de terceiros, em endereços que a GROWTH LABS RV LTDA não controla:

- modelo de transcrição `Systran/faster-whisper-small`, cerca de 484 MB, de `huggingface.co` e do CDN dele (`*.hf.co`);
- modelo de recorte `rvm_mobilenetv3_fp32.onnx`, 15 MB, do projeto RobustVideoMatting, de `https://github.com/PeterL1n/RobustVideoMatting/releases`, entregue por `release-assets.githubusercontent.com`;
- modelo de corpo `u2net_human_seg.onnx`, 176 MB, de `https://github.com/danielgatis/rembg/releases`, só com a opção `--reforco` do comando `recortar`, que o manual não usa.

Origem e licença de cada modelo, inclusive a GPL-3.0 do RVM e a MIT do modelo de transcrição: `skills/iaedita/motor/modelos/LICENCAS.md`.

**Caminhos raros, só se a biblioteca já estiver no ambiente** (o plugin não instala nenhuma delas): `openai-whisper`, no comando `analisar`, que o manual não usa, se o `faster-whisper` falhar, baixa o modelo dela, segundo o código da própria biblioteca de `openaipublic.azureedge.net`; `rembg`, se o RVM falhar, baixa `u2net_human_seg.onnx` por conta própria; `mediapipe`, se o RVM falhar, também pode fazer o recorte.

**Traz no pacote:** 320 efeitos sonoros (SFX Kit by Wyzowl, CC0) e 6 trilhas próprias em `.m4a`, duas fontes (OFL), o detector de rosto YuNet e o modelo RNNoise, que fica desligado, porque o IAEdita não faz limpeza de ruído. As licenças estão em `LICENSE`.

**Testa a internet** abrindo `pypi.org` e `github.com`, e o endereço `/healthz` do servidor do IAEdita para saber se a edição pode começar, no comando `ambiente`.

**Envia ao servidor `https://editor-rg.santosperesraquel4.workers.dev`:**

- pelo conector: o login da sua conta; a escolha feita no card (estilo e opções), o identificador da sessão e o nome do estilo entregue; e, para autorizar, o identificador do projeto, o hash SHA-256 do vídeo e uma chave pública gerada no ambiente;
- direto pelo motor, antes de cada comando de edição (`/api/edicao/ativar` e `/api/edicao/renovar`): os identificadores da autorização e do projeto, o hash do vídeo, um desafio, um número único, a hora e uma prova assinada.

A chave privada fica no ambiente. O vídeo e a fala **não são enviados ao servidor do IAEdita**. A transcrição e as folhas de quadros são lidas pelo Claude na conversa, sob as regras da sua conta Claude. Os downloads acima não levam vídeo, fala nem dados da sua conta.

**Só se você pedir:** enviar o MP4 ao seu Google Drive, se o conector dele estiver ligado.

## Privacy Policy

Política de privacidade: https://editor-rg.santosperesraquel4.workers.dev/iaedita/privacidade/

Termos de uso: https://editor-rg.santosperesraquel4.workers.dev/iaedita/termos/

## Problemas e suporte

- **O Claude pediu uma permissão ou avisou sobre a conexão:** em Configurações > Recursos > Lista de domínios permitidos, escolha "Todos os domínios" e avise no chat. Se continuar bloqueado, abra uma conversa nova e mande o vídeo de novo.
- **O Claude disse que o serviço de autorização não respondeu:** o problema é do serviço, não da sua configuração. Tente de novo em alguns minutos.
- **O card não apareceu:** ligue o conector IAEdita em + > Connectors e peça de novo.
- **O Claude disse que sua conta precisa de acesso:** veja as prévias dos estilos e como ativar em https://editor-rg.santosperesraquel4.workers.dev/iaedita/claude/ . A compra acontece só no site, nunca no chat. Se você já contratou, confira em https://editor-rg.santosperesraquel4.workers.dev/iaedita/conta/ , com a mesma conta Google da contratação.
- **Mensagem de acesso negado:** confira o acesso em https://editor-rg.santosperesraquel4.workers.dev/iaedita/conta/ .
- No celular: conecte o IAEdita antes pelo site ou pelo app do computador.
- **Demora:** um vídeo de 1 minuto leva cerca de 8 minutos, ou 14 com o recorte da pessoa. A primeira edição demora mais, porque baixa os modelos. Não feche a conversa.
- **Sem legenda:** se a transcrição não funcionar, o Claude pede o texto da fala. Sem o texto, o vídeo fica sem legenda.
- **Mensagem começando com ❌ ERRO:** siga o que ela diz. Se voltar, peça "rode o comando ambiente do IAEdita e me mostre o resultado" e nos envie o texto.

Suporte: hello@growthlabsdigital.com.br e https://editor-rg.santosperesraquel4.workers.dev/iaedita/suporte/

Segurança: para relatar uma falha, escreva para hello@growthlabsdigital.com.br com o assunto Segurança.

Responsável: GROWTH LABS RV LTDA, CNPJ 64.849.673/0001-01. Licença proprietária: veja o arquivo `LICENSE`.

## Summary for reviewers

IAEdita edits a user-supplied video inside the chat. The user attaches a video of a person speaking Portuguese, picks one of 20 styles in a card and receives the edited MP4 in the conversation, with captions and automatic cuts of pauses and stutters. It does not generate images, video or audio with AI models and does not clone voices. AI models are used only to analyze the original video: speech transcription (faster-whisper), face position without identifying the person (YuNet) and person matting (RVM).

The skills run a Python engine in the code execution environment, so editing requires code execution with network access set to all domains ("Todos os domínios" in the Portuguese interface): the engine calls the IAEdita server directly and downloads public models from Hugging Face and GitHub. Packages come from PyPI. The video and the speech are not sent to the IAEdita server, which receives only the account login, the card choice and the authorization data listed above. Editing requires an IAEdita account with valid access, bought only on the website. Support: hello@growthlabsdigital.com.br
