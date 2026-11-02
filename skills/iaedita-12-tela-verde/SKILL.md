---
name: iaedita-12-tela-verde
description: Direção profissional do estilo 12 · Tela verde do IAEdita — nos momentos-chave da fala o cenário atrás da pessoa troca (um recorte com linha de luz revela um fundo desenhado pelo motor com um "print" do assunto desenhado — cartão, número, gráfico, lista ou cartão de destaque) e uma faixa de título escura entra embaixo. Use quando o cliente escolher "Tela verde" (12-tela-verde) no card do IAEdita. Precisa da pessoa recortada (comando recortar); sem recorte funciona num modo com a pessoa numa janela.
---

# Estilo 12 · Tela verde

Antes: siga a skill principal `iaedita` (fluxo e regras de edição). Esta skill só ensina a DIREÇÃO deste estilo.

## A essência
É o efeito "tela verde" dos criadores profissionais: a pessoa continua falando, mas **o fundo atrás dela muda** para um cenário desenhado que combina com o assunto. A troca acontece com um **recorte horizontal com uma linha de luz verde-clara** que atravessa a tela da esquerda para a direita. No cenário novo aparece, no alto, um **"print" do assunto** (um cartão de papel com sobretítulo espaçado e título serifado, um número grande, um gráfico subindo, uma lista ou uma "matéria"), e embaixo entra a **faixa de título** escura com o tema. Depois o recorte volta e devolve o fundo original.
Reconhecível por: **cortina de luz trocando o fundo atrás da pessoa**, **cartão claro com título serifado no alto**, **faixa escura de título embaixo**, **legenda com a palavra falada em lavanda**.

O motor cuida sozinho de:
- pôr o cenário ATRÁS da pessoa (ela fica sempre na frente; nada cobre o rosto);
- abrir espaço para o print: se a pessoa estiver perto da câmera, ela "dá um passo para trás" (fica menor, a parte de baixo se dissolve no cenário) e volta ao tamanho normal quando o cenário sai;
- pôr a legenda logo abaixo do queixo e a faixa logo abaixo da legenda, dentro da zona segura.

## Antes de planejar: o recorte
Se ainda não existe `mascara.mkv` na pasta e o `editar` não avisou "sem recorte", rode `recortar`. Olhe `folha_recorte.jpg` (o que não é pessoa deve estar magenta). Se o cabelo ou os ombros falharem muito, siga assim mesmo: o cenário só aparece em volta da pessoa. Sem recorte, veja "Modo sem recorte" no fim.

## Leitura da fala: onde entram os cenários
Leia a fala inteira (`palavras`) e marque os **assuntos** do vídeo (cada mudança de assunto pode virar um cenário):
- **Gancho (primeiros 3 s):** um `cenario` começando em 0,00 s com a promessa do vídeo (print `cartao`), OU uma `faixa` sozinha com o tema.
- **Número dito** ("3 mil clientes", "26 vídeos", "80%") → `cenario` com print `numero`. O número conta de 0 até o valor (se for número inteiro).
- **Resultado, crescimento, antes e depois** ("dobrou", "cresceu", "subiu") → print `grafico` (barras subindo + seta).
- **Lista que a pessoa enumera** ("primeiro…, segundo…, terceiro…", "três coisas") → print `lista`, com `tempos` = início da palavra de cada item. O último tempo precisa ficar **pelo menos 2 s antes do `fim`** do cenário.
- **Fato, notícia, "viralizou", "saiu na imprensa", pesquisa** → print `artigo` (cartão de destaque). Nunca use nome de veículo real; se a fala citar candidato, autoridade ou veículo, use cartao.
- **Frase de efeito ou ideia central** → print `cartao`.
- **Chamada final** ("comenta", "me segue", "link na bio") → `cartao` ou `faixa` com o pedido.
- **Respiro:** entre os cenários o fundo original volta. Isso é parte do estilo: a troca só impressiona porque o fundo real aparece antes e depois.

Use SÓ o que a pessoa disse. Nunca invente número, notícia, resultado ou nome que não está na fala.

