---
name: iaedita-04-quebra-de-moldura
description: Direção profissional do estilo 04 · Quebra de moldura do IAEdita — o vídeo vira um quadro inclinado pendurado numa sala clara (parede creme, sofá verde) e, nas falas fortes, a pessoa sai do quadro com a cabeça na frente da borda. Use quando o cliente escolher "Quebra de moldura" (04-quebra-de-moldura) no card do IAEdita. Precisa da pessoa recortada (comando recortar); sem recorte funciona num modo mais simples.
---

# Estilo 04 · Quebra de moldura

Antes: siga a skill principal `iaedita` (fluxo e regras de edição). Esta skill só ensina a DIREÇÃO deste estilo.

## A essência
Em alguns trechos, o vídeo encolhe e vira um **quadro pendurado numa sala clara** (parede creme com luz, janela, abajur, sofá verde), levemente inclinado e balançando devagar. Nos **momentos fortes da fala**, a borda de cima do quadro desce para trás da cabeça e a pessoa **sai do quadro**: cabeça e pescoço ficam na frente da moldura, sobre a parede. Depois a borda volta e o quadro sai, devolvendo o vídeo em tela cheia.
Reconhecível por: **quadro claro com cantos arredondados na parede creme**, **cabeça "furando" a borda de cima nas palavras de peso**, **títulos escuros na parede, acima da cabeça, com uma palavra em faixa verde-limão**.

## Antes de planejar: o recorte
Este estilo precisa da pessoa recortada. Se ainda não existe `mascara.mkv` na pasta e o `editar` não avisou "sem recorte", rode `recortar`. Olhe `folha_recorte.jpg`.
- O que importa é a **cabeça** estar bem recortada (cabelo, orelhas, queixo). Se o corpo falhar, tudo bem: o estilo só tira do quadro a parte de cima.
- Se não houver recorte, siga o "Modo sem recorte" no fim desta skill.

## Leitura da fala: onde entram os efeitos
Leia a fala inteira (`palavras`) e marque:
- **Gancho (primeiros 3 s):** uma `moldura` começando em 0,00 s (o vídeo já entra virando quadro) OU uma `quebra` na primeira palavra forte. Se a primeira frase traz a promessa do vídeo, um `titulo` com ela.
- **Momentos fortes → `quebra`:** números ("3 milhões"), promessas, revelações ("o segredo é"), negações fortes ("nunca", "zero"), viradas ("mas", "só que", "na verdade"), a palavra-chave do assunto, a frase de efeito. O `inicio` é o início dessa palavra.
- **Trechos de explicação, lista ou contexto → `moldura`:** a pessoa fica dentro do quadro "apresentando". Comece no início de uma frase e termine no fim de outra.
- **Ideia central de um trecho → `titulo`:** 2 a 5 palavras com as palavras do falante (mais curto), `marca` na palavra mais importante (de preferência número ou palavra-chave).
- **Título nunca junto com quebra.** O título sempre começa uns 0,4 s depois do fim da quebra (ou termina antes dela começar). Assim ele aparece em qualquer enquadramento.
- **Respiro:** entre os blocos, o vídeo volta para tela cheia. Silêncio visual também é ritmo.

## Ritmo pela duração do vídeo
| Duração | Molduras | Quebras | Títulos |
|---|---|---|---|
| até 15 s | 1–2 | 1–2 | 0–1 |
| 15–45 s | 2–4 | 3–6 | 1–3 |
| 45–90 s | 4–7 | 5–10 | 2–5 |
| 90 s+ | 1 a cada 12–20 s | 1 a cada 8–12 s | 1 a cada 20–30 s |
- Tela cheia (sem moldura nem quebra) em **35% a 55%** do vídeo.
- `moldura` dura 2–8 s. `quebra` dura 0,8–3 s (do início da palavra forte até o fim da frase).
- Deixe pelo menos 2 s entre uma quebra e a próxima (o mínimo aceito é 0,8 s).
- Uma `quebra` pode ficar sozinha (o vídeo entra no quadro já "quebrado") ou dentro de uma `moldura` (só a borda desce). As duas formas são boas; alterne.
- Eventos de quadro a menos de 0,9 s um do outro viram um bloco só (o quadro não sai e volta). Use isso para encadear: moldura → quebra → moldura.
- Nada nos últimos 0,5 s se a pessoa só respira; termine limpo, em tela cheia.

## Adaptação ao enquadramento
Olhe `folha_original.jpg` e o campo `tamanho_medio.plano` em `rosto.json` (`fechado`, `medio` ou `aberto`). Use o `rosto.json`: é ele que o motor usa (o resumo em `analise.json` pode estar desatualizado). Se a imagem e o campo discordarem, confie na imagem.
- **Plano fechado** (rosto grande, como selfie): o motor encolhe o vídeo para caber na parede. Na quebra, a pessoa **avança** para a câmera (o alto da cabeça vai até a borda da tela) — fica forte. Por isso, **o título não aparece durante a quebra**: ponha os títulos em trechos de `moldura` SEM quebra ao mesmo tempo (ex.: quebra de 17,04 a 18,70 s → título de 19,10 a 20,70 s). Se o queixo estiver muito baixo (no último quarto da imagem), a quebra vira um "soco" do quadro (a cabeça não sai): use mais molduras com título.
- **Plano médio** (cintura para cima): tudo funciona. Mesmo assim, siga a regra: título só depois da quebra.
- **Plano aberto** (pessoa pequena): funciona; prefira quebras mais longas (1,5–3 s) para o efeito ser notado.
- **Algo na frente do pescoço** (microfone, celular, caneca, cartão, mão): a cabeça sairia "decepada". O motor percebe e, nesse instante, troca a saída da cabeça por um "soco" do quadro. Se isso acontece em quase todas as quebras, use mais `moldura` com `titulo` e menos `quebra`.

