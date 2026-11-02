---
name: iaedita-17-tipo-vidro
description: Direção profissional do estilo 17 · Tipo vidro do IAEdita — palavras gigantes de vidro (o próprio vídeo aparece distorcido dentro das letras, borda cromada, reflexo de luz que atravessa, espessura e leve giro 3D), atrás da cabeça da pessoa ou na frente dela, sempre fora do rosto. Use quando o cliente escolher "Tipo vidro" (17-tipo-vidro) no card do IAEdita. Usa a pessoa recortada (rode `recortar`); sem recorte funciona com as palavras na frente.
---

# Estilo 17 · Tipo vidro

Antes: siga a skill principal `iaedita` (fluxo e regras de edição). Esta skill só ensina a DIREÇÃO deste estilo.

## A essência
Nos momentos fortes da fala, UMA palavra que a pessoa disse aparece enorme, feita de vidro: dentro das letras se vê o próprio vídeo, deformado como por uma lente; a borda brilha como cromo; um reflexo de luz passa pelas letras; elas têm espessura (linhas de profundidade) e balançam devagar em 3D. Quando há fundo livre acima da cabeça, a palavra fica ATRÁS da pessoa (a cabeça passa na frente da parte de baixo das letras do meio). Quando não há, ela fica NA FRENTE, fora do rosto (entre o queixo e a legenda).
Reconhecível por: **poucas palavras, gigantes, de vidro, uma de cada vez, com tempo de vídeo limpo entre elas.**
O motor decide sozinho o lugar, o tamanho, se fica atrás ou na frente, o desenho e a animação. Você só decide QUANDO e QUAL palavra.

## Leitura da fala: onde entram as palavras
Rode `palavras` e leia a fala inteira. Marque:
- **Gancho** (primeiros 3 s): a primeira palavra de vidro começa entre 0 e 1 s, na palavra principal da primeira frase, com som.
- **Palavra de peso** → `vidro`: o assunto do vídeo ("vendas", "Instagram"), um número ("26", "100%", "R$10 mil"), o nome de um produto, técnica ou pessoa, uma emoção forte ("medo", "liberdade"), um contraste ("nunca", "zero").
- **Número + o que ele conta** → `texto` com o número e `apoio` com o resto. Ex.: fala "vou lançar 26 vídeos nos próximos dias" → `"texto": "26"`, `"apoio": "vídeos nos próximos dias"`.
- **Chamada final** (comentar, seguir, link) → a última palavra, com `apoio` curto. Ex.: `"texto": "Comente"`, `"apoio": "a palavra QUERO"`.
- **Palavra de peso dita enquanto uma palavra de vidro está na tela** → `brilho` (reflexo forte + borda acende).
- Use a palavra que a pessoa DISSE, com acento certo ("Estúdio", "Ação"). Pode encurtar a forma ("vendendo" → "Vender"), nunca traduzir nem inventar. Escreva normal: o motor põe em MAIÚSCULAS.
- Não use: palavras vazias ("então", "muito", "coisa"), frases inteiras, palavras com mais de 12 letras (o vidro fica fino e difícil de ler — escolha outra palavra da frase).

## Ritmo pela duração do vídeo
| Duração do vídeo | Palavras de vidro | Com `apoio` | `brilho` |
|---|---|---|---|
| até 15 s | 2–4 | 0–1 | 0–1 |
| 15–45 s | 5–9 | 1–2 | 1–2 |
| 45–90 s | 8–14 | 2–4 | 2–3 |
| 90 s+ | 1 a cada 5–7 s | 1 a cada 25 s | 1 a cada 30 s |
- `inicio` = 0,05 a 0,15 s ANTES do `inicio` da palavra (pegue o tempo exato em `palavras`). A palavra de vidro "pousa" uns 0,3 s depois do `inicio`, junto com a voz.
- `fim` = fim da frase daquela palavra. Duração: 1,4–2,0 s (até 3 s com `apoio`; nunca mais de 4 s; nunca menos de 1,2 s).
- Uma palavra por vez: a próxima só começa depois do `fim` da anterior. Na maioria das vezes deixe pelo menos 1 s de vídeo limpo entre duas palavras.
- No máximo 1 palavra a cada 3 s em média (o motor recusa mais que 1 a cada 2,6 s). Espalhe até o fim da fala.
- `brilho`: 0,4–0,8 s, começando no `inicio` da palavra de peso; precisa começar pelo menos 0,35 s depois do `inicio` do `vidro` e 0,25 s antes do `fim` dele.

