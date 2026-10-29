'use strict';
// BN Stream Web: TMDb (server proxy) + Internet Archive + free iptv-org channels. No accounts, no unlicensed sources.
const L = {
  he: {home: 'בית', movies: 'סרטים', tv: 'סדרות', live: 'ערוצים חיים', classic: 'קלאסיקות', search: 'חיפוש בכל המקורות...',
       trendM: 'סרטים חמים השבוע', trendT: 'סדרות חמות השבוע', results: 'תוצאות עבור', none: 'לא נמצאו תוצאות',
       loading: 'טוען...', trailer: 'טריילר', archive: 'צפייה חינם ב-Internet Archive', app: 'פתח באפליקציית BN Stream',
       noTmdb: 'השרת עדיין לא הוגדר (TMDB_TOKEN)', ch: 'ערוצים', ia: 'Internet Archive', titles: 'סרטים וסדרות',
       lists: {il: 'ישראל', he: 'עברית', ru: 'רוסית', en: 'אנגלית', kids: 'ילדים', docs: 'תעודה', news: 'חדשות', music: 'מוזיקה'},
       foot: 'BN Stream Web · מקורות חוקיים בלבד: TMDb, Internet Archive, iptv-org'},
  en: {home: 'Home', movies: 'Movies', tv: 'Series', live: 'Live TV', classic: 'Classics', search: 'Search all sources...',
       trendM: 'Trending movies', trendT: 'Trending series', results: 'Results for', none: 'Nothing found',
       loading: 'Loading...', trailer: 'Trailer', archive: 'Watch free on Internet Archive', app: 'Open in the BN Stream app',
       noTmdb: 'Server not configured yet (TMDB_TOKEN)', ch: 'Channels', ia: 'Internet Archive', titles: 'Movies & series',
       lists: {il: 'Israel', he: 'Hebrew', ru: 'Russian', en: 'English', kids: 'Kids', docs: 'Documentary', news: 'News', music: 'Music'},
       foot: 'BN Stream Web · legal sources only: TMDb, Internet Archive, iptv-org'},
  ru: {home: 'Главная', movies: 'Фильмы', tv: 'Сериалы', live: 'Прямой эфир', classic: 'Классика', search: 'Поиск по всем источникам...',
       trendM: 'Популярные фильмы', trendT: 'Популярные сериалы', results: 'Результаты для', none: 'Ничего не найдено',
       loading: 'Загрузка...', trailer: 'Трейлер', archive: 'Смотреть бесплатно в Internet Archive', app: 'Открыть в BN Stream',
       noTmdb: 'Сервер ещё не настроен (TMDB_TOKEN)', ch: 'Каналы', ia: 'Internet Archive', titles: 'Фильмы и сериалы',
       lists: {il: 'Израиль', he: 'Иврит', ru: 'Русский', en: 'Английский', kids: 'Детям', docs: 'Документальные', news: 'Новости', music: 'Музыка'},
       foot: 'BN Stream Web · только легальные источники: TMDb, Internet Archive, iptv-org'},
};
const TMDB_LANG = {he: 'he-IL', en: 'en-US', ru: 'ru-RU'};
const IMG = 'https://image.tmdb.org/t/p/';
let lang = 'he';
try { lang = localStorage.getItem('bn_lang') || (navigator.language || 'he').slice(0, 2); } catch (e) {}
if (!L[lang]) lang = 'he';
const t = (k) => L[lang][k];
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const view = $('#view');
let hls = null;

