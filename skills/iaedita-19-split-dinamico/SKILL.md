---
name: iaedita-19-split-dinamico
description: Direção profissional do estilo 19 · Split dinâmico do IAEdita — nos momentos de dado a tela se divide — o vídeo desce para um cartão na metade de baixo e um painel escuro cresce em cima com gráfico, número grande, comparação, lista ou frase de impacto; depois volta para a tela cheia. Use quando o cliente escolher "Split dinâmico" (19-split-dinamico) no card do IAEdita. Feito para plano fechado (rosto grande); funciona em plano médio. Não precisa recortar a pessoa.
---

# Estilo 19 · Split dinâmico

Antes: siga a skill principal `iaedita` (fluxo e regras de edição). Esta skill só ensina a DIREÇÃO deste estilo.

## A essência
A pessoa fala em tela cheia. Quando ela diz um **dado** (número, crescimento, comparação, lista, frase forte), a tela se divide: o vídeo encolhe e desce para um cartão de cantos arredondados na metade de baixo, e um **palco escuro esverdeado** aparece em cima com o dado desenhado (gráfico que cresce, número que conta, barras, tópicos numerados ou frase com palavra verde). Uma linha verde luminosa marca a divisão e a legenda (pílula escura com contorno verde) pousa nessa linha. Quando o dado termina, o cartão sobe e volta para a tela cheia.
Reconhecível por: **divisão ao meio só nos momentos de dado**, **palco escuro com verde-limão**, **volta limpa para a tela cheia**.

O motor faz sozinho: animação de abrir/fechar, enquadramento do rosto dentro do cartão, legenda (o estilo desenha a própria legenda), cores e tamanhos. Você só escolhe **quando** dividir e **o que** mostrar no palco.

## Leitura da fala: onde a tela divide
Leia a transcrição inteira (`palavras`) e procure:
- **Número dito** ("26 vídeos", "3 milhões", "70%", "R$ 10 mil", "2,5x") → `numero`.
- **Crescimento ou queda** ("cresceu", "dobrou", "subiu", "caiu", "de 2019 para hoje") → `grafico`.
- **Antes x depois / isto x aquilo** ("antes eu ganhava 2 mil, hoje 10 mil", "orgânico contra pago") → `comparacao`.
- **Lista/enumeração** ("três coisas: ...", nomes falados um atrás do outro) → `topicos`, com o tempo exato de cada item.
- **Frase de efeito / conclusão** sem número ("isso quebrou a internet", "ninguém te conta isso") → `frase`.
- **Gancho**: se os primeiros 3 s tiverem um dado ou uma lista, abra o vídeo com um painel. Se não, deixe a pessoa em tela cheia e divida no primeiro dado.
- Sem dado nenhum num trecho = tela cheia. A divisão só tem valor porque é rara.

Tempos de cada painel:
- `inicio` = início da palavra do dado (tempo exato em `palavras`, nunca chute). A tela começa a dividir nesse instante.
- `fim` = fim da fala daquele dado + 0,2 a 0,4 s. O palco fica na tela até o `fim`. Depois do `fim` o cartão sobe e a tela volta ao normal (leva 0,6 s).
- Nos `topicos`, o último `em` precisa estar pelo menos 0,8 s antes do `fim` (senão o último item quase não aparece).
- O último painel do vídeo precisa terminar pelo menos 0,7 s antes do fim do vídeo (tempo da volta).

## Ritmo pela duração do vídeo
| Duração | Painéis | Tela dividida no total |
|---|---|---|
| até 15 s | 1–2 | até 50% |
| 15–45 s | 3–5 | 35–50% |
| 45–90 s | 4–7 | 30–45% |
| 90 s+ | 1 a cada 15–20 s | 30–40% |
- Cada painel: 2,5 a 8 s (veja a faixa de cada tipo abaixo). Nunca menos de 2,5 s.
- Painéis não podem se sobrepor: um termina antes do outro começar.
- **Painéis encostados** (menos de 1,5 s entre o fim de um e o início do outro) usam a MESMA divisão: a tela fica dividida e só o conteúdo de cima troca. Use isso para encadear "número → frase". Mais de 3 painéis encostados cansa.
- Entre duas divisões separadas, deixe pelo menos 3 s de tela cheia.
- Varie os tipos: não repita o mesmo tipo duas vezes seguidas se a fala permitir.

