---
name: iaedita-08-parede-de-manchetes
description: Direção profissional do estilo 08 · Parede de manchetes do IAEdita — as frases fortes da fala viram manchetes em recortes de papel de jornal, pregadas uma a uma numa parede ATRÁS da pessoa, que depois é limpa para a próxima leva. Use quando o cliente escolher "Parede de manchetes" (08-parede-de-manchetes) no card do IAEdita. Usa a pessoa recortada (tem modo sem recorte).
---

# Estilo 08 · Parede de manchetes

Antes: siga a skill principal `iaedita` (fluxo e regras de edição). Esta skill só ensina a DIREÇÃO deste estilo.

## A essência
Enquanto a pessoa fala, as ideias dela viram **manchetes de jornal em recortes de papel** que vão sendo pregadas, uma de cada vez, na parede atrás dela. A cabeça e os ombros passam NA FRENTE dos papéis (é isso que dá profundidade). Cada parede junta 2 a 4 manchetes de um mesmo assunto; quando o assunto muda, a parede é limpa (os papéis saem juntos, em cascata) e começa outra.
Reconhecível por: **papel creme com letra serifada escura**, **um papel verde-escuro com letra verde-limão para a manchete mais forte**, papéis levemente tortos e sobrepostos, e a **legenda em bloco claro de jornal** com a palavra falada em vinho.

O motor faz sozinho: a posição de cada papel (nunca sobre o rosto, nunca na zona da legenda), o giro, a sombra, o jornal de fundo atrás da cabeça, o recuo de câmera em plano fechado e a legenda. Você decide **o quê** vira manchete, **quando** entra e **quando** a parede é limpa.

## Leitura da fala: o que vira manchete
Leia a transcrição inteira (`palavras`) e marque:
- **Listas e enumerações** ("primeiro…, segundo…", nomes de produtos, passos, ferramentas) → uma manchete por item. É o melhor uso do estilo.
- **Números e promessas** ("3 milhões", "em 7 dias", "26 vídeos") → manchete com o número; use `marca` no número e, se for a ideia principal, `escuro: true`.
- **Afirmação forte / polêmica / virada** ("isso quebrou a internet", "ninguém te conta") → manchete curta, `marca` na palavra-chave.
- **Chamada para ação** no fim ("comenta X", "segue") → 1 manchete escura sozinha numa parede própria, com `chapeu` (ex.: "É só comentar").
- Frase de ligação ("e aí", "então", "olha só") **não** vira manchete.

Escreva a manchete com as palavras do falante, **mais curta** (2 a 5 palavras, até 34 letras, sem ponto final). Corrija o português e os nomes. Pode traduzir termos em outra língua para o português quando o público é brasileiro ("Checklist" → "Lista de verificação").

## Paredes e tempos
- **Parede** = grupo de manchetes com o **mesmo `fim`**. O `fim` é o instante em que o assunto acaba (fim da última frase do grupo). Todas saem juntas nesse momento.
- `inicio` de cada manchete = `inicio` da primeira palavra da frase dela (pegue o tempo exato em `palavras`). Nunca chute tempos.
- Entre duas entradas na mesma parede: **pelo menos 0,8 s** (ideal 1 a 2 s). Entradas coladas não dão tempo de ler.
- Cada manchete precisa ficar **pelo menos 1,5 s** na tela (do `inicio` ao `fim`). Uma parede dura de 3 a 12 s.
- A parede seguinte começa **depois** do `fim` da anterior (pode ser logo depois: 0,2 s já basta, a saída e a entrada se cruzam bonito).
- Respiro (vídeo limpo, sem papéis): só aparece se houver **2 s ou mais** entre o `fim` de uma parede e o `inicio` da próxima. Com intervalo menor, o jornal de fundo e o recuo de câmera continuam (as paredes se emendam). Planeje 1 ou 2 respiros de verdade nos vídeos acima de 20 s. Não precisa ter parede no último segundo.

## Ritmo pela duração do vídeo
| Duração | Paredes | Manchetes no total | Escuras |
|---|---|---|---|
| até 15 s | 1–2 | 3–5 | no máximo 1 por parede |
| 15–45 s | 3–5 | 8–15 | no máximo 1 por parede (pode ter parede sem escura) |
| 45–90 s | 5–8 | 14–24 | no máximo 1 por parede |
| 90 s+ | 1 a cada 10–15 s | 3 por parede | no máximo 1 por parede |
No plano fechado o total fica menor (paredes de 2): veja "Adaptação ao enquadramento".
- No máximo **1 manchete escura por parede** (a mais forte). Nunca 2 escuras seguidas.
- `chapeu` (a palavrinha em cima, ex.: "NOVIDADE", "17 EFEITOS", "EM BREVE"): no máximo 1 por parede, de preferência na primeira ou na escura.

