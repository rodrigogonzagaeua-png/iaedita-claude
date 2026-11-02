---
name: iaedita-18-halo-topo
description: Direção profissional do estilo 18 · Halo de Topo do IAEdita — título e selos SOBEM DE TRÁS DA CABEÇA da pessoa, com um anel de luz verde (halo) em volta do topo da cabeça e o fundo escurecido. Feito para plano fechado (rosto grande). Use quando o cliente escolher "Halo de Topo" (18-halo-topo) no card do IAEdita. Usa a pessoa recortada (rode `recortar`); sem recorte também funciona.
---

# Estilo 18 · Halo de Topo

Antes: siga a skill principal `iaedita` (fluxo e regras de edição). Esta skill só ensina a DIREÇÃO deste estilo.

## A essência
Nos momentos-chave da fala, o fundo escurece de cima para baixo, um anel de luz verde aparece em volta do topo da cabeça e um título curto SOBE DE TRÁS DA CABEÇA: uma linha branca menor em cima e UMA palavra grande em verde embaixo. Um selo escuro pequeno pode surgir acima do título, e um círculo verde com ícone encosta na ponta do anel. Depois tudo desce de volta para trás da cabeça e o vídeo fica limpo.
Reconhecível por: **título que nasce de trás da cabeça + anel de luz no topo + fundo escuro em cima. Poucos títulos, curtos, fortes.**

O motor cuida sozinho do enquadramento: se não houver espaço acima da cabeça (plano fechado), a imagem desce suavemente para abrir um "céu" escuro onde o título entra, e volta quando o título sai. A legenda acompanha. Você não precisa calcular posição nenhuma.

## Leitura da fala: onde entram os efeitos
Leia a transcrição inteira (`palavras`) e marque:
- **Gancho** (primeiros 3 s): sempre um `halo` com a promessa ou o número do começo. Se a pessoa começa direto no assunto, o halo começa em 0,0 s.
- **Ideia central / número / promessa** → `halo`. `destaque` = a palavra mais forte (ou número + palavra: "26 vídeos"); `texto` = o resto da frase, bem curto ("Vou lançar"). Use as palavras da pessoa, nunca invente slogan.
- **Itens de uma lista, nomes, benefícios, passos** → `selo` (só a etiqueta, sem título grande). Ex.: "checklist, manchetes" → selo "Checklist e manchetes".
- **Palavra de impacto** ("nunca", "zero", "quebrou", um número dito com força) → `pulso`: uma onda de luz sai do topo da cabeça. Se houver halo na tela, a palavra verde dá um pulo junto.
- **Chamada final** ("comenta", "segue", "link na bio") → `halo` com a ação (`texto` "É só comentar", `destaque` "estúdio") e ícone `coracao` ou `seta`.

## Ritmo pela duração do vídeo
| Duração | halo | selo | pulso |
|---|---|---|---|
| até 15 s | 1–2 | 0–2 | 1–2 |
| 15–45 s | 2–4 | 2–4 | 2–4 |
| 45–90 s | 4–6 | 3–6 | 4–8 |
| 90 s+ | 1 a cada 15–20 s | 1 a cada 15 s | 1 a cada 10 s |
- Duração: `halo` de 2 a 6 s (o ideal é 2,5–4 s: do início da frase até o fim dela). `selo` de 1,2 a 4 s. `pulso` de 0,3 a 0,8 s.
- **Um título ou selo de cada vez.** Nunca sobreponha `halo` com `halo` ou `halo` com `selo`. Deixe pelo menos 1,5 s de vídeo limpo entre eles quando der.
- Título/selo na tela no máximo ~55% do vídeo. Vídeo limpo também é ritmo.
- `pulso` no máximo 1 a cada 4–5 s, só nas palavras mais fortes. Pode cair dentro de um halo (a palavra verde pula) ou sozinho.
- `inicio` = o tempo exato da primeira palavra da frase (pegue em `palavras`). Nunca chute tempos.
- Termine limpo: nada novo começando no último 1 s do vídeo.

## Adaptação ao enquadramento (olhe a folha_original.jpg)
- **Plano fechado** (rosto grande, cabeça perto do topo — o caso principal deste estilo): use o estilo normalmente. O motor desce a imagem para abrir espaço; por isso prefira `texto` curto (até 3 palavras) e `destaque` de 1 palavra ou número + palavra. Se o título não couber nem assim, o motor o põe na frente, só sobre a testa/cabelo — nunca sobre olhos ou boca.
- **Plano médio** (há espaço acima da cabeça): o título fica acima da cabeça sem mexer na imagem. Todos os campos podem ser usados, inclusive `selo` dentro do `halo`.
- **Plano aberto** (pessoa pequena, muito espaço em cima): funciona, mas o anel fica maior que a cabeça. Use menos eventos (o efeito pede rosto grande) e não mude nada no plano — não existe campo de posição.