async function tmdb(path, params = {}) {
  const qs = new URLSearchParams({path, language: TMDB_LANG[lang], ...params});
  const r = await fetch('api/tmdb?' + qs).catch(() => ({status: 404}));
  if (r.status === 503 || r.status === 404) throw new Error(t('noTmdb'));
  if (!r.ok) throw new Error('TMDb ' + r.status);
  return r.json();
}
async function archive(q, rows = 30) {
  const query = q ? `(title:(${q}) OR subject:(${q})) AND mediatype:movies` : 'collection:feature_films AND mediatype:movies';
  const qs = new URLSearchParams({q: query, rows, output: 'json', sort: q ? '' : 'downloads desc'});
  ['identifier', 'title', 'year'].forEach((f) => qs.append('fl[]', f));
  const r = await fetch('https://archive.org/advancedsearch.php?' + qs);
  return r.ok ? (await r.json()).response.docs : [];
}
// same lists and parser as api/channels.js; used directly when the page runs without the server (GitHub Pages)
const LISTS = {il: 'countries/il', he: 'languages/heb', ru: 'languages/rus', en: 'languages/eng',
               kids: 'categories/kids', docs: 'categories/documentary', news: 'categories/news', music: 'categories/music'};
function parseM3u(text) {
  const out = [], seen = new Set();
  let cur = null;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (line.startsWith('#EXTINF')) {
      const attr = (k) => (line.match(new RegExp(k + '="([^"]*)"')) || [])[1] || '';
      const name = line.slice(line.lastIndexOf('",') > 0 ? line.lastIndexOf('",') + 2 : line.lastIndexOf(',') + 1).trim();
      cur = {name, logo: attr('tvg-logo'), group: attr('group-title').split(';')[0].replace(/^Undefined$/, '')};
    } else if (cur && line && !line.startsWith('#')) {
      if (line.startsWith('https://') && !seen.has(line)) { seen.add(line); out.push({...cur, url: line}); }
      cur = null;
    }
  }
  return out;
}
const chCache = {};
async function channels(list) {
  if (chCache[list]) return chCache[list];
  try {
    const r = await fetch('api/channels?list=' + list);
    if (r.ok) return (chCache[list] = (await r.json()).items);
  } catch (e) {}
  const r = await fetch(`https://iptv-org.github.io/iptv/${LISTS[list]}.m3u`);
  return (chCache[list] = r.ok ? parseM3u(await r.text()) : []);
}

function card(img, title, sub, onClick, wide) {
  const b = document.createElement('button');
  b.className = 'card' + (wide ? ' wide' : '');
  b.innerHTML = `<div class="img" style="background-image:url('${esc(img)}')"></div><div class="t">${esc(title)}</div>` +
                (sub ? `<div class="s">${esc(sub)}</div>` : '');
  b.onclick = onClick;
  return b;
}
function section(title, count) {
  const h = document.createElement('h2');
  h.innerHTML = esc(title) + (count != null ? ` <small>${count}</small>` : '');
  const g = document.createElement('div');
  g.className = 'grid';
  view.append(h, g);
  return g;
}
const tmdbCard = (r) => {
  const type = r.media_type || (r.title ? 'movie' : 'tv');
  return card(r.poster_path ? IMG + 'w342' + r.poster_path : 'icon.png', r.title || r.name,
              (r.release_date || r.first_air_date || '').slice(0, 4), () => openTitle(type, r.id));
};
const iaCard = (d) => card(`https://archive.org/services/img/${d.identifier}`, d.title, d.year || '', () => openArchive(d));
const chCard = (c) => card(c.logo || 'icon.png', c.name, c.group, () => openChannel(c), true);
const msg = (text) => { view.innerHTML = `<p class="msg">${esc(text)}</p>`; };

// ---------------------------------------------------------------- modal / players
function modal(html) {
  $('#sheet').innerHTML = html;
  $('#modal').hidden = false;
  $('.close').focus();
}
function closeModal() {
  if (hls) { hls.destroy(); hls = null; }
  $('#sheet').innerHTML = '';
  $('#modal').hidden = true;
}
$('.close').onclick = closeModal;
$('#modal').onclick = (e) => { if (e.target.id === 'modal') closeModal(); };
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('#modal').hidden) closeModal(); });

