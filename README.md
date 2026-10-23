# Kurumi S90D Toolkit

Home screen com tema da Kurumi Tokisaki para a Samsung S90D (Tizen 9). É um web app Tizen:
relógio dourado com algarismos romanos, papel de parede e atalhos de apps com ícones seus.

Este repositório também tem as ferramentas usadas para transformar o Kurumi no **Home da TV**,
remover apps opcionais e desligar o auto-update de firmware. Tudo foi testado nesta TV:

| Item | Valor |
|---|---|
| Modelo | `QN55S90DAGXZD` |
| Firmware | `T-PTMDUABC-0090-2130.0` (build 2026-05-14) |
| App ID | `KurumiTV01.Home` |
| Perfil de certificado | `kurumi` |

## Artes e créditos

O wallpaper1, os ícones e a chibi do screensaver são artes geradas por IA com o
**Nano Banana (Google)**, modelo **Argon**, e ampliadas com **Waifu2X**. Não são
artes oficiais. Kurumi Tokisaki / Date A Live pertencem aos seus detentores; os
ícones de apps são marcas dos respectivos donos. Os wallpapers 2–6 e a pasta
`originals/` não estão neste repositório; o app inclui só `wallpaper1.webp` e
funciona com os fallbacks para os demais.

## Projetos relacionados

