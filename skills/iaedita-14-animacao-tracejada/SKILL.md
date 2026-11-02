---
name: iaedita-14-animacao-tracejada
description: Direção profissional do estilo 14 · Animação tracejada do IAEdita — desenhos feitos à mão em volta da pessoa, com o tremido de animação quadro a quadro ("doodle boil") — contorno creme na silhueta, setas, estrelas, corações, notas escritas com seta e títulos sublinhados. Use quando o cliente escolher "Animação tracejada" (14-animacao-tracejada) no card do IAEdita. Precisa da pessoa recortada (comando recortar); sem recorte funciona num modo mais simples.
---

# Estilo 14 · Animação tracejada

Antes: siga a skill principal `iaedita` (fluxo e regras de edição). Esta skill só ensina a DIREÇÃO deste estilo.

## A essência
Parece que alguém **desenhou à mão, com caneta, em cima do vídeo**. Nos momentos certos da fala, um traço creme **se desenha em volta da silhueta** da pessoa, e pequenos desenhos (coração, estrela, seta, claquete, lâmpada…) **nascem traço a traço** ao lado da cabeça. Tudo **treme de leve, como desenho animado feito quadro a quadro** — esse tremido é a assinatura do estilo e o motor faz sozinho. O fundo fica um pouco mais escuro, a pessoa em destaque.
Reconhecível por: **linha creme tremida contornando a pessoa**, **desenhos rosa, creme e verde-limão "na parede" atrás dela**, **notas escritas com seta apontando para a pessoa**, **títulos com sublinhado desenhado**, legenda escura com moldura tracejada rosa.

## Antes de planejar: o recorte
Este estilo usa a pessoa recortada. Se ainda não existe `mascara.mkv` na pasta e o `editar` não avisou "sem recorte", rode `recortar`. Olhe `folha_recorte.jpg`.
- O contorno segue a borda do recorte: se o recorte tiver buracos ou pedaços do fundo, a linha também terá. Recorte bom = contorno bonito.
- Se não houver recorte, siga o "Modo sem recorte" no fim desta skill.

## Leitura da fala: onde entram os efeitos
Leia a fala inteira (`palavras`) e marque:
- **Gancho (primeiros 3 s):** um `contorno` começando em 0,00 s (a pessoa "ganha o traço" logo na primeira frase) e, se couber, um `desenho` ligado ao assunto.
- **Palavra que vira desenho → `desenho`:** escolha a forma pelo SENTIDO do que é dito:

| a fala diz… | forma |
|---|---|
| amor, gostar, paixão, cuidado, obrigado | `coracao` |
| melhor, top, incrível, nota máxima, sucesso | `estrela` |
| isso aqui, olha, este, aponte para algo | `seta` |
| vídeo, gravar, filmar, conteúdo, cena | `claquete` |
| rápido, energia, força, poder | `raio` |
| ideia, dica, segredo, solução | `lampada` |
| falar, comentar, dizer, mensagem, pergunta | `balao` |
| certo, sim, pronto, funciona, lista feita | `check` |
| errado, não faça, nunca, erro | `x` |
| atenção, importante, cuidado | `exclamacao` |
| por quê?, como?, será?, dúvida | `interrogacao` |
| dinheiro, vender, preço, lucro, grátis | `cifrao` |
| crescer, resultado, aumentar, número subindo | `grafico` |
| ênfase forte numa palavra (sem objeto) | `brilhos` (riscos dos dois lados da cabeça) |

- **Frase de virada / número / promessa → `contorno`** (de novo) e/ou um `titulo` de 2 a 4 palavras com `marca` na palavra mais importante (número ou palavra-chave).
- **Reação curta → `nota`:** 1 a 3 palavras que COMENTAM a fala, como alguém escrevendo na margem ("viralizou!", "anota isso", "de graça!"). Não copie a legenda (ex.: ele diz "quebrou a internet" → nota "viralizou!", e não "quebrou a internet").
- **Punchline / momento de impacto → `aura`:** riscos de energia em volta da cabeça. No máximo 1 a cada 15 s.
- **Respiro:** deixe trechos sem nada novo. Silêncio visual também é ritmo.

