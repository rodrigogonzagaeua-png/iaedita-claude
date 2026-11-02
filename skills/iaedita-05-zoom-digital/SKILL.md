---
name: iaedita-05-zoom-digital
description: Direção profissional do estilo 05 · Zoom digital do IAEdita — aproximações secas de câmera nas palavras fortes, títulos de impacto com faixa neon e clarões curtos. Use quando o cliente escolher "Zoom digital" (05-zoom-digital) no card do IAEdita. Funciona com qualquer vídeo; não precisa recortar a pessoa.
---

# Estilo 05 · Zoom digital

Antes: siga a skill principal `iaedita` (fluxo e regras de edição). Esta skill só ensina a DIREÇÃO deste estilo.

## A essência
A câmera "reage" à fala: nas palavras de peso ela dá um salto seco para mais perto (punch-in), segura, e volta. É o corte de criador de conteúdo profissional: dá energia sem distrair. De vez em quando um título grande com uma palavra marcada em neon crava a ideia principal.
Reconhecível por: **saltos de enquadramento nítidos e ritmados**, nunca zoom lento e contínuo; **poucos títulos, muito fortes**.

## Leitura da fala: onde entram os efeitos
Leia a transcrição inteira (`palavras`) e marque:
- **Gancho** (primeiros 3 s): sempre um zoom nível 1 ou 2 logo na primeira frase. Se a primeira frase tiver um número/promessa, um `destaque` nela.
- **Palavras de peso** → `zoom`: números ("3 milhões"), contrastes ("mas", "só que", "na verdade"), negações fortes ("nunca", "zero"), a palavra-chave do assunto, o fim de uma frase de efeito.
- **Ideia central** (1 a cada 8-15 s) → `destaque`: 2 a 4 palavras que resumem o trecho, com `marca` na palavra mais importante. Escreva o título com as palavras do falante, mais curto.
- **Momento de virada / punchline** → `zoom` nível 3 + `flash` + som de impacto. Use no máximo 1 vez a cada 20 s.

## Ritmo pela duração do vídeo
| Duração | Zooms | Destaques | Flashes |
|---|---|---|---|
| até 15 s | 3–5 | 1–2 | 0–1 |
| 15–45 s | 6–12 | 2–4 | 1–2 |
| 45–90 s | 10–18 | 4–6 | 2–3 |
| 90 s+ | 1 a cada 4–6 s | 1 a cada 15 s | 1 a cada 30 s |
- Intervalo mínimo de 1,2 s entre o fim de um zoom e o início do próximo. Única exceção: a escada (nível 1 → 2 → 3 colados numa frase crescente; o `inicio` do próximo = `fim` do anterior e o nível SEMPRE sobe). O motor recusa o plano se isso não for seguido.
- Duração de cada zoom: do início da palavra de peso até o fim da frase (normalmente 0,8–2,5 s). Nunca mais de 4 s.
- Alterne os níveis (1, 2, 1, 3, 2…). Nível 3 é raro.
- Nada de efeito nos últimos 0,5 s se a pessoa estiver só respirando; termine limpo.
- **Nunca dois destaques ao mesmo tempo.** Deixe pelo menos 0,3 s entre o `fim` de um e o `inicio` do outro.

## Adaptação ao enquadramento
Onde ler: no arquivo `analise.json` da pasta de trabalho, campo `rosto.plano` ("fechado", "medio" ou "aberto") e `rosto.largura` (fração da largura do vídeo que o rosto ocupa). Confira também olhando a `folha_original.jpg`.
- **Plano fechado** (`rosto.plano` = "fechado", rosto > 38% da largura): o motor já deixa os zooms um pouco mais contidos; prefira nível 1-2. Se um `destaque` estiver na tela durante um zoom nível 3, o título fica menor (sobra pouco espaço acima dos olhos): junto de destaque, use nível 1 ou 2.
- **Plano médio/aberto**: todos os níveis; use `alvo` "rosto" (padrão).
- O motor cuida sozinho de: aproximar sem empurrar o rosto para baixo, manter o queixo acima da legenda, e pôr o título acima dos olhos e fora da legenda (ele escolhe o lugar UMA vez por destaque e diminui o título se faltar espaço).
- Se houver um objeto importante (produto, tela) e a fala apontar para ele, use `alvo: [x, y]` (frações 0-1 do quadro) naquele zoom.

