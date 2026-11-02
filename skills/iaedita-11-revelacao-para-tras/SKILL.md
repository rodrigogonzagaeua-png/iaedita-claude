---
name: iaedita-11-revelacao-para-tras
description: Direção profissional do estilo 11 · Revelação para trás do IAEdita — a câmera recua e revela que o vídeo está dentro de uma janela de editor (barra com três pontinhos, linha do tempo enchendo, cartão com itens que ganham check, título em serifa) e depois volta para o vídeo cheio. Use quando o cliente escolher "Revelação para trás" (11-revelacao-para-tras) no card do IAEdita. Funciona com qualquer vídeo; não precisa recortar a pessoa.
---

# Estilo 11 · Revelação para trás

Antes: siga a skill principal `iaedita` (fluxo e regras de edição). Esta skill só ensina a DIREÇÃO deste estilo.

## A essência
Na maior parte do tempo o vídeo fica cheio, normal. Em poucos momentos fortes da fala, a câmera **recua** e o espectador descobre que o vídeo está "dentro" de uma janela de editor sobre um fundo claro de papel: barra com três pontinhos e um nome, linha do tempo que vai enchendo de verde-limão, um título elegante em serifa acima da janela e, às vezes, um cartão ao lado com itens que ganham check quando a pessoa fala cada um. Depois a câmera **volta** e o vídeo ocupa a tela de novo.
Reconhecível por: **recuo suave e contínuo (sem corte) até a janela, poucos textos grandes, checks no ritmo da fala, e a volta ao vídeo cheio.**
O motor já faz todo o desenho, o movimento de câmera e a legenda. Você só decide QUANDO revelar e QUAIS palavras aparecem.

## Leitura da fala: onde entram as revelações
Rode `palavras` e leia a fala inteira. Marque:
- **Gancho** (primeiros 3 s): a primeira revelação começa entre 0,2 e 1,0 s. Use a promessa/assunto do vídeo no `titulo`.
- **Lista falada** ("três coisas", "primeiro… segundo…", nomes em sequência) → revelação com `lista` (os itens, com as palavras do falante) e `marcas` (o tempo de `inicio` da palavra de cada item, tirado de `palavras`).
- **Número ou resultado** ("26 vídeos", "100%", "3 milhões") → `titulo` com o número e `"contar": true` (o número sobe de 0 até ele).
- **Bastidores / visão de fora** ("por trás", "o processo", "olha o todo", "na prática") → revelação simples com `titulo` e `janela`.
- **Chamada final** (comentar, seguir, link) → última revelação; pode ir até o fim do vídeo (`fim` = duração): a câmera não volta e o vídeo termina dentro da janela.
- Momentos de emoção, piada ou olhar direto na câmera → **NÃO** revele: deixe o vídeo cheio.

## Ritmo pela duração do vídeo
| Duração do vídeo | Revelações | Duração de cada | Com `lista` |
|---|---|---|---|
| até 15 s | 1–2 | 2,5–4 s | 0–1 |
| 15–45 s | 2–4 | 3–5 s | 1–2 |
| 45–90 s | 4–6 | 3–5 s | 2–3 |
| 90 s+ | 1 a cada 15–20 s | 3–5 s | cerca de metade |
- Entre uma revelação e a próxima: pelo menos 2,5 s de vídeo cheio (o motor recusa menos de 1,2 s).
- No máximo ~40% do tempo do vídeo dentro da janela. A pessoa falando em tela cheia é a estrela.
- `inicio` = começo da frase-gatilho (o `inicio` da primeira palavra, ou até 0,2 s antes). `fim` = fim da última palavra da ideia + 0,2 s. Nunca corte uma frase no meio.
- A câmera leva ~0,8 s para recuar e ~0,7 s para voltar. Com lista: o primeiro check precisa estar pelo menos ~1 s depois do `inicio` e o último pelo menos ~1,1 s antes do `fim` (comece a revelação ~1 s antes do primeiro item ser falado). Se não couber, o `previa` avisa em `problemas_no_plano` com o tempo certo.
- Revelação no fim do vídeo pode durar até 8 s.

## Adaptação ao enquadramento (olhe a folha_original.jpg)
- **Plano fechado** (rosto grande, > 38% da largura): funciona muito bem — o recuo mostra a pessoa inteira dentro da janela. O cartão da lista vai para a altura do peito; se não couber, o motor tira o `lista_titulo` sozinho. Use itens curtos (até 12 letras) e no máximo 3.
- **Plano médio**: tudo disponível (título, janela, lista com `lista_titulo`).
- **Plano aberto** (pessoa pequena, longe): dentro da janela ela fica pequena. Use revelações mais curtas (2,5–3,5 s) e prefira `titulo` sem `lista`.
- Pessoa fora do centro: tudo bem; o cartão desvia do rosto sozinho. Confira na prévia.

