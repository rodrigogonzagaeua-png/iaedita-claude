---
name: iaedita-10-crescimento-de-grafico
description: Direção profissional do estilo 10 · Crescimento de gráfico do IAEdita — quando a pessoa fala de números, a câmera recua, o fundo vira parede de papel creme e um gráfico verde-limão cresce ATRÁS dela até um selo com o número; números de passagem viram cartão que conta de 0 ao valor. Use quando o cliente escolher "Crescimento de gráfico" (10-crescimento-de-grafico) no card. Usa a pessoa recortada; sem recorte, o gráfico vai acima da cabeça.
---

# Estilo 10 · Crescimento de gráfico

Antes: siga a skill principal `iaedita` (fluxo e regras de edição). Esta skill só ensina a DIREÇÃO deste estilo.

## A essência
Quando a pessoa fala de um resultado, a câmera recua: o vídeo vira um cartão sobre uma parede de papel creme, a sala do fundo some e a pessoa fica na frente de um painel com grade fina. Uma linha verde-limão (com brilho e núcleo branco) ou barras crescem da esquerda para a direita e terminam num **selo verde-limão** com o número, no instante em que ele é dito. Depois uma faixa de luz atravessa a tela e a câmera volta ao normal.
Reconhecível por: **o gráfico cresce atrás da pessoa e termina no número falado**, **selo verde-limão com seta ↗**, **parede de papel com grade fina**.

O motor já faz sozinho: o recuo da câmera conforme o enquadramento, o tamanho do painel, a posição do selo e do título, a contagem do número no selo, a proteção do rosto (nada passa na frente dos olhos e da boca), os rótulos que sairiam atrás da cabeça e a posição da legenda. Você escolhe QUANDO entra cada gráfico e O QUE ele mostra.

## Leitura da fala: onde entram os efeitos
Rode `palavras` e leia a fala inteira. Marque:
- **Crescimento com números** ("de 2 mil para 10 mil", "dobrei", "3x mais", "cresceu 300%") → `grafico` (o efeito principal). O selo é o número de chegada.
- **Crescimento sem número** ("explodiu", "viralizou", "bombou", "quebrou a internet", "só cresce") → `grafico` com curva ilustrativa e selo com a PALAVRA ("VIRALIZOU", "RECORDE"). Nunca invente um número.
- **Comparação no tempo** ("antes / hoje", "em 2023 / em 2025", mês a mês) → `grafico`; os momentos viram `rotulos`.
- **Número citado de passagem** ("26 vídeos", "3 passos", "10 anos", "R$ 500") → `numero` (cartão que conta de 0 até o valor).
- **Gancho (primeiros 3 s):** sempre algo na tela até 3 s. Se a primeira frase tem número, um `numero` nela; se tem crescimento, um `grafico` que começa em 0. Se não tem nenhum dos dois: um `grafico` curto com `titulo` = o assunto do vídeo e `selo` = uma palavra-chave DITA na primeira frase (ex.: o nome do produto), sem `valores` (o motor usa a curva padrão), com `selo_em` no início dessa palavra. Nunca uma promessa que a pessoa não disse.

Regra de ouro: `selo_em` é o **tempo exato do início da palavra do número** em `palavras`. Nunca chute tempos.

## Ritmo pela duração do vídeo
| Duração | Gráficos | Números | Tempo com gráfico na tela |
|---|---|---|---|
| até 15 s | 1 | 0–1 | até 40% |
| 15–45 s | 2–3 | 1–2 | até 45% |
| 45–90 s | 3–5 | 2–4 | até 45% |
| 90 s+ | 1 a cada 15–25 s | 1 a cada 20 s | até 40% |
- Cada `grafico` dura de 3,5 a 6 s (mínimo 2,6 s, máximo 9 s).
- `inicio` do gráfico = 1,6 a 2,5 s ANTES de `selo_em` (normalmente o começo da frase). O motor precisa desse tempo: 0,55 s de recuo da câmera e o resto para a linha crescer.
- `fim` do gráfico = 1,2 a 2,5 s DEPOIS de `selo_em` (fim da frase). O motor usa os últimos 0,9 s para a faixa de luz e a volta da câmera.
- `numero`: `inicio` = 0,6 s antes da palavra do número (a contagem termina na palavra); `fim` = 1,5 a 3 s depois do `inicio`.
- Entre o `fim` de um efeito e o `inicio` do próximo: mínimo 0,3 s (o validador cobra), ideal 1,5 s ou mais. O rosto também é a estrela: deixe respiros sem efeito.
- Nos últimos segundos, se a pessoa só se despede, termine limpo.