## Ritmo pela duração do vídeo
| Duração | Cenários | Faixas sozinhas |
|---|---|---|
| até 15 s | 1–2 | 0–1 |
| 15–45 s | 2–4 | 0–2 |
| 45–90 s | 4–7 | 1–3 |
| 90 s+ | 1 a cada 12–18 s | 1 a cada 30 s |
- Fundo original (sem cenário) em **30% a 55%** do vídeo. Mais de 75% de cenário é recusado pelo motor.
- Cada cenário dura **3,5 a 8 s** (mínimo 2,5 s; máximo 12 s).
- `inicio` = início da palavra que abre o assunto (tempo exato em `palavras`). A cortina leva 0,6 s e a pessoa recua em seguida: o print fica legível ~1,3 s depois do `inicio` (em plano fechado ele só aparece depois que a pessoa recua).
- `fim` = **0,8 a 1 s depois do fim da frase**: o último 1 s do cenário é a volta (o print some, a pessoa volta ao tamanho e a cortina devolve o fundo).
- **Lista:** cada valor de `tempos` precisa ficar entre `inicio` e `fim - 2 s` (o último item precisa de ~1 s na tela antes da volta). Se o último item é dito tarde, aumente o `fim` (até 8 s de cenário) ou deixe esse item de fora. Exemplo: item dito em 13,64 s → `fim` de pelo menos 15,64 s.
- **Cenários encadeados:** se um cenário começa menos de 1,5 s depois do fim do outro, eles viram um bloco — a cortina passa de um cenário direto para o outro, sem voltar ao fundo original. Ótimo para assuntos em sequência. Regras: cada um com pelo menos 2 s antes do próximo, e **fundos diferentes** (com o mesmo fundo a troca não aparece). O último do bloco precisa de pelo menos 2,5 s.
- `faixa` sozinha dura 1,5–6 s e não pode encostar em cenário (deixe 0,3 s de folga); dentro do cenário use o campo `faixa` dele.
- Termine limpo: nada nos últimos 0,5 s se a pessoa só respira.

## Adaptação ao enquadramento
Olhe `folha_original.jpg` e o campo `tamanho_medio.plano` em `rosto.json` (`fechado`, `medio` ou `aberto`). Se a imagem e o campo discordarem, confie na imagem.
- **Plano fechado** (rosto grande, selfie — o caso mais comum): o motor faz a pessoa "dar um passo para trás" em cada cenário (fica com uns 55-60% do tamanho, centralizada, a parte de baixo se dissolve no cenário). O print fica nos ~20% de cima: escreva **títulos curtos** (2-4 palavras) e listas de 2 itens. **Sempre use um print** (sem print a pessoa recua só um pouco e o cenário aparece pouco em volta da cabeça).
- **Plano médio** (do peito para cima): a pessoa encolhe um pouco com a base na borda de baixo. Tudo funciona; títulos até 6 palavras e listas de 3 itens.
- **Plano aberto** (pessoa pequena): a pessoa não muda de tamanho; o print pode ter até 25% da altura. `nenhum` (só troca de fundo) funciona bem aqui.

