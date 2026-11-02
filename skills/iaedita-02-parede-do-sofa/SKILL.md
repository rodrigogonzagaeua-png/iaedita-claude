---
name: iaedita-02-parede-do-sofa
description: Direção profissional do estilo 02 · Parede do sofá do IAEdita — painéis claros em perspectiva pendurados na parede atrás da pessoa, com títulos curtos que balançam junto com a parede; a cabeça da pessoa passa na frente dos painéis. Use quando o cliente escolher "Parede do sofá" (02-parede-do-sofa) no card do IAEdita. Usa a pessoa recortada (rode `recortar`); sem recorte, segue o modo sem recorte desta skill.
---

# Estilo 02 · Parede do sofá

Antes: siga a skill principal `iaedita` (fluxo e regras de edição). Esta skill só ensina a DIREÇÃO deste estilo.

## A essência
A parede atrás da pessoa vira um mural de "janelas" claras (cartões creme com três pontinhos no topo, uma área verde-sálvia com um círculo verde-limão e uma barrinha de progresso). Cada janela abre na parede como uma porta, mostra um título curto do que a pessoa está falando e fecha quando o assunto muda. A pessoa fica NA FRENTE: a cabeça esconde um pedaço do painel, nunca o texto.
Reconhecível por: **painéis inclinados para dentro (o da esquerda vira para a direita, o da direita vira para a esquerda)**, **um título principal no alto, atrás da cabeça**, **balanço lento da parede** e **legenda em faixa creme com letra escura**.

O motor cuida sozinho de: posição dos painéis em volta da cabeça, onde cabe o texto, o recuo da câmera em plano fechado, a entrada/saída animada e a legenda. Você só escreve O QUE aparece e QUANDO.

## Leitura da fala: onde entram os painéis
Leia a fala inteira (`palavras`) e marque:
- **Gancho** (primeiro segundo): um painel `centro` com a promessa ou o número principal do vídeo (ex.: "3 erros no Instagram", marca "3").
- **Lista ou passos** ("primeiro…", "o segundo…", nomes de itens): um painel por item, alternando esquerda e direita.
- **Comparação** ("antes e depois", "isso ou aquilo"): dois painéis laterais ao mesmo tempo — esquerda = A, direita = B.
- **Número, nome de ferramenta, marca, resultado**: painel com o nome/número (corrigido em `correcoes`).
- **Virada ou ideia central** (1 a cada 15–25 s): painel `centro`.
- **Chamada para ação** ("comente", "siga", "link na bio"): painel no fim, com `icone` "coracao" ou "seta_cima".

Escreva o título com as palavras do falante, mais curto: 1 a 4 palavras, sem ponto final, só a primeira letra maiúscula (siglas e palavras-código podem ir em maiúsculas, ex.: "Comente STUDIO").

## Ritmo pela duração do vídeo
| Duração | Painéis laterais | Painel `centro` (título principal) |
|---|---|---|
| até 15 s | 2–4 | 1 |
| 15–45 s | 5–9 | 1–2 |
| 45–90 s | 8–14 | 2–4 |
| 90 s+ | 1 a cada 5–7 s | 1 a cada 25–30 s |
- Cada painel dura de 1,5 a 6 s (regra: 1 s + 0,4 s por palavra do título, no mínimo). O motor recusa menos de 1,2 s.
- `inicio` = início da palavra que dispara o painel (tempo exato de `palavras`). `fim` = fim da frase daquele assunto. Nunca chute tempos.
- O painel começa a abrir 0,15 s antes do `inicio` e leva 0,4 s para sair depois do `fim`.
- No MESMO lado, deixe pelo menos 0,6 s entre o `fim` de um painel e o `inicio` do próximo.
- No máximo 2 painéis ao mesmo tempo: um na esquerda e um na direita.
- O `centro` aparece SOZINHO: termine os laterais antes dele começar e comece os próximos depois do `fim` dele.
- Nos painéis laterais, nenhuma palavra com mais de 12 letras (ex.: "Produtividade" não cabe — use no `centro` ou troque por "Foco"). Prefira palavras de até 10 letras.
- Espalhe os painéis até a última frase. Nos últimos 0,5 s, se a pessoa só respira, termine limpo.

## Adaptação ao enquadramento (olhe `folha_original.jpg` e o campo `rosto.plano` do `analisar`)
- **Plano fechado** (rosto grande, mais de ~34% da largura): o motor recua a câmera sozinho enquanto houver painéis (o vídeo encolhe um pouco e a parede continua desfocada em volta) e põe os títulos no alto, acima da cabeça. Use textos de até 3 palavras.
- **Plano médio**: os painéis ficam ao lado da cabeça; o `centro` faz a câmera recuar um pouco só enquanto ele aparece. Use o `centro` com moderação (a câmera vai e volta a cada um).
- **Plano aberto** (pessoa pequena, muita parede): tudo cabe com folga; pode usar títulos de 4 palavras.
- **Pessoa fora do centro**: use `lado` "auto" — o motor escolhe o lado com mais parede livre.