## Eventos do plano
Só existe um tipo de evento: `revelacao`.
```json
{
  "estilo": "11-revelacao-para-tras",
  "correcoes": {"Instagran": "Instagram"},
  "eventos": [
    {"tipo": "revelacao", "inicio": 0.30, "fim": 4.10, "titulo": "30 vídeos por mês", "contar": true,
     "janela": "Meu método", "som": "move-zoom-out", "som_volume": 0.3},
    {"tipo": "revelacao", "inicio": 9.80, "fim": 14.60, "janela": "Os três passos",
     "lista": ["Roteiro", "Gravação", "Edição"], "lista_titulo": "Passos", "marcas": [10.90, 12.05, 13.40],
     "som": "move-zoom-out", "som_volume": 0.3},
    {"tipo": "revelacao", "inicio": 26.20, "fim": 30.00, "titulo": "Comente “quero”", "janela": "Comentários",
     "som": "move-zoom-out", "som_volume": 0.3}
  ],
  "efeitos_sonoros": [
    {"som": "data-countup-medium", "t": 0.70, "volume": 0.16},
    {"som": "move-zoom-in", "t": 4.10, "volume": 0.22},
    {"som": "tique", "t": 10.90, "volume": 0.22},
    {"som": "tique", "t": 12.05, "volume": 0.22},
    {"som": "tique", "t": 13.40, "volume": 0.22},
    {"som": "move-zoom-in", "t": 14.60, "volume": 0.22}
  ]
}
```
(Neste exemplo o vídeo tem 30 s: a última revelação vai até o fim, então não tem som de volta.)

| campo | o que é | regra |
|---|---|---|
| `inicio`, `fim` | quando a câmera começa a recuar e quando ela termina de voltar | 2,5–6 s de duração (até 8 s se terminar com o vídeo) |
| `titulo` | texto grande em serifa acima da janela | opcional · 2–4 palavras da fala · até 22 letras · sem ponto final |
| `contar` | `true` = o número do `titulo` conta de 0 até ele | só se o título tiver número |
| `janela` | nome do trecho, na barra da janela | opcional · 2–4 palavras da fala que dão nome ao trecho (ex.: "Meu método", "Comentários") · até 26 letras · nunca nome de arquivo, extensão (.mp4), sublinhado (_), versão (v2) ou código |
| `lista` | itens do cartão ao lado da janela | opcional · 1–3 itens · até 16 letras cada · palavras da fala |
| `lista_titulo` | título do cartão | opcional · até 14 letras |
| `marcas` | segundo em que cada item ganha check | um tempo por item, na ordem; use o `inicio` da palavra do item; se faltar, o motor espalha os checks |
| `volta` | `"suave"` (padrão: a câmera volta) ou `"corte"` (volta seca no `fim`) | use `"corte"` só num corte de cena forte |
| `som`, `som_volume` | som que bate no início do recuo | `"move-zoom-out"`, 0.3 |
- Varie: nem toda revelação precisa de todos os campos. Ex.: uma com título e número, outra só com lista, outra com a chamada final.
- Todo texto sai da fala (resumido). Nunca invente promessa, número ou nome que a pessoa não disse.

## Som
- `som` de cada revelação: `"move-zoom-out"` (ar se afastando), volume 0.3.
- Volta da câmera: em `efeitos_sonoros`, `"move-zoom-in"` com `t` = `fim` da revelação, volume 0.22 (o motor encaixa o som para ele chegar junto com a câmera). Não ponha quando a revelação termina com o vídeo.
- Cada check: `"tique"` no mesmo tempo da marca, volume 0.2–0.25.
- Contagem (`contar`): `"data-countup-medium"` em `inicio` + 0,4 s, volume 0.15–0.18.
- Mais nada: sem whoosh extra, sem som em cada palavra.
- Trilha (se marcada no card): clima "leve" ou "corporativo", energia baixa ou média, abaixo da voz.

## Legenda
O estilo desenha a própria legenda: caixa clara, texto escuro, até 4 palavras por vez, e a palavra falada ganha uma faixa verde-limão de marca-texto. Fora da janela ela fica logo abaixo do queixo; quando a câmera recua, ela desliza (sempre visível) até a base do vídeo dentro da janela e volta do mesmo jeito. Em plano muito fechado, ela vai para o topo e o `titulo` não aparece. Não mude o perfil. Só use `"legenda": {"ativa": false}` se o vídeo não tiver fala.

## Modo sem recorte
Este estilo não usa a pessoa recortada: funciona igual com ou sem `recortar`. Não rode `recortar` só para ele.

## Erros de amador (não faça)
- Revelar a cada frase: cansa e tira a força. Vídeo cheio também é ritmo.
- Copiar textos da prévia de demonstração ("Seu próximo vídeo", "Sua edição", "Organizar / Dar ritmo / Finalizar", "Seu texto aqui", "100%"). São só exemplo do card.
- Pôr na tela nome do estilo, id ("11-revelacao…"), nome de arquivo ("video_final.mp4", "edicao-v2") ou qualquer código. O `previa` avisa em `problemas_no_plano`.
- Título que repete a frase inteira da legenda. Resuma em 2–4 palavras.
- Itens da lista que a pessoa não fala, ou `marcas` chutadas: o check tem que bater com a palavra.
- Revelação que começa ou termina no meio de uma palavra importante.
- Revelações coladas umas nas outras.
- Som de volta esquecido, ou whoosh forte por cima da voz.

## Conferência antes de entregar
- [ ] Primeira revelação nos 3 primeiros segundos.
- [ ] Revelações espalhadas até o fim, cada uma ligada a uma fala real; no máximo ~40% do tempo dentro da janela.
- [ ] Na `folha_previa.jpg`: título inteiro acima da janela, cartão sem cobrir o rosto, legenda legível, nada cortado.
- [ ] Confira também a entrada e a volta: rode `previa --tempos` com `inicio + 0,4` e `fim - 0,3` de uma revelação.
- [ ] Nenhum texto de demonstração, nome de estilo ou código na tela; português correto.
- [ ] Checks no tempo da fala; sons do recuo, da volta e dos checks no plano.
- [ ] `problemas_no_plano` e `problemas` vazios; `folha_resultado.jpg` olhada.
