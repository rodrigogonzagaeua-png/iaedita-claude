---
name: iaedita-06-maquete-de-celular
description: Direção profissional do estilo 06 · Maquete de celular do IAEdita — nos momentos certos a câmera se afasta, a pessoa recortada fica grande numa sala clara e um celular escuro inclinado flutua ao lado mostrando a tela de um app (frase com ícone neon, barra que vira "Tudo pronto", número que sobe). Use quando o cliente escolher "Maquete de celular" (06-maquete-de-celular) no card. Usa o recorte; sem ele, mostra o vídeo dentro do celular.
---

# Estilo 06 · Maquete de celular

Antes: siga a skill principal `iaedita` (fluxo e regras de edição). Esta skill só ensina a DIREÇÃO deste estilo.

## A essência
Igual à prévia do card: a câmera se afasta, o fundo do vídeo some e a pessoa (recortada) fica grande numa sala clara (parede creme, moldura, janela, sofá verde), embaixo do título. Do lado dela entra voando um celular escuro e inclinado. Na tela do celular aparece a interface de um app ligada ao que a pessoa está dizendo: frase com ícone verde-limão, barra de progresso que enche e vira "✓ Tudo pronto", ou número que sobe. Depois o celular sai, a sala some e o vídeo volta para a tela cheia, com o rosto grande.
Reconhecível por: **pessoa recortada na sala**, **celular inclinado com a interface do app** e **título escuro no alto**. A alternância cena ↔ tela cheia dá o ritmo.

O motor faz sozinho: a transição de entrada e saída, o tamanho e o lugar da pessoa (o rosto fica grande e nunca é coberto), o voo e o balanço do celular, a interface dentro da tela, a linha de progresso do vídeo e a legenda.

## Passo a passo para escrever o plano
1. Este estilo usa a pessoa recortada. Se ainda não existe `mascara.mkv` na pasta e o `editar` não avisou "sem recorte", rode `recortar`. Olhe `folha_recorte.jpg`.
2. Rode `palavras` e leia a fala inteira. Anote o tempo exato (segundos) das palavras-gatilho (lista abaixo).
3. Divida o vídeo em blocos: **cenas no celular** (assunto, explicação, números, chamada para ação) e **tela cheia** (piada, desabafo, frase de impacto, olhar para a câmera).
4. Crie os eventos `celular` (um por cena). A primeira cena começa em `0.00`.
5. Dentro de cada cena, ponha 1 a 3 cartões (`cartao`, `progresso` ou `contador`), cada um começando na palavra que o motivou. Eles aparecem DENTRO da tela do celular, um por vez.
6. Escolha os sons (seção Som) e escreva `correcoes` para nomes errados da transcrição.
7. Rode `previa`, olhe a folha, corrija, e só então `renderizar`.

## Leitura da fala: onde entram os efeitos
- **Gancho (primeiro segundo)**: a primeira cena `celular` começa em `0.00` — o vídeo já abre se afastando para a sala. Se a primeira frase tiver número, ponha um `contador` nela.
- **Número dito** ("26 vídeos", "3 mil alunos", "50%", "R$ 200") → `contador`, começando na palavra do número. `valor` = o número; `depois` = a unidade dita.
- **Processo, preparo, lançamento, lista** ("vou lançar", "em 5 minutos fica pronto", "passo a passo") → `progresso`. Ponha `conclui` no segundo da palavra que fecha a ideia ("pronto", o último item da lista, "e é isso").
- **Frase-chave, benefício, ferramenta, chamada para ação** ("comenta QUERO", "link na bio", "sem pagar anúncio") → `cartao` com 2 a 4 palavras e um ícone que combine.
- **Assunto de celular, app, rede social, internet, resultado** → ótimo momento para uma cena.
- **Piada, confissão, emoção, frase de efeito final** → tela cheia (sem cena). O rosto grande vende a emoção.

Ícones do `cartao`: `check` (confirmação, chamada para ação), `estrela` (o melhor, favorito), `raio` (rápido, energia), `alvo` (meta, foco), `grafico` (crescimento, resultado), `dinheiro` (venda, preço), `coracao` (curtir, seguir, amor), `play` (vídeo, assistir), `seta_cima` (subir, aumentar).

