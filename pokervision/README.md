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


### V0.2.1
- detecção das cartas passa a procurar o retângulo branco da própria carta;
- a seleção pode ter margem extra ao redor das cartas;
- não depende mais de dividir a região em posições de largura fixa.


## V0.3.0 — integração com PokerCoach

- publica somente leituras confirmadas em `http://127.0.0.1:8766/state`;
- o navegador do PokerCoach no mesmo Windows consome esse estado automaticamente;
- mão e board só são enviados depois de 3 capturas estáveis;
- nenhuma ação é enviada ao software de poker;
- o bridge aceita apenas origens locais/privadas e permanece restrito ao loopback do Windows.


## V0.3.1 — relay pelo Beelink

O navegador não acessa mais `127.0.0.1:8766`. O PokerVision envia o estado diretamente ao PokerCoach no Beelink e a página consulta o próprio servidor, evitando bloqueios de Local Network Access do navegador.

Destinos tentados automaticamente: `192.168.15.140:8765`, `Beelink:8765` e `beelink.local:8765`. O primeiro que responder passa a ser preferido.


## V0.4.0 — calibração de blinds, stack e pote

Novas regiões persistentes:

- **BLINDS / ANTE**
- **MEU STACK**
- **STACKS DA MESA**
- **POTE**

Essas coordenadas são salvas em `%APPDATA%\PokerVision\config.json` junto com MÃO e BOARD.

O relay já está preparado para transportar:

- small blind / big blind;
- ante;
- stack do hero em fichas;
- stack do hero em BB;
- stacks adversários;
- stack efetivo em BB;
- pote em fichas e em BB.

Nesta versão, essas quatro regiões são apenas de calibração e captura de amostras. O OCR numérico será ativado após validar os recortes reais do replay.


## V0.5.0 — OCR numérico e conversão para BB

As regiões calibradas em V0.4 passam a ser lidas por OCR:

- BLINDS / ANTE;
- MEU STACK;
- STACKS DA MESA;
- POTE.

Conversões automáticas:
- stack do hero em BB = fichas do hero / big blind;
- pote em BB = fichas do pote / big blind;
- stack efetivo = min(stack do hero, maior stack adversário detectado) / big blind.

A leitura numérica exige Tesseract OCR instalado no Windows. O reconhecimento de cartas continua independente do Tesseract.


## V0.6.2 — reconhecimento mais rápido

- Captura visual de mão/board: 125 ms.
- Confirmação: 2 leituras idênticas antes de publicar.
- Envio ao PokerCoach/Beelink: 200 ms.
- OCR de stack/pote permanece em ~1 s para não aumentar o custo do Tesseract.
- Limiares de confiança do reconhecedor de cartas não foram relaxados.


## V0.6.3 — confirmação imediata de cartas

- Captura visual de mão/board: 100 ms.
- Uma leitura válida já confirma mão/board.
- Estado vazio exige 2 capturas para evitar apagar cartas durante animações.
- Publicação ao PokerCoach/Beelink: 100 ms.
- OCR de stack/pote continua separado e conservador.
- Os limiares de confiança do reconhecedor de cartas permanecem inalterados.


## V0.6.4 — board robusto contra fichas sobrepostas

- O BOARD é reconhecido pela parte superior do recorte, onde ficam rank e naipe.
- A parte inferior, onde PokerStars costuma sobrepor fichas e valores, deixa de dominar a detecção.
- Regiões com proporção incompatível com uma carta são descartadas.
- Em leitura incerta, a interface mostra quantas regiões foram detectadas e quantas cartas foram reconhecidas.
- As coordenadas já calibradas continuam válidas.


## V0.6.5 — restauração do reconhecedor estável

- O reconhecedor de mão/board foi restaurado para a versão previamente validada.
- Removidos os filtros agressivos da V0.6.4 que causavam SEM CARTAS e reconhecimento parcial.
- Mantidas as melhorias de velocidade da V0.6.3: captura 100 ms, confirmação imediata de leitura válida e envio 100 ms.
- Mantido o diagnóstico de leitura incerta na interface.
