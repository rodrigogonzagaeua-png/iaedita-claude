---
name: iaedita-01-orbita
description: Direção profissional do estilo 01 · Órbita do IAEdita — cartões de papel que giram ao redor da pessoa, passam por TRÁS da cabeça e param na frente dela, abaixo do queixo, no instante em que a palavra é dita. Use quando o cliente escolher "Órbita" (01-orbita) no card do IAEdita. Usa a pessoa recortada (comando recortar); sem recorte, o motor faz uma versão sem passar por trás.
---

# Estilo 01 · Órbita

Antes: siga a skill principal `iaedita` (fluxo e regras de edição). Esta skill só ensina a DIREÇÃO deste estilo.

## A essência
Cartões de papel claro (texto escuro, um rótulo pequeno em cima e uma barrinha verde-limão embaixo) giram num anel ao redor da pessoa. Cada cartão vem para a frente e PARA abaixo do queixo exatamente quando a pessoa fala aquela palavra; fica ali para ser lido enquanto os outros esperam inteiros dos lados da cabeça; depois o anel gira e o próximo vem para a frente, passando por trás da cabeça. Um anel fino marca o caminho.
Reconhecível por: **profundidade real (o cartão passa atrás da pessoa)**, **um cartão por ideia, grande e legível na frente**, e **uma lista que vai se montando no ritmo da fala**.

O motor já faz sozinho: o tamanho dos cartões, o caminho do anel conforme o rosto, a troca frente/trás, a barra que cresce quando o cartão chega, a posição da legenda e a proteção do rosto (nada passa na frente dos olhos e da boca). Você escolhe QUAIS palavras viram cartão e QUANDO.

## Leitura da fala: onde entram os cartões
Leia a fala inteira (`python3 "$ERG" palavras --pasta /tmp/erg`) e marque:
- **Listas e enumerações** ("três coisas", "primeiro… segundo…", nomes em sequência): é o gatilho principal. Cada item = um cartão, na mesma órbita (até 3).
- **Comparações** ("antes / depois", "errado / certo", "caro / barato"): uma órbita com 2 cartões.
- **Números e resultados** ("10 mil", "3 meses", "26 vídeos"): cartão com o número; o rótulo diz o que é ("FATURAMENTO", "EM 3 MESES").
- **Nomes de ferramentas, marcas, pessoas ou conceitos-chave**: cartão com o nome certo (corrija a grafia).
- **Chamada final** ("comenta", "segue", "salva"): um `titulo` curto ou uma órbita com 1 a 3 cartões ("Siga", "Comente", "Salve").
- **Gancho (primeiros 3 s):** sempre algo na tela até 3 s: uma órbita cujo 1º cartão é a primeira palavra forte, OU um `titulo` com a promessa do vídeo (2 a 5 palavras da fala).

Regra de ouro: o `inicio` da órbita e o `em` de cada cartão são o **tempo exato do início da palavra** em `palavras`. Nunca chute tempos.

## Ritmo pela duração do vídeo
| Duração | Órbitas | Cartões no total | Títulos |
|---|---|---|---|
| até 15 s | 1–2 | 2–5 | 0–1 |
| 15–45 s | 2–4 | 5–10 | 0–1 |
| 45–90 s | 4–7 | 10–18 | 1–2 |
| 90 s+ | 1 a cada 12–18 s | 2–3 por órbita | 1 a cada 45 s |
- Cada órbita dura de 3 a 8 s (mínimo 1,6 s) e tem de 1 a 3 cartões (máximo 4; 3 é o ideal).
- Entre um cartão e o próximo: ideal 1,2 a 3 s (mínimo 0,7 s).
- Depois do último cartão, deixe pelo menos 0,8 s (ideal 1 a 1,5 s) até o `fim` da órbita: é o tempo de leitura dele.
- Entre o `fim` de uma órbita e o `inicio` da próxima: pelo menos 0,75 s (a órbita entra 0,7 s antes do `inicio`). Ideal 1,5 a 4 s de respiro.
- Espalhe as órbitas pelo vídeo inteiro, mas não cubra 100% do tempo: trechos sem cartão fazem o próximo ter impacto.
- Nos últimos segundos, se a pessoa só se despede, termine limpo (sem órbita).