## Ritmo pela duração do vídeo
| Duração | contornos | desenhos | notas | títulos | auras |
|---|---|---|---|---|---|
| até 15 s | 1 | 2–3 | 0–1 | 0–1 | 0–1 |
| 15–45 s | 2–3 | 4–7 | 1–2 | 1–2 | 1 |
| 45–90 s | 3–5 | 7–12 | 2–4 | 2–3 | 1–2 |
| 90 s+ | 1 a cada 15–20 s | 1 a cada 6–8 s | 1 a cada 20 s | 1 a cada 30 s | 1 a cada 45 s |
- Durações: `contorno` 1,5–5 s · `desenho` 1,2–3 s · `nota` 1,4–2,5 s · `titulo` 1,8–3 s · `aura` 0,8–2 s. O traço leva ~0,5 s para se desenhar e ~0,3 s para se apagar, dentro do tempo do evento.
- Comece cada evento no `inicio` exato da palavra (pegue em `palavras`). Termine no fim da frase.
- No máximo **3 elementos** (desenho/nota/título) na tela ao mesmo tempo; o ideal é 1 ou 2. O contorno e a aura não contam.
- **Só 1 texto por vez: 1 nota OU 1 título, mais a legenda.** Uma nota/título só pode começar depois que o texto anterior terminou (`inicio` ≥ `fim` do anterior). Se dois textos se cruzarem, a validação acusa em `problemas_no_plano` e o motor desenha só o primeiro (o outro some, com "Aviso (estilo 14)").
- Dois contornos não podem se sobrepor. Deixe pelo menos 2 s entre um contorno e o próximo.
- Nada nos últimos 0,5 s se a pessoa só respira; termine limpo.

## Adaptação ao enquadramento
Olhe `folha_original.jpg` e o campo `tamanho_medio.plano` em `rosto.json` (`fechado`, `medio` ou `aberto`). Se a imagem e o campo discordarem, confie na imagem.
- **O motor escolhe a posição de cada desenho, nota e título:** nunca sobre o rosto, fora da legenda, dentro da zona segura (a direita da metade de baixo fica livre para os botões das redes) e longe dos outros elementos que estão na tela. Você só escolhe O QUE e QUANDO (e, se quiser, o `lado`).
- **Regra dos textos (nota e título):** nunca em cima da faixa da legenda nem "empilhados" nela — o motor deixa um respiro de ~4% da altura da tela entre o texto e a legenda (mais que o dos desenhos) — nunca sobre olhos, nariz ou boca, e nunca sobre outro texto ou sobre os riscos de uma `aura`. Se não houver lugar assim, o texto não aparece (aviso) em vez de ficar ilegível.
- **Plano fechado** (rosto grande, como selfie): sobra pouco espaço ao lado da cabeça. O motor NÃO encolhe os desenhos até sumirem (eles ficam com pelo menos 1/6 da largura da tela). Com recorte, o desenho fica "na parede", atrás da pessoa, e pode entrar um pouco atrás do boné, do cabelo ou da bochecha: a própria pessoa esconde essa parte e o desenho parece sair de trás dela. Se nem assim couber, ele vai para o peito/ombro, abaixo do queixo e fora da legenda. A `seta` e o `balao` ficam na altura das bochechas para a ponta continuar visível. Mesmo assim:
  - prefira formas simples (`coracao`, `estrela`, `check`, `x`, `raio`, `seta`, `exclamacao`, `brilhos`); evite `claquete`, `grafico` e `lampada` (têm detalhes pequenos);
  - nota com **1 palavra de até 7 letras** ("viral!", "uau!", "26!", "top!") — mais longa não cabe e não aparece. Sem espaço ao lado da cabeça, ela sobe para o alto, ao lado da testa, por cima da borda do boné/cabelo, com uma seta curta que para antes do rosto;
  - título com **até 3 palavras**: como a legenda fica logo abaixo do queixo, o título vai para o **alto da tela, por cima do boné/cabelo** (como na prévia aprovada), nunca sobre olhos/boca e nunca encostado na legenda;
  - no máximo 1 elemento por vez (o contorno e a aura não contam). O contorno e a aura funcionam muito bem: em plano fechado o contorno abraça só a cabeça e some no pescoço (os ombros e o que a pessoa segura ficam sem linha).
- **Plano médio** (cintura para cima): tudo funciona. Os desenhos ficam ao lado da cabeça, na altura da testa, "na parede" atrás da pessoa; o título costuma ir no alto ou no peito, logo abaixo do queixo, sempre com um respiro antes da legenda.
- **Plano aberto** (pessoa pequena): use `tamanho: 3` nos desenhos e contornos mais longos (3–5 s) para o efeito ser notado.
- Se o motor não achar lugar para um elemento, ele avisa na saída da `previa`, antes do resultado (linha "Aviso (estilo 14): … não aparece"), e NÃO desenha. Encurte o texto, troque a nota por um `desenho` ou mude o momento, e rode a `previa` de novo.
- Os desenhos na altura da cabeça ficam "na parede", atrás da pessoa: se ela gesticular, a mão passa NA FRENTE do desenho. Isso é de propósito (dá profundidade).

