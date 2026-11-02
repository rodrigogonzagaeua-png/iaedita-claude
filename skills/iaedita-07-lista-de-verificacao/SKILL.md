---
name: iaedita-07-lista-de-verificacao
description: Direção profissional do estilo 07 · Lista de verificação do IAEdita — painel escuro com 2 a 6 itens tirados da fala, marcados um a um (círculo verde-limão com check e som de tique) no instante em que a pessoa fala cada item, com contador "2 de 5", barra de progresso e legenda clara com sublinhado na palavra falada. Use quando o cliente escolher "Lista de verificação" (07-lista-de-verificacao) no card do IAEdita. Funciona com qualquer vídeo; não precisa recortar a pessoa.
---

# Estilo 07 · Lista de verificação

Antes: siga a skill principal `iaedita` (fluxo e regras de edição). Esta skill só ensina a DIREÇÃO deste estilo.

## A essência
A fala vira uma lista de tarefas que se completa na frente do público. Um painel escuro mostra o título e os itens; cada item acende um pouco antes de ser dito e ganha o check verde-limão (com um "tique") **no instante exato** em que a pessoa fala aquilo. O contador ("3 de 5") e a barra de progresso andam junto. Dá sensação de método, clareza e avanço.
Reconhecível por: **painel escuro com cantos arredondados, círculos que viram check verde-limão, contador no canto e barra fina embaixo**; legenda numa caixa clara com o texto escuro à esquerda e um sublinhado verde-oliva que corre embaixo da palavra falada.

O motor faz sozinho: posição do painel fora do rosto, tamanho, quantas linhas cabem, rolagem quando há mais itens, subida suave da câmera em plano fechado, legenda. Você só decide **o que entra na lista e quando cada item é marcado**.

## Leitura da fala: de onde saem as listas
Rode `palavras` e leia a fala inteira. Procure:
- **Enumerações ditas**: "três coisas", "primeiro… segundo…", "passo 1, passo 2", "você precisa de X, Y e Z", uma sequência de nomes, dicas, ferramentas, etapas.
- **Erros / o que NÃO fazer** ("não faça", "pare de", "o erro é"): mesma lista, mas com `"simbolo": "x"` (círculo rosa com X).
- **Sem lista explícita?** Monte a lista com as ideias principais da fala, na ordem em que aparecem. Cada ideia vira um item curto; a marca entra na palavra-chave daquela ideia.

Como escrever:
- **Título** (`titulo`): 2 a 4 palavras que resumem a lista, sem ponto final. Ex.: "3 erros comuns", "Antes de gravar", "17 efeitos de vídeo".
- **Itens** (`itens`): 1 a 4 palavras cada (até 24 letras), com as palavras da pessoa, todos no mesmo formato (todos verbos: "Grave", "Edite", "Poste" — ou todos nomes). Na ordem em que são ditos.
- **Marca** (`marca`): `inicio` = o tempo de início da palavra que nomeia o item, tirado de `palavras`. Nunca chute tempos. Se o nome do item tem duas palavras ("Parede do sofá"), use a palavra mais forte.
- Nada de texto interno: nunca "Item 1", "Lista A", "Passo X", ids ou nomes de estilo.

## Ritmo pela duração do vídeo
| Duração | Listas | Itens por lista | Observação |
|---|---|---|---|
| até 15 s | 1 | 2–4 | a lista pode ocupar quase o vídeo todo |
| 15–45 s | 1–2 | 3–6 | uma lista por assunto |
| 45–90 s | 2–4 | 3–6 | deixe trechos só com legenda entre as listas |
| 90 s+ | 1 a cada 25–40 s | 3–6 | |
Regras de tempo:
- A **primeira lista abre nos 3 primeiros segundos**. Se a fala anuncia o assunto logo no começo mas só fala os itens depois, abra a lista no anúncio (modo `junto`: os itens ficam apagados esperando) e marque cada um quando for dito.
- A lista começa **pelo menos 0,3 s antes da primeira marca** (ideal 0,5–1 s: na frase que anuncia a lista).
- A lista termina **0,8–1,5 s depois da última marca** (mínimo 0,6 s) para o público ver tudo marcado. Não deixe a lista na tela depois que o assunto mudou.
- Marcas com **pelo menos 0,25 s** entre uma e outra.
- **Mais de 6 itens ditos em sequência** (ex.: um catálogo de 17 nomes): divida em listas seguidas de até 6 itens. Uma pode começar no mesmo instante em que a anterior termina (vira uma "troca de página"). Ex.: "17 efeitos de vídeo" (5 itens) → "Mais 6 efeitos" → "Os últimos 6".
- Lista mínima: 1,6 s. Listas não podem se sobrepor.

## Adaptação ao enquadramento (olhe a folha_original.jpg)
O motor mede o rosto e escolhe sozinho; você confere na prévia.
- **Plano fechado** (rosto grande, como o cliente real): o painel fica no peito, entre o queixo e a legenda. A câmera **sobe de leve** (zoom de 5–15%, ancorado embaixo) enquanto a lista está na tela, para abrir espaço; pode cortar um pouco o topo do cabelo/boné — é normal em close. Cabem 3 linhas; com mais itens a lista **rola sozinha**, mostrando o item marcado e o próximo. Prefira itens curtos (até 18 letras). Se o topo da cabeça for importante (ex.: penteado, chapéu do produto), use `"camera": "fixa"` (cabem menos linhas).
- **Plano médio**: painel abaixo do queixo, 3–4 linhas visíveis, sem mexer na câmera.
- **Plano aberto** (pessoa pequena, espaço acima da cabeça): use `"posicao": "topo"` se a pessoa segura algo no peito; senão deixe `auto`.
- Se o lugar pedido em `posicao` não comportar a lista, o motor escolhe outro sozinho.
- Rosto enorme (quase a tela toda): o motor esconde a legenda enquanto o painel está na tela. Avise o cliente em uma frase só se isso acontecer em mais da metade do vídeo.