## Adaptação ao enquadramento (olhe a folha_original.jpg)
- **Plano fechado** (rosto grande, ocupa mais de 38% da largura): é o caso ideal. O cartão mostra o rosto inteiro; nada a ajustar.
- **Plano médio**: funciona; o motor aproxima um pouco a câmera dentro do cartão (até 1,3x) para o rosto não ficar pequeno.
- **Plano aberto** (pessoa pequena, de corpo inteiro): funciona, mas o rosto fica pequeno no cartão. Use menos painéis (os mais fortes) e prefira `numero` e `frase`.
- Se o vídeo já tiver textos gravados em cima (do próprio criador), eles aparecem dentro do cartão — normal. Não tente cobri-los.

## Eventos do plano
```json
{
  "estilo": "19-split-dinamico",
  "correcoes": {"cláudios": "do Claude", "estúdio": "studio"},
  "eventos": [
    {"tipo": "topicos", "inicio": 0.00, "fim": 5.30, "rotulo": "Feitos com Claude", "titulo": "Os estilos",
     "itens": [{"texto": "Orbit", "em": 0.00}, {"texto": "UI World", "em": 1.46},
               {"texto": "Digital Zoom", "em": 3.32}, {"texto": "Phone Mockup", "em": 4.30}],
     "som": "whoosh-medium-soft", "som_volume": 0.22},
    {"tipo": "numero", "inicio": 17.04, "fim": 19.55, "rotulo": "Nos próximos dias", "valor": "26",
     "titulo": "vídeos diferentes", "som": "whoosh-medium-soft", "som_volume": 0.22},
    {"tipo": "grafico", "inicio": 19.74, "fim": 23.20, "rotulo": "Da última vez", "titulo": "Quebrou a internet",
     "forma": "subida"}
  ],
  "efeitos_sonoros": [
    {"som": "whoosh-medium-soft", "t": 5.40, "volume": 0.2},
    {"som": "data-countup-medium", "t": 17.50, "volume": 0.2},
    {"som": "data-chart-reveal", "t": 20.25, "volume": 0.18},
    {"som": "whoosh-medium-soft", "t": 23.30, "volume": 0.2}
  ]
}
```
Neste exemplo a pessoa disse "26 vídeos" (número real) e "a última vez quebrou a internet" (sem número): por isso o gráfico não tem `valores` nem `marca`. `valores` e `marca` só com números ditos; sem eles, o motor desenha uma curva ilustrativa. O `numero` e o `grafico` estão encostados (0,19 s entre eles): a tela fica dividida e só o palco troca.

| tipo | duração | campos |
|---|---|---|
| `grafico` | 3–7 s | `titulo` (2–5 palavras, até 28 letras), `rotulo` (opcional), `forma` "subida" (padrão) ou "queda", `valores` (opcional: 3 a 8 números reais na ordem do tempo), `marca` (opcional: selo no fim da linha, até 12 letras, ex. "+300%"), `eixo` (opcional: [esquerda, direita], até 14 letras cada, ex. ["2019", "Hoje"]), `som` |
| `numero` | 2,5–6 s | `valor` (o número como a pessoa disse: "26", "3 milhões", "70%", "R$ 10 mil", "2,5x"; até 14 letras — ele conta do zero até o valor), `titulo` (o que o número significa, 2–5 palavras), `rotulo` (opcional), `som` |
| `comparacao` | 3–7 s | `titulo`, `rotulo` (opcional), `itens` (2 a 4: `[{"rotulo": "Antes", "valor": "2 mil"}, {"rotulo": "Hoje", "valor": "10 mil"}]`; rótulo até 12 letras, valor até 10), `destaque` (opcional: número do item que fica verde, 1 = primeiro; padrão = o último), `som` |
| `topicos` | 3–8 s | `titulo`, `rotulo` (opcional), `itens` (2 a 4 textos de até 24 letras; de preferência `{"texto": "...", "em": segundo exato em que a pessoa fala o item}`), `som` |
| `frase` | 2,5–5 s | `titulo` (a frase de impacto, 3–9 palavras, até 48 letras), `marca` (opcional: 1–2 palavras da frase que ficam verdes e sublinhadas), `rotulo` (opcional), `som` |

