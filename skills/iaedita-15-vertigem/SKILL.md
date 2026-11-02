---
name: iaedita-15-vertigem
description: Direção profissional do estilo 15 · Vertigem do IAEdita — efeito "dolly zoom" de cinema, em que o fundo cresce (ou recua), balança e gira de leve enquanto a pessoa fica parada, do mesmo tamanho, no mesmo lugar; título estável em placa clara e legenda fixa. Use quando o cliente escolher "Vertigem" (15-vertigem) no card do IAEdita. Usa a pessoa recortada (comando recortar); sem recorte, o motor faz sozinho uma versão suave. Fica perfeito com fundo limpo.
---

# Estilo 15 · Vertigem

Antes: siga a skill principal `iaedita` (fluxo e regras de edição). Esta skill só ensina a DIREÇÃO deste estilo.

## A essência
É o efeito "vertigem" do cinema (dolly zoom): nas frases de peso, o AMBIENTE atrás da pessoa vem para a frente (ou recua), desliza um pouco de lado e gira de leve em perspectiva, enquanto a PESSOA fica exatamente igual, parada. A sensação é de "o mundo mudou em volta dela". No auge, o fundo também desfoca e escurece de leve, então a pessoa "salta" da tela. Um título curto, em placa creme com traço verde-limão, crava a ideia e fica parado enquanto o fundo se mexe.
Reconhecível por: **pessoa imóvel com o fundo mudando de tamanho**, **movimento lento e curvo (vai, chega no auge, volta)**, **poucos títulos, parados e muito legíveis**.

O motor já faz sozinho: separar a pessoa do fundo, tapar o lugar dela no fundo, o zoom do ambiente, o balanço e o giro (alterna o lado a cada vertigem), o desfoque e a vinheta, a entrada e a saída suaves, o reforço do efeito em plano fechado, manter a parte de baixo do quadro (do queixo para baixo: tronco, mãos, objeto na mão) igual ao original para nada duplicar, a posição do título (no alto à esquerda se couber acima da cabeça; senão embaixo, fora do rosto e da legenda) e a legenda. Você escolhe QUANDO o fundo se mexe, de que FORMA e com que FORÇA.

## Antes de planejar: olhe o fundo e o recorte
Este estilo precisa da pessoa recortada (`recortar`). Confira três coisas:
1. **folha_original.jpg — o fundo.** Fundo limpo (parede, cortina, estante arrumada, ambiente com pouca coisa) = efeito perfeito. Fundo bagunçado (muitos objetos miúdos, gente passando atrás, câmera na mão tremendo, rua) = use `"suave": true` em todas as vertigens e avise o cliente em uma frase na entrega: "Seu fundo tem muitos detalhes, então deixei a vertigem mais suave e desfocada para ficar bonita."
2. **folha_recorte.jpg — o recorte.** O que não é pessoa deve estar magenta. Se o recorte **corta o corpo numa linha reta**, deixa **mãos ou um objeto na mão de fora** (celular, produto, cartaz), ou deixa **pedaços do fundo grudados** na pessoa, use `"recorte": false` nas vertigens daquele trecho (versão suave, sem depender do recorte). Se o problema aparece só numa parte do vídeo (ex.: só enquanto ela segura um objeto), ponha `"recorte": false` só nas vertigens dessa parte. Avise o cliente em uma frase.
3. **Objeto na mão ou mãos na frente do corpo.** A folha_recorte pode parecer boa e o defeito só aparecer quando o fundo se mexe. Se a pessoa segura um objeto (celular, produto, cartaz) ou gesticula na frente do corpo, rode a prévia nos picos (`--tempos`) e procure, na altura do queixo e do rosto, um contorno duplicado, um "painel fantasma" ou uma mancha ao lado do objeto. Do queixo para baixo o motor já protege sozinho; o risco é o objeto erguido perto do rosto. Se aparecer, use `"recorte": false` nas vertigens daquele trecho.