## Eventos do plano
Exemplo (vídeo de 30 s sobre vendas):
```json
{
  "estilo": "12-tela-verde",
  "correcoes": {"Instagran": "Instagram"},
  "eventos": [
    {"tipo": "cenario", "inicio": 0.00, "fim": 4.60, "fundo": "violeta", "print": "cartao",
     "sobretitulo": "O segredo", "titulo": "Vender sem\nparecer vendedor", "faixa": "Vendas pelo Instagram",
     "som": "whoosh-slow-soft", "som_atraso": 0.3, "som_volume": 0.2},
    {"tipo": "cenario", "inicio": 8.40, "fim": 10.60, "fundo": "noite", "print": "numero",
     "sobretitulo": "Em 30 dias", "numero": "3 mil", "rotulo": "clientes novos", "faixa": "O resultado",
     "som": "whoosh-slow-soft", "som_atraso": 0.3, "som_volume": 0.2},
    {"tipo": "cenario", "inicio": 10.60, "fim": 14.80, "fundo": "lima", "print": "grafico",
     "sobretitulo": "Faturamento", "titulo": "Dobrou em um mês", "valor": "2x", "faixa": "O resultado",
     "som": "whoosh-medium-soft", "som_atraso": 0.25, "som_volume": 0.18},
    {"tipo": "faixa", "inicio": 17.10, "fim": 19.60, "texto": "Os 3 passos"},
    {"tipo": "cenario", "inicio": 20.20, "fim": 26.40, "fundo": "papel", "print": "lista",
     "sobretitulo": "Passo a passo", "itens": ["Mostre o bastidor", "Responda dúvidas", "Chame no direct"],
     "tempos": [21.10, 22.60, 24.00], "faixa": "Os 3 passos",
     "som": "whoosh-slow-soft", "som_atraso": 0.3, "som_volume": 0.2}
  ],
  "efeitos_sonoros": [
    {"som": "whoosh-medium-soft", "t": 4.35, "volume": 0.15},
    {"som": "data-countup-short", "t": 9.00, "volume": 0.12},
    {"som": "whoosh-medium-soft", "t": 14.55, "volume": 0.15},
    {"som": "whoosh-medium-soft", "t": 26.15, "volume": 0.15}
  ]
}
```
(No exemplo, os cenários de 8,40 s e 10,60 s formam um bloco: a cortina vai do fundo `noite` direto para o `lima`, e a faixa "O resultado" fica parada porque o texto é o mesmo.)

| tipo | campos | o que acontece |
|---|---|---|
| `cenario` | `inicio`, `fim` (3,5–8 s), `fundo`, `print`, campos do print (abaixo), `faixa` (2–5 palavras, opcional), `som`, `som_atraso`, `som_volume` | a cortina de luz troca o fundo atrás da pessoa; o print aparece no alto; a faixa entra embaixo; no fim tudo volta |
| `faixa` | `inicio`, `fim` (1,5–6 s), `texto` (2–5 palavras, até 28 letras) | só a faixa escura de título embaixo, sem trocar o cenário |

**Fundos** (`fundo`):
| fundo | visual | combina com |
|---|---|---|
| `violeta` (padrão) | a sala violeta da prévia: parede com moldura, janela, abajur, anéis de luz | história, opinião, abertura, qualquer assunto |
| `lima` | verde-limão claro, sol suave e pontos gráficos | energia, dica rápida, crescimento, novidade |
| `noite` | escuro com brilho violeta, estrelas e chão quadriculado | tecnologia, dinheiro, números, lançamento |
| `papel` | creme com quadriculado de caderno | explicação, passo a passo, lista, chamada final |
| `rosa` | rosa com anéis claros | emoção, relacionamento, assunto leve |
Alterne os fundos; não repita o mesmo em cenários seguidos.

**Prints** (`print`) e seus campos:
| print | campos | uso |
|---|---|---|
| `cartao` | `sobretitulo` (1–3 palavras, opcional), `titulo` (2–6 palavras; use `\n` para escolher a quebra de linha) | ideia central, frase de efeito, promessa |
| `numero` | `sobretitulo`, `numero` (até 7 caracteres: "26", "+80%", "3 mil", "R$ 10"), `rotulo` (2–5 palavras: o que o número conta) | número que a pessoa falou |
| `grafico` | `sobretitulo`, `titulo` (2–5 palavras), `valor` (opcional, 1–2 palavras: "2x", "+40%") | crescimento, resultado |
| `lista` | `sobretitulo`, `itens` (2 ou 3, até 4 palavras / 22 letras cada), `tempos` (opcional: um tempo por item = início da palavra). `tempos` precisam estar entre `inicio` e `fim - 2 s`; se o último item é dito tarde, aumente o `fim` (até 8 s de cenário) ou deixe esse item de fora | itens que a pessoa enumera |
| `artigo` | `sobretitulo` (o rótulo: "Da última vez", "Pesquisa"), `titulo` (o destaque, 2–6 palavras) | fato, notícia, "viralizou" |
| `nenhum` | — | só troca o fundo (use em plano aberto; evite em plano fechado) |
- Se você não escrever `print`, o motor escolhe pelo que existe: `numero` → número, `itens` → lista, `titulo` → cartão.
- Escreva em português correto, com acentos, sem ponto final nos títulos curtos. Nada de ids, nomes de estilo ("TELA VERDE 12"), nomes de arquivo ou textos internos.
- A `faixa` nomeia o TEMA do trecho; ela não repete o título do print nem a legenda.
- O sobretítulo aparece em MAIÚSCULAS com letras espaçadas (escreva normal; o motor converte).

