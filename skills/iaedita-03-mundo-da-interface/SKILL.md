---
name: iaedita-03-mundo-da-interface
description: Direção profissional do estilo 03 · Mundo da interface do IAEdita — a câmera passeia por um aplicativo de edição desenhado (janela, menu, tela principal, linha do tempo), com a pessoa recortada dentro da tela principal, títulos digitados atrás dela e cartões de nota inclinados. Use quando o cliente escolher "Mundo da interface" (03-mundo-da-interface) no card do IAEdita. Usa a pessoa recortada; sem recorte, o vídeo aparece dentro da tela do aplicativo.
---

# Estilo 03 · Mundo da interface

Antes: siga a skill principal `iaedita` (fluxo e regras de edição). Esta skill só ensina a DIREÇÃO deste estilo.

## A essência
O vídeo vira um "aplicativo de edição" bonito e claro: fundo quadriculado, uma janela com menu lateral, a tela principal (fundo verde-sálvia com um grande círculo verde-lima) e a linha do tempo embaixo. A pessoa, recortada do fundo, fica dentro da tela principal. Acima da cabeça, um **título grande é digitado** (com cursor) e fica atrás da pessoa, dando profundidade. A **câmera passeia pelo aplicativo**: abre mostrando a janela inteira, mergulha na tela principal, se aproxima do rosto nas palavras fortes e recua para mostrar um **cartão de nota inclinado** com a ideia-chave.
Reconhecível por: **movimentos de câmera suaves pelo "mundo" da interface**, **título digitado no alto da tela**, **nota inclinada com faixa lima**, **legenda digitada palavra por palavra numa caixa escura à esquerda**.

O motor faz sozinho: posição da pessoa, enquadramentos seguros (rosto nunca coberto, nada cortado), barra de progresso da linha do tempo, ícone ativo do menu e a legenda. Você só escreve 3 tipos de evento.

## Leitura da fala: onde entram os efeitos
Leia a transcrição inteira (`palavras`) e marque:
- **Gancho** (primeiros 3 s): SEMPRE `camera` com `foco` "geral" de 0.0 a 0.4 (a câmera abre no aplicativo inteiro e mergulha na tela) + o primeiro `titulo` começando em 0.3 com o assunto ou a promessa do vídeo.
- **Assunto do trecho** → `titulo`: 2 a 5 palavras que resumem o que a pessoa está falando AGORA. Troque o título quando o assunto mudar ("primeiro", "segundo", "agora", "o outro ponto", "mas"). O título é o nome do capítulo, não a legenda.
- **Ideia-chave, dica, número, passo, nome de ferramenta, resultado** → `nota`: `rotulo` curto ("DICA", "PASSO 2", "RESULTADO", "ATENÇÃO") + `texto` de 2 a 6 palavras com a ideia. A câmera recua sozinha para mostrar o cartão.
- **Palavra de peso / punchline** (número grande, promessa, negação forte, a frase de efeito) → `camera` com `foco` "perto": aproxima do rosto por 1 a 2,5 s.
- **Chamada para ação** ("comenta", "segue", "link") → `nota` com rótulo "COMENTE" / "PRÓXIMO PASSO" e o título do trecho com a ação.
- **Final**: se a pessoa já terminou de falar ou está se despedindo, `camera` "geral" nos últimos 2 a 3 s (a câmera volta a mostrar o aplicativo inteiro, como no começo).