## Ritmo pela duração do vídeo
| Duração | Cenas `celular` | Cartões (somando os 3 tipos) | Tempo nas cenas |
|---|---|---|---|
| até 15 s | 1–2 | 1–3 | 50–70% |
| 15–45 s | 2–4 | 3–7 | 50–70% |
| 45–90 s | 4–7 | 6–12 | 45–65% |
| 90 s+ | 1 cena a cada 12–20 s | 1 a cada 6–10 s (só dentro das cenas) | 45–60% |
- Cada cena dura de **3 a 9 s** (mínimo 2,5 s). A entrada leva ~0,8 s e a saída ~0,55 s (o motor faz).
- Entre duas cenas deixe **pelo menos 1,5 s de tela cheia** (o motor recusa menos de 1 s).
- Cada cartão dura **1,5 a 4 s** (mínimo 1 s), começa **pelo menos 0,4 s depois** do início da cena e termina **pelo menos 0,2 s antes** do fim dela.
- `progresso` dura **2,5 a 5 s**. O `conclui` fica **entre `inicio` + 0,8 s e `fim` − 1 s**: o botão "pronto" precisa ficar pelo menos 1 s inteiro na tela (é o momento principal). Se a palavra que fecha a ideia está perto do fim, estique o `fim` do progresso.
- Um cartão por vez: o próximo começa quando o anterior termina.
- Alterne `lado` entre as cenas em vídeos longos ("direita", "esquerda", "direita"…).
- Use `titulo` em mais ou menos metade das cenas, com **até 22 letras** (cabe em uma linha). Sem título a pessoa e o celular ficam maiores.
- Termine limpo: nos últimos 1–3 s, tela cheia ou uma cena que termina junto com a fala. Nada de efeito em silêncio no final.

## Adaptação ao enquadramento (olhe a folha_original.jpg)
- **Plano fechado** (rosto ocupa mais de 38% da largura — o caso mais comum do cliente): funciona bem. O motor diminui a pessoa na cena (rosto com ~22–26% da largura) para a cabeça inteira ficar a pelo menos 6% das bordas e o celular caber ao lado; a pessoa fica "de pé" na parte de baixo da sala, com o corpo saindo pela base do quadro, e o celular desce para ficar na frente do lado de dentro do corpo. Prefira títulos curtos (uma linha). Textos ou telas que o criador gravou na frente do peito continuam aparecendo junto com a pessoa: se forem muitos, prefira `fundo: "video"` ou cenas mais curtas nesses trechos.
- **Plano médio** (rosto entre 20% e 38%): tudo funciona; o motor aproxima a pessoa para o rosto não ficar pequeno.
- **Plano aberto** (pessoa de corpo inteiro, rosto abaixo de 20%): faça cenas curtas (3–5 s), no máximo 40% do tempo nas cenas, sem título, e mantenha os momentos de emoção em tela cheia.

## Eventos do plano
```json
{
  "estilo": "06-maquete-de-celular",
  "correcoes": {"Insta": "Instagram"},
  "eventos": [
    {"tipo": "celular", "inicio": 0.00, "fim": 6.20, "titulo": "Vendas no Instagram", "som": "interface", "som_volume": 0.2},
    {"tipo": "contador", "inicio": 1.10, "fim": 4.00, "valor": 3000, "depois": "cursos", "texto": "Em 30 dias", "som": "tique", "som_volume": 0.26},
    {"tipo": "cartao", "inicio": 4.30, "fim": 5.90, "texto": "Só com o celular", "detalhe": "Sem anúncio", "icone": "check", "som": "pop", "som_volume": 0.32},

    {"tipo": "celular", "inicio": 9.40, "fim": 16.80, "lado": "esquerda", "som": "interface", "som_volume": 0.18},
    {"tipo": "progresso", "inicio": 10.00, "fim": 14.70, "texto": "Seu primeiro post", "final": "Tudo pronto", "conclui": 13.60, "som": "clique", "som_volume": 0.45},
    {"tipo": "cartao", "inicio": 14.80, "fim": 16.40, "texto": "Poste todo dia", "icone": "raio", "som": "pop", "som_volume": 0.32},

    {"tipo": "celular", "inicio": 21.00, "fim": 27.50, "titulo": "Quer o passo a passo?", "fundo": "video", "som": "interface", "som_volume": 0.18},
    {"tipo": "cartao", "inicio": 22.10, "fim": 26.80, "texto": "Comente “quero”", "detalhe": "Eu te mando", "icone": "coracao", "som": "pop", "som_volume": 0.32}
  ],
  "efeitos_sonoros": [{"som": "ding", "t": 13.60, "volume": 0.12}]
}
```
| tipo | campos |
|---|---|
| `celular` | `inicio`, `fim` (3–9 s), `titulo` (opcional, até 22 letras, aparece no alto), `lado` "direita" (padrão) ou "esquerda" (onde fica o celular; a pessoa fica do outro lado), `fundo` "sala" (padrão, a sala clara da prévia) / "sala-escura" / "video" (o próprio vídeo desfocado atrás da pessoa), `som`. Não use `modo`: o motor escolhe sozinho. |
| `cartao` | `inicio`, `fim`, `texto` (obrigatório, 2–4 palavras curtas, até 30 letras), `detalhe` (opcional, linha pequena em cima, até 26 letras), `icone` (lista acima; padrão `check`), `som` |
| `progresso` | `inicio`, `fim` (2,5–5 s), `texto` (rótulo, até 26 letras), `final` (texto do botão no fim, até 11 letras: "Tudo pronto", "Pronto!", "No ar"; sem ele aparece só o ✓), `conclui` (segundo exato em que a barra enche e o botão fica verde; entre `inicio` + 0,8 s e `fim` − 1 s), `som` |
| `contador` | `inicio`, `fim`, `valor` (número simples: `26`, `3000`, `2.5` — sem ponto de milhar), `antes` (opcional, até 4 letras: "R$", "+"), `depois` (unidade, até 12 letras: "vídeos", "%", "mil"), `texto` (opcional, rótulo pequeno em cima, até 26 letras), `som` |
- Tempos sempre tirados de `palavras` (o segundo exato em que a palavra começa). Nunca chute.
- O número do contador aparece no formato brasileiro (3000 → "3.000"; 2.5 → "2,5").
- Palavras muito compridas não cabem na tela do celular (ex.: "Empreendedorismo"): o motor acusa; troque por uma mais curta.
- `fundo`: use "sala" na maioria das cenas (é a cara do estilo). "sala-escura" serve para variar ou para um trecho mais sério; "video" mantém as cores do lugar da pessoa.
- Cartões só aparecem dentro de uma cena `celular` (fora dela o motor acusa erro).

