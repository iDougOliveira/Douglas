# PokerVision

Aplicativo Windows de captura por coordenadas para o PokerCoach.

## V0.1.0

Esta primeira versão faz somente a camada de captura/calibração:

- seleciona visualmente a região das duas cartas do jogador;
- seleciona visualmente a região do board;
- salva as coordenadas no perfil do Windows;
- mostra os dois recortes em tempo real;
- permite salvar amostras para a próxima etapa de reconhecimento.

O reconhecimento de valor/naipe será adicionado depois da calibração com imagens reais do software usado nos testes. Isso evita treinar o detector em um layout diferente e gerar cartas erradas.

## Executar no Windows

Abra `run_windows.bat`.

Na primeira execução ele cria `.venv` e instala apenas `mss` e `Pillow`.

As coordenadas ficam em:

`%APPDATA%\PokerVision\config.json`

Amostras ficam em:

`%USERPROFILE%\PokerVisionCaptures`

## Calibração

1. Deixe o software de teste visível na tela.
2. Clique em **Selecionar MÃO**.
3. Arraste um único retângulo envolvendo as duas cartas do jogador.
4. Clique em **Selecionar BOARD**.
5. Arraste um único retângulo envolvendo as cinco posições do board.
6. Clique em **Iniciar monitoramento**.
7. Confirme que os previews mostram exatamente as áreas desejadas.
8. Com cartas visíveis, clique em **Salvar amostra** para gerar material de calibração.

Captura por coordenadas lê os pixels que estão naquela posição da tela. Se outra janela cobrir a região, essa outra janela será capturada.
