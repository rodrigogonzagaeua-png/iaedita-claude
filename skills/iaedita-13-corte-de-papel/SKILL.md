---
name: iaedita-13-corte-de-papel
description: Direção profissional do estilo 13 · Corte de papel do IAEdita — o vídeo vira uma colagem num caderno quadriculado; a pessoa aparece recortada com borda branca de papel, na frente de folhas coloridas, com títulos serifados circulados a lápis, etiquetas de papel e rabiscos de lápis. Use quando o cliente escolher "Corte de papel" (13-corte-de-papel) no card do IAEdita. Usa a pessoa recortada; sem recorte, o vídeo vira uma foto colada no caderno.
---

# Estilo 13 · Corte de papel

Antes: siga a skill principal `iaedita` (fluxo e regras de edição). Esta skill só ensina a DIREÇÃO deste estilo.

## A essência
O vídeo vira uma colagem de papel. O fundo do vídeo some e entra um caderno creme quadriculado. A pessoa fica recortada, com uma borda branca de papel em volta (como recortada de revista), levemente torta e balançando devagar. Atrás dela ficam duas folhas coloridas: uma lilás no alto, com hachura de lápis, e uma verde-limão do lado.
Nas ideias fortes, um **título serifado** aparece na folha do alto e um **círculo de lápis** é desenhado em volta dele. De vez em quando uma **etiqueta de papel** ("crie.") é colada no peito e um **rabisco de lápis** aparece ao lado da cabeça.
O estilo é reconhecido por três coisas: o **recorte com borda branca**, o **título circulado a lápis** e a **legenda numa tira de papel**. O motor desenha a colagem do começo ao fim do vídeo. O seu plano só diz QUANDO entram títulos, etiquetas, rabiscos e trocas de cor.

## Precisa do recorte
Antes do plano, se ainda não existe `mascara.mkv` na pasta e o `editar` não avisou "sem recorte", rode `recortar`. Olhe `folha_recorte.jpg`: o que não for pessoa deve estar magenta. Se o recorte falhar, siga o "Modo sem recorte" no fim desta skill.

## Leitura da fala: onde entram os efeitos
Leia a transcrição inteira (`palavras`) e marque:
- **Gancho** (primeiros 3 s): sempre um `titulo` com `traco: "circulo"` na primeira frase. Se ela tiver número ou promessa, ponha o número no título e use-o como `marca`.
- **Ideia central de cada trecho** → `titulo`: 2 a 5 palavras que resumem a frase, com as palavras do falante, mais curtas. Use `circulo` para a ideia principal e `sublinhado` + `marca` para destacar UMA palavra-chave (um contraste, um nome, um número).
- **Pedido ou palavra de ação** ("crie", "salve", "comente", "teste", "grátis") → `etiqueta` com 1 ou 2 palavras, em minúsculas e com ponto, como "crie." ou "comente.".
- **Reações curtas na fala** → `rabisco`:
  - "não", "nunca", "erro", "pare" → `x`
  - "sim", "pronto", "funciona", "certo" → `visto`
  - "olha", "aqui", "isso", "esse" → `seta`
  - "uau", "incrível", "viralizou", "explodiu" → `brilho`
  - "melhor", "favorito", "top", "nota 10" → `estrela`
- **Mudança de assunto** ("mas", "agora", "segundo ponto", "parte 2", virada da história) → `cena`: as folhas trocam de cor (rosa, azul ou areia) até o fim do trecho.

