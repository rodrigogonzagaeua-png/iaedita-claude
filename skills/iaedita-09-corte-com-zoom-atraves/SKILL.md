---
name: iaedita-09-corte-com-zoom-atraves
description: Direção profissional do estilo 09 · Corte com zoom através do IAEdita — a cada mudança de assunto a câmera mergulha no rosto com rastro de movimento, um portal verde-limão se abre em volta da cabeça e revela outro enquadramento do mesmo vídeo com o título do novo assunto. Use quando o cliente escolher "Corte com zoom através" (09-corte-com-zoom-atraves) no card. Funciona com qualquer vídeo; não precisa recortar a pessoa.
---

# Estilo 09 · Corte com zoom através

Antes: siga a skill principal `iaedita` (fluxo e regras de edição). Esta skill só ensina a DIREÇÃO deste estilo.

## A essência
O vídeo é dividido em "planos", um por assunto. Quando a pessoa muda de assunto, a câmera **atravessa** a tela: mergulha no rosto num zoom forte e rápido (com rastro de movimento), um **anel verde-limão** aparece em volta da cabeça (contornando o rosto inteiro, nunca em cima dos olhos ou da boca) e se abre para fora como um portal, há um clarão curtinho no meio, e do outro lado chega o próximo plano — vindo de muito perto e assentando — com o **título do novo assunto** no alto da tela. Entre uma travessia e outra a câmera nunca para: avança bem devagar (zoom contínuo).
Reconhecível por: **poucas travessias, todas fortes e no lugar certo da fala**; anel verde-limão; título curto no alto à esquerda com um traço verde-limão em cima; planos alternando entre "aberto" (vídeo inteiro) e "fechado" (mais perto do rosto, com cantos escurecidos).

O motor faz sozinho: o zoom, o rastro, o anel, o clarão, o enquadramento de cada plano, o avanço contínuo, o lugar e o tamanho do título (sempre fora do rosto e da legenda) e a legenda. Você só decide **onde ficam as travessias, a força de cada uma e o texto dos títulos**.

## Leitura da fala: onde entram as travessias
Rode `palavras` e leia a fala inteira. Divida a fala em blocos de assunto e marque:
- **Gancho** (primeiros 3 s): SEMPRE um `titulo` com o tema do vídeo (1 a 4 palavras), começando entre 0,1 e 0,3 s. Se a primeira frase for forte (promessa, número, provocação), abra também com uma `chegada` (o vídeo começa saindo do portal).
- **Mudança de assunto** → `passagem` com `titulo`. Sinais na fala: "mas", "só que", "agora", "então", "outra coisa", "o segundo…", "e o melhor", "por isso", "resumindo", o começo de uma história, um anúncio ("eu vou lançar…"), a chamada final ("comenta", "segue", "clica", "salva").
- **Pausa longa (0,4 s ou mais) no meio de uma lista comprida** → pode ter uma `passagem` leve (`"forca": 1`) **sem título**, só para dar respiro. No máximo 1 por lista.
- **A virada principal / chamada final** → `passagem` com `"forca": 3`. No máximo 1 por vídeo (2 se o vídeo passar de 60 s).
- **Frase de efeito dentro de um plano** (sem mudar de assunto) → `titulo` sozinho, sem passagem.

Como escrever:
- **Tempo da passagem**: o MEIO da passagem cai no início da primeira palavra do novo assunto. Pegue esse tempo em `palavras` (ex.: "Eu·16.42") e faça `inicio` = tempo − 0,35 e `fim` = tempo + 0,35 (duração 0,7 s). Se houver uma pausa antes da palavra, a passagem pode ficar dentro da pausa. Nunca chute tempos.
- **Título**: 1 a 4 palavras (até 32 letras) com as palavras da pessoa, sem ponto final, em português correto. Ex.: "26 vídeos novos", "Quebrou a internet", "Comente ESTÚDIO". Não repita a frase inteira da legenda.
- Sem `titulo_fim`, o título da passagem fica até 3 s depois do `fim`. Se a próxima passagem começar até 5 s depois do `fim`, ele fica na tela até ela e é levado pelo zoom (o motor faz isso sozinho).
- Quer um `titulo` sozinho entre duas passagens? Ponha `titulo_fim` na passagem anterior, pelo menos 0,3 s antes do `inicio` desse `titulo`. Exemplo abaixo: a passagem de 16,07 tem `"titulo_fim": 19.50` e o `titulo` "Quebrou a internet" começa em 20,10. Sem esse `titulo_fim`, os dois títulos ficariam um por cima do outro.
- Nada de texto interno: nunca "Plano 2", "Cena A", "Passagem", ids, nomes de estilo ou códigos.