## Eventos do plano
```json
{
  "estilo": "14-animacao-tracejada",
  "correcoes": {"Instagran": "Instagram"},
  "eventos": [
    {"tipo": "contorno", "inicio": 0.00, "fim": 3.20, "som": "lapis", "som_volume": 0.9},
    {"tipo": "desenho", "inicio": 0.56, "fim": 3.30, "forma": "claquete"},
    {"tipo": "desenho", "inicio": 5.28, "fim": 7.00, "forma": "check", "som": "writing-pencil-tick", "som_volume": 0.9},
    {"tipo": "desenho", "inicio": 8.42, "fim": 10.40, "forma": "grafico", "lado": "esquerda", "som": "lapis", "som_volume": 0.8},
    {"tipo": "contorno", "inicio": 16.42, "fim": 19.60, "cor": "rosa", "som": "lapis", "som_volume": 0.9},
    {"tipo": "titulo", "inicio": 17.04, "fim": 19.50, "texto": "26 vídeos novos", "marca": "26", "som": "writing-pencil-write", "som_volume": 0.9},
    {"tipo": "nota", "inicio": 20.32, "fim": 22.30, "texto": "viralizou!", "som": "writing-pencil-write", "som_volume": 0.9},
    {"tipo": "aura", "inicio": 20.76, "fim": 22.10, "som": "writing-scribble", "som_volume": 0.7},
    {"tipo": "desenho", "inicio": 22.74, "fim": 25.00, "forma": "balao", "som": "lapis", "som_volume": 0.8}
  ],
  "efeitos_sonoros": [{"som": "writing-eraser", "t": 19.25, "volume": 0.6}]
}
```
| tipo | campos | o que acontece |
|---|---|---|
| `contorno` | `inicio`, `fim` (1,5–5 s), `cor` "creme" (padrão), "rosa" ou "lima", `som` | uma linha feita à mão sai do alto da cabeça, desce pelos dois lados contornando a cabeça e os ombros (só a borda de FORA: celular, produto ou microfone na frente do peito não ganham linha), treme, e no fim se apaga de volta; o fundo escurece um pouco |
| `desenho` | `inicio`, `fim` (1,2–3 s), `forma` (lista acima), `lado` "auto" (padrão), "esquerda" ou "direita", `tamanho` 1, 2 (padrão) ou 3, `cor` (opcional), `som` | o desenho nasce traço a traço ao lado da cabeça, treme, e se apaga de trás para frente |
| `nota` | `inicio`, `fim` (1,4–2,5 s), `texto` (1–3 palavras, até 18 letras), `lado`, `cor` (cor da seta, opcional), `som` | palavra escrita em creme, inclinada, com uma seta desenhada apontando para a pessoa |
| `titulo` | `inicio`, `fim` (1,8–3 s), `texto` (2–5 palavras, até 28 letras, sem ponto final), `marca` (1 palavra do texto, opcional), `posicao` "auto" (padrão), "topo" ou "baixo", `som` | título grande escrito da esquerda para a direita; a `marca` fica rosa com sublinhado duplo verde-limão (sem marca: sublinhado rosa na última linha) |
| `aura` | `inicio`, `fim` (0,8–2 s), `cor` (opcional, padrão "lima"), `som` | riscos de energia saem de trás da cabeça, pulsam e recolhem |
- `cor` só aceita "creme", "rosa" ou "lima" (a paleta do estilo). Cada forma já tem sua cor certa; só mude se tiver motivo.
- `lado` "auto" alterna esquerda/direita sozinho. Use "esquerda"/"direita" só se a fala apontar para um lado.
- Escreva notas e títulos em português correto, com acentos. Nada de ids, nomes de estilo ou textos internos.