## Adaptação ao enquadramento (olhe a folha_original.jpg)
O motor ajusta o anel sozinho; você ajusta a QUANTIDADE e o TAMANHO dos textos.
- **Plano fechado** (rosto ocupa mais de ~38% da largura, como selfie): o anel passa atrás da boca e do queixo; o cartão da frente fica entre o queixo e a legenda. Não sobra espaço ao lado da cabeça, então os outros cartões aparecem só enquanto giram (passando por trás da cabeça) e ficam escondidos enquanto o cartão da frente é lido — nunca fica palavra pela metade na tela. Use textos de 1 a 2 palavras, até 12 letras (cartão grande, com rótulo). Prefira 3 cartões por órbita (o giro entre eles é o que mostra a órbita).
- **Plano fechado demais** (queixo abaixo de 2/3 da altura do vídeo): 1 a 2 cartões por órbita, 1 palavra cada.
- **Plano médio** (rosto entre 20% e 38% da largura): o padrão, como na prévia. Enquanto um cartão é lido, os outros ficam INTEIROS dos dois lados da cabeça (um pouco menores). 3 cartões por órbita. Textos de até 12 letras deixam os cartões de lado caberem; com textos mais longos (até 18 letras) o motor esconde os de lado enquanto o da frente é lido.
- **Plano aberto** (pessoa de corpo inteiro ou longe): funciona como na prévia; a legenda vai sozinha para cima da cabeça quando há espaço.

## Eventos do plano
```json
{
  "estilo": "01-orbita",
  "correcoes": {"Instagran": "Instagram"},
  "eventos": [
    {"tipo": "titulo", "inicio": 0.00, "fim": 2.40, "texto": "3 erros que travam vendas",
     "som": "papel", "som_volume": 0.35},
    {"tipo": "orbita", "inicio": 3.20, "fim": 9.80, "som": "whoosh", "som_volume": 0.3, "som_atraso": -0.6,
     "cartoes": [
       {"texto": "Preço baixo", "rotulo": "Erro 1"},
       {"texto": "Sem oferta", "rotulo": "Erro 2", "em": 5.42},
       {"texto": "Pouco vídeo", "rotulo": "Erro 3", "em": 8.05}
     ]},
    {"tipo": "orbita", "inicio": 13.36, "fim": 17.60, "som": "whoosh", "som_volume": 0.3, "som_atraso": -0.6,
     "cartoes": [
       {"texto": "R$ 2 mil", "rotulo": "Antes"},
       {"texto": "R$ 10 mil", "rotulo": "Depois", "em": 15.90}
     ]}
  ],
  "efeitos_sonoros": [
    {"som": "whoosh-curto", "t": 5.17, "volume": 0.3},
    {"som": "whoosh-curto", "t": 7.80, "volume": 0.3},
    {"som": "whoosh-curto", "t": 15.65, "volume": 0.3}
  ]
}
```
| tipo | campos |
|---|---|
| `orbita` | `inicio` = início da palavra do 1º cartão (ele chega na frente nesse instante; a órbita aparece 0,7 s antes). `fim` = quando a órbita já sumiu (ela some nos últimos ~0,5 s). `cartoes`: lista de 1 a 3 cartões — **prefira 3**. Com 2 cartões, o 2º espera de um lado e, depois que chega, o 1º fica do outro lado (bom para comparação: antes/depois). Use 2 só em comparações. `sentido` (opcional): 1 = cartões vêm da direita, -1 = da esquerda; se omitir, o motor alterna sozinho a cada órbita. `som`, `som_volume`, `som_atraso`. |
| cartão (dentro de `cartoes`) | `texto`: 1 a 3 palavras, até 18 letras (ideal até 12 = uma linha). `rotulo` (opcional): 1 a 2 palavras que dão contexto, até 14 letras (o motor escreve em maiúsculas). `em`: início da palavra deste cartão (o 1º cartão usa o `inicio` da órbita e não precisa de `em`). Sem `em`, o motor espalha os cartões por igual. |
| `titulo` | `inicio`, `fim` (1,5 a 3,5 s), `texto` (2 a 5 palavras da fala, sem ponto final), `som`. Placa de papel grande; o motor põe acima da cabeça se houver espaço, senão entre o queixo e a legenda. **Nunca ao mesmo tempo que uma órbita.** |