async function openTitle(type, id) {
  modal(`<p class="msg">${t('loading')}</p>`);
  try {
    const [d, v] = await Promise.all([tmdb(`/${type}/${id}`), tmdb(`/${type}/${id}/videos`, {include_video_language: `${lang},en,null`})]);
    const tr = (v.results || []).find((x) => x.site === 'YouTube' && x.type === 'Trailer') || (v.results || []).find((x) => x.site === 'YouTube');
    const year = (d.release_date || d.first_air_date || '').slice(0, 4);
    const title = d.title || d.name;
    const genres = (d.genres || []).map((g) => g.name).join(' · ');
    modal(`${tr ? `<div class="player"><iframe src="https://www.youtube-nocookie.com/embed/${esc(tr.key)}" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen title="${t('trailer')}"></iframe></div>` : ''}
      <div class="detail"><img src="${d.poster_path ? IMG + 'w342' + d.poster_path : 'icon.png'}" alt="">
      <div><h3>${esc(title)}</h3><div class="meta">${esc([year, genres, d.vote_average ? '★ ' + d.vote_average.toFixed(1) : ''].filter(Boolean).join(' · '))}</div>
      <p>${esc(d.overview)}</p><div class="actions">
      <button class="btn ghost" id="iaBtn">${t('archive')}</button>
      <a class="btn" href="https://bennymat93.github.io/novatv/">${t('app')}</a></div><div id="iaRes"></div></div></div>`);
    $('#iaBtn').onclick = async () => {
      const docs = await archive(d.original_title || d.original_name || title, 12);
      const box = $('#iaRes');
      box.innerHTML = docs.length ? '<div class="grid" style="margin-top:16px"></div>' : `<p class="msg">${t('none')}</p>`;
      docs.forEach((x) => box.firstChild.append(iaCard(x)));
    };
  } catch (e) { modal(`<p class="msg">${esc(e.message)}</p>`); }
}
function openArchive(d) {
  modal(`<div class="player"><iframe src="https://archive.org/embed/${encodeURIComponent(d.identifier)}" allowfullscreen title="${esc(d.title)}"></iframe></div>
    <div class="detail" style="grid-template-columns:1fr"><div><h3>${esc(d.title)}</h3><div class="meta">${esc(d.year || '')} · Internet Archive</div></div></div>`);
}
function openChannel(c) {
  modal(`<div class="player"><video id="vid" controls autoplay playsinline></video></div>
    <div class="detail" style="grid-template-columns:1fr"><div><h3>${esc(c.name)}</h3><div class="meta">${esc(c.group)}</div></div></div>`);
  const v = $('#vid');
  if (v.canPlayType('application/vnd.apple.mpegurl')) v.src = c.url;           // Safari / iOS: native HLS
  else if (window.Hls && Hls.isSupported()) { hls = new Hls(); hls.loadSource(c.url); hls.attachMedia(v); }
  else v.src = c.url;
}

