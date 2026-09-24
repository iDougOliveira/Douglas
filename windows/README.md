# Instalador Windows

A partir da versão 3.18.0, o PokerCoach pode ser distribuído como um único instalador para Windows 10/11 x64.

O instalador inclui:
- PokerCoach web local empacotado, sem exigir Python no computador;
- PokerVision com dependências Python empacotadas;
- atalho "PokerCoach";
- inicialização conjunta: o atalho sobe o servidor em `127.0.0.1:8765`, abre o navegador e inicia o PokerVision;
- banco/configuração gravados em `%LOCALAPPDATA%\PokerCoach`, fora de Program Files;
- modo desktop restrito ao loopback, sem senha no navegador local;
- opção de tentar instalar Tesseract OCR por Winget para stack/pote. Sem Tesseract, reconhecimento de cartas continua funcionando e o OCR numérico fica indisponível.

## Build manual no Windows

```powershell
py -3.13 -m pip install --upgrade pip
py -3.13 -m pip install pyinstaller -r pokervision\requirements.txt

py -3.13 -m PyInstaller --noconfirm --clean --onefile --noconsole --name PokerCoach windows\launcher.py
py -3.13 -m PyInstaller --noconfirm --clean --onefile --noconsole --name PokerCoachServer --add-data "static;static" --add-data "VERSION;." windows\server.py
py -3.13 -m PyInstaller --noconfirm --clean --onefile --noconsole --name PokerVision --paths pokervision pokervision\app.py

& "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe" /DMyAppVersion=3.18.0 windows\installer.iss
```

Saída: `windows\Output\PokerCoach-Setup-3.18.0.exe`.

## Execução instalada

Ao abrir o atalho:
1. inicia o servidor local oculto;
2. espera o health check;
3. abre `http://127.0.0.1:8765` no navegador padrão;
4. abre o PokerVision para seleção das regiões;
5. ao fechar o PokerVision, o servidor iniciado por aquela sessão também é encerrado.

O instalador é por usuário e não exige privilégio de administrador para os arquivos do PokerCoach. A instalação opcional do Tesseract pode exigir confirmação do Windows/Winget.
