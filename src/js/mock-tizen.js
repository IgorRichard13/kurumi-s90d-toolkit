/* Stand-in for the Tizen APIs so the layout can be previewed in a PC browser.
   index.html only loads this file when the real `tizen` object is missing,
   and deploy.ps1 leaves it out of the TV package. */
(function () {
  'use strict';
  if (window.tizen) return;
  window.__kurumiPreview = true;

  var fake = [
    { id: 'abc0000001.YouTube', name: 'YouTube' },
    { id: 'abc0000002.Netflix', name: 'Netflix' },
    { id: 'abc0000003.Crunchyroll', name: 'Crunchyroll' },
    { id: 'abc0000004.PrimeVideo', name: 'Prime Video' },
    { id: 'abc0000005.Spotify', name: 'Spotify' },
    { id: 'abc0000006.Globoplay', name: 'Globoplay' },
    { id: 'abc0000007.Plex', name: 'Plex' },
    { id: 'abc0000008.SmartIPTV', name: 'Smart IPTV' }
  ];

  // A fake pendrive. Images point at the wallpapers so the viewer has something to show.
  var tree = {
    'removable_sda1': ['Animes/', 'Fotos/', 'Musicas/', 'leia-me.txt'],
    'removable_sda1/Animes': ['Date A Live 01.mkv', 'Date A Live 02.mkv', 'Abertura.mp4'],
    'removable_sda1/Fotos': ['wallpaper1.webp', 'wallpaper2.webp', 'wallpaper3.webp'],
    'removable_sda1/Musicas': ['tema.mp3']
  };
  function file(path, entry) {
    var dir = entry.slice(-1) === '/';
    var name = dir ? entry.slice(0, -1) : entry;
    return {
      name: name, isDirectory: dir, fileSize: dir ? 0 : 734003200,
      toURI: function () { return /\.webp$/.test(name) ? 'assets/' + name : 'missing/' + name; }
    };
  }

  window.tizen = {
    application: {
      getAppsInfo: function (ok) { setTimeout(function () { ok(fake); }, 50); },
      launch: function (id, ok) { console.log('[mock] launch', id); if (ok) ok(); },
      launchAppControl: function (c, id, ok) { console.log('[mock] appcontrol', c.uri); if (ok) ok(); },
      getAppInfo: function () { return { version: '0.2.0' }; },
      getCurrentApplication: function () { return { exit: function () { console.log('[mock] exit'); } }; }
    },
    ApplicationControl: function (op, uri, mime) { this.operation = op; this.uri = uri; this.mime = mime; },
    tvinputdevice: {
      getSupportedKeys: function () { return [{ name: 'ColorF0Red' }, { name: 'ColorF3Blue' }]; },
      registerKeyBatch: function () {}
    },
    systeminfo: {
      getPropertyValue: function (p, ok) {
        var v = {
          VIDEOSOURCE: { connected: [{ type: 'HDMI', number: 2 }], disconnected: [{ type: 'HDMI', number: 1 }, { type: 'HDMI', number: 3 }, { type: 'HDMI', number: 4 }] },
          BUILD: { model: 'QN55S90DAGXZD', buildVersion: 'T-PTMDUABC-0090' },
          NETWORK: { networkType: 'WIFI' },
          WIFI_NETWORK: { status: 'ON', ssid: 'Casa', ipAddress: '192.168.1.50', signalStrength: 0.8 },
          ETHERNET_NETWORK: {},
          DISPLAY: { resolutionWidth: 3840, resolutionHeight: 2160 },
          STORAGE: { units: [{ type: 'INTERNAL', capacity: 8e9, availableCapacity: 2.1e9 }] }
        }[p];
        setTimeout(function () { ok(v || {}); }, 30);
      },
      getAvailableMemory: function () { return 812e6; },
      getTotalMemory: function () { return 3e9; }
    },
    filesystem: {
      listStorages: function (ok) { ok([{ label: 'removable_sda1', type: 'EXTERNAL', state: 'MOUNTED' }]); },
      resolve: function (path, ok, fail) {
        if (!tree[path]) { fail(new Error('not found')); return; }
        ok({ listFiles: function (cb) { cb(tree[path].map(function (e) { return file(path, e); })); } });
      },
      addStorageStateChangeListener: function () { return 1; }
    },
    tvwindow: { setSource: function (s, ok) { console.log('[mock] source', s.type, s.number); ok(); } }
  };
})();