## Som
- Entrada de cada cena: `interface` (volume 0.18–0.22) — o "app abrindo". O movimento do celular em si é silencioso, como na prévia aprovada: não ponha whoosh nele.
- `cartao`: `pop` (0.3–0.35).
- `contador`: `tique` (0.26); se for dinheiro, `moeda` (0.14).
- `progresso`: `clique` (0.45) no início e, em `efeitos_sonoros`, um `ding` (0.1–0.12) no segundo exato de `conclui` (o momento "Tudo pronto"). Para uma grande conclusão use `sino` (0.13).
- No máximo um som a cada 1,5 s. Trilha (se marcada no card): leve, abaixo da voz (o motor faz o ducking).

## Legenda
O estilo desenha a própria legenda, com o perfil da ficha: Inter 750, caixa escura de largura fixa, até 4 palavras por vez, e a palavra falada ganha uma caixinha verde-limão que desliza de palavra em palavra. Em tela cheia ela fica abaixo do queixo; nas cenas ela sobe para logo abaixo do título. Na transição ela some e reaparece no lugar novo (nunca atravessa o rosto). Não mude o perfil. Para desligar: `"legenda": {"ativa": false}`.

## Recorte da pessoa
**Use o recorte** (se ainda não existe `mascara.mkv` e o `editar` não avisou "sem recorte", rode `recortar` antes da prévia): é ele que deixa a pessoa grande na sala, como na prévia do card.
- **Sem recorte** (o ambiente não consegue recortar): não mude nada no plano. O motor troca sozinho para o modo "vídeo dentro do celular": o vídeo inteiro vira a tela do celular inclinado e os cartões aparecem ao lado, sempre abaixo do queixo. Avise o cliente em uma frase: "Neste ambiente não deu para recortar você do fundo, então o seu vídeo aparece dentro do celular."
- Sem recorte e plano fechado: cena com `progresso` fica **sem título** (o cartão de progresso é alto e precisa caber abaixo do queixo).

## Erros de amador (não faça)
- Deixar o vídeo nas cenas o tempo todo (ou nunca sair da tela cheia): a alternância é o ritmo do estilo.
- Cenas coladas, com menos de 1,5 s de tela cheia entre elas (vira um vai e vem cansativo).
- Cartão que começa junto com a cena (o celular ainda está chegando) ou que termina na saída dela.
- `progresso` com `conclui` perto do fim: o "Tudo pronto" pisca e some. Deixe 1 s ou mais depois do `conclui`.
- Cartão que repete a legenda palavra por palavra, frase longa, ou texto em inglês quando existe palavra em português.
- `contador` com número que a pessoa não disse, ou sem a unidade (`depois`).
- `progresso` sem um momento real de conclusão na fala.
- Título em todas as cenas, ou título com mais de 22 letras.
- Som em todo evento, ou whoosh no movimento do celular.
- Qualquer texto interno na tela ("Cena 1", "Celular", ids, nomes de estilo).

## Conferência antes de entregar
- [ ] O recorte foi feito (ou o cliente foi avisado em uma frase de que não deu).
- [ ] A primeira cena `celular` começa em 0.00.
- [ ] Entre 45% e 70% do tempo nas cenas; frases de impacto em tela cheia.
- [ ] Cada cartão nasce de uma palavra real, em português correto, curto; números com unidade.
- [ ] Todo `progresso` tem `fim` pelo menos 1 s depois do `conclui`.
- [ ] Na folha de prévia: nada sobre olhos e boca, nada cortado pela borda, textos da tela do celular legíveis.
- [ ] `problemas_no_plano` vazio na prévia (sem recorte, o aviso "Sem máscara da pessoa" em `avisos` é esperado) e `problemas` vazio no resultado; folha_resultado olhada.