## Adaptação ao enquadramento (olhe a folha_original.jpg)
- **Plano fechado** (rosto grande, mais de 38% da largura, cabeça perto do topo): não sobra fundo acima da cabeça. O motor põe a palavra NA FRENTE, entre o queixo e a legenda. Prefira palavras curtas (até 7 letras): ficam bem maiores. Regra do `apoio` em plano fechado: use no máximo 2 (o número com o que ele conta, e a chamada final), cada um com até 4 palavras curtas (até 24 letras). Para caber a frase, o motor diminui a palavra de vidro (na chamada final com `"camada": "frente"`, até o mínimo legível). Não force `"camada": "atras"` nem `"posicao": "topo"`.
- Se mesmo assim o `apoio` não couber, o `previa` e o `renderizar` mostram no terminal uma linha `AVISO (17-tipo-vidro): ... o apoio '...' NÃO coube`. Nesse caso encurte o apoio (até 3 palavras), ponha `"camada": "frente"` nessa palavra, ou tire o apoio — e rode o `previa` de novo.
- **Plano médio** (cabeça e ombros, fundo acima da cabeça): o motor põe a palavra ATRÁS da cabeça quando ela continua grande e legível; números e palavras com `apoio` costumam ir para a frente, abaixo do queixo. Palavras de até 8 letras ficam grandes.
- **Plano aberto** (pessoa pequena, muito fundo): palavras atrás da pessoa, enormes. Tudo funciona.
- Deixe `camada` e `posicao` em "auto" (padrão). Force só com motivo: `"camada": "frente"` quando a palavra precisa aparecer inteira o tempo todo (nome de marca, chamada final); `"camada": "atras"` numa palavra curta em plano médio/aberto, para mais profundidade.

## Eventos do plano
Dois tipos: `vidro` (a palavra) e `brilho` (reflexo forte dentro de uma palavra que já está na tela).
```json
{
  "estilo": "17-tipo-vidro",
  "correcoes": {"Instagran": "Instagram"},
  "eventos": [
    {"tipo": "vidro", "inicio": 0.20, "fim": 1.80, "texto": "Vendas", "som": "foley-glass-slide", "som_volume": 0.22},
    {"tipo": "vidro", "inicio": 4.85, "fim": 6.40, "texto": "Medo"},
    {"tipo": "vidro", "inicio": 9.90, "fim": 12.40, "texto": "3 erros", "apoio": "que travam o seu negócio",
     "som": "foley-glass-slide", "som_volume": 0.2},
    {"tipo": "brilho", "inicio": 10.60, "fim": 11.20, "som": "vidro", "som_volume": 0.18},
    {"tipo": "vidro", "inicio": 15.30, "fim": 16.90, "texto": "Preço"},
    {"tipo": "vidro", "inicio": 20.10, "fim": 21.70, "texto": "Confiança", "som": "foley-glass-slide", "som_volume": 0.2},
    {"tipo": "vidro", "inicio": 26.00, "fim": 28.60, "texto": "Comente", "apoio": "a palavra QUERO", "camada": "frente",
     "som": "shimmer-short-soft", "som_volume": 0.16}
  ]
}
```
(Neste exemplo o vídeo tem 30 s.)

| tipo | campo | regra |
|---|---|---|
| `vidro` | `inicio`, `fim` | 1,2–4 s; uma palavra por vez |
| | `texto` | 1 palavra da fala (no máximo 2 curtas, ex.: "3 erros", "R$10 mil"); até 12 letras; sem ponto final |
| | `apoio` | opcional · 2–5 palavras da fala, em letra branca menor · até 34 letras (plano fechado: até 4 palavras / 24 letras) · NÃO repita a palavra de vidro · use em 1 a cada 4 palavras, no máximo |
| | `camada` | `"auto"` (padrão) · `"atras"` = atrás da pessoa · `"frente"` = na frente, fora do rosto |
| | `posicao` | só quando fica na frente: `"auto"` (padrão) · `"topo"` = acima da cabeça · `"baixo"` = entre o queixo e a legenda |
| | `som`, `som_volume` | ver "Som" |
| `brilho` | `inicio`, `fim` | 0,4–0,8 s, dentro de um `vidro` (regra no Ritmo) |
| | `som`, `som_volume` | ver "Som" |
- Não existem campos de posição em pixels nem de tamanho: o motor calcula tudo para nada cobrir o rosto nem ser cortado.