## Eventos do plano
```json
{
  "estilo": "07-lista-de-verificacao",
  "correcoes": {"Instagran": "Instagram"},
  "eventos": [
    {"tipo": "lista", "inicio": 0.40, "fim": 7.90, "titulo": "Antes de gravar",
     "itens": ["Luz na frente", "Celular na altura", "Fale com uma pessoa"],
     "som": "interface", "som_volume": 0.2},
    {"tipo": "marca", "inicio": 1.62, "fim": 1.92, "som": "tique", "som_volume": 0.3},
    {"tipo": "marca", "inicio": 3.95, "fim": 4.25, "som": "tique", "som_volume": 0.3},
    {"tipo": "marca", "inicio": 6.80, "fim": 7.10, "som": "tique", "som_volume": 0.3},

    {"tipo": "lista", "inicio": 14.10, "fim": 21.30, "titulo": "Erros que travam", "chamada": "NÃO FAÇA ISSO",
     "revelar": "um_a_um", "itens": ["Gravar contra a luz", "Começar devagar"],
     "som": "interface", "som_volume": 0.2},
    {"tipo": "marca", "inicio": 15.02, "fim": 15.32, "simbolo": "x", "som": "tique", "som_volume": 0.3},
    {"tipo": "marca", "inicio": 19.48, "fim": 19.78, "simbolo": "x", "som": "tique", "som_volume": 0.3}
  ]
}
```
| tipo | campos |
|---|---|
| `lista` | `inicio`, `fim`, `titulo` (2–4 palavras, até 24 letras), `itens` (lista de 2 a 6 textos, até 24 letras cada, na ordem da fala), `chamada` (opcional: linha pequena em maiúsculas acima do título, até 22 letras; só aparece se houver espaço), `revelar` "junto" (padrão: todos os itens aparecem apagados e acendem um a um) ou "um_a_um" (cada item entra quando vai ser dito e o painel cresce — use quando os itens são surpresa), `posicao` "auto" (padrão)/"baixo"/"topo", `camera` "auto" (padrão)/"fixa", `som` |
| `marca` | `inicio` (início da palavra que nomeia o item), `fim` (= `inicio` + 0,3), `item` (opcional: número do item, 1 = primeiro; sem ele marca o próximo da lista), `simbolo` "check" (padrão) ou "x" (erro / o que não fazer), `som` |
- Uma `marca` por item, dentro do intervalo da sua `lista`. Sem `item`, as marcas seguem a ordem dos itens.
- Item sem marca fica sem check (use só se a pessoa realmente não concluir aquele item).
- Prefira `revelar: "junto"` (é o visual da prévia aprovada). Use "um_a_um" em no máximo metade das listas.

## Som
- `lista`: `"som": "interface"`, volume 0.18–0.22 (o painel abrindo).
- `marca`: `"som": "tique"`, volume 0.3, em TODA marca. Lista muito rápida (marcas a menos de 0,5 s): volume 0.22.
- Na última marca da lista mais importante do vídeo pode usar `"ding"` volume 0.14 (no máximo 1–2 por vídeo).
- Não use whoosh nos itens. Para não ter som de propósito, escreva `"som": "nenhum"`.
- Trilha (se marcada no card): calma ou média, abaixo da voz (o motor faz o ducking).

## Legenda
O estilo desenha a própria legenda (caixa clara, texto escuro à esquerda, sublinhado verde-oliva que cresce durante a palavra falada), na base da zona segura, alinhada com o painel. Não mude o perfil. Corrija nomes na transcrição com `correcoes`.

## Sem recorte
Este estilo não usa a pessoa recortada: funciona igual com ou sem `recortar`. Não rode o recorte só para ele.

## Erros de amador (não faça)
- Marcar o item antes de a pessoa falar (estraga a surpresa) ou muito depois (parece atrasado). A marca é na palavra.
- Itens longos que repetem a frase inteira, ou a legenda palavra por palavra.
- Inventar itens que a pessoa não disse, ou traduzir/trocar o sentido.
- Mais de 6 itens numa lista só, ou duas listas sobrepostas.
- Lista que fica na tela depois que o assunto mudou; lista em todo segundo do vídeo (deixe respiros só com legenda).
- Formatos misturados ("Luz", "Ajustar a câmera", "Falar bem").
- Usar "x" para coisas boas, ou check para erros.
- Marca sem som, ou com som diferente a cada item.

## Conferência antes de entregar
- [ ] Primeira lista nos 3 primeiros segundos; listas ligadas a falas reais até o fim do vídeo.
- [ ] Cada marca no tempo da palavra certa (confira em `palavras`); uma marca por item.
- [ ] Na prévia, use `--tempos` com instantes logo depois de algumas marcas (marca + 0,4 s) e o fim de cada lista: o item certo está marcado, o contador bate ("3 de 5").
- [ ] Painel e legenda fora da boca e dos olhos, nada cortado; título e itens em português correto, sem rótulos internos.
- [ ] `problemas_no_plano` e `problemas` vazios; folha_resultado olhada.
