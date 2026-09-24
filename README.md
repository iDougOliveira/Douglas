# PokerCoach Local

Painel web local para estudo/revisão de mãos e gestão de banca. Funciona no navegador do celular ou computador; não requer instalação nesses dispositivos.

Interface visual: escolha de 2 a 10 jogadores, clique no assento com o botão e selecione as duas cartas no baralho gráfico. Em heads-up, o botão também é SB.

## Motor 3.17.1

O módulo `strategy.py` substitui integralmente as heurísticas antigas. Cada resultado informa perfil, fonte, motivo e limites; o histórico registra a entrada usada. Não existe LLM nem sorteio de ação.

- Spin & Go: motor próprio 3-handed → heads-up, dirigido por stack efetivo em BB. Aberturas do BTN em 8/10/15/20/25 BB usam os resumos públicos de soluções do [PreflopRanges](https://preflopranges.app/charts/spins/25bb), complementados pelo [curso Spin & Go da PokerStars Learn](https://www.pokerstars.com/poker/learn/course/spin-go-strategy-pokerstars-tips/) para estrutura, limps, reshoves, defesa de blind e HU. Estados impossíveis (por exemplo BTN enfrentando um raise antes de sua primeira ação) são marcados como ESTADO INVÁLIDO; spots válidos com frequência não separável aparecem como MISTA, não como SEM COBERTURA.
- Aberturas gerais: resumos escritos da [PokerCoaching](https://pokercoaching.com/preflop-charts/), separados por mesa, posição e stack. Cash 6-max/100 BB; cash 8-max (referência adaptada, limitada pelo app a 100 BB); torneio 9-max/75 ou 100 BB; torneio 8-max/10 BB.
- Cash 8-max: o texto não especifica stack nem rake. A limitação a 100 BB é uma decisão de implementação, não validação GTO. O tamanho de abertura de 3 BB está na [imagem pública full-ring](https://cdn-pokercoachin.pressidium.com/wp-content/uploads/2026/06/65097636-0-preflop-ranges-for-f.jpg).
- Não são reproduzidas frequências de solver. A fonte tem diferenças entre listas textuais e imagens de ações mistas; o motor identifica explicitamente a consulta como resumo. Grupos sem ação individual discriminada, como SB, permanecem MISTA.
- 3-bet: [diretriz Upswing](https://upswingpoker.com/3-bet-strategy-aggressive-preflop/), núcleo QQ+/AK, cash 100 BB sem ante. O app restringe a um open de 2–5 BB sem callers; 3× em posição, 4× fora. Essas são simplificações de especialista, não tabelas completas contra cada posição. Fora do núcleo, não deduz fold.
- O total do primeiro raise e os blinds determinam o valor a pagar e o mínimo legal; valores inconsistentes geram erro. Nunca se usa o antigo piso fixo de 7,5 BB.
- Pós-flop: [pot odds](https://upswingpoker.com/pot-odds-step-by-step/). EV(call) = equity × (pote antes do call + call) − call, relativamente ao fold. Ação por EV só em cash, heads-up, com encerramento das apostas, sem side pots/rake adicional e com equity fornecida. Sem estimativa de equity nem análise de board.
- Torneios exigem confirmação de contexto sem pressão de ICM/bounty. Não há ajuste automático de ante, rake, stacks intermediários, mesas diferentes, limp, squeeze, 3-bet ou 4-bet.

Conceitos conferidos também no [GTO Wizard](https://blog.gtowizard.com/how-stack-sizes-change-your-range/) e nas [regras Poker TDA](https://www.pokertda.com/view-poker-tda-rules/). Discussões do [Two Plus Two](https://forumserver.twoplustwo.com/170/live-no-limit-holdem-cash/how-closely-do-you-follow-preflop-charts-1821061/) foram contexto de pesquisa, não tabelas incorporadas. Consulta: 21/09/2026.

Use “Carregar exemplo de estudo” para explorar perfis; ao revisar uma mão, preserve os dados reais. “REVISAR” indica falta de cobertura, não fold. A banca total é separada do stack efetivo.

Validação local: `python3 -m unittest -v test_app test_strategy` e `node --check static/app.js`. Os testes incluem transição Spin 3-handed → heads-up, stacks efetivos assimétricos, regressão K4s/BTN e uma matriz automática das 169 mãos nos stacks padrão 8/10/15/20/25 BB para impedir retorno de SEM COBERTURA nos principais estados pré-flop válidos. Não são prova de lucratividade ou de equilíbrio GTO.

Código oficial: `https://github.com/iDougOliveira/Douglas`

## Escopo e conformidade

- O PokerVision pode ler regiões locais da tela para cartas/stacks/mesa; não clica, não controla mouse e não executa apostas.
- O analisador exige confirmação de que a mão terminou ou é uma simulação.
- Não use as recomendações durante partidas comerciais. Consulte as regras da sala.
- Os ranges são educacionais e simplificados, não uma solução GTO.
- O modo torneio ainda não calcula ICM.

## Instalação no Debian/Beelink

```bash
unzip PokerCoach_Local.zip
cd pokercoach-local
chmod +x install.sh
./install.sh
```

O instalador solicita uma senha, cria o serviço `pokercoach.service` e inicia a aplicação automaticamente. Depois abra:

```text
http://IP_DO_BEELINK:8765
```

Para acesso remoto, conecte primeiro à VPN/Tailscale e use o IP VPN do Beelink. Não encaminhe a porta 8765 diretamente no roteador.

## Operação

```bash
systemctl status pokercoach
journalctl -u pokercoach -f
sudo systemctl restart pokercoach
```

Os registros ficam em `data/pokercoach.db`. O projeto usa somente a biblioteca padrão do Python 3.

## Atualização de uma instalação existente

Extraia a nova versão e execute:

```bash
chmod +x pokercoach-local/update.sh
./pokercoach-local/update.sh /home/douglas/PokerCoach
```

A atualização preserva a senha e o banco de dados existente.

## Atualização automática via GitHub

Depois da migração inicial, o timer `pokercoach-update.timer` consulta o GitHub a cada cinco minutos. Uma versão nova só entra em operação após validação; se o health check falhar, o código anterior é restaurado.

Para buscar imediatamente a versão mais nova no Beelink:

```bash
sudo bash /home/douglas/PokerCoach/auto_update.sh
```

Comandos de auditoria:

```bash
systemctl status pokercoach-update.timer
sudo systemctl start pokercoach-update.service
journalctl -u pokercoach-update.service -n 50 --no-pager
```

## Desinstalação do serviço

```bash
sudo systemctl disable --now pokercoach
sudo rm /etc/systemd/system/pokercoach.service
sudo systemctl daemon-reload
```

Os arquivos e o banco não são removidos automaticamente.