## Som
- Entrada de cada cenário (ou bloco): `"som": "whoosh-slow-soft", "som_atraso": 0.3, "som_volume": 0.2` — ar amplo e discreto no meio da cortina.
- Cenário encadeado (a cortina passa de um cenário para outro): `"som": "whoosh-medium-soft", "som_atraso": 0.25, "som_volume": 0.18`.
- Volta do cenário (no fim do bloco): em `efeitos_sonoros`, `{"som": "whoosh-medium-soft", "t": FIM - 0.25, "volume": 0.15}` (FIM = `fim` do último cenário do bloco).
- Print `numero` com número inteiro: opcional `{"som": "data-countup-short", "t": INICIO + 0.6, "volume": 0.12}`.
- `faixa` sozinha: sem som (ou `swipe-medium-soft` a 0,12 no máximo uma vez).
- Trilha (se marcada no card): calma ou média, abaixo da voz (o motor abaixa sozinho).

## Legenda
O perfil já vem pronto: Inter 850, uma linha, creme numa caixa escura, palavra falada em lavanda. O motor põe a legenda logo abaixo do queixo (inclusive quando a pessoa recua) e a faixa de título logo abaixo da legenda. Não mude o perfil.

## Modo sem recorte
Se `recortar` não funcionar no ambiente, faça o MESMO plano. O estilo continua bonito: em cada cenário o vídeo encolhe e vira uma **janela com moldura clara** na frente do cenário novo; o print fica no alto, atrás da janela; a cortina de luz passa por trás da janela (sobre uma cópia desfocada do fundo original) e a faixa entra embaixo. Só o fundo de dentro da janela continua o original. Nesse modo a `previa` mostra o aviso "Sem máscara da pessoa" em `avisos`: é esperado. `problemas_no_plano` precisa vir vazio. Avise o cliente em uma frase, por exemplo: "Neste ambiente não deu para recortar você do fundo, então o cenário novo aparece em volta de uma janela com o seu vídeo."

## Erros de amador (não faça)
- Cenário no vídeo inteiro, sem deixar o fundo original voltar.
- Trocar de cenário a cada frase (vira apresentação de slides). No máximo um cenário a cada ~6 s.
- `fim` colado no fim da frase: a volta (último 1 s) passa por cima da palavra importante. Dê 0,8–1 s de folga.
- Lista com o último `tempo` a menos de 2 s do `fim`: o item aparece e o cartão já some (ninguém lê). A `previa` recusa; corrija aumentando o `fim` ou tirando o item — nunca encurtando o `fim`.
- Print com a frase inteira ou que repete a legenda palavra por palavra.
- Faixa igual ao título do print.
- Inventar número, notícia, gráfico ou resultado que a pessoa não disse.
- Mesmo fundo em cenários encadeados (a troca some).
- Print `nenhum` em plano fechado (o cenário aparece pouco e a troca perde a força).
- Som em todos os eventos ou alto demais (o som deste estilo é discreto).

## Conferência antes de entregar
Na `folha_previa.jpg` (inclua com `--tempos` o meio de cada cenário, ~1,5 s depois do `inicio`) e na `folha_resultado.jpg`:
- [ ] Primeiro efeito nos 3 primeiros segundos; cenários espalhados até o fim, ligados a assuntos reais da fala.
- [ ] A pessoa está na FRENTE do cenário; nada cobre olhos e boca.
- [ ] Print inteiro, legível, com o texto certo e acentos; nada cortado pela borda.
- [ ] Legenda abaixo do queixo e faixa logo abaixo da legenda, sem se encostarem, acima da faixa de baixo da tela.
- [ ] Fundo original aparece em 30% a 55% do vídeo.
- [ ] `problemas_no_plano` e `problemas` vazios (sem recorte, o aviso "Sem máscara da pessoa" em `avisos` é esperado).