// ---------------------------------------------------------------- pages
async function pageHome() {
  msg(t('loading'));
  try {
    const [m, s] = await Promise.all([tmdb('/trending/movie/week'), tmdb('/trending/tv/week')]);
    view.innerHTML = '';
    const g1 = section(t('trendM')); m.results.forEach((r) => g1.append(tmdbCard(r)));
    const g2 = section(t('trendT')); s.results.forEach((r) => g2.append(tmdbCard(r)));
  } catch (e) {           // no TMDb server: classics and Israeli channels instead
    const [docs, chs] = await Promise.all([archive('', 24), channels('il')]);
    view.innerHTML = '';
    const g1 = section(t('live'), chs.length); chs.forEach((c) => g1.append(chCard(c)));
    const g2 = section(t('classic'), docs.length); docs.forEach((d) => g2.append(iaCard(d)));
  }
}
async function pageList(type) {
  msg(t('loading'));
  try {
    const d = await tmdb(`/discover/${type}`, {sort_by: 'popularity.desc', 'vote_count.gte': 100});
    view.innerHTML = '';
    const g = section(t(type === 'movie' ? 'movies' : 'tv'));
    d.results.forEach((r) => g.append(tmdbCard({...r, media_type: type})));
  } catch (e) { msg(e.message); }
}
async function pageLive(list = 'il') {
  view.innerHTML = '<div class="chips"></div>';
  const chips = view.firstChild;
  Object.entries(t('lists')).forEach(([k, name]) => {
    const b = document.createElement('button');
    b.className = 'chip' + (k === list ? ' on' : '');
    b.textContent = name;
    b.onclick = () => { location.hash = '#/live/' + k; };
    chips.append(b);
  });
  const items = await channels(list);
  const g = section(t('lists')[list], items.length);
  items.forEach((c) => g.append(chCard(c)));
  if (!items.length) g.outerHTML = `<p class="msg">${t('none')}</p>`;
}
async function pageClassic() {
  msg(t('loading'));
  const docs = await archive('', 60);
  view.innerHTML = '';
  const g = section(t('classic'), docs.length);
  docs.forEach((d) => g.append(iaCard(d)));
}
async function pageSearch(q) {
  $('#q').value = q;
  view.innerHTML = `<h2>${esc(t('results'))} “${esc(q)}”</h2>`;
  const ql = q.toLowerCase();
  // every source in parallel; each section appears as soon as its source answers
  const jobs = [
    tmdb('/search/multi', {query: q}).then((d) => {
      const r = (d.results || []).filter((x) => x.media_type === 'movie' || x.media_type === 'tv');
      if (r.length) { const g = section(t('titles'), r.length); r.forEach((x) => g.append(tmdbCard(x))); }
      return r.length;
    }).catch(() => 0),
    archive(q).then((docs) => {
      if (docs.length) { const g = section(t('ia'), docs.length); docs.forEach((d) => g.append(iaCard(d))); }
      return docs.length;
    }).catch(() => 0),
    Promise.all(['il', 'he', 'ru', 'en'].map(channels)).then((all) => {
      const seen = new Set();
      const hit = all.flat().filter((c) => c.name.toLowerCase().includes(ql) && !seen.has(c.url) && seen.add(c.url)).slice(0, 40);
      if (hit.length) { const g = section(t('ch'), hit.length); hit.forEach((c) => g.append(chCard(c))); }
      return hit.length;
    }).catch(() => 0),
  ];
  const n = (await Promise.all(jobs)).reduce((a, b) => a + b, 0);
  if (!n) view.insertAdjacentHTML('beforeend', `<p class="msg">${t('none')}</p>`);
}

// ---------------------------------------------------------------- shell
const NAV = [['#/', 'home'], ['#/movies', 'movies'], ['#/tv', 'tv'], ['#/live', 'live'], ['#/classic', 'classic']];
function shell() {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === 'he' ? 'rtl' : 'ltr';
  $('#lang').value = lang;
  $('#q').placeholder = t('search');
  $('#foot').textContent = t('foot');
  $('#nav').innerHTML = NAV.map(([h, k]) => `<a href="${h}">${esc(t(k))}</a>`).join('');
}
function route() {
  closeModal();
  const [, page = '', arg = ''] = location.hash.split('/');
  document.querySelectorAll('#nav a').forEach((a) => a.classList.toggle('on', a.getAttribute('href') === '#/' + page));
  const q = decodeURIComponent(arg);
  ({movies: () => pageList('movie'), tv: () => pageList('tv'), live: () => pageLive(q || 'il'), classic: pageClassic,
    search: () => pageSearch(q)}[page] || pageHome)();
  window.scrollTo(0, 0);
}
$('#search').onsubmit = (e) => {
  e.preventDefault();
  const q = $('#q').value.trim();
  if (q) location.hash = '#/search/' + encodeURIComponent(q);
};
$('#lang').onchange = (e) => {
  lang = e.target.value;
  try { localStorage.setItem('bn_lang', lang); } catch (x) {}
  shell(); route();
};
window.addEventListener('hashchange', route);
shell(); route();