## Eventos do plano
Só existe um tipo: `painel`.
```json
{
  "estilo": "02-parede-do-sofa",
  "correcoes": {"Instagran": "Instagram"},
  "eventos": [
    {"tipo": "painel", "inicio": 0.00, "fim": 3.10, "lado": "centro", "texto": "3 erros no Instagram", "marca": "3", "etiqueta": "Dica", "som": "whoosh", "som_volume": 0.2},
    {"tipo": "painel", "inicio": 3.40, "fim": 6.20, "lado": "esquerda", "texto": "Postar sem horário", "etiqueta": "Erro 1", "icone": "x", "som": "swipe", "som_volume": 0.18},
    {"tipo": "painel", "inicio": 6.50, "fim": 9.30, "lado": "direita", "texto": "Legenda gigante", "etiqueta": "Erro 2", "icone": "x"},
    {"tipo": "painel", "inicio": 9.80, "fim": 12.60, "lado": "esquerda", "texto": "Sem chamada", "etiqueta": "Erro 3", "icone": "x"},
    {"tipo": "painel", "inicio": 13.20, "fim": 16.00, "lado": "direita", "texto": "Comente QUERO", "marca": "QUERO", "etiqueta": "Bônus", "icone": "coracao", "som": "pop", "som_volume": 0.2}
  ]
}
```
| campo | o que é |
|---|---|
| `inicio`, `fim` | segundos do vídeo original (de `palavras`) |
| `texto` | o título do painel: 1 a 4 palavras, sem ponto final (obrigatório) |
| `lado` | "auto" (padrão), "esquerda", "direita" ou "centro" (título principal no alto, atrás da cabeça) |
| `marca` | opcional: UMA palavra do `texto` que ganha marca-texto verde (número ou palavra-chave) |
| `etiqueta` | opcional: 1 a 2 palavras na barrinha do topo (categoria: "Dica", "Passo 2", "Antes", "Depois", "Ferramenta") |
| `icone` | opcional, dentro do círculo verde: check, x, estrela, raio, alvo, grafico, dinheiro, coracao, play, seta_cima, seta_baixo, seta_dir |
| `som`, `som_volume` | opcional (veja "Som") |

## Som
- `whoosh` (volume 0,15–0,22) quando a parede abre: no primeiro painel de cada sequência e em cada `centro`.
- `swipe` (0,15–0,2) em cerca de 1 a cada 3 painéis laterais — nunca em todos.
- `pop` (0,2) no painel da chamada para ação.
- Nada de som em painel que entra junto com outro.
- Trilha (se marcada no card): calma/média, abaixo da voz (o motor faz o ducking).

## Legenda
Perfil do estilo já vem pronto (Inter 700, faixa creme, letra escura, palavra falada em verde-oliva, 1 linha de até ~22 letras, entra subindo). O motor põe a legenda abaixo do queixo (ou acima da cabeça) e acompanha o recuo da câmera. Não mude.

## Modo sem recorte
Se `recortar` não funcionar neste ambiente, o motor muda sozinho: os painéis ficam AO LADO ou ACIMA da cabeça, desenhados na frente, sem nunca encostar no rosto. O plano é o mesmo, mas:
- use textos ainda mais curtos (1 a 3 palavras; em plano fechado, 1 a 2);
- evite dois painéis ao mesmo tempo em plano fechado;
- avise o cliente em uma frase: "Os painéis ficaram ao lado da cabeça em vez de passar por trás dela, porque este ambiente não conseguiu recortar a pessoa."
(O aviso "Sem máscara da pessoa" em `avisos` é esperado neste caso.)

## Erros de amador (não faça)
- Título com frase inteira ou repetindo a legenda palavra por palavra.
- Painel que não tem a ver com o que está sendo dito (painel "de enfeite").
- Dois painéis no mesmo lado colados, um saindo e outro entrando no mesmo instante.
- Três painéis ao mesmo tempo, ou o `centro` junto com um lateral.
- Palavra comprida em painel lateral ("Desenvolvimento", "Produtividade").
- Etiqueta com texto interno: "Painel 1", "02-parede", "evento", nome de arquivo ou do estilo. Na dúvida, deixe sem etiqueta.
- Painel de menos de 1,2 s (ninguém lê) ou de mais de 8 s (parede parada).
- `centro` em toda frase (a câmera fica indo e voltando).
- Tempos chutados em vez de tirados de `palavras`.

## Conferência antes de entregar
- [ ] Primeiro painel no primeiro segundo (gancho), de preferência `centro`.
- [ ] Painéis ligados a palavras reais e espalhados até o fim da fala.
- [ ] Na `folha_previa.jpg`: todo título inteiro e legível; nenhum painel sobre olhos ou boca; a cabeça passa NA FRENTE dos painéis (com recorte).
- [ ] Nada cortado pela borda; nenhum texto colado na direita.
- [ ] Legenda fora do rosto e sem cobrir painel.
- [ ] Português correto nos títulos (acentos, nomes corrigidos).
- [ ] `problemas_no_plano` vazio, `problemas` vazio no resultado e `folha_resultado.jpg` olhada.
- Dica: para conferir um momento com dois painéis, rode `previa --tempos 4.6,8.9` com instantes no meio deles.