## Adaptação ao enquadramento (olhe a folha_original.jpg)
O motor recua a câmera sozinho e põe a cabeça na frente da parte de baixo do painel. Você ajusta a QUANTIDADE de informação:
- **Plano fechado** (rosto ocupa mais de ~38% da largura, selfie): o recuo é maior (o vídeo fica em ~70%). Use de 2 a 5 valores, `titulo` de até 2 palavras, `rotulos` curtos (até 5 letras, ex.: "2023"/"HOJE") ou nenhum. Prefira `forma` "linha". O motor esconde o rótulo que ficaria atrás da cabeça: se algum sumir na prévia, encurte ou tire.
- **Plano médio** (rosto entre 20% e 38% da largura): o padrão. De 4 a 7 valores, linha ou barras, título de até 4 palavras.
- **Plano aberto** (pessoa pequena, cabeça abaixo de 1/3 da tela): o motor quase não recua; tudo cabe como na prévia aprovada.

## Eventos do plano
```json
{
  "estilo": "10-crescimento-de-grafico",
  "correcoes": {"Instagran": "Instagram"},
  "eventos": [
    {"tipo": "numero", "inicio": 0.40, "fim": 2.60, "valor": 3, "rotulo": "passos simples",
     "som": "data-countup-short", "som_volume": 0.25, "som_atraso": 0.1},
    {"tipo": "grafico", "inicio": 5.10, "fim": 10.20, "forma": "linha", "valores": [2, 10],
     "titulo": "Faturamento", "selo": "10 MIL", "selo_em": 7.84, "rotulos": ["2023", "HOJE"],
     "som": "data-chart-reveal", "som_volume": 0.3},
    {"tipo": "grafico", "inicio": 16.30, "fim": 21.00, "forma": "barras", "valores": [3, 5, 8, 12, 20],
     "titulo": "Seguidores", "selo": "20 MIL", "selo_em": 18.92,
     "rotulos": ["JAN", "FEV", "MAR", "ABR", "MAI"], "som": "data-chart-reveal", "som_volume": 0.3}
  ],
  "efeitos_sonoros": [
    {"som": "riser-2s-soft", "t": 7.84, "volume": 0.16},
    {"som": "pop", "t": 7.84, "volume": 0.3},
    {"som": "riser-2s-soft", "t": 18.92, "volume": 0.16},
    {"som": "pop", "t": 18.92, "volume": 0.3}
  ]
}
```
| tipo | campos |
|---|---|
| `grafico` | `inicio` (a câmera começa a recuar), `fim` (tudo já voltou), `forma` "linha" (padrão) ou "barras", `valores` (2 a 7 números em ordem de tempo; o **último é o maior**), `selo` (até 12 letras: o número ou a palavra de chegada, ex. "+300%", "10 MIL", "VIRALIZOU"), `selo_em` (início exato da palavra do selo), `titulo` (opcional, 1 a 4 palavras, até 22 letras: o QUE cresce), `rotulos` (opcional: 2 textos [começo, fim] ou 1 por valor, até 9 letras cada), `som`, `som_volume` |
| `numero` | `inicio`, `fim` (1,5 a 4 s), `valor` (só o número: 26, 3.5, 10000), `prefixo` (opcional: "+", "R$"), `sufixo` (opcional: "%", " mil", " mi", "x"), `rotulo` (1 a 3 palavras, até 18 letras: o que é o número), `contar` (true = padrão, conta de 0 até o valor; false = número parado), `posicao` "auto" (padrão: abaixo do queixo ou acima da cabeça, onde couber), "baixo" ou "topo", `som` |