## Leitura da fala: onde entra a vertigem
Leia a fala inteira (`python3 "$ERG" palavras --pasta /tmp/erg`) e marque:
- **Gancho (primeiros 3 s):** sempre uma vertigem `ida-e-volta` começando na primeira frase, com o `pico` na palavra mais forte dela, e um `titulo` com a promessa do vídeo (2 a 5 palavras da fala).
- **Viradas e revelações** ("mas", "só que", "na verdade", "aí eu percebi", "foi quando"): `ida-e-volta` com o `pico` na palavra da virada. É o gatilho principal deste estilo.
- **Sensação de peso, choque ou pressão** ("tudo mudou", "eu travei", "perdi tudo", "ninguém acreditou", números grandes): `segurar` — o fundo vem, fica perto enquanto a frase dura, e volta.
- **Uma palavra-soco** ("zero", "nunca", "pronto", "acabou", um número): `pulso` — empurrão curto e seco do fundo na palavra.
- **Distância, solidão, perda, "sair de cena"** ("fiquei sozinho", "desapareceu", "longe", "do nada", "caiu"): `direcao: "afastar"` — o fundo recua. É o mais dramático: no máximo 1 a cada 20 s.
- **Ideia central** (1 a cada 10-20 s): `titulo` com 2 a 5 palavras do próprio falante, mais curto que a frase. Junto com uma vertigem fica ainda melhor (o título parado contra o fundo em movimento é a assinatura do estilo).

Regra de ouro: o `pico` (ou o `inicio` do `pulso`) é o **tempo exato do início da palavra** em `palavras`. Nunca chute tempos.

## Ritmo pela duração do vídeo
| Duração | Vertigens | Títulos | Fortes (intensidade 3 ou afastar) |
|---|---|---|---|
| até 15 s | 2–3 | 1 | 0–1 |
| 15–45 s | 3–6 | 1–3 | 1–2 |
| 45–90 s | 6–10 | 2–4 | 2–3 |
| 90 s+ | 1 a cada 8–12 s | 1 a cada 25–30 s | 1 a cada 25 s |
- O fundo deve se mexer em **25% a 45% do vídeo** (some as durações das vertigens). Mais de 60% o motor reprova (cansa e enjoa).
- Entre o `fim` de uma vertigem e o `inicio` da próxima: mínimo 0,8 s; ideal 2 a 5 s de fundo parado.
- Alterne as formas (ida-e-volta, segurar, ida-e-volta, pulso…) e as intensidades (2, 1, 3, 2…).
- Nos últimos segundos, se a pessoa só se despede, termine limpo ou com uma `ida-e-volta` leve (intensidade 1).

## Como montar cada vertigem (tempos)
| forma | duração | onde ficam os tempos |
|---|---|---|
| `ida-e-volta` (padrão) | 1,5–5 s (mín. 1,2; máx. 6) | `inicio` = começo da frase (0,6–1,5 s antes da palavra forte); `pico` = início da palavra forte; `fim` = 0,8–1,5 s depois do pico |
| `segurar` | 2–7 s (mín. 1,6; máx. 8) | `inicio` = palavra que abre a frase de peso; `fim` = fim da frase. O fundo leva ~1 s para chegar e ~0,8 s para voltar |
| `pulso` | 0,6–1,6 s (mín. 0,5; máx. 1,8) | `inicio` = início da palavra-soco; `fim` = 0,6–1,2 s depois. O fundo chega em 0,3 s |

Intensidade: 1 = leve (fundo cresce ~16%), 2 = médio (~28%, padrão), 3 = forte (~42%). Em `afastar`, o fundo encolhe 7%, 12% ou 16%.