## Eventos do plano
```json
{
  "estilo": "18-halo-topo",
  "correcoes": {"broke": "quebrou"},
  "eventos": [
    {"tipo": "halo", "inicio": 0.00, "fim": 3.40, "texto": "17 efeitos de", "destaque": "vídeo",
     "selo": "Feitos com o Claude", "icone": "seta", "som": "whoosh-medium-soft", "som_volume": 0.25},
    {"tipo": "selo", "inicio": 5.20, "fim": 7.90, "texto": "Checklist e manchetes", "icone": "check",
     "som": "whoosh-fast-soft", "som_volume": 0.22},
    {"tipo": "pulso", "inicio": 7.22, "fim": 7.70},
    {"tipo": "halo", "inicio": 16.42, "fim": 19.45, "texto": "Vou lançar", "destaque": "26 vídeos",
     "selo": "Nos próximos dias", "icone": "seta", "som": "whoosh-medium-soft", "som_volume": 0.25},
    {"tipo": "pulso", "inicio": 17.04, "fim": 17.50},
    {"tipo": "pulso", "inicio": 21.36, "fim": 21.80, "som": "shimmer-short-soft", "som_volume": 0.18},
    {"tipo": "halo", "inicio": 22.74, "fim": 26.60, "texto": "É só comentar", "destaque": "estúdio",
     "icone": "coracao", "som": "whoosh-medium-soft", "som_volume": 0.25}
  ],
  "efeitos_sonoros": [
    {"som": "whoosh-fast-soft", "t": 3.10, "volume": 0.16},
    {"som": "whoosh-fast-soft", "t": 19.15, "volume": 0.16},
    {"som": "whoosh-fast-soft", "t": 26.30, "volume": 0.16}
  ]
}
```
| tipo | campos |
|---|---|
| `halo` | `inicio`, `fim` (2–6 s), `destaque` (OBRIGATÓRIO: a linha verde grande, 1–2 palavras, até 14 letras), `texto` (opcional: linha branca em cima, até 4 palavras / 24 letras), `selo` (opcional: etiqueta pequena acima do título, até 24 letras), `icone` (opcional, círculo verde na ponta do anel: `seta` (padrão), `check`, `estrela`, `raio`, `play`, `coracao`, `dinheiro`, `alvo`, `grafico`, `seta_cima` ou `nenhum`), `som`, `som_volume` |
| `selo` | `inicio`, `fim` (1,2–4 s), `texto` (2–4 palavras, até 24 letras), `icone` (opcional, dentro da etiqueta, mesma lista), `som`, `som_volume` |
| `pulso` | `inicio`, `fim` (0,3–0,8 s), `som` (opcional), `som_volume` |
- Sem ponto final nos títulos. Primeira letra maiúscula em `texto` e `selo`; `destaque` pode ser minúsculo ("vídeo", "estúdio").
- `destaque` é a palavra que fica na cabeça de quem assiste: escolha a mais concreta (número, resultado, nome). Nunca "isso", "aqui", "coisa".
- `texto` + `destaque` leem como uma frase só: "Vou lançar / 26 vídeos", "É só comentar / estúdio".
- Corrija nomes e palavras em inglês que a transcrição errou em `correcoes` (a legenda usa a fala corrigida).

## Som
- `halo`: `whoosh-medium-soft` no `inicio` (volume 0,2–0,3) — é o "ar" da subida. E um `whoosh-fast-soft` (0,14–0,18) em `efeitos_sonoros` em `fim - 0,3` — o recuo.
- `selo`: `whoosh-fast-soft` no `inicio` (0,18–0,25). Sem som de saída.
- `pulso`: `shimmer-short-soft` (0,15–0,2) só em 1 de cada 2 pulsos; quando o pulso cai dentro de um halo que acabou de entrar, deixe sem som.
- Nada de impacto, glitch ou sons altos: o estilo é elegante. Trilha (se marcada no card): calma/média, abaixo da voz.

## Legenda
O estilo monta a própria legenda (pílula escura no peito, uma linha, palavra falada em verde). Não mude o perfil. Ela acompanha o rosto quando a imagem desce e nunca sobe para a área do título.

## Modo sem recorte
Se o ambiente não conseguir rodar `recortar` (sem `mascara.mkv`), o estilo continua igual no plano: não mude nada. O motor faz o título nascer de uma linha logo acima da cabeça (nunca passa pelo rosto), escurece só o fundo de cima e apaga o anel onde ele cruzaria a cabeça. Avise o cliente em uma frase: "Neste ambiente não deu para recortar a pessoa, então o título nasce logo acima da cabeça em vez de sair de trás dela."

## Erros de amador (não faça)
- Título longo ("Vou lançar 26 vídeos diferentes nos próximos dias") — o motor encolhe e perde o impacto. Corte para "Vou lançar / 26 vídeos" e ponha o resto no `selo`.
- Halo em toda frase, ou um colado no outro: a imagem sobe e desce o tempo todo e cansa.
- Dois títulos ao mesmo tempo, ou `selo` sobreposto a `halo`.
- `destaque` com palavra fraca ("isso", "muito", "você").
- Pulso em toda palavra; som em todo evento.
- Textos em inglês ou com erro só porque a transcrição errou. Nada de rótulos internos ("halo 1", "seu texto aqui").
- Halo de menos de 2 s: o título nem termina de subir.

## Conferência antes de entregar
- [ ] Um `halo` nos 3 primeiros segundos.
- [ ] Eventos espalhados até o fim do vídeo, ligados a frases reais, um de cada vez.
- [ ] Na `folha_previa.jpg`: título inteiro, legível, acima da cabeça (ou sobre a testa no máximo), nada sobre olhos/boca, nada cortado pela borda, selo acima do título sem encostar no topo da tela.
- [ ] Anel passando atrás da cabeça (com recorte) ou cortado em volta dela (sem recorte).
- [ ] Português correto; `correcoes` aplicadas na legenda.
- [ ] `problemas_no_plano` e `problemas` vazios; `folha_resultado.jpg` olhada.