## Ritmo pela duração do vídeo
| Duração | Passagens | Títulos (contando os das passagens) | Força 3 |
|---|---|---|---|
| até 15 s | 1 (no máximo 2) | 1–2 | 0–1 |
| 15–30 s | 2–3 | 2–3 | 0–1 |
| 30–60 s | 3–5 | 3–5 | 1 |
| 60–90 s | 5–7 | 4–7 | 1–2 |
| 90 s+ | 1 a cada 12–18 s | 1 a cada 15 s | 1 a cada 45 s |
Regras de tempo:
- Pelo menos **2 s de plano entre duas passagens** (o ideal é 4 s ou mais). Travessia demais vira enjoo.
- O primeiro evento (o `titulo` do gancho ou a `chegada`) fica nos 3 primeiros segundos.
- Espalhe as passagens pelo vídeo inteiro, sempre ligadas a mudanças reais de assunto.
- Nada de passagem nos últimos 0,6 s: o vídeo termina limpo, no último plano.
- `chegada`: só no começo (`inicio` 0, `fim` 0,6), no máximo 1, e pelo menos 2 s antes da primeira passagem.

## Adaptação ao enquadramento (olhe a folha_original.jpg)
O motor mede o rosto e ajusta sozinho; você confere na prévia.
- **Plano fechado** (rosto ocupa mais de 38% da largura, como o cliente real): o motor já diminui o mergulho; o plano "fechado" chega 1,16x mais perto, anda um pouco para o lado (alternando esquerda e direita) e tem uma cor levemente mais fria e contrastada, para o outro lado do portal parecer outra câmera. Prefira `forca` 1–2; use a 3 uma vez só. O espaço acima da cabeça é pequeno: o título fica menor e no alto — escreva 1 a 3 palavras.
- **Plano médio** (rosto entre 20% e 38%): todas as forças; os planos "fechado" chegam bem mais perto (1,22x) e ficam bem diferentes dos "abertos".
- **Plano aberto** (pessoa pequena): o mergulho vai até o rosto e o plano "fechado" chega a 1,32x. Use `"enquadramento": "fechado"` na passagem mais importante para dar um close de verdade.
- `enquadramento` "auto" (padrão) alterna aberto → fechado → aberto… O vídeo começa sempre "aberto". Só troque se quiser dois closes seguidos ou voltar ao aberto de propósito.
- Se o rosto não foi encontrado (`rosto.metodo` = "estimativa" na análise), o mergulho vai para o meio da parte de cima da tela: confira na prévia se o anel abre em volta da cabeça da pessoa.
- Com o rosto muito grande, o anel contorna o rosto inteiro e por isso aparece quase só como um arco na parte de baixo e nas laterais da tela. Isso é o certo: o anel nunca fica pequeno em cima do nariz ou da boca.

