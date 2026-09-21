# PokerCoach Local

Painel web local para estudo/revisão de mãos e gestão de banca. Funciona no navegador do celular ou computador; não requer instalação nesses dispositivos.

Interface visual: escolha 3, 4 ou 8 jogadores, clique no assento que contém o botão do dealer e a posição do jogador é calculada automaticamente. As duas cartas são selecionadas em um baralho gráfico.

Código oficial: `https://github.com/iDougOliveira/Douglas`

## Escopo e conformidade

- Não captura tela, não lê cliente de poker, não controla mouse e não executa apostas.
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