## Ritmo pela duração do vídeo
| Duração | Títulos | Etiquetas | Rabiscos | Cenas |
|---|---|---|---|---|
| até 15 s | 2–3 | 0–1 | 1–2 | 0 |
| 15–45 s | 4–7 | 1–3 | 2–4 | 1–2 |
| 45–90 s | 7–12 | 2–4 | 4–7 | 2–3 |
| 90 s ou mais | 1 a cada 7–10 s | 1 a cada 20 s | 1 a cada 12 s | 1 a cada 25–30 s |
- Só um título por vez: entre o `fim` de um título e o `inicio` do próximo, deixe pelo menos 0,35 s (o título leva 0,3 s para sair).
- Duração do título: do começo ao fim da frase, normalmente 1,5 a 4 s. O círculo leva cerca de 1 s para ser desenhado; título com menos de 1,5 s não mostra o círculo inteiro.
- Etiqueta: 1 a 3 s. Rabisco: 0,8 a 3 s. No máximo 2 rabiscos ao mesmo tempo.
- Cena: pelo menos 4 s. Depois do `fim` de uma cena, espere 0,5 s antes da próxima. Para a cor ficar até o fim do vídeo, use `fim` = duração do vídeo.
- Espalhe os efeitos pelo vídeo inteiro, sempre ligados a palavras reais. Silêncio visual também é ritmo: a colagem continua bonita sem nada por cima.
- Nos últimos segundos, se a pessoa só respira ou o vídeo escurece, não ponha nada.

## Adaptação ao enquadramento (olhe a folha_original.jpg)
O motor ajusta a composição sozinho: diminui a pessoa e a ancora embaixo, só o necessário para abrir a faixa do título acima da cabeça e a tira da legenda abaixo do queixo. Você não precisa mexer em posição.
- **Plano fechado** (rosto ocupa mais de 38% da largura): a pessoa diminui mais (até cerca de 70%) e a faixa do título fica mais baixa. Use títulos de 2 a 3 palavras e etiquetas de 1 palavra.
- **Plano médio**: a pessoa diminui pouco. Títulos de até 5 palavras.
- **Plano aberto** (corpo inteiro, pessoa pequena): a pessoa quase não muda e sobra muito caderno em volta. Use mais rabiscos, sempre com `lado` "auto".
- Se a pessoa segura um objeto (celular, produto), ele entra no recorte junto com ela. Não ponha etiqueta em cima dele.

## Eventos do plano
```json
{
  "estilo": "13-corte-de-papel",
  "correcoes": {"Instagran": "Instagram"},
  "eventos": [
    {"tipo": "titulo", "inicio": 0.00, "fim": 2.40, "texto": "17 efeitos de vídeo", "marca": "17", "traco": "circulo", "som": "lapis", "som_atraso": 0.3, "som_volume": 0.28},
    {"tipo": "etiqueta", "inicio": 3.32, "fim": 4.90, "texto": "zoom.", "som": "papel", "som_volume": 0.3},
    {"tipo": "titulo", "inicio": 5.28, "fim": 7.10, "texto": "Checklist e manchetes", "marca": "Checklist", "traco": "sublinhado", "som": "lapis", "som_atraso": 0.3, "som_volume": 0.24},
    {"tipo": "cena", "inicio": 6.18, "fim": 12.20, "paleta": "rosa", "som": "papel", "som_volume": 0.32},
    {"tipo": "rabisco", "inicio": 7.22, "fim": 8.40, "forma": "seta", "som": "lapis", "som_volume": 0.18},
    {"tipo": "titulo", "inicio": 16.42, "fim": 19.50, "texto": "26 vídeos novos", "marca": "26", "traco": "circulo", "som": "lapis", "som_atraso": 0.3, "som_volume": 0.28},
    {"tipo": "rabisco", "inicio": 21.36, "fim": 22.60, "forma": "x"},
    {"tipo": "etiqueta", "inicio": 23.18, "fim": 25.00, "texto": "comente.", "som": "papel", "som_volume": 0.3}
  ]
}
```
| tipo | campos |
|---|---|
| `titulo` | `inicio` (quando a frase começa), `fim` (quando ela termina), `texto` (2 a 5 palavras, até 32 letras, sem ponto final), `traco` "circulo" (padrão) / "sublinhado" / "nenhum", `marca` (opcional: 1 palavra do próprio texto; fica cor de vinho e, no "sublinhado", ganha o risco), `som` |
| `etiqueta` | `inicio`, `fim` (1–3 s), `texto` (1 ou 2 palavras, até 12 letras), `lado` "auto" (padrão) / "esquerda" / "direita", `som` |
| `rabisco` | `inicio`, `fim` (0,8–3 s), `forma` "x" / "visto" / "seta" / "brilho" / "estrela", `lado` "auto" (padrão) / "esquerda" / "direita", `som` |
| `cena` | `inicio`, `fim` (4 s ou mais), `paleta` "rosa" / "azul" / "areia" / "lilas" (lilás é a cor normal), `som` |
- Pegue `inicio` no tempo exato da palavra em `palavras`. Nunca chute tempos.
- `marca` precisa ser uma palavra que está no `texto` (sem a pontuação).
- Nada de texto interno na tela: nunca escreva "cena 2", "título", "estilo 13" ou nomes de arquivo nos campos `texto`.