## Adaptação ao enquadramento (olhe a folha_original.jpg)
O espaço da parede é o que sobra **em volta e acima da cabeça**. Por isso o número de manchetes que cabem juntas depende do enquadramento:

| Enquadramento | Como reconhecer | Manchetes por parede |
|---|---|---|
| **Fechado** | rosto ocupa mais de ~32% da largura | **2**. Só 3 se as 3 forem 1 palavra de até 8 letras ("Órbita", "Sofá", "Zoom"). |
| **Médio** | cabeça e ombros, rosto ~22–32% da largura | **3**. Só 4 se todas tiverem até 12 letras. |
| **Aberto** | corpo inteiro ou quase | até 5 |

- O papel **escuro** (letra larga) ocupa mais lugar: dê a ele o texto mais curto da parede.
- **Recuo de câmera:** quando o rosto é grande (mais de ~32% da largura) ou o alto da cabeça está no quarto de cima da tela, o motor encolhe o vídeo um pouco (no máximo 20%, ancorado embaixo) enquanto há paredes, e preenche a borda com o próprio vídeo desfocado e escurecido. Isso é esperado e serve para abrir parede acima da cabeça. Com paredes emendadas, o recuo fica o tempo todo (sem vai-e-vem).
- **Papel que some antes da hora = parede cheia demais.** Se não houver lugar, o motor tira o papel antigo para pousar o novo e escreve no terminal uma linha assim:
  `Aviso (parede de manchetes): 'Lista de verificação' sai em 7.22s, antes do fim 10.00s, para dar lugar a 'Corte com zoom'. ...`
  ou `Aviso (parede de manchetes): sem espaço livre para '...'`.
  **Trate qualquer linha `Aviso (parede de manchetes)` como erro:** tire uma manchete dessa parede ou encurte os textos e rode a prévia de novo, até não aparecer nenhum aviso.
- O campo `lado` só serve para corrigir algo que você viu na prévia ("esquerda", "direita", "topo"). Deixe "auto" no resto.

### Prévia no momento mais cheio de cada parede
A prévia padrão não mostra todas as paredes. Rode a prévia com `--tempos` em **(fim − 0,3 s)** de cada parede, que é o instante em que todos os papéis dela estão na tela:
```bash
python3 "$ERG" previa --pasta /tmp/erg --tempos 4.6,9.7,16.1,22.0,26.2
```
(Exemplo para paredes com `fim` 4.90, 10.00, 16.40, 22.30 e 26.50.) Confira na folha que cada parede tem TODOS os papéis dela, inteiros e legíveis, e que o terminal não mostrou nenhum `Aviso (parede de manchetes)`.

## Eventos do plano
Só existe um tipo de evento: `manchete`.

| campo | obrigatório | o que é |
|---|---|---|
| `tipo` | sim | sempre `"manchete"` |
| `inicio` | sim | segundo em que a frase da manchete começa a ser dita |
| `fim` | sim | segundo em que a parede é limpa (o MESMO para todas as manchetes da parede) |
| `texto` | sim | 1 a 5 palavras (até 34 letras), sem ponto final; 1 palavra só para nomes (ex.: "Órbita") |
| `chapeu` | não | 1 a 3 palavras curtas acima da manchete (até 16 letras); sai em maiúsculas |
| `escuro` | não | `true` = papel verde-escuro com letra verde-limão (a manchete mais forte da parede) |
| `marca` | não | 1 palavra do `texto` que ganha um sublinhado de caneta (número, nome, palavra-chave) |
| `lado` | não | `"auto"` (padrão), `"esquerda"`, `"direita"` ou `"topo"` |
| `som` | não | use `"papel"` (ver "Som") |
| `som_volume` | não | 0.2 a 0.3 |