## Eventos do plano
```json
{
  "estilo": "05-zoom-digital",
  "correcoes": {"Instagran": "Instagram"},
  "eventos": [
    {"tipo": "zoom", "inicio": 0.00, "fim": 1.40, "nivel": 1, "som": "lente"},
    {"tipo": "destaque", "inicio": 0.10, "fim": 1.60, "texto": "3 milhões de livros", "marca": "3"},
    {"tipo": "zoom", "inicio": 4.32, "fim": 5.90, "nivel": 2, "som": "lente"},
    {"tipo": "zoom", "inicio": 17.04, "fim": 18.60, "nivel": 3, "som": "impacto", "som_volume": 0.2},
    {"tipo": "flash", "inicio": 17.04, "fim": 17.20}
  ]
}
```
| tipo | campos |
|---|---|
| `zoom` | `inicio`, `fim` (0,8–2,5 s; nunca mais de 4 s), `nivel` 1 (leve, 1,15x) / 2 (médio, 1,27x) / 3 (forte, 1,42x), `transicao` "corte" (padrão, salto seco) ou "suave" (empurrão — use 1 em cada 4, em frases calmas), `alvo` "rosto" (padrão) ou [x,y], `som` |
| `destaque` | `inicio`, `fim` (1,2–2,5 s; nunca mais de 2,5 s), `texto` (2–4 palavras, sem ponto final), `marca` (1 palavra EXATA do texto, com acento igual), `posicao` "auto" (use sempre) ou "topo", `som` |
| `flash` | `inicio`, `fim` (0,1–0,25 s; nunca mais de 0,3 s) |
- Não use `posicao` "baixo": embaixo fica a legenda. Se aparecer, o motor só aceita quando o título cabe grande abaixo da legenda; senão troca para o topo.
- `inicio` do zoom = `inicio` da palavra de peso (pegue o tempo exato em `palavras`). Nunca chute tempos.

## Som
- `lente` (trava de lente curta) em ~60% dos zooms com transição "corte"; volume padrão.
- `impacto` só no zoom nível 3, volume 0.15–0.25.
- `whoosh` no destaque só se ele entrar sem zoom junto.
- Trilha (se marcada no card): energia média, abaixo da voz (o motor faz o ducking).

## Legenda
Perfil do estilo já vem pronto, igual à prévia aprovada: 1 ou 2 palavras por vez, Inter 900 grande, entra subindo, palavra falada em verde-claro. Não mude. Os destaques ficam automaticamente longe da legenda (normalmente no topo).

## Erros de amador (não faça)
- Zoom em toda frase (cansa e perde o impacto). Silêncio visual também é ritmo.
- Zoom lento e contínuo do começo ao fim — isso é outro estilo.
- Destaque com frase inteira ou que repete a legenda palavra por palavra.
- Dois destaques na tela ao mesmo tempo, ou `marca` que não é uma palavra do texto.
- Zoom que corta o topo da cabeça ou o queixo (confira na prévia).
- Efeito sonoro em todo zoom (vira barulho).

## Conferência antes de entregar
- [ ] Primeiro efeito nos 3 primeiros segundos.
- [ ] Efeitos espalhados até o fim do vídeo, ligados a palavras reais.
- [ ] Nenhum título em cima dos olhos/boca ou cortado; marca neon na palavra certa; acentos visíveis (VOCÊ, ESTÚDIO, NÃO).
- [ ] Nenhum destaque ao mesmo tempo que outro; nenhum com mais de 2,5 s.
- [ ] Zooms não cortam cabeça/queixo.
- [ ] `problemas` vazio no resultado; folha_resultado olhada.
