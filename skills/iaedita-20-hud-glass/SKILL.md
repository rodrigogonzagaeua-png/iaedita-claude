---
name: iaedita-20-hud-glass
description: Direção profissional do estilo 20 · HUD Glass do IAEdita — painéis de vidro fosco com ícone verde-claro e título curto flutuando acima da cabeça, ligados à pessoa por linhas finas de HUD, mais etiquetas em pílula e cantos de mira em volta do rosto. Use quando o cliente escolher "HUD Glass" (20-hud-glass) no card do IAEdita. Feito para plano fechado (rosto grande); funciona também em plano médio. Não precisa recortar a pessoa.
---

# Estilo 20 · HUD Glass

Antes: siga a skill principal `iaedita` (fluxo e regras de edição). Esta skill só ensina a DIREÇÃO deste estilo.

## A essência
Uma "tela de vidro" futurista aparece acima da cabeça da pessoa: painéis de vidro fosco (o cenário atrás fica desfocado) com um ícone verde-claro e um título curto em branco. Eles entram subindo e assentando com suavidade, um depois do outro, e uma linha fina com um ponto verde "liga" cada painel à pessoa. É calmo, limpo e premium — parece interface de filme de ficção, não cartaz.
Reconhecível por: **vidro desfocado + ícone verde + título curto**, **dois painéis lado a lado (um largo à esquerda, um alto à direita) com entrada escalonada**, **nada no rosto**.

O motor cuida sozinho do espaço: se a cabeça estiver alta demais (plano fechado), a câmera desce suavemente enquanto os painéis estão na tela e o topo vira uma continuação desfocada do cenário. Você não precisa calcular posições.

## Leitura da fala: onde entram os efeitos
Leia a transcrição inteira (`palavras`) e marque:
- **Gancho** (primeiros 3 s): sempre um `painel` começando entre 0,0 e 0,5 s com a promessa/assunto do vídeo. Se a frase tiver um segundo dado, um segundo painel entra 1–1,5 s depois (lado oposto).
- **Ideia central de cada trecho** → `painel`: 2 a 4 palavras que resumem o que a pessoa diz (ex.: fala "eu vou lançar 26 vídeos nos próximos dias" → painel "26 vídeos novos", detalhe "nos próximos dias").
- **Dupla de informações** (antes/depois, problema/solução, número + o quê) → dois painéis: o primeiro na palavra principal, o segundo 0,8–1,5 s depois, e os DOIS saem juntos (mesmo `fim`).
- **Palavra-relâmpago** (um nome, um número, uma frase de efeito curta) → `chamada` (pílula de vidro com ponto verde e uma linha curta que desce até o alto da cabeça).
- **Momento de foco** ("presta atenção", "o segredo é", "olha isso", virada da história) → `mira`: cantos de HUD travam em volta do rosto.
- Pedido de ação no fim ("comenta", "segue", "salva") → um `painel` com ícone `check`.

## Ritmo pela duração do vídeo
| Duração | Painéis | Chamadas | Miras |
|---|---|---|---|
| até 15 s | 2–3 (1 dupla) | 0–1 | 0–1 |
| 15–45 s | 4–7 (2–3 duplas) | 1–2 | 1–2 |
| 45–90 s | 7–12 | 2–3 | 2–3 |
| 90 s+ | 1 dupla a cada 12–18 s | 1 a cada 25 s | 1 a cada 30 s |
- Painel: 2 a 6 s na tela (o mínimo é 1,5 s para dar tempo de ler). Chamada: 1,2 a 3 s. Mira: 0,8 a 2,5 s.
- Mira pelo menos 1 s DEPOIS do fim de um painel ou chamada (a câmera ainda está voltando; a mira em cima desse movimento fica tremida).
- Máximo de 2 painéis ao mesmo tempo (um de cada lado). Chamada nunca junto com painel.
- Deixe 2 a 5 s de "respiro" sem painel entre os grupos: o vidro é elegante porque não está o tempo todo na tela.
- O `inicio` é o momento da palavra que motiva o painel (copie o tempo de `palavras`, pode adiantar até 0,15 s). Nunca chute tempos.
- Termine limpo: nada novo nos últimos 1,5 s do vídeo.

## Adaptação ao enquadramento (olhe a folha_original.jpg)
- **Plano fechado** (rosto grande, cabeça perto do topo — o caso mais comum): é o plano ideal deste estilo. O motor desce a câmera durante os painéis (até ~20% da altura) e, se ainda faltar espaço, diminui um pouco os painéis (o texto continua legível). Prefira textos de 2–3 palavras e, no máximo, um `detalhe` curto. Agrupe os painéis próximos (menos de 1,5 s entre um e outro) para a câmera não subir e descer à toa.
- **Plano médio** (rosto pequeno, espaço acima da cabeça): a câmera desce pouco ou nada. Pode usar 4 palavras e o campo `detalhe`.
- **Plano aberto** (corpo inteiro): funciona, mas os painéis ficam longe da pessoa; use menos painéis e mais `mira`.
- Se a pessoa segura um objeto/celular no peito, a legenda fica por cima dele (é a altura fixa da legenda); isso é esperado.