## Som
- `titulo`: `"som": "lapis"` com `"som_atraso": 0.3` (o lápis toca quando o círculo começa), volume 0.22–0.3.
- `etiqueta`: `"papel"`, volume 0.25–0.35.
- `cena`: `"papel"`, volume 0.3–0.35 (as folhas deslizando).
- `rabisco`: `"lapis"` em volume baixo (0.15–0.2), só em metade dos rabiscos. Para o `visto` você pode usar `"writing-pencil-tick"`; para o `x`, `"writing-scribble"`.
- Nunca ponha som em todo evento. A voz é a estrela.
- Trilha (se marcada no card): clima "leve" ou "motivacional", energia baixa ou média.

## Legenda
O perfil do estilo já vem pronto: uma tira de papel creme, letra serifada (Cormorant 700), até 3 palavras por tira, as palavras aparecem conforme são ditas e a palavra falada fica cor de vinho. A tira fica logo abaixo do queixo, dentro da zona segura. Não mude o perfil. Corrija nomes, marcas e números em `correcoes`.

## Modo sem recorte
Se não der para recortar a pessoa (o ambiente não tem o recorte, ou o `recortar` falhou), o motor faz sozinho a versão sem recorte: o vídeo inteiro vira uma **foto colada no caderno**, com margem branca, duas fitas adesivas e leve inclinação. As folhas, os títulos circulados, as etiquetas, os rabiscos e a legenda continuam iguais. Use o MESMO plano.
Avise o cliente em uma frase: "Neste ambiente não deu para recortar você do fundo, então seu vídeo virou uma foto colada no caderno; o resto do estilo ficou igual."

## Erros de amador (não faça)
- Título com a frase inteira ou repetindo a legenda palavra por palavra. Resuma em 2 a 5 palavras.
- Título em toda frase. Deixe a colagem respirar entre um título e outro.
- Etiqueta com mais de 2 palavras: ela fica pequena e ninguém lê no celular.
- Rabisco em todo segundo, ou rabisco sem relação com o que foi dito.
- Trocar de `cena` a cada poucos segundos: a cor troca só quando o assunto muda.
- Título que entra antes ou depois da frase certa.
- Pôr texto que é rótulo interno ("parte 1", "cena 2").

## Conferência antes de entregar
- [ ] `folha_recorte.jpg` olhada: a pessoa está inteira e o fundo saiu (ou você avisou o modo sem recorte).
- [ ] Primeiro título nos 3 primeiros segundos, com círculo.
- [ ] Na `folha_previa.jpg`: títulos legíveis, círculo inteiro na tela, nada em cima dos olhos ou da boca.
- [ ] Legenda abaixo do queixo, sem cobrir a boca; português correto.
- [ ] Etiquetas e rabiscos ao lado do rosto ou no peito, nunca em cima do rosto.
- [ ] Efeitos espalhados até o fim, ligados a palavras reais.
- [ ] `problemas_no_plano` e `problemas` vazios; `folha_resultado.jpg` olhada.
