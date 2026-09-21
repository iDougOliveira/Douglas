# PokerVision

Aplicativo Windows de captura por coordenadas para o PokerCoach.

## V0.2.1

A V0.2.1 torna o reconhecimento tolerante à margem do retângulo selecionado:

- reconhece valor e naipe das duas cartas da mão;
- reconhece 0, 3, 4 ou 5 cartas no board;
- diferencia **sem carta**, **leitura incerta** e **carta reconhecida**;
- detecta automaticamente **PRÉ-FLOP / FLOP / TURN / RIVER**;
- exige a mesma leitura em 3 capturas antes de confirmá-la;
- continua salvando as coordenadas e permitindo novas amostras.

Os templates armazenados no repositório são máscaras binárias normalizadas. As imagens brutas do replay não são armazenadas no GitHub.

## Executar no Windows

Abra `run_windows.bat`.

Na primeira execução, ou quando entra uma dependência nova, ele prepara automaticamente o ambiente `.venv`.

As coordenadas ficam em:

`%APPDATA%\PokerVision\config.json`

Amostras ficam em:

`%USERPROFILE%\PokerVisionCaptures`

## Calibração

1. Deixe o replay ou software de teste visível.
2. Clique em **Selecionar MÃO**.
3. Arraste um retângulo envolvendo exatamente as duas posições das suas cartas.
4. Clique em **Selecionar BOARD**.
5. Arraste um retângulo envolvendo as cinco posições do board.
6. Clique em **Iniciar monitoramento**.
7. O programa mostrará os recortes e as cartas detectadas.
8. Board vazio é tratado como **PRÉ-FLOP**, não como erro.
9. Se aparecer **LEITURA INCERTA**, use **Salvar amostra** para gerar material de ajuste.

Captura por coordenadas lê os pixels visíveis naquela posição da tela. Se outra janela cobrir a região, essa outra janela será capturada.


A seleção pode conter margem verde/escura ao redor das cartas. O reconhecedor encontra o corpo branco de cada carta e recorta cada carta internamente antes de comparar valor e naipe.