Exemplo (vídeo de 31 s, plano médio; fala: lista de efeitos, depois um anúncio e um "comenta"; 3 manchetes por parede, a 4ª só com textos curtos):
```json
{
  "estilo": "08-parede-de-manchetes",
  "correcoes": {"cláudios": "do Claude", "estúdio": "STUDIO"},
  "eventos": [
    {"tipo": "manchete", "inicio": 0.00, "fim": 5.10, "texto": "Órbita", "chapeu": "17 efeitos", "som": "papel", "som_volume": 0.3},
    {"tipo": "manchete", "inicio": 0.56, "fim": 5.10, "texto": "Parede do sofá"},
    {"tipo": "manchete", "inicio": 3.32, "fim": 5.10, "texto": "Zoom digital", "escuro": true, "som": "papel", "som_volume": 0.24},
    {"tipo": "manchete", "inicio": 5.28, "fim": 10.30, "texto": "Lista de verificação", "som": "papel", "som_volume": 0.28},
    {"tipo": "manchete", "inicio": 6.18, "fim": 10.30, "texto": "Manchetes", "escuro": true},
    {"tipo": "manchete", "inicio": 8.42, "fim": 10.30, "texto": "Gráfico que cresce"},
    {"tipo": "manchete", "inicio": 17.04, "fim": 22.30, "texto": "26 vídeos", "chapeu": "Em breve", "escuro": true, "marca": "26", "som": "papel", "som_volume": 0.3},
    {"tipo": "manchete", "inicio": 18.86, "fim": 22.30, "texto": "Nos próximos dias"},
    {"tipo": "manchete", "inicio": 20.76, "fim": 22.30, "texto": "Quebrou a internet", "marca": "internet"},
    {"tipo": "manchete", "inicio": 22.46, "fim": 27.20, "texto": "Comente STUDIO", "chapeu": "É só comentar", "escuro": true, "marca": "STUDIO", "som": "papel", "som_volume": 0.3}
  ]
}
```
Entre 10.30 e 17.04 não há parede: é o respiro (vídeo limpo). No plano fechado, este mesmo vídeo ficaria com paredes de 2 (por exemplo, "Órbita" + "Zoom digital", "Lista de verificação" + "Corte com zoom").

## Som
- `papel` (folha deslizando e assentando) na **primeira manchete de cada parede** e na **escura**. Nas outras, sem som — senão vira barulho. Volume 0.2–0.3.
- Nada de whoosh, impacto ou ding neste estilo.
- Trilha (se marcada no card): calma/editorial, abaixo da voz (o motor faz o ducking).

## Legenda
O estilo desenha a própria legenda: bloco claro de jornal, letra serifada escura, fio vinho em cima e a palavra falada em vinho, na parte de baixo da zona segura. Não mude o perfil. As manchetes nunca entram na faixa da legenda. Se a boca da pessoa descer até a legenda, o motor sobe a legenda para cima da cabeça naquele trecho e as manchetes desviam.
Para desligar (vídeo sem fala): `"legenda": {"ativa": false}`.

## Modo sem recorte
Se `recortar` não funcionar no ambiente, o motor continua: os papéis ficam POR CIMA do vídeo, em volta e acima da cabeça (podem tapar o alto do cabelo e os ombros, com sombra; nunca o rosto). Não muda nada no plano: use os mesmos limites de "Adaptação ao enquadramento" (no máximo 3 por parede; 2 no plano fechado) e trate os avisos do mesmo jeito. Avise o cliente em uma frase: "Fiz sem o recorte da pessoa, então as manchetes ficam em volta dela em vez de atrás."

## Erros de amador (não faça)
- Frase inteira como manchete, ou manchete que repete a legenda palavra por palavra. Manchete é título: curta e forte.
- Uma manchete para cada palavra falada (parede lotada, nada se lê). Escolha os itens que importam.
- Cada manchete com um `fim` diferente (os papéis saem um a um, sem ritmo). A parede sai junta.
- Parede que fica o vídeo inteiro sem ser limpa.
- Várias manchetes escuras na mesma parede (o destaque perde o valor).
- Som de papel em todas as manchetes.
- Manchete com erro de português, nome errado ou palavra em inglês sem necessidade.

## Conferência antes de entregar
- [ ] Primeira manchete nos 3 primeiros segundos (na primeira frase forte).
- [ ] Paredes espalhadas até o fim do vídeo, cada uma ligada a um assunto real da fala.
- [ ] Número de manchetes por parede dentro do limite do enquadramento (fechado: 2; médio: 3).
- [ ] Prévia rodada com `--tempos` no (fim − 0,3 s) de cada parede: todos os papéis de cada parede aparecem juntos, inteiros e legíveis.
- [ ] Nenhuma linha `Aviso (parede de manchetes)` no terminal (na prévia nem no render).
- [ ] Na folha: nenhum papel sobre olhos/boca, nenhum texto cortado pela borda.
- [ ] Textos curtos, em português correto, sem ids ou rótulos internos.
- [ ] 1 escura por parede, no máximo; `marca` numa palavra que existe no `texto`.
- [ ] `problemas_no_plano` e `problemas` vazios; folha_previa e folha_resultado olhadas.
