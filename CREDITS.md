# Créditos e atribuições

Este projeto é pessoal e não é afiliado à Samsung, à Date A Live/Kurumi Tokisaki
ou aos donos dos apps citados.

## Projetos e ideias que ajudaram

- **[Couchroot](https://github.com/splitcipher/couchroot)** (splitcipher, licença
  0BSD) — pesquisas de Home routing, screensaver e setup para S90D/QN90A. As
  ideias de `app_operation_set_current_app`/vconf do helper de Home e do boot
  helper do screensaver foram adaptadas daí.
- **[samsung-tv-root](https://github.com/chris-ritsen/samsung-tv-root)**
  (licença Unlicense) — rota de root `archive-launcher` usada por
  `tools/root.py`; os payloads compilados vêm do release oficial do projeto.
- **[motodrizzle no r/Tizen](https://www.reddit.com/r/Tizen/comments/1wl4e0n/i_made_a_minimal_plexyoutube_launcher_the_default/)**
  — relato original de transformar um launcher local no Home do S90D e de
  enxugar os helpers do Samsung Home.
- **[cleanyourtv](https://github.com/Gathin23/cleanyourtv)** (MIT) — debloat +
  launcher para Android TV/Google TV. Não é Tizen; é a inspiração do conceito
  “debloat + launcher”, e este projeto é o equivalente Tizen para a S90D.
- **[samsung-tizen-tv-debloat](https://github.com/ardazeytin/samsung-tizen-tv-debloat)**
  (MIT) — referência pública de debloat em Tizen retail.
- **[withoutbg](https://github.com/withoutbg/withoutbg)** — modelo local usado
  por `tools/remove_bg.py` para remover o fundo branco das imagens. O modelo não
  é redistribuído neste repositório.

## Artes

- Wallpaper1, ícones e a chibi do screensaver: artes geradas por IA com o
  **Nano Banana (Google)**, modelo **Argon**, e ampliadas em qualidade com
  **Waifu2X**.
- Kurumi Tokisaki e Date A Live pertencem aos seus respectivos detentores.
- Os ícones de YouTube, Crunchyroll, Plex, IPTV e PC são usados apenas para
  identificar os apps; as marcas pertencem aos seus donos.
- Os wallpapers 2–6 e a pasta `originals/` não fazem parte deste repositório.

## Ferramentas de terceiros não redistribuídas

- Samsung Tizen Studio / `sdb` / Certificate Manager.
- Samsung `samsung-tv-root` release e payloads.
- Python, Pillow, .NET SDK, OpenSSL e demais dependências instaladas pelo usuário.