## Ritmo pela duração do vídeo
| Duração | Títulos | Notas | Câmera "perto" | Câmera "geral" |
|---|---|---|---|---|
| até 15 s | 1–2 | 1 | 1 | só a abertura |
| 15–45 s | 3–5 | 2–4 | 2–3 | abertura + final |
| 45–90 s | 5–8 | 4–6 | 3–5 | abertura + 1 virada + final |
| 90 s+ | 1 a cada 10–15 s | 1 a cada 12–20 s | 1 a cada 20 s | abertura, viradas grandes e final |
- **Título**: dura o trecho inteiro do assunto (normalmente 3 a 8 s). Um título por vez; deixe 0,2 s entre um e outro. Prefira ter sempre um título na tela.
- **Nota**: 1,8 a 4 s. Comece a nota ~0,4 s ANTES da frase-chave (o cartão entra 0,3 s depois do `inicio`, enquanto a câmera recua). Pelo menos 2 s entre uma nota e a próxima.
- **Câmera**: `inicio` = início da palavra de peso (tempo exato em `palavras`); 1 a 2,5 s. Pelo menos 8 s entre um "perto" e o próximo (12 s no plano fechado); o `validar` avisa se ficar menor.
- **Título durante o "perto"**: o título NÃO some. O motor o mantém no alto da tela, dentro da área segura, e o encolhe se precisar para caber acima da cabeça. Pode usar "perto" no meio de um título sem medo. Deixe pelo menos 1 s (ideal 1,5 s) entre o fim de uma `camera` ou `nota` e o início da próxima `camera` ou `nota` (cada movimento leva ~1 s). A abertura "geral" (0.0–0.4) leva ~1,3 s para mergulhar: a primeira nota só depois de 1,8 s.
- **Nunca** ponha `camera` ao mesmo tempo que uma `nota` (a nota já move a câmera).
- Silêncio visual também é ritmo: entre os eventos a câmera fica parada na tela principal, com a pessoa grande e nítida.

## Adaptação ao enquadramento (olhe a folha_original.jpg)
- **Plano fechado** (rosto ocupa mais de 38% da largura, como selfie): o motor põe o título numa etiqueta de papel por cima do cabelo/boné (nunca nos olhos) e aproxima pouco no "perto". Use títulos de até 3 palavras e notas de até 4 palavras (o `validar` não mede o rosto, então confira você mesmo). Use "perto" com moderação (no máximo 1 a cada 12 s).
- **Plano médio** (rosto 20–38%): use tudo como na tabela. O título fica atrás da cabeça (efeito de profundidade).
- **Plano aberto** (rosto menor que 20%): o motor aproxima um pouco a pessoa; use "perto" um pouco mais (1 a cada 8–10 s) para mostrar o rosto.
- Se a pessoa se mexe muito ou sai do quadro, confira a prévia nesses instantes: o motor segue o rosto, mas evite "perto" nesses trechos.

## Eventos do plano
```json
{
  "estilo": "03-mundo-da-interface",
  "correcoes": {"Instagran": "Instagram"},
  "eventos": [
    {"tipo": "camera", "inicio": 0.00, "fim": 0.40, "foco": "geral"},
    {"tipo": "titulo", "inicio": 0.30, "fim": 6.80, "texto": "3 erros ao gravar"},
    {"tipo": "nota", "inicio": 2.10, "fim": 5.20, "rotulo": "Erro 1", "texto": "Luz atrás de você", "som": "lente", "som_volume": 0.35},
    {"tipo": "titulo", "inicio": 7.00, "fim": 13.40, "texto": "O som importa mais"},
    {"tipo": "camera", "inicio": 9.32, "fim": 11.00, "foco": "perto", "som": "lente", "som_volume": 0.42},
    {"tipo": "nota", "inicio": 12.10, "fim": 15.00, "rotulo": "Dica", "texto": "Microfone de lapela barato"},
    {"tipo": "titulo", "inicio": 13.60, "fim": 21.00, "texto": "Grave em pé"},
    {"tipo": "camera", "inicio": 17.62, "fim": 19.00, "foco": "perto", "som": "lente", "som_volume": 0.42},
    {"tipo": "nota", "inicio": 20.20, "fim": 23.20, "rotulo": "Próximo passo", "texto": "Salve este vídeo"},
    {"tipo": "titulo", "inicio": 21.20, "fim": 27.00, "texto": "Salve para depois"},
    {"tipo": "camera", "inicio": 27.40, "fim": 30.00, "foco": "geral", "som": "lente", "som_volume": 0.35}
  ]
}
```
| tipo | campos |
|---|---|
| `camera` | `inicio`, `fim`, `foco`: "geral" (recua e mostra o aplicativo inteiro) ou "perto" (aproxima no rosto) ou "tela" (enquadramento normal — quase nunca precisa: fora dos eventos a câmera já fica na tela), `som` |
| `titulo` | `inicio`, `fim` (mínimo 1,2 s), `texto` (2–5 palavras, até 36 letras, sem ponto final; com acentos corretos) |
| `nota` | `inicio`, `fim` (1,8–4 s), `rotulo` (1–3 palavras, até 18 letras; vira maiúsculas sozinho; opcional), `texto` (2–6 palavras, até 44 letras), `som` |
- Tempos sempre em segundos do vídeo original, tirados de `palavras`. Nunca chute.
- O último evento pode ir até a duração do vídeo (ex.: 30.00 num vídeo de 30 s), nunca além.
- Escreva os textos com as palavras do falante, mais curtos. Nada de textos genéricos de modelo.