### Como escrever os cartões
- O texto do cartão é a palavra-chave que a pessoa FALA naquele instante (pode encurtar: "vinte e seis vídeos" → "26 vídeos").
- Ideal: até 12 letras. Cartão curto fica maior na frente e cabe inteiro ao lado da cabeça.
- Nomes de produtos ou termos em outra língua: escreva como a pessoa falou ("Couch Wall", "Greenscreen"). Se passar de 12 letras, use só a palavra principal ("Headline Wall" → "Headlines").
- O rótulo responde "o que é isso?": "Erro 1", "Passo 2", "Antes", "Depois", "Resultado", "Ferramenta", "Em 3 meses". Pode ficar sem rótulo.
- Português correto, com acentos. Números em algarismos ("10 mil", "3 passos").
- Proibido: ids, nomes de estilo ou de arquivo ("ÓRBITA 01", "01-orbita", "cartão 2"), placeholders ("Seu texto aqui") e frases inteiras.

## Som
- Na órbita: `"som": "whoosh"`, `"som_volume": 0.3`, `"som_atraso": -0.6` (o ar passa enquanto o 1º cartão entra). Se a órbita começa no segundo 0, o som é pulado sozinho.
- Para cada cartão seguinte (do 2º em diante): em `efeitos_sonoros`, `{"som": "whoosh-curto", "t": ..., "volume": 0.3}` com `t` = `em` do cartão **menos 0,25** (é quando o giro está mais rápido; ex.: em 5.42 → t 5.17).
- No título: `"som": "papel"`, `"som_volume": 0.35`.
- Ar curto e leve, sempre abaixo da voz. Em vídeos com muitos cartões (mais de 8), use o whoosh-curto só em cartões alternados.
- Trilha (se marcada no card): calma ou média, abaixo da voz (o motor abaixa sozinha quando a pessoa fala).

## Legenda
O perfil do estilo já vem pronto: Inter 800, uma linha, caixa escura, palavra falada em verde-limão. O motor coloca a legenda **acima da cabeça** quando há espaço (como na prévia aprovada) e **embaixo** (abaixo do cartão da frente) quando o rosto está perto da câmera. Não mude a posição nem o tamanho.

## Sem recorte
Se `recortar` falhar ou o ambiente não tiver o programa de recorte, renderize assim mesmo: o motor troca a órbita por um carrossel abaixo do queixo.
Sem recorte, a prévia mostra em `avisos` o aviso "Sem máscara da pessoa…". **Esse aviso é esperado: ignore-o.** `problemas_no_plano` precisa vir vazio. Os cartões vêm pelas laterais, param na frente com sombra e nunca cobrem o rosto, mas não passam por trás da pessoa. Na entrega, avise em uma frase: "Neste ambiente não deu para recortar você do fundo, então os cartões giram na sua frente, sem passar por trás."
O plano é o mesmo; não mude nada.

## Erros de amador (não faça)
- Cartão com frase inteira, ou texto que não tem nada a ver com o que está sendo dito naquele segundo.
- Órbita do começo ao fim do vídeo, sem respiro.
- 4 ou mais cartões numa órbita, ou cartões a cada 0,5 s (ninguém consegue ler).
- `em` chutado (o cartão chega antes ou depois da palavra).
- Rótulos internos ou de sistema na tela ("ÓRBITA 01", "CARTÃO 2", "EVENTO").
- Título junto com órbita (vira bagunça na frente da pessoa).
- Textos longos em plano fechado (o cartão encolhe e perde o rótulo).
- Órbita de 2 cartões fora de comparação (prefira 3: o giro entre eles é a identidade do estilo).
- Whoosh alto em todo cartão (vira barulho e briga com a voz).

## Conferência antes de entregar
- [ ] Algo na tela nos 3 primeiros segundos (1º cartão ou título).
- [ ] Rode a prévia nos instantes em que os cartões chegam e no meio das leituras: `python3 "$ERG" previa --pasta /tmp/erg --tempos 3.2,4.3,5.42,6.7,8.05,13.36` (use os seus `inicio`/`em` e um instante entre eles). Na chegada, o cartão certo está na frente, inteiro, legível, com rótulo, abaixo do queixo. No meio da leitura, nenhum cartão aparece pela metade (cada cartão de lado está inteiro ou não aparece).
- [ ] Nenhum cartão, título ou anel na frente dos olhos ou da boca; nada cortado pela borda.
- [ ] Os cartões passam por trás da cabeça (se houve recorte). Em plano médio, os de lado aparecem inteiros ao lado da cabeça; em plano fechado, só aparecem enquanto giram (isso é o normal).
- [ ] Órbitas espalhadas até o fim da fala, com respiro entre elas.
- [ ] `problemas_no_plano` vazio na prévia (sem recorte, o aviso "Sem máscara da pessoa" em `avisos` é esperado) e `problemas` vazio no resultado; folha_resultado olhada.