## Eventos do plano
```json
{
  "estilo": "04-quebra-de-moldura",
  "correcoes": {"Instagran": "Instagram"},
  "eventos": [
    {"tipo": "moldura", "inicio": 0.00, "fim": 4.20, "som": "whoosh", "som_volume": 0.18},
    {"tipo": "titulo", "inicio": 0.30, "fim": 2.30, "texto": "3 erros de iniciante", "marca": "erros"},
    {"tipo": "quebra", "inicio": 2.42, "fim": 3.90, "som": "whoosh-curto", "som_volume": 0.14},
    {"tipo": "quebra", "inicio": 7.22, "fim": 8.70, "som": "whoosh", "som_volume": 0.16},
    {"tipo": "moldura", "inicio": 16.42, "fim": 24.40, "som": "whoosh", "som_volume": 0.18},
    {"tipo": "quebra", "inicio": 17.04, "fim": 18.70, "som": "whoosh-curto", "som_volume": 0.14},
    {"tipo": "titulo", "inicio": 19.10, "fim": 20.70, "texto": "26 vídeos novos", "marca": "26"},
    {"tipo": "titulo", "inicio": 22.70, "fim": 24.40, "texto": "Comente “estúdio”", "marca": "estúdio"}
  ]
}
```
| tipo | campos | o que acontece |
|---|---|---|
| `moldura` | `inicio`, `fim` (2–8 s), `som` | o vídeo encolhe e vira um quadro inclinado na parede; a pessoa fica DENTRO |
| `quebra` | `inicio`, `fim` (0,8–3 s), `som` | a borda de cima desce para trás da cabeça e a pessoa sai do quadro |
| `titulo` | `inicio`, `fim`, `texto` (2–5 palavras, até 34 letras, sem ponto final), `marca` (1 palavra do texto, opcional) | título escuro na parede, acima da cabeça; a palavra `marca` ganha faixa verde-limão |
- Tempos: pegue o `inicio` exato da palavra em `palavras`. Nunca chute.
- O `titulo` só aparece enquanto há `moldura` na tela: o tempo dele precisa caber dentro de uma `moldura`.
- O `titulo` nunca fica ao mesmo tempo que uma `quebra`: comece uns 0,4 s depois do `fim` da quebra.
- Escreva o título em português correto, com acentos. Nada de ids, nomes de estilo ou textos internos.

## Som
- `whoosh` na entrada de cada `moldura` (`som_volume` 0,15–0,2).
- `whoosh-curto` na `quebra` que acontece dentro de uma moldura (0,12–0,16).
- `quebra` sozinha (sem moldura em volta): `whoosh` (é a entrada do quadro), 0,14–0,18.
- `moldura` que começa a menos de 0,9 s do fim de outra (vira o mesmo bloco, o quadro não entra de novo): sem som.
- Título não leva som. Se dois sons caírem a menos de 0,4 s, deixe só um.
- Trilha (se marcada no card): calma ou média, abaixo da voz (o motor abaixa sozinho).

## Legenda
O perfil já vem pronto: uma ou duas palavras por vez, tinta escura numa etiqueta creme (a cor da parede), palavra falada em verde-escuro, embaixo — dentro do quadro quando ele está na tela. Não mude. Os títulos ficam no alto, a legenda embaixo: não brigam.

## Modo sem recorte
Se `recortar` não funcionar no ambiente, faça o MESMO plano. O estilo continua bonito: o quadro entra, inclina e balança na sala e, nas quebras, dá um "soco" (cresce e se inclina) no tempo da palavra forte. Só a cabeça não sai do quadro. Avise o cliente em uma frase, por exemplo: "Neste ambiente não deu para recortar você do fundo, então o quadro pulsa nos momentos fortes em vez de você sair dele."

## Erros de amador (não faça)
- Moldura no vídeo inteiro, sem voltar para tela cheia: cansa e a quebra perde a surpresa.
- Quebra em toda frase, ou em palavra fraca ("então", "tipo", "né").
- Quebra longa (mais de 3 s): a surpresa acaba.
- Título com a frase inteira, repetindo a legenda, ou fora do tempo de uma moldura.
- Título ao mesmo tempo que uma quebra (em plano fechado ele não aparece).
- Som em todos os eventos (vira barulho).
- Moldura começando no meio de uma palavra ou terminando no meio de uma frase.

## Conferência antes de entregar
Na `folha_previa.jpg` (inclua com `--tempos` o meio de cada quebra) e na `folha_resultado.jpg`:
- [ ] Primeiro efeito nos 3 primeiros segundos; efeitos espalhados até o fim, ligados a palavras reais.
- [ ] Na quebra, a cabeça inteira está FORA do quadro, na frente da parede, sem faixa de parede entre o queixo e a borda ("cabeça flutuando").
- [ ] Nenhuma linha reta cortando o alto da cabeça sobre a parede (se aparecer, o recorte falhou no cabelo: troque essa quebra por moldura).
- [ ] A borda do quadro passa abaixo do queixo: nada cobre olhos e boca.
- [ ] Objeto na frente do pescoço (microfone, celular, cartão) ou queixo cortado reto sobre a parede → troque essa quebra por `moldura`.
- [ ] Nenhuma barra ou mancha saindo das laterais do quadro sobre a parede.
- [ ] Títulos legíveis, inteiros, sem encostar na cabeça; marca na palavra certa.
- [ ] Tela cheia em 35% a 55% do tempo.
- [ ] `problemas_no_plano` e `problemas` vazios.