## Adaptação ao enquadramento (olhe a folha_original.jpg e o `"plano"` em analise.json)
- **Plano fechado** (rosto grande, mais de ~38% da largura — o caso mais comum do cliente): sobra pouco fundo à vista. O motor já aumenta sozinho o empurrão (~30% a mais), o desfoque e a vinheta. Prefira `ida-e-volta` e `segurar` com intensidade 2–3; `pulso` aparece menos. O título vai sozinho para baixo da legenda (não há espaço acima da cabeça) — isso é o certo.
- **Plano médio** (rosto 20–38% da largura): tudo funciona. O título fica no alto, à esquerda, como na prévia do estilo, quando a cabeça deixa espaço.
- **Plano aberto** (pessoa pequena, muito fundo): o efeito fica muito forte. Use intensidade 1–2; 3 só no auge do vídeo. `afastar` fica lindo aqui.
- Se a fala aponta para algo no fundo (um quadro, um produto na estante), use `"centro": [x, y]` (frações 0–1 do quadro) naquela vertigem para o fundo crescer a partir dali.

## Eventos do plano
```json
{
  "estilo": "15-vertigem",
  "correcoes": {"Instagran": "Instagram"},
  "eventos": [
    {"tipo": "vertigem", "inicio": 0.10, "fim": 2.60, "forma": "ida-e-volta", "intensidade": 2, "pico": 1.42, "som": "whoosh-slow-soft", "som_atraso": 1.32, "som_volume": 0.22},
    {"tipo": "titulo", "inicio": 0.30, "fim": 3.40, "texto": "Pare de postar todo dia"},
    {"tipo": "vertigem", "inicio": 9.84, "fim": 12.90, "forma": "segurar", "intensidade": 2, "som": "subida", "som_atraso": 1.0, "som_volume": 0.18},
    {"tipo": "vertigem", "inicio": 17.06, "fim": 18.10, "forma": "pulso", "intensidade": 3, "som": "grave", "som_volume": 0.2},
    {"tipo": "titulo", "inicio": 17.10, "fim": 19.80, "texto": "Zero clientes"},
    {"tipo": "vertigem", "inicio": 24.40, "fim": 27.00, "forma": "ida-e-volta", "direcao": "afastar", "intensidade": 1, "som": "descida", "som_volume": 0.2}
  ]
}
```
| tipo | campos |
|---|---|
| `vertigem` | `inicio`, `fim`, `forma` ("ida-e-volta" padrão / "segurar" / "pulso"), `intensidade` 1/2/3 (padrão 2), `direcao` ("aproximar" padrão = o fundo vem para a frente / "afastar" = o fundo recua), `pico` (só em ida-e-volta: segundo exato do auge; sem ele, o auge é o meio), `lado` ("auto" padrão / "esquerda" / "direita": para onde o ambiente balança), `suave` (true = fundo bem desfocado, para fundo bagunçado), `recorte` (false = não usa o recorte; para recorte ruim), `centro` ("rosto" padrão ou [x, y]), `som`, `som_atraso`, `som_volume` |
| `titulo` | `inicio`, `fim` (2–6 s; mín. 1,2), `texto` (2–5 palavras da fala, sem ponto final, até ~40 letras), `posicao` ("auto" padrão / "topo" / "baixo"), `som` |
- Nunca duas vertigens ao mesmo tempo; um título por vez.
- O `pico` precisa ficar dentro do evento, com pelo menos 0,25 s de folga das pontas.
- Título: escreva com acentos e grafia certos. Nada de nome do estilo, números de evento ou códigos.

## Som
O som é ar grave e macio (profundidade), nunca estalo. O som toca no `inicio` do evento + `som_atraso`.
| forma | som | som_atraso | som_volume |
|---|---|---|---|
| `ida-e-volta` | `whoosh-slow-soft` | `pico` − `inicio` (bate no auge) | 0,2–0,25 |
| `segurar` | `subida` | 0,7 (vertigem de 2 s) · 0,9 (2,5 s) · 1,0 (3 s ou mais) — termina quando o fundo chega | 0,15–0,2 |
| `pulso` | `grave` | 0 | 0,18–0,22 |
| `afastar` (qualquer forma) | `descida` | 0 | 0,18–0,22 |
- Som em no máximo ~70% das vertigens; as leves (intensidade 1) podem ir sem som.
- Título que entra junto com uma vertigem: sem som próprio. Título sozinho: `whoosh-curto` com `som_volume` 0,15 (opcional).
- Trilha (se marcada no card): clima "emocional", "tensao" ou "motivacional", energia baixa ou média.