## Som
- **Lápis agrupado por desenho:** `lapis` (lápis desenhando) no `contorno` e em cada `desenho` que entra sozinho. Esse som é baixinho: use `som_volume` 0,8–0,9.
- `writing-pencil-write` (escrevendo) no `titulo` e na `nota`, 0,8–0,9.
- `writing-pencil-tick` no `check`, 0,9. `writing-scribble` na `aura`, 0,6–0,7.
- Apagar (opcional, 1 ou 2 vezes no vídeo): `{"som": "writing-eraser", "t": <fim do contorno − 0,35>, "volume": 0.6}` em `efeitos_sonoros`.
- Dois elementos que nascem a menos de 0,6 s um do outro: som só no primeiro. Nunca som por traço, palavra ou hachura.
- Trilha (se marcada no card): leve ou média, abaixo da voz (o motor abaixa sozinho).

## Legenda
O perfil já vem pronto: Inter grossa creme, palavra falada em rosa, caixa escura com **moldura tracejada rosa** (desenhada pelo estilo), fora do rosto. Não mude. Os desenhos, notas e títulos fogem da legenda sozinhos.

## Modo sem recorte
Se `recortar` não funcionar no ambiente, faça o MESMO plano. O estilo continua bonito: o `contorno` vira um **círculo feito à mão em volta da cabeça** (em plano fechado, quando o círculo não cabe, vira um **arco feito à mão por cima da cabeça**, de um lado ao outro; uma nota no mesmo momento fica fora do arco e a seta para antes da linha), o fundo ganha uma vinheta escura, e os desenhos ficam na frente do vídeo, sempre fora do rosto. Só a linha em volta da silhueta e os desenhos "atrás da pessoa" não existem. Avise o cliente em uma frase, por exemplo: "Neste ambiente não deu para recortar você do fundo, então o traço contorna a sua cabeça em vez do corpo todo."

## Erros de amador (não faça)
- Desenho em toda frase, ou vários ao mesmo tempo (vira caderno rabiscado). Poucos e no tempo certo.
- Forma que não combina com a fala (coração quando ele fala de dinheiro). Leia o sentido da frase.
- Nota que repete a legenda palavra por palavra. A nota comenta; a legenda transcreve.
- Título com a frase inteira ou com mais de 5 palavras.
- Nota e título ao mesmo tempo (ou duas notas): os textos se amontoam com a legenda e ninguém lê. Um texto por vez.
- Contorno no vídeo inteiro (perde a surpresa) ou dois contornos colados.
- Desenho curto demais (menos de 1,2 s): não dá tempo de ver o traço nascer.
- Som de lápis em todos os eventos e em volume alto (vira chiado). Ele é textura, não protagonista.
- Mudar o perfil da legenda ou pedir cores fora da paleta.

## Conferência antes de entregar
Rode `previa` com `--tempos` no meio de cada elemento (e 0,3 s depois do início de um contorno, para ver o traço nascendo). Os tempos vão entre aspas, em segundos com ponto, separados por vírgula e sem espaço:
```
python3 "$ERG" previa --pasta /tmp/erg --tempos "0.3,1.5,6.1,18.0"
```
Na `folha_previa.jpg` e na `folha_resultado.jpg`:
- [ ] Primeiro efeito nos 3 primeiros segundos; efeitos espalhados até o fim, ligados a palavras reais.
- [ ] O contorno abraça a cabeça e os ombros (sem linhas soltas no meio do fundo ou do peito). Se o recorte falhou (linha fora da pessoa, buracos), troque aquele contorno por `brilhos` ou `aura`.
- [ ] Nenhum desenho, nota ou título sobre olhos ou boca; nada cortado pela borda; nada em cima da legenda; nada no canto de baixo à direita (botões das redes). Desenho saindo de trás do boné ou do cabelo está certo.
- [ ] Nota/título com respiro visível da legenda (nunca encostados nem empilhados nela) e nunca dois textos do estilo juntos: em cada quadro, no máximo 1 nota ou título + a legenda.
- [ ] Desenhos grandes o bastante para ver no celular (pelo menos 1/6 da largura). Se um sumiu ou ficou miúdo, mude o momento para quando a legenda estiver mais baixa ou troque por `brilhos`.
- [ ] A saída da `previa` não tem "Aviso (estilo 14)". Se tiver, corrija o elemento citado.
- [ ] Notas e títulos legíveis e em português correto; marca na palavra certa.
- [ ] Se o vídeo original já tem textos gravados nele (legenda própria, nome, logotipo), o motor não os enxerga: confira se nenhuma nota ou título caiu em cima deles. Se caiu, troque o `lado`, o momento ou use um `desenho`.
- [ ] Formas combinam com a fala.
- [ ] `problemas_no_plano` e `problemas` vazios.