Regras dos textos:
- `rotulo` = pequeno chapéu verde em CAIXA ALTA acima do título (1–4 palavras, até 24 letras). Ele dá contexto: "Nos próximos dias", "Da última vez", "Resultado".
- `titulo` com as palavras do falante, mais curto. Sem ponto final. Português correto.
- `valores` só se a pessoa disser os números de verdade; senão omita (o motor desenha uma curva ilustrativa crescente ou em queda). Nunca invente dados que pareçam reais.
- Na `comparacao`, as alturas das barras saem dos valores ("2 mil" x "10 mil"). Use a mesma unidade nos itens.
- Nos `topicos`, cada `em` precisa estar dentro de [inicio, fim] do painel, e o último `em` pelo menos 0,8 s antes do `fim`.
- Nunca escreva ids, nomes de estilo ou palavras como "painel", "evento", "gráfico 1" na tela.

## Som
- Abertura da divisão: `whoosh-medium-soft` (ou `swish-soft`) no `inicio`, volume 0.2–0.25 — coloque no campo `som` do evento. Em painéis encostados, só no primeiro.
- Volta à tela cheia: `whoosh-medium-soft` no `fim` do último painel do grupo + 0,1 s, volume 0.2 (em `efeitos_sonoros`). A volta acontece logo depois do `fim`.
- Durante o painel, um só som de dado, ~0,5 s depois do `inicio`: `data-chart-reveal` (gráfico), `data-countup-medium` (número), `data-bar-grow` (comparação), `data-tick` (tópicos, opcional). Volume 0.15–0.22.
- Nunca o mesmo som duas vezes no mesmo instante (não repita no `som` do evento e em `efeitos_sonoros`).
- Trilha (se marcada no card): corporativo ou tecnologia, energia média, abaixo da voz.

## Legenda
O estilo desenha a própria legenda: pílula escura com contorno verde, 1 linha, palavra falada em verde-claro. Em tela cheia ela fica abaixo do queixo; com a tela dividida ela pousa na linha da divisão, acima do cartão. Não mude o perfil. Corrija nomes e palavras em `correcoes`.

## Modo sem recorte
Este estilo não usa recorte da pessoa. Funciona igual em qualquer ambiente.

## Erros de amador (não faça)
- Dividir a tela em toda frase ou deixar dividida mais da metade do vídeo (perde o impacto e esconde a pessoa).
- Painel sem dado na fala (o palco tem que mostrar o que a pessoa está dizendo naquele instante).
- Inventar números, porcentagens ou datas que a pessoa não disse.
- Título longo que vira parágrafo; tópicos com frases inteiras.
- Painel que começa antes da palavra do dado ou termina no meio da frase.
- Painéis colados com intervalo de 1,5 a 3 s (a tela fecha e reabre logo em seguida: parece erro). Ou encoste (menos de 1,5 s) ou afaste (3 s ou mais).
- Som em todo movimento.

## Conferência antes de entregar
- [ ] Cada painel nasce de um dado real da fala, com `inicio` no tempo exato da palavra.
- [ ] `fim` = fim da fala do dado + 0,2 a 0,4 s; nos tópicos, o último `em` pelo menos 0,8 s antes do `fim`.
- [ ] Nenhum número, porcentagem, selo ou data que a pessoa não disse.
- [ ] Tela dividida no máximo ~50% do vídeo; tela cheia no resto.
- [ ] Na folha: rosto inteiro dentro do cartão, nada sobre olhos e boca, título e números inteiros (nada cortado).
- [ ] Português correto nos títulos, rótulos e legenda; nenhum texto interno.
- [ ] `problemas_no_plano` e `problemas` vazios; folha_previa e folha_resultado olhadas.