## Eventos do plano
```json
{
  "estilo": "09-corte-com-zoom-atraves",
  "correcoes": {"cláudios": "do Claude", "broke": "quebrou"},
  "eventos": [
    {"tipo": "chegada", "inicio": 0.00, "fim": 0.60, "som": "whoosh-curto", "som_volume": 0.3},
    {"tipo": "titulo", "inicio": 0.15, "fim": 3.50, "texto": "17 efeitos de vídeo"},
    {"tipo": "passagem", "inicio": 12.19, "fim": 12.89, "forca": 1,
     "som": "whoosh-curto", "som_atraso": 0.35, "som_volume": 0.25},
    {"tipo": "passagem", "inicio": 16.07, "fim": 16.77, "titulo": "26 vídeos novos", "titulo_fim": 19.50,
     "som": "whoosh", "som_atraso": 0.35, "som_volume": 0.3},
    {"tipo": "titulo", "inicio": 20.10, "fim": 21.40, "texto": "Quebrou a internet"},
    {"tipo": "passagem", "inicio": 21.45, "fim": 22.15, "titulo": "Comente ESTÚDIO", "forca": 3,
     "som": "whoosh", "som_atraso": 0.35, "som_volume": 0.38}
  ]
}
```
| tipo | campos |
|---|---|
| `passagem` | `inicio`, `fim` (0,6–0,8 s; o meio no início da palavra do novo assunto), `titulo` (opcional, 1–4 palavras), `titulo_fim` (opcional, segundos; pelo menos 0,8 s depois do `fim`), `enquadramento` "auto" (padrão)/"aberto"/"fechado", `forca` 1 (leve) / 2 (padrão) / 3 (forte, com clarão maior), `som`, `som_atraso` (= metade da duração, ex.: 0,35), `som_volume` |
| `titulo` | `inicio`, `fim` (pelo menos 1,2 s), `texto` (1–4 palavras): título no plano atual, sem travessia; entra vindo da câmera e assenta. Não pode começar no meio de uma passagem |
| `chegada` | `inicio` 0, `fim` 0,6, `som`: o vídeo abre saindo do portal (zoom que freia + anel que se abre) |
- Um título por vez na tela. Se um `titulo` encostar na próxima passagem, ele é levado pelo zoom (isso é bonito; use de propósito como no exemplo, terminando o `fim` logo antes da passagem).
- Na passagem de força 1 sem título, o próximo plano chega limpo (bom para respiros no meio de listas).

## Som
- `passagem`: `"som": "whoosh"`, `"som_atraso"` = metade da duração (0,35 para 0,7 s), volume 0.3. O pico do som bate no clarão, no meio da travessia. Sem o `som_atraso` certo a prévia acusa problema.
- Passagem de força 1: `"whoosh-curto"`, volume 0.25. Força 3: `"whoosh"`, volume 0.35–0.4.
- `chegada`: `"whoosh-curto"`, volume 0.3.
- `titulo` sozinho: sem som.
- Trilha (se marcada no card): energia média, abaixo da voz (o motor faz o ducking).

## Legenda
Perfil do estilo já vem pronto (Inter 900, uma linha curta numa caixa escura, palavra falada em verde-limão, sobe de leve ao entrar). Não mude. O motor tira os títulos do caminho da legenda sozinho. Corrija nomes na transcrição com `correcoes`.

## Sem recorte
Este estilo não usa a pessoa recortada: funciona igual com ou sem `recortar`. Não rode o recorte só para ele.

## Erros de amador (não faça)
- Passagem em toda frase, ou duas passagens coladas (menos de 2 s): o efeito perde a força e cansa.
- Passagem no meio de uma frase ou de uma palavra: ela marca a VIRADA de assunto.
- Força 3 em tudo; o clarão grande é para o momento principal.
- Título que repete a legenda, frase inteira, título em outra língua ou com nome errado.
- Esquecer o `som_atraso` (o som chega antes do movimento) ou som em todo título.
- Passagem no finalzinho do vídeo ou depois da última fala.
- Começar sem nada nos 3 primeiros segundos.

## Conferência antes de entregar
- [ ] Gancho nos 3 primeiros segundos; passagens só em mudanças reais de assunto, espalhadas até o fim.
- [ ] Meio de cada passagem no início da palavra certa (confira em `palavras`); 2 s ou mais entre elas.
- [ ] Na prévia, use `--tempos` com `inicio` + 0,2 de cada passagem (o anel verde-limão contorna a cabeça, fora dos olhos e da boca) e 0,8 s depois de cada `fim` (o título do novo assunto assentado e legível no alto).
- [ ] Título e legenda fora dos olhos e da boca, nada cortado; títulos em português correto, sem rótulos internos.
- [ ] `problemas_no_plano` e `problemas` vazios; folha_resultado olhada.