## Som
- `som` do `vidro`: `"foley-glass-slide"` (vidro deslizando), volume 0.18–0.22. Na primeira palavra sempre; depois em mais ou menos metade das palavras (alternando), nunca em todas.
- `som` do `brilho`: `"vidro"` (toque de vidro) ou `"shimmer-short-soft"` (brilho suave), volume 0.15–0.2.
- Nada de whoosh forte, impacto ou som em cada palavra. O som deste estilo é baixo e cristalino; a voz é a estrela.
- Trilha (se marcada no card): clima "leve" ou "tecnologia", energia baixa ou média, abaixo da voz.

## Legenda
O perfil já vem pronto: Inter 800, 1 linha, caixa verde-escura translúcida, palavra falada em verde-claro, na parte de baixo da zona segura. O motor mantém a palavra de vidro e o `apoio` fora da faixa da legenda. Não mude o perfil. Só use `"legenda": {"ativa": false}` se o vídeo não tiver fala.

## Modo sem recorte
Se o ambiente não conseguir rodar `recortar` (sem `mascara.mkv`), o motor põe TODAS as palavras na frente, fora do rosto (entre o queixo e a legenda, ou acima da cabeça quando há espaço), com o mesmo vidro, reflexo e giro. O plano é o mesmo: não precisa mudar nada (`"camada": "atras"` vira frente sozinho). O `previa` traz em `avisos` o aviso "Sem máscara da pessoa": isso é esperado neste caso. Avise o cliente em uma frase: "Neste ambiente não deu para recortar a pessoa, então as palavras de vidro ficaram na frente dela, fora do rosto."

## Erros de amador (não faça)
- Palavra de vidro em toda frase: perde o impacto. Vídeo limpo entre as palavras também é ritmo.
- Frase inteira em vidro, ou palavra com mais de 12 letras.
- Duas palavras de vidro ao mesmo tempo, ou coladas sem respiro.
- Palavra que entra depois de ser dita (`inicio` atrasado) ou que fica na tela muito depois da frase.
- Copiar os textos da prévia do card ("TEXTO", "Forma e luz.", "Sua história merece movimento"). São só exemplo.
- Pôr na tela nome do estilo, id ("17-tipo-vidro"), nome de arquivo ou código.
- Traduzir, trocar ou escrever errado a palavra da pessoa; esquecer acento.
- `apoio` que repete a palavra de vidro (ex.: `"texto": "Estúdio"` + `"apoio": "comente no estúdio"` — o `previa` acusa), que passa de 5 palavras ou que a pessoa não disse.
- `brilho` fora de uma palavra de vidro, ou um `brilho` em cada palavra.
- Forçar `"camada": "atras"` em plano fechado (a cabeça esconderia as letras; o motor acaba pondo na frente e menor).

## Conferência antes de entregar
- [ ] Primeira palavra de vidro nos 3 primeiros segundos, com som.
- [ ] Palavras espalhadas até o fim da fala, cada uma ligada a uma palavra realmente dita, no tempo dela.
- [ ] Na `folha_previa.jpg` (por padrão o meio de cada evento): cada palavra inteira, legível, grande; nada sobre olhos e boca; nada cortado na borda; legenda livre. Atrás da pessoa, a metade de cima das letras aparece inteira.
- [ ] Confira também a chegada: `previa --tempos` com `inicio + 0,35` de duas palavras (a palavra já tem que estar quase pousada e nítida).
- [ ] Nenhum texto de demonstração, nome de estilo ou código na tela; português correto, com acentos.
- [ ] Sons só na chegada de algumas palavras e nos brilhos, volume baixo.
- [ ] Cada `apoio` do plano aparece na folha, inteiro e legível. Nenhuma linha `AVISO (17-tipo-vidro)` no terminal (se houver, faça o que ela pede).
- [ ] `problemas_no_plano` e `problemas` vazios; `folha_resultado.jpg` olhada.
