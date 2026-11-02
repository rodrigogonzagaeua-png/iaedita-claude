---
name: iaedita-16-historia-de-capa
description: Direção profissional do estilo 16 · História de capa do IAEdita — o vídeo vira capa de revista, com um título enorme em serifa ATRÁS da pessoa (a cabeça passa na frente das letras), nome da revista e número da edição no alto, chamadas ao lado do rosto, moldura fina e legenda editorial. Use quando o cliente escolher "História de capa" (16-historia-de-capa) no card do IAEdita. Usa a pessoa recortada; sem recorte, o título fica acima da cabeça.
---

# Estilo 16 · História de capa

Antes: siga a skill principal `iaedita` (fluxo e regras de edição). Esta skill só ensina a DIREÇÃO deste estilo.

## A essência
Cada assunto da fala vira uma capa de revista. O título enorme (serifa elegante, maiúsculas) aparece de cima para baixo ATRÁS da pessoa: a cabeça cobre a parte de baixo da última linha, e a primeira linha fica inteira. No alto, o nome da revista e o número da edição; ao lado do rosto, chamadas curtas que surgem quando a pessoa fala delas; uma moldura fina fecha a página. A capa assenta, segura e se recolhe; entre capas o vídeo respira limpo.
Reconhecível por: **título gigante atrás da cabeça** e **página de revista que se monta e se desmonta no ritmo dos assuntos**.

O motor faz sozinho a parte técnica: mede o topo da cabeça, recua a câmera só o necessário (o vídeo encolhe um pouco e o fundo continua desfocado em volta), escolhe tinta escura ou creme pelo brilho do fundo, posiciona chamadas e legenda fora do rosto. Você decide O QUE vai na capa e QUANDO.

## Antes de planejar: o recorte
Este estilo precisa da pessoa recortada. Se ainda não existe `mascara.mkv` na pasta e o `editar` não avisou "sem recorte":
```bash
python3 "$ERG" recortar --pasta /tmp/erg
```
Olhe `folha_recorte.jpg`: o que não é pessoa deve estar magenta. Se o recorte não for possível, siga o "Modo sem recorte" abaixo.

## Leitura da fala: onde entram as capas
Leia a transcrição inteira (`palavras`) e divida a fala em **blocos de assunto** de 3 a 10 segundos.
- **Uma capa por assunto.** `inicio` = tempo da primeira palavra do assunto (copie de `palavras`). `fim` = quando o assunto acaba (antes do próximo).
- **Gancho:** a primeira capa começa nos primeiros 0,5 s, na primeira frase.
- **Título** = a ideia do bloco em 1 a 3 palavras, de preferência palavras que a pessoa diz. Curto é mais bonito: 1 palavra de até 8 letras fica enorme; palavra de 9-10 letras fica menor. Só letras (número vai na `edicao` ou numa chamada).
- **Chamadas** = itens, números, promessas e nomes ditos no bloco (1 a 3 palavras cada, no máximo 3 por capa). `em` = o segundo exato em que a palavra é dita.
- **Frase** = a frase de efeito do bloco, curta (até 30 letras), com `frase_em` = quando ela é dita.
- **Revista** = o nome da "revista", igual no vídeo inteiro, ligado ao tema (ex.: "Guia do criador", "Diário fitness", "Negócios em casa"). **Edição** = um número que apareça na fala ("26 vídeos" → "Nº 26") ou "Nº 01". Pode mudar entre capas se a fala trouxer outro número.

