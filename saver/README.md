# Kurumi Saver

App web Tizen usado como conteúdo do screensaver nativo do S90D
(`KurumiSvr1.Saver`). A chibi quica na diagonal, espelha ao bater nas laterais e
fica em fundo preto. O launcher nativo cuida do idle, do wake e do keygrab; o app
apenas desenha. Ele declara `launch_mode="caller"` e não captura teclas, para o
launcher tratar o centro/voltar e devolver o app que estava na tela.

## OLED / burn-in

O launcher de idle do S90D entrega o caminho de idle, mas **não** garante
proteção de burn-in por conta própria: o conteúdo web é responsável pela
política. Este app:

- mantém o fundo preto;
- não tem texto, logo ou label fixo em operação normal;
- mantém a chibi em movimento contínuo;
- faz fade para preto no último minuto e para de desenhar aos 10 minutos
  (`MAX_MS`/`FADE_MS` em `js/saver.js`).

O limite de 10 minutos é uma **política conservadora nossa**, não um valor
seguro especificado pela Samsung. Ajuste as constantes em `js/saver.js` se
quiser outra duração. O placeholder "TESTE" só aparece se `assets/chibi.png`
falhar; ele não faz parte da operação normal.