## Eventos do plano
```json
{
  "estilo": "20-hud-glass",
  "correcoes": {"Instagran": "Instagram"},
  "eventos": [
    {"tipo": "painel", "inicio": 0.05, "fim": 3.9, "texto": "17 efeitos de vídeo", "icone": "olho", "som": "vidro", "som_volume": 0.22},
    {"tipo": "painel", "inicio": 1.40, "fim": 3.9, "texto": "Feitos com IA", "icone": "raio", "som": "vidro", "som_volume": 0.18},
    {"tipo": "mira", "inicio": 5.28, "fim": 6.9, "som": "digital-scan-subtle", "som_volume": 0.2},
    {"tipo": "painel", "inicio": 16.95, "fim": 20.3, "texto": "26 vídeos novos", "detalhe": "nos próximos dias", "icone": "olho", "som": "vidro", "som_volume": 0.22},
    {"tipo": "painel", "inicio": 18.00, "fim": 20.3, "texto": "Feitos com Claude", "icone": "raio", "som": "vidro", "som_volume": 0.18},
    {"tipo": "chamada", "inicio": 20.70, "fim": 22.3, "texto": "Quebrou a internet", "som": "shimmer-short-soft", "som_volume": 0.25},
    {"tipo": "painel", "inicio": 22.70, "fim": 25.6, "texto": "Comente STUDIO", "icone": "check", "som": "vidro", "som_volume": 0.22}
  ],
  "efeitos_sonoros": [{"som": "whoosh-curto", "t": 25.1, "volume": 0.12}]
}
```
| tipo | campos |
|---|---|
| `painel` | `inicio`, `fim` (2–6 s), `texto` (2–4 palavras, sem ponto final, primeira letra maiúscula), `detalhe` (opcional, **só no painel da ESQUERDA**: até 18 letras em verde, ex. "nos próximos dias", "em 30 dias", "R$ 97"), `icone`, `lado` "auto" (padrão) / "esquerda" / "direita", `som`, `som_volume` |
| `chamada` | `inicio`, `fim` (1,2–3 s), `texto` (1 a 3 palavras, até 22 letras: nome, número, frase-relâmpago), `som`, `som_volume` |
| `mira` | `inicio`, `fim` (0,8–2,5 s), `som`, `som_volume` |

- **Lado:** deixe "auto". O primeiro painel vai para a ESQUERDA (largo, ícone grande); quem entra enquanto ele está na tela vai para a DIREITA (alto e estreito).
- **Painel da direita:** 1 a 3 palavras de até 8 letras cada (ex.: "Com IA", "Com Claude", "Sem custo") e SEM `detalhe`. Palavra comprida (ex.: "Acompanhamento") não cabe nele: ponha esse texto no primeiro painel da dupla.
- **Ícones:** `olho` (ideia, atenção — padrão do painel largo), `mira` (foco, objetivo — padrão do painel alto), `check` (feito, ação, lista), `raio` (rápido, IA, energia), `grafico` (crescimento, resultado), `dinheiro` (preço, lucro), `coracao` (gostar, saúde), `estrela` (melhor, destaque), `alvo` (meta), `play` (vídeo, começar), `seta_cima` (subir, aumentar). Escolha o que combina com o sentido do texto.
- Textos em português correto, com acento. Nunca escreva nomes de estilo, códigos ou "Seu texto aqui".

## Som
- `vidro` (toque de vidro discreto) na entrada de cada painel: `som_volume` 0.18–0.25 (o segundo painel da dupla um pouco mais baixo).
- `shimmer-short-soft` na chamada (0.2–0.3).
- `digital-scan-subtle` na mira (0.15–0.2).
- Um `whoosh-curto` bem baixo (0.1–0.15) em `efeitos_sonoros` quando o último grupo de painéis sai (no `fim` menos 0,5 s). Só um ou dois por vídeo.
- Trilha (se marcada no card): clima "tecnologia" ou "corporativo", energia baixa a média.

## Legenda
O perfil do estilo já vem pronto: Inter forte, 1 linha curta, palavra falada em verde-claro, numa faixa de vidro escuro na altura do peito. Não mude. Ela nunca disputa espaço com os painéis (eles ficam no topo).

## Correções da transcrição
Em `correcoes`, escreva só a palavra, sem pontuação dos dois lados (ex.: `"estúdio": "STUDIO"`, não `"estúdio,": "STUDIO,"` — a pontuação original é mantida sozinha).

## Erros de amador (não faça)
- Frase inteira no painel ou repetir a legenda palavra por palavra. Painel é RESUMO.
- Painel em toda frase, ou painéis colados um no outro o vídeo todo (vira poluição e a câmera fica descida o tempo inteiro).
- Dois painéis que entram no mesmo instante (perde a entrada escalonada) ou que saem em momentos diferentes numa dupla.
- Texto longo ou `detalhe` no painel da direita (ele é estreito: 1–3 palavras curtas, sem detalhe).
- `detalhe` comprido (mais de 18 letras): vira 2 linhas e pesa o painel. Detalhe é complemento curto.
- Mira logo depois de um painel (menos de 1 s).
- Chamada ao mesmo tempo que painel.
- Ícone sem relação com o texto.
- Efeito sonoro alto: o vidro é delicado; a voz é a estrela.

## Conferência antes de entregar
- [ ] Primeiro painel nos 0,5 s iniciais; efeitos espalhados até perto do fim, ligados a palavras reais.
- [ ] Na `folha_previa.jpg`: painéis inteiros (nada cortado pela borda), texto legível, nada sobre olhos e boca, borda direita livre.
- [ ] Duplas entram escalonadas e saem juntas.
- [ ] A câmera não sobe e desce o tempo todo (agrupe painéis próximos).
- [ ] `problemas_no_plano` e `problemas` vazios; `folha_resultado.jpg` olhada.