## Ritmo pela duração do vídeo
| Duração | Capas | Chamadas por capa | Tempo sem capa |
|---|---|---|---|
| até 15 s | 1–2 | 0–2 | pelo menos o último 1 s |
| 15–45 s | 3–5 | 1–3 | uns 20% do vídeo |
| 45–90 s | 5–8 | 1–3 | uns 20% do vídeo |
| 90 s+ | 1 a cada 10–15 s | 1–3 | uns 20% do vídeo |
- Cada capa dura de 3 a 10 s (mínimo 2,5 s; o título leva ~1 s para se revelar).
- Capas com menos de 1,6 s entre elas viram uma "página" só: a câmera fica parada e o nome da revista não pisca. Use isso para assuntos seguidos.
- Deixe pelo menos um respiro de 2 s ou mais sem capa no meio do vídeo (a câmera volta ao normal e o público descansa).
- Uma chamada (e a frase) precisa entrar pelo menos 0,8 s antes do `fim` da capa. Se a palavra é dita no finzinho, aumente o `fim` ou escolha uma palavra dita antes.
- Título de 1 linha: o motor garante que a cabeça nunca cubra mais que a metade de baixo das letras, mesmo quando a pessoa se inclina para a câmera (ele recua a câmera um pouco mais nessa capa).

## Adaptação ao enquadramento (olhe a folha_original.jpg)
- **Plano fechado** (rosto ocupa mais de 38% da largura, como no celular perto do rosto): o motor recua a câmera para a cabeça encaixar no título. As chamadas vão para o lado do rosto quando sobra coluna; se não sobrar, viram uma linha de rodapé logo abaixo da legenda, separadas por pontos verdes. Você não escolhe qual dos dois: escreva chamadas que funcionem nos dois lugares. Use títulos de 1 palavra curta e chamadas de **1 palavra** (no máximo 3 por capa): na coluna estreita, uma chamada de 2 palavras pode quebrar em 2 linhas ("Próximos / dias").
- **Plano médio**: chamadas ao lado do rosto, no lado com mais espaço. Títulos de 1 a 2 palavras.
- **Plano aberto** (pessoa pequena, cabeça baixa no quadro): o título desce até encostar na cabeça. Tudo funciona; prefira 2 linhas de título.
- Chamadas e frase ficam NA FRENTE da pessoa. Quando o que está atrás delas é a roupa da pessoa ou um fundo muito misturado, o motor põe sozinho uma placa escura translúcida atrás do texto (igual à da legenda). Isso é normal: não tente evitar.
- Se o terminal mostrar `[16-historia-de-capa] ... não couberam e foram omitidas`, encurte as chamadas ou use menos.
- Se o terminal mostrar `[16-historia-de-capa] não achei o caminho da máscara`, o recorte não chegou ao estilo: avise na entrega que o título pode ficar menos preciso.

## Eventos do plano
Um tipo só: `capa`.
```json
{
  "estilo": "16-historia-de-capa",
  "correcoes": {"broke": "quebrou", "estúdio": "STUDIO"},
  "eventos": [
    {"tipo": "capa", "inicio": 0.00, "fim": 4.40, "titulo": "Efeitos", "revista": "Guia do criador", "edicao": "Nº 17",
     "chamadas": [{"texto": "Órbita", "em": 0.00}, {"texto": "Parede do sofá", "em": 0.56}, {"texto": "Zoom digital", "em": 3.32}],
     "som": "props-page-turn", "som_volume": 0.28},
    {"tipo": "capa", "inicio": 5.28, "fim": 9.40, "titulo": "Estilos", "revista": "Guia do criador", "edicao": "Nº 17",
     "chamadas": [{"texto": "Lista de tarefas", "em": 5.28}, {"texto": "Gráfico", "em": 8.42}],
     "som": "props-page-turn", "som_volume": 0.22},
    {"tipo": "capa", "inicio": 17.04, "fim": 21.90, "titulo": "Vídeos novos", "revista": "Guia do criador", "edicao": "Nº 26",
     "chamadas": [{"texto": "26 vídeos", "em": 17.04}, {"texto": "Nos próximos dias", "em": 18.86}],
     "frase": "Quebrou a internet", "frase_em": 20.76, "som": "props-page-turn", "som_volume": 0.26}
  ],
  "efeitos_sonoros": [
    {"som": "impact-light-soft", "t": 0.80, "volume": 0.12},
    {"som": "foley-paper-slide", "t": 9.40, "volume": 0.18},
    {"som": "foley-paper-slide", "t": 21.90, "volume": 0.18}
  ]
}
```
| campo | o que é |
|---|---|
| `inicio`, `fim` | início e fim da capa (3 a 10 s), tempos copiados de `palavras` |
| `titulo` | 1 a 3 palavras, só letras, até 10 letras por palavra; o motor põe em maiúsculas |
| `revista` | nome da revista no alto, 1 a 4 palavras, até 26 letras; o mesmo no vídeo todo |
| `edicao` | opcional, até 10 letras, ex.: "Nº 26" |
| `chamadas` | opcional, lista de 0 a 3 itens `{"texto": "...", "em": segundo}`; texto de 1 a 3 palavras, até 18 letras |
| `frase` | opcional, frase curta em serifa (até 30 letras) |
| `frase_em` | opcional, segundo em que a frase é dita (sem ele, ela entra logo depois das chamadas) |
| `letras` | "auto" (padrão: o motor escolhe pelo brilho do fundo), "escuras" (fundo claro) ou "claras" (fundo escuro). Deixe "auto" |
| `lado` | "auto" (padrão), "esquerda" ou "direita": lado das chamadas no plano médio |
| `som`, `som_volume` | "props-page-turn", 0.22 a 0.30 |