### Como escrever os dados (honestidade vem primeiro)
- **Valores:** se a fala dá os números, use exatamente eles, na ordem ("de 2 mil para 10 mil" → `[2, 10]`; mês a mês → um valor por mês). Se a fala só diz que cresceu, omita `valores` (o motor usa a curva da prévia aprovada) e ponha no selo uma PALAVRA, nunca um número inventado.
- **Selo:** o número ou a palavra que a pessoa diz no `selo_em`, curto e em algarismos ("10 MIL", "+300%", "3X", "26 VÍDEOS"). O motor escreve em maiúsculas e, quando o selo tem um número, faz esse número contar de 0 até o valor (ex.: "+0%" → "+300%").
- **Título:** o que está crescendo, com as palavras da fala ("Faturamento", "Meus seguidores", "Vendas no mês"). Nunca uma frase inteira.
- **Rótulos:** os momentos do eixo ("2023"/"HOJE", "ANTES"/"AGORA", "JAN"…"MAI"). Sem momento claro na fala, não use rótulos.
- `valor` do `numero`: o número sem texto (26, não "26 vídeos"); o texto vai no `rotulo` e no `sufixo`. Decimais com ponto no JSON (3.5); o motor mostra "3,5".
- Português correto, com acentos. Proibido: ids, nomes de estilo ("GRÁFICO 10", "10-crescimento"), placeholders ("Seu texto aqui") e frases inteiras.

## Som
- No `grafico`: `"som": "data-chart-reveal"`, `"som_volume": 0.3` (o painel aparecendo).
- Para cada `grafico`, em `efeitos_sonoros`: `{"som": "riser-2s-soft", "t": <selo_em>, "volume": 0.16}` (a subida termina exatamente no selo; se o desenho for curto, menos de 2 s entre `inicio` e `selo_em`, use "riser-1s-soft") e `{"som": "pop", "t": <selo_em>, "volume": 0.3}` (o selo entrando).
- No `numero`: `"som": "data-countup-short"`, `"som_volume": 0.25`, `"som_atraso": 0.1` (os tiques da contagem).
- Tudo baixo, sempre abaixo da voz. Trilha (se marcada no card): calma ou média, de clima "corporativo", "motivacional" ou "tecnologia"; o motor abaixa sozinho quando a pessoa fala.

## Legenda
O perfil do estilo já vem pronto: Inter 800, creme, caixa grafite, palavra falada em verde-limão, sempre na faixa de baixo (como na prévia aprovada). O motor recua a câmera de modo que o queixo nunca encoste na legenda. Não mude a posição nem o tamanho.

## Sem recorte
Se `recortar` falhar ou o ambiente não tiver o programa de recorte, renderize assim mesmo: o vídeo inteiro recua como um cartão de cantos arredondados sobre a parede de papel, e o gráfico cresce ACIMA da cabeça (não passa atrás da pessoa). Nada cobre o rosto. O plano é o mesmo; não mude nada.
Na entrega, avise em uma frase: "Neste ambiente não deu para recortar você do fundo, então o gráfico aparece acima de você, sem passar por trás."

## Erros de amador (não faça)
- Gráfico sem número nem crescimento na fala (gráfico de enfeite). A única exceção é o gancho dos 3 primeiros segundos (veja acima), e mesmo nele o selo é uma palavra dita.
- Inventar números ou palavras: o selo, os valores e os rótulos saem da fala.
- `selo_em` chutado: o selo entra antes ou depois do número (pegue o tempo em `palavras`).
- `inicio` colado no `selo_em` (menos de 1,4 s): a linha não tem tempo de crescer.
- Gráfico atrás de gráfico, sem respiro, ou gráfico em mais da metade do vídeo.
- Último valor menor que os anteriores (é um estilo de crescimento; para queda, use outro tipo de efeito).
- Título com frase inteira, selo com mais de 12 letras, rótulos longos em plano fechado.
- `numero` para um número que já está no selo do gráfico ao mesmo tempo (repetição).
- Som em excesso (riser alto, pop em tudo).

## Conferência antes de entregar
- [ ] Algo na tela nos 3 primeiros segundos.
- [ ] Rode a prévia no selo de cada gráfico e no meio de cada número: `python3 "$ERG" previa --pasta /tmp/erg --tempos 7.9,19.0,1.5` (use os seus `selo_em` + 0,1 s e o meio dos `numero`). Em cada selo: a linha (ou a última barra) chegou ao selo, o selo está inteiro e legível, o título não encosta no selo.
- [ ] A pessoa está na frente do painel (com recorte) e nada cobre olhos nem boca.
- [ ] Rótulos inteiros (nenhum pedaço escondido atrás da cabeça). Se um rótulo sumiu, encurte ou tire.
- [ ] Números iguais aos da fala, em português correto ("10 mil", "3,5 mi").
- [ ] Efeitos espalhados até o fim da fala, com respiros.
- [ ] `problemas_no_plano` vazio na prévia e `problemas` vazio no resultado; folha_resultado olhada.