## Legenda
Perfil do estilo já vem pronto (Inter 700, creme, palavra falada em verde-claro discreto, caixa escura, uma linha, sem pulo: "leitura estável"). Não mude. O motor põe a legenda abaixo do queixo (ou acima da cabeça) e o título desvia dela sozinho.

## Modo sem recorte
Se o ambiente não conseguir recortar a pessoa (sem máscara), o motor faz sozinho a **versão suave**: o fundo cresce em volta de uma silhueta macia da pessoa, estimada pelo rosto; perto da pessoa ele fica quase nítido (dá para ver crescer) e nas bordas bem desfocado. Não precisa mudar o plano. O mesmo acontece em toda vertigem com `"recorte": false`. A prévia vai avisar que falta o recorte; nesse caso é esperado.
- Em plano fechado sem recorte, o efeito aparece mais nas bordas de cima da tela: prefira `segurar` com intensidade 3 nos 2 ou 3 momentos mais fortes.
- Avise o cliente em uma frase: "Neste ambiente não deu para separar você do fundo, então a vertigem ficou mais suave (o fundo desfoca e se aproxima ao redor)."

## Erros de amador (não faça)
- Vertigem em toda frase: enjoa e perde o impacto. Fundo parado também é ritmo.
- Auge fora da palavra: o `pico` tem que cair no início da palavra forte, não no meio da frase.
- `afastar` repetido ou colado em outra vertigem.
- Intensidade 3 em plano aberto ou em frase calma (vira desenho animado).
- `pulso` em frase longa e calma (use `ida-e-volta`).
- Título que repete a legenda palavra por palavra, ou frase inteira como título.
- Esquecer de olhar a folha_recorte: recorte ruim aparece como linha reta, mão "fantasma" ou objeto duplicado quando o fundo se mexe.
- Ignorar fundo bagunçado sem `suave: true`.

## Conferência antes de entregar
- [ ] Primeira vertigem e título nos 3 primeiros segundos.
- [ ] Rode a prévia nos auges: `python3 "$ERG" previa --pasta /tmp/erg --tempos <pico1>,<pico2>,…` (para `segurar`/`pulso`, use um tempo no meio do evento).
- [ ] Na folha_previa: a pessoa está igual ao original (mesmo tamanho e lugar) e o fundo está maior/menor e um pouco girado atrás dela.
- [ ] Nenhuma linha reta cortando o corpo, nem mão ou objeto duplicado, nem mancha ao lado de um objeto na mão (se tiver: `"recorte": false` naquela vertigem).
- [ ] Em volta da cabeça, um halo macio da cor da parede é normal; manchas fortes ou riscos = fundo bagunçado → `"suave": true`.
- [ ] Título inteiro, legível, fora do rosto e da legenda, com acentos certos. Ele abre da esquerda para a direita em ~0,4 s: se a prévia pegar esse instante, ele aparece pela metade — confira num tempo do meio do título.
- [ ] Todo título do plano aparece na prévia (em rosto muito grande ele pode não caber sem cobrir o rosto; aí o motor não desenha). Se um título não aparecer, use `"posicao": "baixo"` e um texto mais curto (2 ou 3 palavras).
- [ ] Fundo se mexendo entre 25% e 45% do vídeo; vertigens espalhadas até o fim, ligadas a palavras reais.
- [ ] `problemas_no_plano` vazio na prévia (com recorte) e `problemas` vazio no resultado; folha_resultado olhada.