## Som
- Cada capa: `"som": "props-page-turn"` (página virando), volume 0.22–0.30. O som bate no `inicio` da capa, junto com a revelação do título.
- Assentamento: em `efeitos_sonoros`, `impact-light-soft` (volume 0.10–0.14) cerca de 0,8 s depois do início da PRIMEIRA capa de cada página. Não repita em toda capa.
- Saída: `foley-paper-slide` (volume 0.15–0.20) no `fim` da última capa de cada página.
- Mais nada: este estilo é elegante e silencioso. Trilha (se marcada no card): clima "leve" ou "corporativo", energia baixa ou média.

## Legenda
O estilo desenha a própria legenda editorial (serifa Cormorant 700 creme em bloco escuro, fio verde-limão no alto, palavra falada em verde-limão), alinhada à esquerda a 65% da altura; ela desce sozinha se a boca estiver baixa. Não mude o perfil. Para desligar: `"legenda": {"ativa": false}`.

## Modo sem recorte
Sem `mascara.mkv`, o motor não consegue pôr a cabeça na frente das letras. Ele então deixa o título INTEIRO acima da cabeça (recuando a câmera um pouco mais) e nada passa sobre olhos ou boca. O plano é o mesmo. Avise o cliente em uma frase: "Neste ambiente não deu para recortar você do fundo, então o título da capa ficou acima da sua cabeça em vez de atrás."

## Erros de amador (não faça)
- Título com frase inteira, palavra longa demais ou número ("26 VÍDEOS"): o título é gigante; número vai na `edicao` ou numa chamada.
- Capa no vídeo inteiro, sem respiro.
- Nome da revista diferente em cada capa (é UMA revista), ou com nome do estilo, do arquivo ou códigos internos.
- Chamadas compridas, mais de 3 por capa, ou repetindo a legenda palavra por palavra.
- Tempo de chamada (`em`) chutado em vez do tempo real da palavra.
- Capa que começa muito depois de o assunto começar.
- Forçar `letras` sem necessidade (o "auto" já garante contraste).

## Conferência antes de entregar
Na prévia, inclua instantes logo depois de cada `inicio` + 1 s (título já revelado), por exemplo:
`python3 "$ERG" previa --pasta /tmp/erg --tempos 1.5,6.5,13.5,19.0,24.0`
- [ ] Primeira capa nos 3 primeiros segundos; capas espalhadas até o fim, ligadas a assuntos reais.
- [ ] A cabeça passa NA FRENTE da parte de baixo do título e a primeira linha está inteira (com recorte).
- [ ] Título legível, nada sobre olhos ou boca, nada cortado nas bordas, nada colado na direita.
- [ ] Chamadas aparecem quando são ditas; nenhum aviso de "omitida" no terminal.
- [ ] Português correto (acentos, nomes) e nenhum texto interno na tela.
- [ ] `problemas_no_plano` vazio; `folha_resultado.jpg` olhada; `problemas` vazio.
