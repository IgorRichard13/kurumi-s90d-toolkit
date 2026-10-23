/* Kurumi Home: clock, wallpaper and app tiles, driven by the TV remote.
   Leveza: nenhum timer por segundo (os ponteiros giram por CSS), o relógio
   digital acorda uma vez por minuto e tudo para quando o app sai da tela. */
(function () {
  'use strict';

  var KEY = {
    LEFT: 37, UP: 38, RIGHT: 39, DOWN: 40, ENTER: 13,
    BACK: 10009, ESC: 27, BACKSPACE: 8,
    RED: 403, GREEN: 404, YELLOW: 405, BLUE: 406,
    PLAYPAUSE: 10252, PLAY: 415, PAUSE: 19, STOP: 413, FF: 417, RW: 412, PREV: 10232, NEXT: 10233
  };
  var TV_KEYS = ['ColorF0Red', 'ColorF1Green', 'ColorF2Yellow', 'ColorF3Blue',
    'MediaPlayPause', 'MediaPlay', 'MediaPause', 'MediaStop', 'MediaFastForward', 'MediaRewind',
    'MediaTrackPrevious', 'MediaTrackNext'];

  // zone: 'tiles' (app row) or 'actions' (buttons under the apps, reached with Down)
  var state = {
    cfg: null, installed: [], tiles: [], focus: 0, view: 'home', allFocus: 0, wall: 0,
    zone: 'tiles', actFocus: 0, wallFocus: 0, wallBefore: 0, moreItems: [], moreFocus: 0
  };
  var MORE_COLS = 3;

  function $(id) { return document.getElementById(id); }
  function show(id) { $(id).classList.remove('hidden'); }
  function hide(id) { $(id).classList.add('hidden'); }
  function errText(e) { return e && e.message ? e.message : String(e); }

  function fit() {
    var s = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
    $('stage').style.transform = 'scale(' + s + ')';
  }

  function toast(msg) {
    var t = $('toast');
    t.textContent = msg;
    show('toast');
    clearTimeout(toast.timer);
    toast.timer = setTimeout(function () { hide('toast'); }, 3500);
  }

  function loadJSON(url, timeout) {
    return new Promise(function (resolve, reject) {
      var x = new XMLHttpRequest();
      x.open('GET', url);
      if (timeout) x.timeout = timeout;
      x.onload = function () {
        // status 0 is what a packaged app's local file returns
        if (x.status === 200 || x.status === 0) {
          try { resolve(JSON.parse(x.responseText)); } catch (e) { reject(e); }
        } else { reject(new Error(url + ': ' + x.status)); }
      };
      x.onerror = x.ontimeout = function () { reject(new Error('could not read ' + url)); };
      x.send();
    });
  }

  function store(key, val) {
    try {
      if (val === undefined) { var raw = localStorage.getItem(key); return raw ? JSON.parse(raw) : null; }
      localStorage.setItem(key, JSON.stringify(val));
    } catch (e) { /* storage off */ }
    return null;
  }

  /* Ajustes, guardados na TV */
  var prefs = { sec: true, anim: true, quote: true, weather: true };
  function loadPrefs() {
    var p = store('kurumi.prefs');
    if (p) for (var k in prefs) if (typeof p[k] === 'boolean') prefs[k] = p[k];
    applyPrefs();
  }
  function applyPrefs() {
    document.body.classList.toggle('nosec', !prefs.sec);
    document.body.classList.toggle('noanim', !prefs.anim);
    $('quote').classList.toggle('hidden', !prefs.quote);
    $('weather').classList.toggle('hidden', !prefs.weather);
    if (prefs.sec) syncHands();
  }

  var APP_CACHE = 'kurumi.apps.v1';
  var CONSUMER_IDS = [
    'org.tizen.netflix-app', 'org.tizen.primevideo', 'org.tizen.browser',
    'com.samsung.tv.tvplus', 'com.samsung.tv.store'
  ];

  // A TV expoe centenas de servicos internos em getAppsInfo. O painel de apps
  // so precisa dos apps de verdade; filtrar cedo tambem reduz o custo de
  // renderizar a lista inteira.
  function isConsumerApp(a) {
    return /^[A-Za-z0-9]{10}\./.test(a.id) || CONSUMER_IDS.indexOf(a.id) >= 0;
  }

  function normalizeApps(list) {
    return list
      .filter(function (a) { return a.show !== false && isConsumerApp(a); })
      .map(function (a) { return { id: a.id, name: a.name || a.id, icon: a.iconPath }; })
      .sort(function (a, b) { return a.name.localeCompare(b.name); });
  }

  // Devolve o cache na hora e atualiza em segundo plano; so espera o
  // getAppsInfo (a chamada lenta do Tizen) na primeira execucao.
  function installedApps() {
    return new Promise(function (resolve) {
      var cached = store(APP_CACHE);
      if (cached && !cached.length) cached = null;
      var answered = false;
      function answer(list) {
        if (answered) return;
        answered = true;
        resolve(list);
      }
      if (cached) answer(cached);
      try {
        tizen.application.getAppsInfo(function (list) {
          var apps = normalizeApps(list);
          var same = cached && JSON.stringify(apps) === JSON.stringify(cached);
          if (!same) store(APP_CACHE, apps);
          if (!cached) { answer(apps); return; }
          if (same) return;
          state.installed = apps;
          if (state.cfg) {
            state.tiles = state.cfg.apps.map(resolveTile);
            state.moreItems = (state.cfg.extras || []).map(resolveExtra);
            renderTiles();
          }
        }, function () { answer(cached || []); });
      } catch (e) { answer(cached || []); }
    });
  }

  // A config entry names its app by Tizen id ("appId") or by part of its title ("match").
  function resolveTile(entry) {
    // "hdmi": a port number, or "auto" for the first HDMI with something plugged in
    if (entry.hdmi !== undefined) {
      return { name: entry.name || 'HDMI', hdmi: entry.hdmi, icons: [entry.icon].filter(Boolean), installed: true };
    }
    var app = null, i;
    if (entry.appId) {
      for (i = 0; i < state.installed.length && !app; i++) {
        if (state.installed[i].id === entry.appId) app = state.installed[i];
      }
    }
    if (!app && entry.match) {
      var m = entry.match.toLowerCase();
      for (i = 0; i < state.installed.length && !app; i++) {
        if (state.installed[i].name.toLowerCase().indexOf(m) >= 0) app = state.installed[i];
      }
    }
    return {
      name: entry.name || (app && app.name) || entry.appId || '?',
      appId: app ? app.id : entry.appId,
      icons: [entry.icon, app && app.icon].filter(Boolean),
      installed: !!app
    };
  }

  // An <img> that walks down a list of sources, then falls back to the first letter.
  function iconEl(sources, name, letterClass, lazy) {
    var wrap = document.createDocumentFragment();
    var i = 0;
    function next() {
      if (i >= sources.length) {
        var l = document.createElement('div');
        l.className = letterClass;
        l.textContent = (name || '?').charAt(0).toUpperCase();
        if (img.parentNode) img.parentNode.replaceChild(l, img);
        else wrap.replaceChild(l, img);
        return;
      }
      img.src = sources[i++];
    }
    var img = document.createElement('img');
    img.alt = '';
    img.decoding = 'async';
    if (lazy) img.loading = 'lazy';
    img.onerror = next;
    wrap.appendChild(img);
    next();
    return wrap;
  }

  function renderTiles() {
    var box = $('tiles');
    var frag = document.createDocumentFragment();
    box.style.gridTemplateColumns = 'repeat(' + state.cfg.columns + ', 1fr)';
    state.tiles.forEach(function (t, idx) {
      var el = document.createElement('div');
      el.className = 'tile' + (t.installed ? '' : ' missing');
      el.appendChild(iconEl(t.icons, t.name, 'letter'));
      var label = document.createElement('div');
      label.className = 'label';
      label.textContent = t.installed ? t.name : t.name + ' (não instalado)';
      el.appendChild(label);
      el.onclick = function () { state.zone = 'tiles'; state.focus = idx; paintFocus(); openTile(t); };
      frag.appendChild(el);
    });
    box.innerHTML = '';
    box.appendChild(frag);
    state.focus = Math.min(state.focus, Math.max(0, state.tiles.length - 1));
    paintFocus();
  }

  function paintFocus() {
    var els = $('tiles').children, i;
    for (i = 0; i < els.length; i++) els[i].classList.toggle('focus', state.zone === 'tiles' && i === state.focus);
    var pills = $('actions').children;
    for (i = 0; i < pills.length; i++) pills[i].classList.toggle('focus', state.zone === 'actions' && i === state.actFocus);
  }

  function runAction(name) {
    if (name === 'walls') openWalls();
    else if (name === 'all') openAll();
    else if (name === 'more') openMore();
    else if (name === 'samsung') openSamsungHome();
  }

  /* "Mais" menu: less-used shortcuts from cfg.extras.
     Each entry is an app (appId/match), an HDMI input (hdmi), or an action:
     usb, inputs, info, prefs, walls, all, samsung, reload, refresh.
     A "glyph" or "icon" draws the badge. */
  function resolveExtra(entry) {
    var x = { name: entry.name || '?', glyph: entry.glyph || '', icon: entry.icon, sub: entry.sub || '' };
    if (entry.action) { x.action = entry.action; return x; }
    if (entry.hdmi !== undefined) { x.hdmi = entry.hdmi; return x; }
    var t = resolveTile(entry);
    x.appId = t.appId;
    return x;
  }

  var ACTIONS = {
    usb: function () { openUsb(); },
    inputs: function () { openInputs(); },
    info: function () { openInfo(); },
    prefs: function () { openPrefs(); },
    walls: function () { closeMore(); openWalls(); },
    all: function () { closeMore(); openAll(); },
    samsung: function () { openSamsungHome(); },
    reload: function () { location.reload(); },
    // esquece o cache de apps e o clima, e recarrega
    refresh: function () {
      try { localStorage.removeItem(APP_CACHE); localStorage.removeItem('kurumi.wx'); localStorage.removeItem('kurumi.loc'); } catch (e) { /* */ }
      location.reload();
    }
  };

  function runExtra(x) {
    if (!x) return;
    if (x.action) {
      if (ACTIONS[x.action]) ACTIONS[x.action]();
      else toast('Ação desconhecida: ' + x.action);
    }
    else if (x.hdmi !== undefined) switchHdmi(x.hdmi, x.name);
    else launch(x.appId, x.name);
  }

  // Shared renderer for the "Mais" grid and the list panel.
  function renderItems(box, items, onPick) {
    var frag = document.createDocumentFragment();
    items.forEach(function (x, idx) {
      var el = document.createElement('div');
      el.className = 'mitem' + (x.cls ? ' ' + x.cls : '');
      var badge = document.createElement('div');
      badge.className = 'badge';
      if (x.icon) badge.appendChild(iconEl([x.icon], x.glyph || x.name, 'badge-letter', true));
      else badge.textContent = x.glyph || (x.name || '?').charAt(0).toUpperCase();
      el.appendChild(badge);
      var txt = document.createElement('div');
      txt.className = 'mtext';
      var name = document.createElement('div');
      name.className = 'mname';
      name.textContent = x.name;
      txt.appendChild(name);
      var sub = document.createElement('div');
      sub.className = 'msub';
      sub.textContent = x.sub || '';
      if (x.sub) txt.appendChild(sub);
      el.appendChild(txt);
      el.onclick = function () { onPick(idx); };
      frag.appendChild(el);
    });
    box.innerHTML = '';
    box.appendChild(frag);
  }

  function paintGrid(box, focus) {
    var els = box.children;
    if (box.lastFocus !== undefined && els[box.lastFocus]) els[box.lastFocus].classList.remove('focus');
    if (els[focus]) {
      els[focus].classList.add('focus');
      if (els[focus].scrollIntoView) els[focus].scrollIntoView({ block: 'nearest' });
    }
    box.lastFocus = focus;
  }

  function openMore(keepFocus) {
    if (!state.moreItems.length) { toast('Nenhum item em "extras" no config.json'); return; }
    hideOverlays();
    state.view = 'more';
    if (!keepFocus) state.moreFocus = 0;
    var grid = $('moregrid');
    grid.lastFocus = undefined;
    renderItems(grid, state.moreItems, function (idx) { state.moreFocus = idx; paintMore(); runExtra(state.moreItems[idx]); });
    show('more');
    paintMore();
  }

  function paintMore() { paintGrid($('moregrid'), state.moreFocus); }

  function closeMore() { state.view = 'home'; hide('more'); paintFocus(); }

  function hideOverlays() { ['more', 'panel', 'all', 'walls'].forEach(hide); }

  /* List panel: one DOM section reused by pendrive, entradas, informações e ajustes.
     o = { title, hint, items, cols, compact, focus, back } */
  var panel = { items: [], cols: 3, focus: 0, back: null };

  function openPanel(o) {
    hideOverlays();
    state.view = 'panel';
    panel = o;
    panel.cols = o.cols || 3;
    panel.focus = Math.min(o.focus || 0, Math.max(0, o.items.length - 1));
    $('ptitle').textContent = o.title;
    $('phint').textContent = o.hint || 'OK abre · Voltar volta';
    var box = $('plist');
    box.className = o.compact ? 'compact' : '';
    box.style.gridTemplateColumns = 'repeat(' + panel.cols + ', 1fr)';
    box.lastFocus = undefined;
    renderItems(box, o.items, function (idx) { panel.focus = idx; paintGrid(box, idx); pickPanel(); });
    show('panel');
    paintGrid(box, panel.focus);
  }

  function pickPanel() {
    var it = panel.items[panel.focus];
    if (it && it.run) it.run(it, panel.focus);
  }

  function panelBack() {
    if (panel.back) panel.back();
    else { hide('panel'); openMore(true); }
  }

  function setItem(idx, sub, glyph, cls) {
    var el = $('plist').children[idx];
    var it = panel.items[idx];
    if (!el || !it) return;
    if (sub !== undefined) {
      it.sub = sub;
      var s = el.querySelector('.msub');
      if (!s) { s = document.createElement('div'); s.className = 'msub'; el.lastChild.appendChild(s); }
      s.textContent = sub;
    }
    if (glyph !== undefined) el.firstChild.textContent = glyph;
    if (cls !== undefined) { el.classList.toggle('on', cls === 'on'); }
  }

  // O Kurumi pode ser o Home da TV. Sair do app sozinho voltaria para ele
  // mesmo, entao o Voltar abre o Samsung Home de proposito.
  function openSamsungHome() { launch('com.samsung.tv.csfs', 'Home da Samsung'); }

  function openTile(t) {
    if (t.hdmi !== undefined) switchHdmi(t.hdmi, t.name);
    else launch(t.appId, t.name);
  }

  function hdmiSources(cb, fail) {
    try {
      tizen.systeminfo.getPropertyValue('VIDEOSOURCE', function (vs) {
        function onlyHdmi(list, on) {
          return (list || []).filter(function (s) { return s.type === 'HDMI'; })
            .map(function (s) { return { src: s, number: s.number, on: on }; });
        }
        cb(onlyHdmi(vs.connected, true).concat(onlyHdmi(vs.disconnected, false))
          .sort(function (a, b) { return a.number - b.number; }));
      }, fail);
    } catch (e) { fail(e); }
  }

  // Switch the TV to an HDMI input, then bring up Samsung's TV viewer to show it.
  function switchHdmi(port, name) {
    function fail(e) { toast(name + ': ' + errText(e)); }
    hdmiSources(function (list) {
      var hit = list.filter(function (s) { return port === 'auto' ? s.on : s.number === Number(port); })[0];
      if (!hit) {
        toast(name + ': HDMI ' + port + ' não encontrada. Ligadas: ' +
          (list.filter(function (s) { return s.on; }).map(function (s) { return 'HDMI ' + s.number; }).join(', ') || 'nenhuma'));
        return;
      }
      try {
        tizen.tvwindow.setSource(hit.src, function () {
          tizen.application.launch('org.tizen.tv-viewer', function () {}, fail);
        }, fail, 'MAIN');
      } catch (e) { fail(e); }
    }, fail);
  }

  function launch(appId, name) {
    if (!appId) { toast(name + ': app não encontrado'); return; }
    try {
      tizen.application.launch(appId, function () {}, function (e) {
        toast('Não abriu ' + name + ': ' + errText(e));
      });
    } catch (e) { toast('Erro: ' + errText(e)); }
  }

  // Tries each app id in turn until one opens.
  function launchFirst(ids, name) {
    var i = 0;
    (function next() {
      if (i >= ids.length) { toast('Não abriu ' + name); return; }
      try { tizen.application.launch(ids[i++], function () {}, next); } catch (e) { next(); }
    })();
  }

  /* Entradas HDMI, com o que está ligado */
  function openInputs() {
    hdmiSources(function (list) {
      if (!list.length) { toast('Nenhuma entrada HDMI encontrada'); return; }
      openPanel({
        title: 'Entradas', hint: 'OK troca a entrada · Voltar volta', cols: 4,
        items: list.map(function (s) {
          return {
            name: 'HDMI ' + s.number, sub: s.on ? 'Aparelho ligado' : 'Nada conectado',
            glyph: 'H' + s.number, cls: s.on ? 'on' : 'dim',
            run: function () { switchHdmi(s.number, 'HDMI ' + s.number); }
          };
        })
      });
    }, function (e) { toast('Entradas: ' + errText(e)); });
  }

  /* Pendrive: lista as pastas e abre fotos, vídeos e músicas no próprio app */
  var MEDIA = {
    video: /\.(mp4|m4v|mkv|webm|mov|avi|ts|m2ts|mts|mpg|mpeg|wmv|flv|3gp)$/i,
    audio: /\.(mp3|m4a|aac|flac|wav|ogg|oga|opus|wma)$/i,
    image: /\.(jpe?g|png|gif|bmp|webp)$/i
  };
  var MIME = { mp4: 'video/mp4', m4v: 'video/mp4', mkv: 'video/x-matroska', webm: 'video/webm', mov: 'video/quicktime',
    avi: 'video/x-msvideo', ts: 'video/mp2t', mp3: 'audio/mpeg', m4a: 'audio/mp4', aac: 'audio/aac', flac: 'audio/flac',
    wav: 'audio/wav', ogg: 'audio/ogg', jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', gif: 'image/gif', webp: 'image/webp' };
  var MAX_ENTRIES = 400;
  var usb = { roots: [], stack: [], cur: '', listener: null };

  function kindOf(name) {
    if (MEDIA.video.test(name)) return 'video';
    if (MEDIA.audio.test(name)) return 'audio';
    if (MEDIA.image.test(name)) return 'image';
    return 'file';
  }
  function extOf(name) { var m = /\.([^.]+)$/.exec(name); return m ? m[1].toLowerCase() : ''; }
  function sizeText(b) {
    if (!b && b !== 0) return '';
    if (b >= 1073741824) return (b / 1073741824).toFixed(1).replace('.', ',') + ' GB';
    if (b >= 1048576) return Math.round(b / 1048576) + ' MB';
    return Math.max(1, Math.round(b / 1024)) + ' KB';
  }

  function usbStorages(cb) {
    try {
      tizen.filesystem.listStorages(function (list) {
        cb(list.filter(function (s) { return /^removable/i.test(s.label) && (!s.state || s.state === 'MOUNTED'); }));
      }, function () { cb([]); });
    } catch (e) { cb([]); }
  }

  // Lists a folder as [{ name, dir, size, uri }]. Uses resolve()/listFiles(), the path the
  // Samsung USB guide documents, and falls back to the newer path-based API.
  function listDir(path, ok, fail) {
    function viaNewApi() {
      try {
        var fs = tizen.filesystem;
        fs.listDirectory(path, function (names) {
          ok(names.map(function (n) {
            var p = path + '/' + n, dir = false;
            try { dir = fs.isDirectory(p); } catch (e) { /* */ }
            return { name: n, dir: dir, size: null, uri: dir ? '' : fs.toURI(p) };
          }));
        }, fail);
      } catch (e) { fail(e); }
    }
    try {
      tizen.filesystem.resolve(path, function (d) {
        d.listFiles(function (files) {
          ok(files.map(function (f) {
            return { name: f.name, dir: f.isDirectory, size: f.isDirectory ? null : f.fileSize, uri: f.isDirectory ? '' : f.toURI() };
          }));
        }, function () { viaNewApi(); });
      }, function () { viaNewApi(); }, 'r');
    } catch (e) { viaNewApi(); }
  }

  function openUsb() {
    usbStorages(function (roots) {
      usb.roots = roots;
      usb.stack = [];
      if (roots.length === 1) browseUsb(roots[0].label, 0);
      else showUsbRoots();
    });
  }

  function openSamsungMedia() {
    launchFirst((state.cfg && state.cfg.usbApps) || ['com.samsung.tv.mycontents', 'org.tizen.usb-launcher-tv'], 'app de mídia da Samsung');
  }

  function showUsbRoots() {
    var items = usb.roots.map(function (r, i) {
      return { name: 'Pendrive ' + (i + 1), sub: r.label.replace(/^removable_?/i, ''), glyph: 'USB',
        run: function () { usb.stack = []; browseUsb(r.label, 0); } };
    });
    if (!items.length) {
      items.push({ name: 'Nenhum pendrive', sub: 'Conecte na USB da TV e aperte OK', glyph: '!', cls: 'dim', run: openUsb });
    }
    items.push({ name: 'App de mídia da Samsung', sub: 'Abre o leitor da própria TV', glyph: 'APP', run: openSamsungMedia });
    items.push({ name: 'Procurar de novo', glyph: '↻', run: openUsb });
    openPanel({ title: 'Pendrive', items: items, cols: 3 });
  }

  function browseUsb(path, focus) {
    usb.cur = path;
    listDir(path, function (entries) {
      entries = entries.filter(function (e) {
        return e.name && e.name.charAt(0) !== '.' && e.name.charAt(0) !== '$' && e.name !== 'System Volume Information';
      }).sort(function (a, b) {
        if (a.dir !== b.dir) return a.dir ? -1 : 1;
        return a.name.localeCompare(b.name, 'pt-BR', { numeric: true, sensitivity: 'base' });
      });
      var cut = entries.length > MAX_ENTRIES;
      if (cut) entries = entries.slice(0, MAX_ENTRIES);
      var media = entries.filter(function (e) { return !e.dir && kindOf(e.name) !== 'file'; });
      var GLYPH = { video: 'VÍDEO', audio: 'SOM', image: 'FOTO', file: 'ARQ' };
      var items = entries.map(function (e) {
        if (e.dir) {
          return { name: e.name, sub: 'Pasta', glyph: 'PASTA', run: function () {
            usb.stack.push({ path: path, focus: panel.focus });
            browseUsb(path + '/' + e.name, 0);
          } };
        }
        var kind = kindOf(e.name);
        return {
          name: e.name, sub: sizeText(e.size), glyph: kind === 'file' ? (extOf(e.name).toUpperCase().slice(0, 4) || GLYPH.file) : GLYPH[kind],
          cls: kind === 'file' ? 'dim' : '',
          run: function () {
            if (kind === 'file') openExternal(e);
            else openViewer(media, media.indexOf(e));
          }
        };
      });
      if (!items.length) items.push({ name: 'Pasta vazia', glyph: '-', cls: 'dim' });
      var rel = path.split('/').slice(1).join(' / ');
      openPanel({
        title: 'Pendrive' + (rel ? ' / ' + rel : ''),
        hint: (cut ? 'mostrando ' + MAX_ENTRIES + ' itens · ' : '') + 'OK abre · Voltar sobe uma pasta',
        items: items, cols: 3, compact: true, focus: focus,
        back: function () {
          var up = usb.stack.pop();
          if (up) browseUsb(up.path, up.focus);
          else if (usb.roots.length > 1) showUsbRoots();
          else { hide('panel'); openMore(true); }
        }
      });
    }, function (e) {
      toast('Não consegui ler o pendrive: ' + errText(e));
      showUsbRoots();
    });
  }

  // Hands the file to the TV's own player, for formats the web player can't open.
  function openExternal(e) {
    try {
      var ctl = new tizen.ApplicationControl('http://tizen.org/appcontrol/operation/view', e.uri, MIME[extOf(e.name)] || null);
      tizen.application.launchAppControl(ctl, null, function () {}, function () { toast('A TV não tem app para abrir ' + e.name); });
    } catch (err) { toast('A TV não tem app para abrir ' + e.name); }
  }

  function watchUsb() {
    try {
      usb.listener = tizen.filesystem.addStorageStateChangeListener(function (s) {
        if (!/^removable/i.test(s.label)) return;
        if (s.state === 'MOUNTED') toast('Pendrive conectado. Aperte o botão azul → Pendrive');
        else if (s.state === 'REMOVED' || s.state === 'UNMOUNTABLE') {
          toast(s.state === 'REMOVED' ? 'Pendrive removido' : 'Não consegui ler esse pendrive');
          if (state.view === 'viewer') closeViewer();
          if (state.view === 'panel' && usb.cur.indexOf(s.label) === 0) openUsb();
        }
      });
    } catch (e) { /* preview / sem API */ }
  }

  /* Visualizador: fotos, vídeos e músicas do pendrive */
  var vw = { list: [], i: 0, slide: null, barTimer: null, kind: '' };

  function openViewer(list, i) {
    if (!list.length) return;
    vw.list = list;
    state.view = 'viewer';
    hide('panel');
    show('viewer');
    showMedia(i < 0 ? 0 : i);
  }

  function stopVideo() {
    var v = $('vvid');
    v.pause();
    // free the decoder right away instead of waiting for GC
    v.removeAttribute('src');
    v.load();
  }

  function showMedia(i) {
    var n = vw.list.length;
    vw.i = ((i % n) + n) % n;
    var e = vw.list[vw.i];
    vw.kind = kindOf(e.name);
    var img = $('vimg'), v = $('vvid');
    stopVideo();
    if (vw.kind === 'image') {
      img.classList.remove('hidden');
      v.classList.add('hidden');
      hide('vaudio');
      img.src = e.uri;
    } else {
      img.classList.add('hidden');
      img.removeAttribute('src');
      v.classList.toggle('hidden', vw.kind === 'audio');
      $('vaudio').textContent = e.name;
      $('vaudio').classList.toggle('hidden', vw.kind !== 'audio');
      v.src = e.uri;
      var p = v.play();
      if (p && p.catch) p.catch(function () { /* reported by onerror */ });
    }
    showBar();
  }

  function fmtTime(s) {
    if (!isFinite(s)) return '--:--';
    s = Math.floor(s);
    var h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60;
    return (h ? h + ':' + pad(m) : m) + ':' + pad(s % 60);
  }

  function paintBar() {
    var e = vw.list[vw.i], v = $('vvid');
    if (!e) return;
    $('vname').textContent = e.name;
    var pos = (vw.i + 1) + ' de ' + vw.list.length;
    if (vw.kind === 'image') {
      $('vfill').style.width = ((vw.i + 1) / vw.list.length * 100) + '%';
      $('vinfo').textContent = pos + ' · ◀ ▶ troca · OK ' + (vw.slide ? 'para' : 'inicia') + ' a apresentação · Voltar sai';
    } else {
      $('vfill').style.width = (v.duration ? v.currentTime / v.duration * 100 : 0) + '%';
      $('vinfo').textContent = fmtTime(v.currentTime) + ' / ' + fmtTime(v.duration) + ' · ' + pos +
        ' · ◀ ▶ 10 s · ▲ ▼ arquivo · OK ' + (v.paused ? 'continua' : 'pausa');
    }
  }

  function showBar() {
    show('vbar');
    paintBar();
    clearTimeout(vw.barTimer);
    vw.barTimer = setTimeout(function () {
      if (vw.kind === 'image' || !$('vvid').paused) hide('vbar');
    }, 4000);
  }

  function toggleSlide() {
    if (vw.slide) { clearInterval(vw.slide); vw.slide = null; }
    else vw.slide = setInterval(function () { showMedia(vw.i + 1); }, (state.cfg && state.cfg.slideSeconds || 6) * 1000);
    showBar();
  }

  function closeViewer() {
    if (vw.slide) { clearInterval(vw.slide); vw.slide = null; }
    clearTimeout(vw.barTimer);
    stopVideo();
    $('vimg').removeAttribute('src');
    hide('viewer');
    hide('vbar');
    state.view = 'panel';
    show('panel');
  }

  function viewerKey(code, back) {
    var v = $('vvid'), av = vw.kind !== 'image';
    if (back || code === KEY.STOP) { closeViewer(); return; }
    if (code === KEY.UP || code === KEY.PREV) showMedia(vw.i - 1);
    else if (code === KEY.DOWN || code === KEY.NEXT) showMedia(vw.i + 1);
    else if (code === KEY.LEFT || code === KEY.RW) {
      if (av) v.currentTime = Math.max(0, v.currentTime - 10); else showMedia(vw.i - 1);
    }
    else if (code === KEY.RIGHT || code === KEY.FF) {
      if (av) v.currentTime = Math.min(v.duration || 0, v.currentTime + 10); else showMedia(vw.i + 1);
    }
    else if (code === KEY.ENTER || code === KEY.PLAYPAUSE || code === KEY.PLAY || code === KEY.PAUSE) {
      if (!av) toggleSlide();
      else if (code === KEY.PAUSE || (code !== KEY.PLAY && !v.paused)) v.pause();
      else v.play();
    }
    showBar();
  }

  function wireViewer() {
    var v = $('vvid');
    v.addEventListener('timeupdate', function () { if (!$('vbar').classList.contains('hidden')) paintBar(); });
    v.addEventListener('pause', showBar);
    v.addEventListener('ended', function () {
      if (vw.i < vw.list.length - 1) showMedia(vw.i + 1); else showBar();
    });
    v.addEventListener('error', function () {
      if (!v.getAttribute('src') || state.view !== 'viewer') return;
      var e = vw.list[vw.i];
      toast('Esse formato não toca aqui. Tentando o player da TV...');
      closeViewer();
      openExternal(e);
    });
  }

  /* Informações do sistema */
  function openInfo() {
    var rows = [
      ['Modelo', 'TV'], ['Firmware', 'FW'], ['Rede', 'REDE'], ['Endereço IP', 'IP'],
      ['Wi-Fi', 'WIFI'], ['Tela', 'TELA'], ['Memória livre', 'RAM'], ['Armazenamento', 'HD'],
      ['Pendrives', 'USB'], ['Kurumi Home', 'K'], ['Clima', 'CLIMA'], ['Relógio', 'HORA']
    ];
    openPanel({
      title: 'Informações', hint: 'Voltar volta', cols: 3,
      items: rows.map(function (r) { return { name: r[0], sub: '...', glyph: r[1] }; })
    });
    function set(i, text) { if (state.view === 'panel' && panel.items[0] && panel.items[0].name === 'Modelo') setItem(i, text || 'indisponível'); }
    function sys(prop, cb, i) {
      try { tizen.systeminfo.getPropertyValue(prop, cb, function () { set(i, ''); }); } catch (e) { set(i, ''); }
    }
    sys('BUILD', function (b) { set(0, b.model); set(1, b.buildVersion); }, 0);
    sys('NETWORK', function (n) { set(2, n.networkType); }, 2);
    sys('WIFI_NETWORK', function (w) {
      if (w.status === 'ON' && w.ssid) {
        set(4, w.ssid + (w.signalStrength !== undefined ? ' · sinal ' + Math.round(w.signalStrength * 100) + '%' : ''));
        if (w.ipAddress) set(3, w.ipAddress);
      } else set(4, 'desligado');
    }, 4);
    sys('ETHERNET_NETWORK', function (n) { if (n.ipAddress) set(3, n.ipAddress + ' (cabo)'); }, 3);
    sys('DISPLAY', function (d) { set(5, d.resolutionWidth + ' x ' + d.resolutionHeight); }, 5);
    try {
      set(6, sizeText(tizen.systeminfo.getAvailableMemory()) + ' de ' + sizeText(tizen.systeminfo.getTotalMemory()));
    } catch (e) { set(6, ''); }
    sys('STORAGE', function (s) {
      var u = (s.units || []).filter(function (x) { return x.type === 'INTERNAL'; })[0] || (s.units || [])[0];
      set(7, u ? sizeText(u.availableCapacity) + ' livres de ' + sizeText(u.capacity) : '');
    }, 7);
    usbStorages(function (r) { set(8, r.length ? r.length + ' conectado(s)' : 'nenhum'); });
    try { set(9, 'versão ' + tizen.application.getAppInfo().version); } catch (e) { set(9, ''); }
    var loc = store('kurumi.loc');
    set(10, !prefs.weather ? 'desligado nos Ajustes' : (loc && loc.city ? loc.city : 'sem local ainda'));
    set(11, Intl.DateTimeFormat().resolvedOptions().timeZone || '');
  }

  /* Ajustes */
  var PREF_ITEMS = [
    { key: 'sec', name: 'Ponteiro dos segundos', on: 'Ligado', off: 'Desligado (mais leve)' },
    { key: 'anim', name: 'Animações de foco', on: 'Ligadas', off: 'Desligadas (mais leve)' },
    { key: 'quote', name: 'Frase da Kurumi', on: 'Muda a cada 10 min', off: 'Escondida' },
    { key: 'weather', name: 'Clima', on: 'Ligado (precisa de internet)', off: 'Desligado' }
  ];
  function openPrefs() {
    openPanel({
      title: 'Ajustes', hint: 'OK liga/desliga · Voltar volta', cols: 2,
      items: PREF_ITEMS.map(function (p) {
        return {
          name: p.name, sub: prefs[p.key] ? p.on : p.off, glyph: prefs[p.key] ? 'ON' : 'OFF', cls: prefs[p.key] ? 'on' : '',
          run: function (it, idx) {
            prefs[p.key] = !prefs[p.key];
            store('kurumi.prefs', prefs);
            applyPrefs();
            if (p.key === 'weather' && prefs.weather) updateWeather(true);
            setItem(idx, prefs[p.key] ? p.on : p.off, prefs[p.key] ? 'ON' : 'OFF', prefs[p.key] ? 'on' : '');
          }
        };
      })
    });
  }

  /* Wallpaper */
  // Show wallpaper i. save=false is a live preview while browsing the picker.
  function setWallpaper(i, save) {
    var list = state.cfg.wallpapers || [];
    var wall = $('wall');
    if (!list.length) { wall.style.backgroundImage = ''; return; }
    state.wall = ((i % list.length) + list.length) % list.length;
    var src = list[state.wall];
    var probe = new Image();
    probe.onload = function () { if (list[state.wall] === src) wall.style.backgroundImage = 'url("' + src + '")'; };
    probe.onerror = function () { wall.style.backgroundImage = ''; toast('Papel de parede não encontrado: ' + src); };
    probe.src = src;
    if (save !== false) {
      try { localStorage.setItem('kurumi.wall', String(state.wall)); } catch (e) { /* storage off */ }
    }
  }

  // deploy.ps1 writes small copies to assets/thumbs/; the preview falls back to the full image
  function thumbOf(src) { return 'assets/thumbs/' + src.split('/').pop(); }

  function openWalls() {
    var list = state.cfg.wallpapers || [];
    if (!list.length) { toast('Nenhum papel de parede no config.json'); return; }
    hideOverlays();
    state.view = 'walls';
    state.wallBefore = state.wall;
    state.wallFocus = state.wall;
    var grid = $('wallgrid');
    grid.innerHTML = '';
    list.forEach(function (src, idx) {
      var el = document.createElement('div');
      el.className = 'thumb' + (idx === state.wall ? ' current' : '');
      var t = new Image();
      t.onload = function () { el.style.backgroundImage = 'url("' + t.src + '")'; };
      t.onerror = function () { el.style.backgroundImage = 'url("' + src + '")'; };
      t.src = thumbOf(src);
      el.onclick = function () { state.wallFocus = idx; pickWall(); };
      grid.appendChild(el);
    });
    show('walls');
    paintWalls();
  }

  function paintWalls() {
    var els = $('wallgrid').children;
    for (var i = 0; i < els.length; i++) els[i].classList.toggle('focus', i === state.wallFocus);
    if (els[state.wallFocus] && els[state.wallFocus].scrollIntoView) els[state.wallFocus].scrollIntoView({ block: 'nearest' });
    setWallpaper(state.wallFocus, false);
  }

  function pickWall() { setWallpaper(state.wallFocus, true); closeWalls(); }
  function cancelWalls() { setWallpaper(state.wallBefore, false); closeWalls(); }
  function closeWalls() { state.view = 'home'; hide('walls'); paintFocus(); }

  /* Clock: a gold clock face like Kurumi's left eye, plus digital time */
  var ROMAN = ['XII', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI'];

  function hand(id, y1, y2, color, width) {
    return '<svg class="hand" id="' + id + '" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">' +
      '<line x1="100" y1="' + y1 + '" x2="100" y2="' + y2 + '" stroke="' + color + '" stroke-width="' + width +
      '" stroke-linecap="round"/></svg>';
  }

  function buildFace() {
    var s = '<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">' +
      '<defs><radialGradient id="iris" cx="50%" cy="50%" r="50%">' +
      '<stop offset="0%" stop-color="#f3d27a"/><stop offset="70%" stop-color="#c99a36"/>' +
      '<stop offset="100%" stop-color="#7a5414"/></radialGradient></defs>' +
      '<circle cx="100" cy="100" r="96" fill="url(#iris)"/>' +
      '<circle cx="100" cy="100" r="92" fill="none" stroke="#3a2306" stroke-width="2"/>' +
      '<circle cx="100" cy="100" r="66" fill="none" stroke="#3a2306" stroke-width="1.5" opacity=".7"/>';
    for (var h = 0; h < 12; h++) {
      var a = (h * 30 - 90) * Math.PI / 180;
      s += '<text x="' + (100 + 79 * Math.cos(a)).toFixed(1) + '" y="' + (100 + 79 * Math.sin(a)).toFixed(1) +
        '" fill="#2b1704" font-size="14" font-family="Georgia,serif" font-weight="bold" ' +
        'text-anchor="middle" dominant-baseline="central">' + ROMAN[h] + '</text>';
    }
    for (var m = 0; m < 60; m++) {
      if (m % 5 === 0) continue;
      var b = (m * 6 - 90) * Math.PI / 180;
      s += '<line x1="' + (100 + 64 * Math.cos(b)).toFixed(1) + '" y1="' + (100 + 64 * Math.sin(b)).toFixed(1) +
        '" x2="' + (100 + 60 * Math.cos(b)).toFixed(1) + '" y2="' + (100 + 60 * Math.sin(b)).toFixed(1) +
        '" stroke="#3a2306" stroke-width="1"/>';
    }
    s += '</svg>' +
      hand('hh', 100, 58, '#2b1704', 6) + hand('mh', 100, 42, '#2b1704', 4) + hand('sh', 112, 38, '#c0142f', 2) +
      '<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">' +
      '<circle cx="100" cy="100" r="6" fill="#c0142f" stroke="#2b1704" stroke-width="2"/></svg>';
    $('clockface').innerHTML = s;
  }

  // Puts each CSS-animated hand at the right phase. A negative delay starts the
  // animation part-way through; restarting it is the only way to change the phase.
  function syncHands() {
    var d = new Date();
    var sec = d.getSeconds() + d.getMilliseconds() / 1000;
    var mins = d.getMinutes() * 60 + sec;
    var hrs = (d.getHours() % 12) * 3600 + mins;
    [['sh', sec], ['mh', mins], ['hh', hrs]].forEach(function (p) {
      var el = $(p[0]);
      if (!el) return;
      el.style.animationName = 'none';
      void el.getBoundingClientRect(); // flush, so the restart is seen
      el.style.animationDelay = (-p[1]).toFixed(3) + 's';
      el.style.animationName = '';
    });
  }

  function pad(n) { return (n < 10 ? '0' : '') + n; }

  /* Saudação por hora, frase e clima */
  var GREETINGS = {
    madrugada: 'Ara ara~ ainda acordado a esta hora?',
    manha: 'Ara ara~ bom dia',
    tarde: 'Ara ara~ boa tarde',
    noite: 'Ara ara~ boa noite'
  };
  var QUOTES = [
    'O tempo é a coisa mais preciosa que existe.',
    'Kihihi~ quanto do seu tempo você vai me dar hoje?',
    'Cada segundo que passa não volta mais.',
    'Zafkiel guarda cada um dos seus minutos.',
    'Que tal um encontro? Prometo não roubar muito do seu tempo.',
    'Um bom episódio vale cada minuto.',
    'O relógio nunca para. Aproveite.',
    'Ara ara~ não fique acordado até tarde demais.',
    'Até o tempo para quando a história é boa.',
    'Ponteiros dourados, coração carmesim.'
  ];
  function periodOf(h) { return h < 5 ? 'madrugada' : h < 12 ? 'manha' : h < 18 ? 'tarde' : 'noite'; }

  function paintGreeting(h) {
    var cfg = state.cfg || {};
    var g = cfg.greetings === false ? null : (cfg.greetings || GREETINGS);
    $('greeting').textContent = (g && g[periodOf(h)]) || cfg.greeting || '';
  }

  function paintQuote(d) {
    var list = (state.cfg && state.cfg.quotes) || QUOTES;
    if (!list.length) { $('quote').textContent = ''; return; }
    var slot = Math.floor(d.getTime() / 600000); // a cada 10 minutos
    $('quote').textContent = list[slot % list.length];
  }

  // Open-Meteo (sem chave). Local: config "weather" {lat, lon, city}, ou "auto" pelo IP.
  var WX_TEXT = [[0, 'Céu limpo'], [2, 'Poucas nuvens'], [3, 'Nublado'], [48, 'Neblina'], [57, 'Garoa'],
    [67, 'Chuva'], [77, 'Neve'], [82, 'Pancadas de chuva'], [86, 'Neve'], [99, 'Tempestade']];
  var wxBusy = false;
  function wxText(code) {
    for (var i = 0; i < WX_TEXT.length; i++) if (code <= WX_TEXT[i][0]) return WX_TEXT[i][1];
    return '';
  }
  function paintWeather() {
    var wx = store('kurumi.wx');
    $('weather').textContent = prefs.weather && wx && Date.now() - wx.t < 3 * 3600000
      ? Math.round(wx.temp) + '° ' + wxText(wx.code) : '';
  }
  function locate() {
    var conf = state.cfg && state.cfg.weather;
    if (conf && typeof conf === 'object' && conf.lat !== undefined) {
      return Promise.resolve({ lat: conf.lat, lon: conf.lon, city: conf.city || '' });
    }
    var loc = store('kurumi.loc');
    if (loc && Date.now() - loc.t < 7 * 86400000) return Promise.resolve(loc);
    return loadJSON('https://ipapi.co/json/', 8000).then(function (r) {
      return { lat: r.latitude, lon: r.longitude, city: r.city };
    }).catch(function () {
      return loadJSON('https://ipwho.is/', 8000).then(function (r) {
        return { lat: r.latitude, lon: r.longitude, city: r.city };
      });
    }).then(function (l) {
      if (l.lat === undefined) throw new Error('sem local');
      l.t = Date.now();
      store('kurumi.loc', l);
      return l;
    });
  }
  function updateWeather(force) {
    var conf = state.cfg && state.cfg.weather;
    if (!prefs.weather || conf === false || wxBusy) { paintWeather(); return; }
    var wx = store('kurumi.wx');
    if (!force && wx && Date.now() - wx.t < 30 * 60000) { paintWeather(); return; }
    // nunca mais de uma tentativa a cada 10 min, mesmo se a rede falhar
    if (!force && updateWeather.tried && Date.now() - updateWeather.tried < 10 * 60000) return;
    updateWeather.tried = Date.now();
    wxBusy = true;
    locate().then(function (l) {
      return loadJSON('https://api.open-meteo.com/v1/forecast?latitude=' + l.lat + '&longitude=' + l.lon +
        '&current=temperature_2m,weather_code&timezone=auto', 8000);
    }).then(function (r) {
      store('kurumi.wx', { t: Date.now(), temp: r.current.temperature_2m, code: r.current.weather_code });
    }).catch(function () { /* sem internet: fica sem clima */ }).then(function () {
      wxBusy = false;
      paintWeather();
    });
  }

  // Runs once a minute (aligned to the minute), never every second.
  var minuteTimer = null, last = {};
  function minuteTick() {
    var d = new Date();
    var h = d.getHours();
    $('time').textContent = pad(h) + ':' + pad(d.getMinutes());
    if (d.getDate() !== last.day) {
      var ds = d.toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' });
      $('dtxt').textContent = ds.charAt(0).toUpperCase() + ds.slice(1);
      last.day = d.getDate();
    }
    if (h !== last.hour) {
      if (last.hour !== undefined && prefs.sec) syncHands(); // corrige qualquer deriva de hora em hora
      paintGreeting(h);
      last.hour = h;
    }
    if (prefs.quote) paintQuote(d);
    updateWeather(false);
    clearTimeout(minuteTimer);
    minuteTimer = setTimeout(minuteTick, 60050 - (d.getSeconds() * 1000 + d.getMilliseconds()));
  }

  /* All apps panel */
  function openAll() {
    hideOverlays();
    state.view = 'all';
    var box = $('alllist');
    box.innerHTML = '';
    if (!state.installed.length) box.textContent = 'Nenhum app listado (permissão application.info?)';
    var frag = document.createDocumentFragment();
    state.installed.forEach(function (a, idx) {
      var row = document.createElement('div');
      row.className = 'row';
      row.appendChild(iconEl([a.icon].filter(Boolean), a.name, 'letter', true));
      var txt = document.createElement('div');
      txt.style.minWidth = '0';
      txt.innerHTML = '<div class="n"></div><div class="id"></div>';
      txt.firstChild.textContent = a.name;
      txt.lastChild.textContent = a.id;
      row.appendChild(txt);
      row.onclick = function () { state.allFocus = idx; paintAll(); launch(a.id, a.name); };
      frag.appendChild(row);
    });
    box.appendChild(frag);
    box.lastFocus = undefined;
    state.allFocus = Math.min(state.allFocus, Math.max(0, state.installed.length - 1));
    show('all');
    paintAll();
  }
  function closeAll() { state.view = 'home'; hide('all'); paintFocus(); }
  function paintAll() { paintGrid($('alllist'), state.allFocus); }

  /* Remote */
  function move(cur, total, cols, code) {
    if (!total) return 0;
    var col = cur % cols;
    if (code === KEY.LEFT && col > 0) return cur - 1;
    if (code === KEY.RIGHT && col < cols - 1 && cur + 1 < total) return cur + 1;
    if (code === KEY.UP && cur - cols >= 0) return cur - cols;
    if (code === KEY.DOWN && cur + cols < total) return cur + cols;
    // Down on the second-to-last row with no item right below: go to the last item
    if (code === KEY.DOWN && Math.floor(cur / cols) < Math.floor((total - 1) / cols)) return total - 1;
    return cur;
  }

  var PREVIEW_KEYS = { r: KEY.RED, g: KEY.GREEN, y: KEY.YELLOW, b: KEY.BLUE, ' ': KEY.PLAYPAUSE };

  function onKey(e) {
    var code = e.keyCode;
    // browser preview: r / g / y / b stand in for the colour keys
    if (window.__kurumiPreview && PREVIEW_KEYS[e.key]) code = PREVIEW_KEYS[e.key];
    var back = code === KEY.BACK || code === KEY.ESC || code === KEY.BACKSPACE;
    e.preventDefault();

    if (state.view === 'viewer') { viewerKey(code, back); return; }
    if (code === KEY.YELLOW) { location.reload(); return; }
    if (code === KEY.BLUE) {
      if (state.view === 'more') closeMore();
      else { if (state.view === 'walls') cancelWalls(); openMore(); }
      return;
    }

    if (state.view === 'walls') {
      if (back || code === KEY.RED) cancelWalls();
      else if (code === KEY.ENTER) pickWall();
      else { state.wallFocus = move(state.wallFocus, $('wallgrid').children.length, 3, code); paintWalls(); }
    }
    else if (state.view === 'more') {
      if (back) closeMore();
      else if (code === KEY.ENTER) runExtra(state.moreItems[state.moreFocus]);
      else { state.moreFocus = move(state.moreFocus, state.moreItems.length, MORE_COLS, code); paintMore(); }
    }
    else if (state.view === 'panel') {
      if (back) panelBack();
      else if (code === KEY.ENTER) pickPanel();
      else { panel.focus = move(panel.focus, panel.items.length, panel.cols, code); paintGrid($('plist'), panel.focus); }
    }
    else if (code === KEY.RED) { if (state.view === 'all') closeAll(); openWalls(); }
    else if (state.view === 'all') {
      if (back || code === KEY.GREEN) closeAll();
      else if (code === KEY.ENTER) { var a = state.installed[state.allFocus]; if (a) launch(a.id, a.name); }
      else { state.allFocus = move(state.allFocus, state.installed.length, 4, code); paintAll(); }
    } else {
      var pills = $('actions').children;
      if (!state.cfg) return;
      if (code === KEY.GREEN) openAll();
      else if (back && state.zone === 'actions') { state.zone = 'tiles'; paintFocus(); }
      else if (back) openSamsungHome();
      else if (state.zone === 'actions') {
        if (code === KEY.ENTER) runAction(pills[state.actFocus].getAttribute('data-act'));
        else if (code === KEY.UP) state.zone = 'tiles';
        else if (code === KEY.LEFT && state.actFocus > 0) state.actFocus--;
        else if (code === KEY.RIGHT && state.actFocus < pills.length - 1) state.actFocus++;
        paintFocus();
      }
      else if (code === KEY.ENTER) { var t = state.tiles[state.focus]; if (t) openTile(t); }
      else if (code === KEY.DOWN && state.focus + state.cfg.columns >= state.tiles.length) { state.zone = 'actions'; paintFocus(); }
      else { state.focus = move(state.focus, state.tiles.length, state.cfg.columns, code); paintFocus(); }
    }
  }

  function registerKeys() {
    try {
      var supported = tizen.tvinputdevice.getSupportedKeys().map(function (k) { return k.name; });
      tizen.tvinputdevice.registerKeyBatch(TV_KEYS.filter(function (k) { return supported.indexOf(k) >= 0; }));
    } catch (e) {
      try { tizen.tvinputdevice.registerKeyBatch(TV_KEYS.slice(0, 4)); } catch (e2) { /* preview */ }
    }
  }

  // Nothing runs while another app is on screen.
  function onVisibility() {
    if (document.hidden) {
      clearTimeout(minuteTimer);
      if (state.view === 'viewer') $('vvid').pause();
    } else {
      last.hour = undefined; // forces greeting refresh
      if (prefs.sec) syncHands();
      minuteTick();
    }
  }

  /* Start */
  function start() {
    fit();
    window.addEventListener('resize', fit);
    buildFace();
    loadPrefs();
    minuteTick();
    registerKeys();
    wireViewer();
    document.addEventListener('keydown', onKey);
    document.addEventListener('visibilitychange', onVisibility);
    Array.prototype.forEach.call($('actions').children, function (p, idx) {
      p.onclick = function () { state.zone = 'actions'; state.actFocus = idx; paintFocus(); runAction(p.getAttribute('data-act')); };
    });

    Promise.all([
      loadJSON('config.json').catch(function (e) { toast('config.json: ' + e.message); return {}; }),
      installedApps()
    ]).then(function (r) {
      var cfg = r[0];
      cfg.columns = cfg.columns || 6;
      cfg.apps = cfg.apps || [];
      state.cfg = cfg;
      // O refresh em segundo plano pode ter chegado antes do config.json.
      state.installed = state.installed.length ? state.installed : r[1];
      $('subtitle').textContent = cfg.subtitle || '';
      last.hour = undefined;
      minuteTick(); // now with the config's greetings, quotes and weather place
      var saved = 0;
      try { saved = parseInt(localStorage.getItem('kurumi.wall'), 10) || 0; } catch (e) { /* storage off */ }
      setWallpaper(saved);
      state.tiles = cfg.apps.map(resolveTile);
      state.moreItems = (cfg.extras || []).map(resolveExtra);
      renderTiles();
      // pendrive watcher only after the first paint, so it never delays the boot
      setTimeout(watchUsb, 1500);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