- [Couchroot](https://github.com/splitcipher/couchroot) — Minimal Hub e pesquisas
  de Home/screensaver para S90D/QN90A; várias ideias daqui vieram de lá.
- [samsung-tv-root](https://github.com/chris-ritsen/samsung-tv-root) — rota de
  root `archive-launcher` usada por `tools/root.py`.
- [cleanyourtv](https://github.com/Gathin23/cleanyourtv) — debloat + launcher para
  **Android TV/Google TV**; não é Tizen, mas é a inspiração do conceito. Este
  projeto é o equivalente Tizen para a S90D.
- [samsung-tizen-tv-debloat](https://github.com/ardazeytin/samsung-tizen-tv-debloat)
  — referência de debloat em Tizen retail.

## Personalizar pelo PC

Tudo fica em `src/`:

| O quê | Onde |
|---|---|
| Papéis de parede | Imagens em `src/assets/` listadas em `wallpapers` no `src/config.json`. Rode `tools\optimize_assets.py` depois de adicionar: ele gera `.webp` 1920x1080 |
| Ícones | Imagens com fundo transparente em `src/assets/icons/`, referenciadas em `icon` (o otimizador gera `.webp` 320x320) |
| Apps | `apps` no `src/config.json`: `match` é parte do nome do app na TV; `appId` (opcional) é o ID exato |
| Entrada HDMI | Um item com `"hdmi": 2` (número da porta) ou `"hdmi": "auto"` (primeira HDMI com algo ligado) em vez de `match` |
| Menu "Mais" | Lista `extras`: cada item é um app (`appId`/`match`), uma HDMI (`hdmi`) ou uma ação (`"action"`, veja abaixo). `glyph` é o texto do selo, `sub` a linha de baixo, `icon` opcional |
| Saudação | `greetings` com `madrugada` (0-4h), `manha`, `tarde` e `noite`. `"greetings": false` usa o `greeting` fixo |
| Frase | `quotes`: lista de frases (troca a cada 10 min). Sem a chave, usa as frases da Kurumi do app |
| Clima | `"weather": "auto"` (local pelo IP, via ipapi.co), `{"lat": -19.9, "lon": -43.9, "city": "BH"}` ou `false` |
| Pendrive | `usbApps`: IDs a tentar no item "App de mídia da Samsung" (padrão `com.samsung.tv.mycontents`, `org.tizen.usb-launcher-tv`) |
| Outros | `subtitle`, `columns`, `slideSeconds` (apresentação de fotos, padrão 6) |

Ações do `extras`: `usb` (pendrive), `inputs` (entradas HDMI com status), `info` (informações do sistema),
`prefs` (ajustes), `walls`, `all`, `samsung`, `reload` e `refresh` (limpa o cache de apps e do clima e recarrega).

O clima é opcional. Com `"weather": "auto"`, o app consulta `ipapi.co` (ou
`ipwho.is`) para localizar por IP e a Open-Meteo para o clima; use
`"weather": false` para não fazer essas requisições.

O repo público inclui só `wallpaper1.webp`; para adicionar outros, coloque as
imagens em `src/assets/`, rode o otimizador e liste-as em `wallpapers`. A pasta
`originals/` não está incluída. Para um ícone novo com fundo branco:

```powershell
tools\venv\Scripts\python.exe tools\remove_bg.py "C:\caminho\imagem.jpg" src\assets\icons\nome.png
```

Se um ícone não existir, o app usa o ícone oficial do app instalado; se nem ele existir, a inicial do nome.

Para ver os IDs exatos dos apps instalados: abra o Kurumi Home na TV e aperte o **botão verde**.

## Controle remoto

| Tecla | Ação |
|---|---|
| Setas / OK | Navegar e abrir |
| ▼ na fileira de apps | Botões "Papel de parede", "Apps instalados", "☰ Mais" e "Home da Samsung" no rodapé; ▲ volta aos apps |
| Azul | Abre/fecha o menu **Mais** de qualquer tela |
| Vermelho | Abre o seletor de papel de parede: setas mostram a prévia, OK salva, Voltar cancela |
| Verde | Apps instalados (com IDs, só os apps de verdade) |
| Amarelo | Recarregar |
| Voltar | Volta uma tela; na tela inicial abre o **Home da Samsung** |

O Voltar abre o Samsung Home de propósito: quando o Kurumi é o Home da TV, sair do app sozinho
voltaria para o próprio Kurumi. O botão **Home** do controle volta para o Kurumi.

## Menu "Mais"

| Item | O que faz |
|---|---|
| Pendrive | Navega pelas pastas do pendrive e abre fotos, vídeos e músicas no próprio Kurumi. Formatos que o player web não abre vão para o player da TV. Avisa quando um pendrive é conectado |
| Entradas HDMI | Lista HDMI 1-4 e mostra em quais há aparelho ligado; OK troca a entrada |
| Navegador, Loja Samsung, Configurações | Abrem os apps da TV |
| Protetor de tela | Abre o Kurumi Saver na hora |
| Papel de parede, Apps instalados, Home da Samsung | O mesmo dos botões do rodapé |
| Informações | Modelo, firmware, rede, IP, Wi-Fi, tela, memória, armazenamento, pendrives, versão, local do clima |
| Ajustes | Liga/desliga ponteiro dos segundos, animações de foco, frase e clima (fica salvo na TV) |
| Recarregar | Limpa o cache de apps e do clima e recarrega |

No visualizador do pendrive: ◀ ▶ trocam a foto (ou avançam/voltam 10 s no vídeo), ▲ ▼ vão para o
arquivo anterior/próximo, OK pausa (ou inicia a apresentação de fotos), Voltar sai. As teclas ⏯ ⏪ ⏩ ⏹
do controle também funcionam.

## Otimização do app

O app foi ajustado para o hardware da TV:

- wallpapers em WebP 1920x1080 e ícones em WebP 320x320: os assets caíram de ~4,7 MB (original)
  para ~1 MB. O app desenha em 1920x1080, então um wallpaper 4K só gastaria memória
  (~33 MB decodificado contra ~8 MB);
- **nenhum timer por segundo**: os ponteiros giram por animação CSS no compositor da TV, e o
  JS só acorda uma vez por minuto para o relógio digital, a saudação e a frase. Parado na tela
  inicial, o app não mexe em nada do DOM;
- tudo para quando outro app está na tela (`visibilitychange`), e o relógio se acerta ao voltar;
- os efeitos de foco não animam `box-shadow` (só `transform`/`opacity`); "Animações: desligado"
  nos Ajustes tira até isso;
- o menu "Mais" e as telas de pendrive/entradas/informações/ajustes usam um único painel e
  selos de texto, sem imagens para decodificar;
- o vídeo do pendrive libera o decodificador ao sair do visualizador;
- o clima é buscado no máximo a cada 30 min e fica em cache; o local, a cada 7 dias;
- a lista de apps é filtrada para apps de verdade e fica em cache no `localStorage`, então o
  segundo boot é instantâneo;
- o `mock-tizen.js` (simulador para o PC) não vai para o pacote da TV.

Para reotimizar depois de adicionar wallpapers ou ícones:

```powershell
tools\venv\Scripts\python.exe tools\optimize_assets.py
```

Uma cópia dos assets antigos fica em `tools/backups/assets-<data>/`.

## Testar no PC

```powershell
.\preview.ps1
```

Abra http://localhost:8765. Setas, Enter, Esc (Voltar), `r`, `g`, `y`, `b` imitam o controle.
O preview simula um pendrive com algumas pastas.

## Enviar para a TV

Uma vez: criar o perfil de certificado Samsung chamado `kurumi` no Certificate Manager
(`C:\tizen-studio\tools\certificate-manager\certificate-manager.exe`).

Depois, a cada mudança:

```powershell
.\deploy.ps1
```

Use sempre o mesmo perfil de certificado: desinstalar para contornar um certificado diferente apaga o
papel de parede salvo. Mantenha o ID `KurumiTV01.Home`.

## Screensaver (Kurumi Saver)

O screensaver nativo do S90D é o `com.samsung.tv.spotlight-ss`; o launcher
`com.samsung.tv.glscreensaver-launcher` lê o `ContentList.json` e lança o app
escolhido. O Kurumi Saver é um app web separado (`KurumiSvr1.Saver`) com a chibi
quicando na diagonal e espelhando ao bater nas bordas, em fundo preto.

```powershell
.\deploy-saver.ps1                  # instala/atualiza o app
py -3 tools\saver.py apply --yes    # fallback manual (sem o boot hook)
py -3 tools\saver.py restore --yes  # tira o mount atual
py -3 tools\boot_prepare.py         # gera o patch desta firmware
py -3 tools\boot_install.py install # instala o boot hook automatico
py -3 tools\boot_install.py restore # remove o boot hook automatico
```

A imagem fica em `saver/assets/chibi.png`. Para trocar por outra com fundo branco:

```powershell
tools\venv\Scripts\python.exe tools\remove_bg.py "C:\caminho\chibi.jpg" saver\assets\chibi.png
```

O `ContentList.json` fica em `/usr` (read-only). O boot hook é opcional e, nesta
TV, está instalado: no boot ele roda o `/opt/minimal-saver/Boot.dll` pelo AT-HUB,
preserva o `/opt/etc/parseinfo.sh` original e faz o bind-mount read-only do
ContentList do Kurumi. Em uma TV nova, rode `boot_prepare.py` (gera o patch e o
`boot-meta.json` a partir da sua `oneservice`) e `boot_install.py install`. Os
backups do `oneservice`/tabela/parseinfo/ContentList ficam em
`/opt/minimal-saver`, e o log do boot fica em `/opt/minimal-saver/last-boot.log`.

O helper é específico desta firmware (`T-PTMDUABC-0090-2130.0`): ele confere os
hashes do `parseinfo.sh` (`c636...`), do ContentList stock (`23b0...`) e do
ContentList do Kurumi (`e802...`). Se uma atualização de firmware mudar algum,
ele registra no log e mantém o screensaver original; nesse caso o hook precisa
ser revalidado/regenerado antes de reinstalar. O `systemctl show AT-HUB.service`
pode continuar mostrando o `parseinfo.sh` estático; quem lê a cache patchada é o
`oneservice` no boot, então o teste real é reiniciar a TV.

Para reinstalar o hook: `py -3 tools\boot_install.py install`. Para remover e
voltar ao screensaver da Samsung: `py -3 tools\boot_install.py restore`.

## Deixar o Kurumi como Home da TV

```powershell
py -3 tools\home.py query
py -3 tools\home.py set --yes
py -3 tools\home.py restore --yes
```

O `set` faz três coisas, pela API nativa da TV:

1. aponta a operação `http://tizen.org/appcontrol/operation/main` para `KurumiTV01.Home`
   (é o que o botão Home consulta);
2. grava `db/appfw/home_appid=KurumiTV01.Home`;
3. liga o autostart do Smart Hub (`auto_start=1`), para o app abrir no boot.

Antes de mudar, ele salva os valores originais em `tools/home-route/stock.json`. O `restore`
usa esse arquivo para devolver o Home da Samsung e o boot originais. Sem o `stock.json`, ele
não mexe em nada.

O helper roda na TV como `uid=901(sdk)` via `/usr/bin/dotnet`. O código está em
`tools/home-route/` e é compilado para `net6.0`, o runtime da TV.

## Remover apps opcionais (debloat)

```powershell
py -3 tools\debloat.py plan
py -3 tools\debloat.py apply --yes
```

Categorias configuradas em `tools/debloat.py`:

| Categoria | O que sai |
|---|---|
| TV Plus | App Samsung TV Plus, canais e `slive-daemon` |
| Bixby/voz | Bixby, capsule viewer, voz on-device, far-field e serviços de voz |
| Jogos | Gaming Hub, Game Home, GamePad Guide e daemons `gh*` |
| SmartThings/IoT | SmartThings, hub IoT, Digital Butler e notificações |
| Saúde/Life+ | Samsung Health (MDE), Life+ e preview |
| Arte/Ambient | Art App, HomeArt, Generative Wallpaper e os templates de ambient |

Ficam de fora da remoção: `com.samsung.tv.gamebar` (Game Bar), `context-aware-service`,
`CinemaGraph*`, `custom-picture-resource` e o pipeline de imagem.

O que **não** é tocado: YouTube, Crunchyroll, Plex, Globoplay, Kurumi, Samsung Home,
a loja, a conta Samsung, o `tv-viewer`, o Game Bar (`com.samsung.tv.gamebar`) e o pipeline
de imagem. Por isso **Game Mode, 144 Hz, VRR, HDR e ALLM continuam funcionando**; só a
loja/área de nuvem do Gaming Hub sai.

Antes de remover, o script:

- confere no banco de pacotes se cada alvo é `removable=true`, `preload=false`,
  `readonly=false` e `system=false`;
- recusa qualquer pacote que seja dependência de um app que fica;
- copia `/opt/dbspace/.pkgmgr_parser.db` e `.appsvc.db` para `tools/backups/<data>/`;
- remove um a um com `/usr/bin/pkgcmd -u`, confere que sumiu do banco e roda
  `pragma integrity_check`;
- para no primeiro erro.

Pode rodar de novo: pacotes já ausentes são ignorados. Se um firmware futuro reinstalar
algum app, o `apply` remove de novo.

O próprio sistema pode restaurar alguns apps depois de um reboot. Nesta TV voltaram
`HEPsqFNie0` (TV Plus), `com.samsung.tv.SmartThingsApp`,
`com.samsung.tv.tvPlusDeeplinker`, `com.samsung.tv.context-aware-service` e
`com.samsung.tv.CinemaGraphApp`. Os dois últimos ficaram **de fora da lista de
propósito**: o AI Picture usa esse pipeline. O `apply` remove os apps de loja que
voltarem; é idempotente e não toca nos serviços de imagem.

## Desligar atualizações automáticas

```powershell
py -3 tools\updates.py off --yes
py -3 tools\updates.py query
py -3 tools\updates.py on --yes
```

As chaves são as mesmas que o `SWUAutoUpgrade` usa:

| Chave | Desligado |
|---|---|
| `db/menu/support/softwareupdate/autoupdate` | `0` |
| `db/menu/support/softwareupdate/preupdate_consent` | `0` |
| `db/menu/support/softwareupdate/block_standby_scan` | não existe nesta firmware; o `autoupdate` é o interruptor principal |

Confira também no menu da TV: **Configurações → Todas as configurações → Suporte →
Atualização de software → Atualização automática** deve estar desligado.

Isso reduz o risco, mas não é uma garantia absoluta:

- um update **manual** ou um **factory reset** pode restaurar o Home da Samsung,
  reinstalar os apps removidos e religar o auto-update;
- atualizações de **apps** não desfazem o Home (o Kurumi é sideloaded e o ID não muda);
  apps removidos não são reinstalados por update de app;
- se quiser uma camada extra, bloqueie no roteador/DNS os domínios de OTA da Samsung
  (ex.: `osbcngr.samsung.com`, `otn.samsungcloudcdn.com`, `samsungotn.net`), sem bloquear
  a loja se você ainda usa a loja.

## Depois de uma atualização de firmware

Se a TV atualizar mesmo assim, o comando abaixo reaplica tudo:

```powershell
.\reapply.ps1
```

Ele faz, nesta ordem: deploy do Kurumi Home, deploy do Kurumi Saver, Home no Kurumi,
auto-update desligado, debloat e screensaver. Leva cerca de 9 a 12 minutos porque o
script espera o `sdbd` liberar entre as injeções. Use `-SkipSaver` se não quiser a
parte do screensaver. Os backups do banco de pacotes ficam em `tools/backups/`; os
valores originais do Home ficam em `tools/home-route/stock.json`.

O `reapply.ps1` reaplica o screensaver pelo `saver.py` (mount manual). O boot hook
do AT-HUB é separado e específico da firmware; depois de um firmware novo, valide
os hashes do `Boot.dll`/`oneservice` antes de reinstalar com
`py -3 tools\boot_install.py install`.

## Root temporário (opcional)

O debloat precisa de root. O root desta TV é **volátil**: não instala serviço no boot e
some no reboot. O script usa o caminho `archive-launcher` do projeto
[samsung-tv-root](https://github.com/chris-ritsen/samsung-tv-root), que foi testado no
S90D. Ele troca `/etc/passwd` e a chave pública do SDB apenas dentro de um namespace de
mount privado, executa o payload como root e limpa tudo no final.

```powershell
$env:PATH = 'C:\Program Files\Git\usr\bin;' + $env:PATH   # openssl do Git
py -3 tools\root.py probe
py -3 tools\root.py exec "id"
```

Requisitos: `sdb` do Tizen Studio, .NET 6 no PC para compilar o helper, OpenSSL no PATH
para assinar o arquivo do archive-launcher, e a ferramenta `samsung-tv-root` 0.0.11 em
`%LOCALAPPDATA%\kurumi-tv-tools\` (o `tools/root.py` aponta para lá).

O `sdbd` desta TV fica preso por alguns minutos depois de cada `appinstall`. Por isso o
`tools/tv_agent.py` abre **um** shell `sdk` persistente com uma única injeção e faz todo o
resto por ele. Se um comando travar, espere ~3 minutos e tente de novo.

## Ferramentas

| Arquivo | Para quê |
|---|---|
| `tools/tv.py` | shell `sdk`, push e diagnóstico pela injeção de nome de pacote |
| `tools/tv_agent.py` | shell `sdk` persistente por TCP, sem novas injeções |
| `tools/home.py` | aponta/restaura o Home da TV |
| `tools/home-route/` | helper C# que usa `app_operation_set_current_app` e `vconf` |
| `saver/` + `deploy-saver.ps1` | app web da chibi para o screensaver |
| `tools/saver.py` | aponta/restaura o screensaver Kurumi (mount manual) |
| `tools/boot-hook/` | `Boot.dll` que monta o ContentList no boot |
| `tools/boot_prepare.py` | gera o patch/`boot-meta.json` desta firmware |
| `tools/boot_install.py` | instala/remove o boot hook do AT-HUB |
| `tools/debloat.py` | plano e remoção dos apps opcionais |
| `tools/updates.py` | liga/desliga auto-update de firmware |
| `tools/root.py` | root temporário pelo archive-launcher |
| `tools/backups/` | backups do banco de pacotes feitos antes do debloat |
| `reapply.ps1` | reaplica Home + updates + debloat + screensaver depois de um firmware novo |

## Avisos

- Isto é ferramenta pessoal, testada em **uma** TV e firmware. Não é um instalador universal.
- Remover apps pode quebrar recursos que você usa. O backup é do banco de pacotes, não dos
  binários; apps removidos podem ser reinstalados pela loja, mas nem sempre com o mesmo estado.
- Root e mudanças de sistema têm risco. Leia o que cada comando faz antes de rodar.
- Não remova `com.samsung.tv.csfs` (Samsung Home): ele é o fallback do botão Voltar.
- Não afiliado à Samsung, à Date A Live/Kurumi Tokisaki ou aos donos dos apps citados.

## Licença

O código original está sob **MIT**; veja `LICENSE`. As artes de IA incluídas são
para o tema do projeto; personagens, marcas e ícones de apps pertencem aos seus
donos. Veja `CREDITS.md` para as atribuições dos projetos e bibliotecas usados.