## Som
- `lente` (suave) nos movimentos de câmera: "perto" e "geral" com `som_volume` 0.35–0.45 (metade do normal: aqui o som é discreto). Pode pôr também em algumas notas (a câmera recua), `som_volume` 0.30–0.35.
- Não use som de teclado na digitação do título nem na legenda. Nada de som em todo evento (vira barulho): no máximo 1 som a cada 3–4 s.
- Trilha (se marcada no card): calma e moderna, abaixo da voz (o motor faz o ducking).

## Legenda
Este estilo desenha a própria legenda: caixa escura à esquerda, perto da base segura, palavras aparecem no instante em que são faladas (como digitação, com cursor), até 4 palavras por página, palavra falada em verde-lima. Não mude. Para desligar: `"legenda": {"ativa": false}`.
- Corrija nomes e marcas em `correcoes` usando a palavra SEM pontuação (ex.: `"estúdio": "STUDIO"`). A vírgula/ponto da fala é mantida sozinha. Nunca escreva `"estúdio,": "STUDIO,"` (sai vírgula dobrada).

## Modo sem recorte
Se não houver máscara da pessoa (o ambiente não conseguiu recortar), o motor mostra o vídeo original dentro da tela principal do aplicativo, como num editor de vídeo; o título ganha a etiqueta de papel e o resto (câmera, notas, linha do tempo, legenda) continua igual. Não mude o plano. Avise o cliente em uma frase: "Neste ambiente não deu para recortar você do fundo, então seu vídeo aparece dentro da tela do aplicativo com o fundo original."
- Sem recorte, a `previa` mostra em `avisos` o aviso "Sem máscara da pessoa". É o único aviso esperado nesse caso: siga para o render (ele não bloqueia).
- Se o recorte existir mas falhar em alguns trechos (só a cabeça aparece), o motor completa os ombros sozinho e suaviza a borda do recorte; confira na folha. Se o vídeo tiver textos ou cartões gravados por cima da pessoa, eles podem aparecer junto com ela (o recorte não sabe separar): avise o cliente.

## Erros de amador (não faça)
- Título que repete a legenda palavra por palavra, ou título trocando a cada frase.
- Nota com frase inteira, nota em cima de nota, ou nota durante um movimento de `camera`.
- "Perto" em toda frase ou com menos de 8 s de distância (perde o impacto) ou "geral" no meio de uma explicação importante (o rosto fica pequeno).
- Texto de modelo ou interno na tela: "Seu projeto", "Seu texto aqui", "AJUSTE FINO", nome do estilo, números de evento. Nunca.
- Começar sem a abertura "geral" em 0.0, ou deixar os primeiros 3 s sem título.
- Eventos que acabam antes do fim da fala (distribua até o final do vídeo).
- Som de teclado ou som em todos os eventos.

## Conferência antes de entregar
- [ ] Abre com `camera` "geral" em 0.0 e o primeiro título até 0,5 s.
- [ ] Um título por assunto, cobrindo o vídeo do começo ao fim, textos curtos e em português correto.
- [ ] Na `folha_previa.jpg`: nada sobre olhos/boca, título inteiro (não cortado), nota inteira e abaixo da boca, legenda fora do rosto. A prévia padrão mostra o meio de cada evento; se quiser ver outro instante, use `--tempos 0.2,3.5,9.8`.
- [ ] Notas e "perto" ligados a palavras reais, nunca ao mesmo tempo.
- [ ] `problemas_no_plano` e `problemas` vazios; `folha_resultado.jpg` olhada.
