'use strict';
// BN Stream Web: main menu -> Movies, Series, Live TV, Radio, Favorites, BN Stream, Settings.
// Sources: TMDb through the server (api/tmdb, when it is set up) or Internet Archive, free iptv-org channels,
// radio-browser. No accounts, no unlicensed sources. Favorites and settings stay in this browser.
const L = {
  he: {home: 'תפריט ראשי', back: 'חזרה לתפריט הראשי', movies: 'סרטים', tv: 'סדרות', live: 'טלוויזיה', radio: 'רדיו',
       favs: 'מועדפים', bn: 'BN Stream', settings: 'הגדרות', search: 'חיפוש בכל המקורות...', results: 'תוצאות עבור',
       none: 'לא נמצאו תוצאות', loading: 'טוען...', trailer: 'טריילר', archive: 'צפייה חינם ב-Internet Archive',
       app: 'פתח באפליקציית BN Stream', ch: 'ערוצים', ia: 'Internet Archive', titles: 'סרטים וסדרות', stations: 'תחנות',
       all: 'הכל', fav_add: '♡ הוסף למועדפים', fav_rm: '♥ הסר מהמועדפים', favs_none: 'עדיין אין מועדפים. לחצו ♡ בכל סרט, ערוץ או תחנה.',
       popular: 'הפופולריים', trendM: 'סרטים חמים השבוע', trendT: 'סדרות חמות השבוע', classics: 'סרטים קלאסיים',
       series_classic: 'סדרות קלאסיות', play: 'נגן', stop: 'עצור',
       sub: {movies: 'סרטים קלאסיים מלאים', tv: 'סדרות טלוויזיה', live: 'ערוצים חיים חינמיים', radio: 'תחנות מכל העולם',
             favs: 'מה ששמרתם', bn: 'האפליקציה המלאה', settings: 'שפה, תצוגה ועוד'},
       lists: {il: 'ישראל', he: 'עברית', ru: 'רוסית', en: 'אנגלית', kids: 'ילדים', docs: 'תעודה', news: 'חדשות', music: 'מוזיקה'},
       countries: {IL: 'ישראל', RU: 'רוסיה', US: 'ארה"ב', GB: 'בריטניה', FR: 'צרפת', DE: 'גרמניה', UA: 'אוקראינה', top: 'הכי מושמעות'},
       genres: {Comedy: 'קומדיה', Drama: 'דרמה', Horror: 'אימה', Western: 'מערבון', 'Science Fiction': 'מדע בדיוני',
                'Film Noir': 'פילם נואר', Animation: 'אנימציה', Silent: 'אילם', '@soviet': 'קולנוע סובייטי'},
       sorts: {popular: 'הנצפים ביותר', top: 'המדורגים ביותר', new: 'נוספו לאחרונה'}, f_sort: 'מיון', f_genre: 'סוגה', f_decade: 'עשור', f_lang: 'שפה', f_style: 'סגנון', f_country: 'מדינה',
       ialangs: {English: 'אנגלית', Russian: 'רוסית', French: 'צרפתית', German: 'גרמנית', Spanish: 'ספרדית', Italian: 'איטלקית'},
       rtags: {news: 'חדשות ודיבור', pop: 'פופ ולהיטים', rock: 'רוק', classical: 'קלאסית', jazz: 'ג׳אז', 'world middle east': 'מזרח תיכון', kids: 'ילדים', jewish: 'יהדות'},
       s_lang: 'שפה', s_theme: 'ערכת צבעים', t_auto: 'לפי המכשיר', t_dark: 'כהה', t_light: 'בהירה',
       s_live: 'רשימת ערוצים בפתיחה', s_radio: 'מדינת רדיו בפתיחה', s_clear: 'מחיקת המועדפים', s_cleared: 'המועדפים נמחקו',
       s_family: 'סינון תוכן למשפחה', s_family_txt: 'פעיל תמיד: תכנים למבוגרים מסוננים מ-Internet Archive.',
       s_store: 'ההגדרות והמועדפים נשמרים בדפדפן הזה בלבד.',
       bn_txt: 'BN Stream היא אפליקציית הטלוויזיה המלאה: סרטים וסדרות עם Real-Debrid, ערוצים ישראליים, כתוביות בעברית ועוד. גרסת הדפדפן כוללת את התכנים החינמיים.',
       bn_kodi: 'התקנה ב-Kodi (מאגר NovaTV)', bn_android: 'אנדרואיד (64 ביט)', bn_android32: 'אנדרואיד (32 ביט)',
       bn_win: 'Windows', bn_guide: 'מדריך למשתמש', bn_kodi_how: 'ב-Kodi: הגדרות ← מנהל קבצים ← הוספת מקור ← https://bennymat93.github.io/novatv/ ← הרחבות ← התקנה מקובץ zip',
       foot: 'BN Stream Web · מקורות חוקיים בלבד: TMDb, Internet Archive, iptv-org, radio-browser'},
  en: {home: 'Main menu', back: 'Back to main menu', movies: 'Movies', tv: 'Series', live: 'Live TV', radio: 'Radio',
       favs: 'Favorites', bn: 'BN Stream', settings: 'Settings', search: 'Search all sources...', results: 'Results for',
       none: 'Nothing found', loading: 'Loading...', trailer: 'Trailer', archive: 'Watch free on Internet Archive',
       app: 'Open in the BN Stream app', ch: 'Channels', ia: 'Internet Archive', titles: 'Movies & series', stations: 'Stations',
       all: 'All', fav_add: '♡ Add to favorites', fav_rm: '♥ Remove from favorites', favs_none: 'No favorites yet. Press ♡ on any film, channel or station.',
       popular: 'Popular', trendM: 'Trending movies', trendT: 'Trending series', classics: 'Classic films',
       series_classic: 'Classic series', play: 'Play', stop: 'Stop',
       sub: {movies: 'Full classic films', tv: 'TV series', live: 'Free live channels', radio: 'Stations worldwide',
             favs: 'What you saved', bn: 'The full app', settings: 'Language, display and more'},
       lists: {il: 'Israel', he: 'Hebrew', ru: 'Russian', en: 'English', kids: 'Kids', docs: 'Documentary', news: 'News', music: 'Music'},
       countries: {IL: 'Israel', RU: 'Russia', US: 'USA', GB: 'UK', FR: 'France', DE: 'Germany', UA: 'Ukraine', top: 'Most played'},
       genres: {Comedy: 'Comedy', Drama: 'Drama', Horror: 'Horror', Western: 'Western', 'Science Fiction': 'Sci-fi',
                'Film Noir': 'Film noir', Animation: 'Animation', Silent: 'Silent', '@soviet': 'Soviet cinema'},
       sorts: {popular: 'Most watched', top: 'Top rated', new: 'Recently added'}, f_sort: 'Sort', f_genre: 'Genre', f_decade: 'Decade', f_lang: 'Language', f_style: 'Style', f_country: 'Country',
       ialangs: {English: 'English', Russian: 'Russian', French: 'French', German: 'German', Spanish: 'Spanish', Italian: 'Italian'},
       rtags: {news: 'News & talk', pop: 'Pop & hits', rock: 'Rock', classical: 'Classical', jazz: 'Jazz', 'world middle east': 'Middle East', kids: 'Kids', jewish: 'Jewish'},
       s_lang: 'Language', s_theme: 'Theme', t_auto: 'Device', t_dark: 'Dark', t_light: 'Light',
       s_live: 'Channel list on open', s_radio: 'Radio country on open', s_clear: 'Clear favorites', s_cleared: 'Favorites cleared',
       s_family: 'Family filter', s_family_txt: 'Always on: adult uploads are filtered from Internet Archive.',
       s_store: 'Settings and favorites are kept in this browser only.',
       bn_txt: 'BN Stream is the full TV app: movies and series with Real-Debrid, Israeli channels, Hebrew subtitles and more. The browser version has the free content.',
       bn_kodi: 'Install in Kodi (NovaTV repository)', bn_android: 'Android (64-bit)', bn_android32: 'Android (32-bit)',
       bn_win: 'Windows', bn_guide: 'User guide', bn_kodi_how: 'In Kodi: Settings → File manager → Add source → https://bennymat93.github.io/novatv/ → Add-ons → Install from zip file',
       foot: 'BN Stream Web · legal sources only: TMDb, Internet Archive, iptv-org, radio-browser'},
  ru: {home: 'Главное меню', back: 'Назад в главное меню', movies: 'Фильмы', tv: 'Сериалы', live: 'ТВ', radio: 'Радио',
       favs: 'Избранное', bn: 'BN Stream', settings: 'Настройки', search: 'Поиск по всем источникам...', results: 'Результаты для',
       none: 'Ничего не найдено', loading: 'Загрузка...', trailer: 'Трейлер', archive: 'Смотреть бесплатно в Internet Archive',
       app: 'Открыть в BN Stream', ch: 'Каналы', ia: 'Internet Archive', titles: 'Фильмы и сериалы', stations: 'Станции',
       all: 'Все', fav_add: '♡ В избранное', fav_rm: '♥ Убрать из избранного', favs_none: 'Пока пусто. Нажмите ♡ у фильма, канала или станции.',
       popular: 'Популярное', trendM: 'Популярные фильмы', trendT: 'Популярные сериалы', classics: 'Классика кино',
       series_classic: 'Классические сериалы', play: 'Играть', stop: 'Стоп',
       sub: {movies: 'Полные классические фильмы', tv: 'Телесериалы', live: 'Бесплатные каналы', radio: 'Станции мира',
             favs: 'Сохранённое', bn: 'Полное приложение', settings: 'Язык, вид и другое'},
       lists: {il: 'Израиль', he: 'Иврит', ru: 'Русский', en: 'Английский', kids: 'Детям', docs: 'Документальные', news: 'Новости', music: 'Музыка'},
       countries: {IL: 'Израиль', RU: 'Россия', US: 'США', GB: 'Великобритания', FR: 'Франция', DE: 'Германия', UA: 'Украина', top: 'Популярные'},
       genres: {Comedy: 'Комедия', Drama: 'Драма', Horror: 'Ужасы', Western: 'Вестерн', 'Science Fiction': 'Фантастика',
                'Film Noir': 'Нуар', Animation: 'Мультфильмы', Silent: 'Немое кино', '@soviet': 'Советское кино'},
       sorts: {popular: 'Самые просматриваемые', top: 'Лучшие по рейтингу', new: 'Недавно добавленные'}, f_sort: 'Сортировка', f_genre: 'Жанр', f_decade: 'Десятилетие', f_lang: 'Язык', f_style: 'Стиль', f_country: 'Страна',
       ialangs: {English: 'Английский', Russian: 'Русский', French: 'Французский', German: 'Немецкий', Spanish: 'Испанский', Italian: 'Итальянский'},
       rtags: {news: 'Новости и разговор', pop: 'Поп и хиты', rock: 'Рок', classical: 'Классика', jazz: 'Джаз', 'world middle east': 'Ближний Восток', kids: 'Детям', jewish: 'Еврейское'},
       s_lang: 'Язык', s_theme: 'Тема', t_auto: 'Как на устройстве', t_dark: 'Тёмная', t_light: 'Светлая',
       s_live: 'Список каналов при открытии', s_radio: 'Страна радио при открытии', s_clear: 'Очистить избранное', s_cleared: 'Избранное очищено',
       s_family: 'Семейный фильтр', s_family_txt: 'Всегда включён: материалы для взрослых из Internet Archive отфильтрованы.',
       s_store: 'Настройки и избранное хранятся только в этом браузере.',
       bn_txt: 'BN Stream — полное ТВ-приложение: фильмы и сериалы с Real-Debrid, израильские каналы, субтитры на иврите и многое другое. В браузере — бесплатный контент.',
       bn_kodi: 'Установка в Kodi (репозиторий NovaTV)', bn_android: 'Android (64 бит)', bn_android32: 'Android (32 бит)',
       bn_win: 'Windows', bn_guide: 'Руководство', bn_kodi_how: 'В Kodi: Настройки → Файловый менеджер → Добавить источник → https://bennymat93.github.io/novatv/ → Дополнения → Установить из zip',
       foot: 'BN Stream Web · только легальные источники: TMDb, Internet Archive, iptv-org, radio-browser'},
};
const SITE = 'https://bennymat93.github.io/novatv/';
const REL = 'https://github.com/bennymat93/novatv/releases/latest/download/';
const TMDB_LANG = {he: 'he-IL', en: 'en-US', ru: 'ru-RU'};
const IMG = 'https://image.tmdb.org/t/p/';
const RADIO = 'https://de1.api.radio-browser.info/json';
const MENU = [['movies', '🎬'], ['tv', '📺'], ['live', '📡'], ['radio', '📻'], ['favs', '♥'], ['bn', '★'], ['settings', '⚙']];

// ---------------------------------------------------------------- per-browser storage (never required)
function get(k, d) { try { const v = localStorage.getItem('bn_' + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } }
function put(k, v) { try { localStorage.setItem('bn_' + k, JSON.stringify(v)); } catch (e) {} }
const cfg = Object.assign({lang: (navigator.language || 'he').slice(0, 2), theme: 'auto', live: 'il', radio: 'IL'}, get('cfg', {}));
try { const old = localStorage.getItem('bn_lang'); if (old && !get('cfg', null)) cfg.lang = old; } catch (e) {}
if (!L[cfg.lang]) cfg.lang = 'he';
const t = (k) => L[cfg.lang][k];
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const view = $('#view');
let hls = null, hasTmdb = true;

// ---------------------------------------------------------------- sources
async function tmdb(path, params = {}) {
  if (!hasTmdb) throw new Error('no tmdb');
  const qs = new URLSearchParams({path, language: TMDB_LANG[cfg.lang], ...params});
  const r = await fetch('api/tmdb?' + qs).catch(() => ({status: 404}));
  if (r.status === 503 || r.status === 404) { hasTmdb = false; throw new Error('no tmdb'); }
  if (!r.ok) throw new Error('TMDb ' + r.status);
  return r.json();
}
// same family filter as the Kodi add-on (resources/lib/ia.py)
const ADULT = '(naturis* OR nudis* OR nude OR nudity OR erot* OR porn* OR sex OR sexy OR xxx OR adult OR softcore OR hentai OR эрот* OR порн* OR секс* OR нудис* OR עירום OR ארוט*)';
// same list as the add-on's '@soviet' (exact subject phrases: loose words pulled in war documentaries)
const SOVIET = '(' + ['Soviet film', 'Soviet films', 'Soviet cinema', 'Soviet movie', 'Soviet animation', 'советский фильм', 'советское кино']
  .map((s) => `subject:("${s}")`).concat(['мосфильм', 'ленфильм', 'Mosfilm', 'Lenfilm', 'союзмультфильм', 'Soyuzmultfilm'].map((s) => `subject:(${s})`)).join(' OR ') + ')';
const SORTS = {popular: 'downloads desc', top: 'avg_rating desc', new: 'addeddate desc'};
async function archive({q = '', collection = 'feature_films', subject = '', rows = 40, sort = 'popular', decade = '', language = ''} = {}) {
  q = q.replace(/[:()[\]{}"^~*?\\/!+-]/g, ' ').trim();
  const what = subject === '@soviet' ? SOVIET : q ? `title:(${q})` : `collection:${collection}` + (subject ? ` AND subject:("${subject}")` : '');
  const extra = (decade ? ` AND year:[${decade} TO ${+decade + 9}]` : '') + (language ? ` AND language:(${language})` : '') +
                (sort === 'top' ? ' AND num_reviews:[3 TO 100000]' : '');      // "top rated" needs a few reviews to mean anything
  const qs = new URLSearchParams({q: `${what}${extra} AND mediatype:movies AND NOT subject:${ADULT} AND NOT title:${ADULT}`, rows, output: 'json'});
  qs.append('sort[]', SORTS[sort] || SORTS.popular);
  ['identifier', 'title', 'year'].forEach((f) => qs.append('fl[]', f));
  const r = await fetch('https://archive.org/advancedsearch.php?' + qs);
  return r.ok ? (await r.json()).response.docs : [];
}
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
async function stations(cc, q, tag) {
  const path = tag ? `/stations/bytagexact/${encodeURIComponent(tag)}?` + new URLSearchParams({limit: 120, hidebroken: true, order: 'clickcount', reverse: true})
    : q ? '/stations/search?' + new URLSearchParams({name: q, limit: 60, hidebroken: true, order: 'clickcount', reverse: true})
    : cc === 'top' ? '/stations/topclick/80?hidebroken=true'
      : `/stations/bycountrycodeexact/${cc}?` + new URLSearchParams({limit: 120, hidebroken: true, order: 'clickcount', reverse: true});
  const r = await fetch(RADIO + path);
  // browsers block http audio on an https page: https streams only
  return r.ok ? (await r.json()).filter((s) => (s.url_resolved || '').startsWith('https://')) : [];
}

// ---------------------------------------------------------------- favorites
const favs = () => get('favs', []);
const isFav = (key) => favs().some((f) => f.key === key);
function toggleFav(item) {
  const list = favs();
  const i = list.findIndex((f) => f.key === item.key);
  if (i >= 0) list.splice(i, 1); else list.unshift(item);
  put('favs', list);
  return i < 0;
}
function favButton(item) {
  const b = document.createElement('button');
  b.className = 'btn ghost';
  const label = () => { b.textContent = isFav(item.key) ? t('fav_rm') : t('fav_add'); };
  label();
  b.onclick = () => { toggleFav(item); label(); };
  return b;
}

// ---------------------------------------------------------------- building blocks
const tidy = (n) => n.replace(/\s*\((\d{3,4}p|\d+i)\)|\s*\[[^\]]*\]/gi, '').trim();     // "Kan 11 (1080p) [Not 24/7]" -> "Kan 11"
function card(img, title, sub, onClick, kind, badge) {
  const b = document.createElement('button');
  b.className = 'card' + (kind ? ' ' + kind : '');
  b.innerHTML = (badge ? `<span class="badge">${esc(badge)}</span>` : '') + `<div class="img" style="background-image:url('${esc(img)}')"></div>` +
                `<div class="t" dir="auto">${esc(title)}</div>` + (sub != null ? `<div class="s" dir="auto">${esc(sub)}</div>` : '');
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
// every screen except the main menu: a back button to the menu and the screen's title
function page(key, title) {
  view.innerHTML = `<div class="pagehead"><a class="backbtn" href="#/">${cfg.lang === 'he' ? '→' : '←'} ${esc(t('back'))}</a>` +
                   `<h1>${esc(title || t(key))}</h1></div>`;
}
function chips(items, on, go) {
  const box = document.createElement('div');
  box.className = 'chips';
  items.forEach(([k, name]) => {
    const b = document.createElement('button');
    b.className = 'chip' + (k === on ? ' on' : '');
    b.textContent = name;
    b.onclick = () => go(k);
    box.append(b);
  });
  view.append(box);
  return box;
}
function skeleton(n = 12) {
  const g = document.createElement('div');
  g.className = 'grid skelgrid';
  g.innerHTML = '<div class="card skel"><div class="img"></div><div class="t"></div><div class="s"></div></div>'.repeat(n);
  view.append(g);
  return g;
}
const empty = (where, text) => { where.outerHTML = `<p class="msg">${esc(text || t('none'))}</p>`; };
const tmdbCard = (r) => {
  const type = r.media_type || (r.title ? 'movie' : 'tv');
  return card(r.poster_path ? IMG + 'w342' + r.poster_path : 'icon.png', r.title || r.name,
              (r.release_date || r.first_air_date || '').slice(0, 4), () => openTitle(type, r.id));
};
const iaCard = (d) => card(`https://archive.org/services/img/${d.identifier}`, d.title, d.year || '', () => openArchive(d));
const chCard = (c) => card(c.logo || 'icon.png', tidy(c.name), c.group, () => openChannel(c), 'wide', 'LIVE');
const radioCard = (s) => card(s.favicon || 'icon.png', s.name.trim(), [s.country, s.tags && s.tags.split(',')[0]].filter(Boolean).join(' · '),
                               () => playRadio(s), 'square');

// ---------------------------------------------------------------- players
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
    const [d, v] = await Promise.all([tmdb(`/${type}/${id}`), tmdb(`/${type}/${id}/videos`, {include_video_language: `${cfg.lang},en,null`})]);
    const tr = (v.results || []).find((x) => x.site === 'YouTube' && x.type === 'Trailer') || (v.results || []).find((x) => x.site === 'YouTube');
    const title = d.title || d.name;
    const genres = (d.genres || []).map((g) => g.name).join(' · ');
    modal(`${tr ? `<div class="player"><iframe src="https://www.youtube-nocookie.com/embed/${esc(tr.key)}" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen title="${t('trailer')}"></iframe></div>` : ''}
      <div class="detail"><img src="${d.poster_path ? IMG + 'w342' + d.poster_path : 'icon.png'}" alt="">
      <div><h3>${esc(title)}</h3><div class="meta">${esc([(d.release_date || d.first_air_date || '').slice(0, 4), genres, d.vote_average ? '★ ' + d.vote_average.toFixed(1) : ''].filter(Boolean).join(' · '))}</div>
      <p>${esc(d.overview)}</p><div class="actions" id="acts">
      <button class="btn ghost" id="iaBtn">${t('archive')}</button>
      <a class="btn" href="${SITE}">${t('app')}</a></div><div id="iaRes"></div></div></div>`);
    $('#acts').prepend(favButton({key: `tmdb:${type}:${id}`, kind: type === 'movie' ? 'movies' : 'tv', title,
                                  img: d.poster_path ? IMG + 'w342' + d.poster_path : '', data: {type, id}}));
    $('#iaBtn').onclick = async () => {
      const docs = await archive({q: d.original_title || d.original_name || title, rows: 12});
      const box = $('#iaRes');
      box.innerHTML = docs.length ? '<div class="grid" style="margin-top:16px"></div>' : `<p class="msg">${t('none')}</p>`;
      docs.forEach((x) => box.firstChild.append(iaCard(x)));
    };
  } catch (e) { modal(`<p class="msg">${esc(t('none'))}</p>`); }
}
function openArchive(d) {
  modal(`<div class="player"><iframe src="https://archive.org/embed/${encodeURIComponent(d.identifier)}" allowfullscreen title="${esc(d.title)}"></iframe></div>
    <div class="detail" style="grid-template-columns:1fr"><div><h3 dir="auto">${esc(d.title)}</h3><div class="meta">${esc(d.year || '')} · Internet Archive</div>
    <div class="actions" id="acts"></div></div></div>`);
  $('#acts').append(favButton({key: 'ia:' + d.identifier, kind: 'movies', title: d.title,
                               img: `https://archive.org/services/img/${d.identifier}`, data: d}));
}
function openChannel(c) {
  modal(`<div class="player"><video id="vid" controls autoplay playsinline></video></div>
    <div class="detail" style="grid-template-columns:1fr"><div><h3 dir="auto">${esc(tidy(c.name))}</h3><div class="meta">${esc(c.group)}</div>
    <div class="actions" id="acts"></div></div></div>`);
  $('#acts').append(favButton({key: 'ch:' + c.url, kind: 'live', title: tidy(c.name), img: c.logo, data: c}));
  stopRadio();
  const v = $('#vid');
  if (v.canPlayType('application/vnd.apple.mpegurl')) v.src = c.url;           // Safari / iOS: native HLS
  else if (window.Hls && Hls.isSupported()) { hls = new Hls(); hls.loadSource(c.url); hls.attachMedia(v); }
  else v.src = c.url;
}
// radio plays in the bar at the bottom, so you can keep browsing
const audio = new Audio();
function playRadio(s) {
  audio.src = s.url_resolved;
  audio.play().catch(() => {});
  const bar = $('#radiobar');
  bar.hidden = false;
  bar.innerHTML = `<img src="${esc(s.favicon || 'icon.png')}" alt=""><div class="rb-t" dir="auto"><b>${esc(s.name.trim())}</b><span>${esc(s.country || '')}</span></div>` +
                  `<span id="rbfav"></span><button class="btn" id="rbstop">■ ${esc(t('stop'))}</button>`;
  $('#rbfav').append(favButton({key: 'radio:' + s.stationuuid, kind: 'radio', title: s.name.trim(), img: s.favicon, data: s}));
  $('#rbstop').onclick = stopRadio;
}
function stopRadio() { audio.pause(); audio.removeAttribute('src'); $('#radiobar').hidden = true; }

// ---------------------------------------------------------------- screens
function pageHome() {
  view.innerHTML = '<div class="menu"></div>';
  MENU.forEach(([k, ic]) => {
    const a = document.createElement('a');
    a.className = 'tile';
    a.href = '#/' + k;
    a.innerHTML = `<span class="ic">${ic}</span><b>${esc(t(k))}</b><small>${esc(t('sub')[k])}</small>`;
    view.firstChild.append(a);
  });
}
// inner menu: sort, then genre / decade / language - every choice is kept in the address (#/movies/sort=top&d=1950)
function filterRow(label, items, cur, onPick) {
  const row = chips(items, cur, onPick);
  row.insertAdjacentHTML('afterbegin', `<span class="chiplabel">${esc(label)}</span>`);
}
async function browse(key, arg, collection, tmdbPath) {
  page(key);
  try {
    const d = await tmdb(tmdbPath, {sort_by: 'popularity.desc', 'vote_count.gte': 100});
    const g = section(t('popular'));
    d.results.forEach((r) => g.append(tmdbCard({...r, media_type: key === 'movies' ? 'movie' : 'tv'})));
    return;
  } catch (e) {}
  const f = Object.fromEntries(new URLSearchParams(arg));
  f.sort = SORTS[f.sort] ? f.sort : 'popular';
  const go = (k, v) => {
    const n = {...f, [k]: v};
    if (!v) delete n[k];
    location.hash = `#/${key}/` + new URLSearchParams(n);
  };
  filterRow(t('f_sort'), Object.entries(t('sorts')), f.sort, (v) => go('sort', v));
  if (key === 'movies') filterRow(t('f_genre'), [['', t('all')], ...Object.entries(t('genres'))], f.g || '', (v) => go('g', v));
  // series: television starts in the 1940s, and the archive's classic TV is English / Russian / French / German (audit 29/10)
  const decades = (key === 'movies' ? [1910, 1920, 1930] : []).concat([1940, 1950, 1960, 1970, 1980, 1990, 2000]).map((y) => [String(y), y + 's']);
  filterRow(t('f_decade'), [['', t('all')], ...decades], f.d || '', (v) => go('d', v));
  const langs = Object.entries(t('ialangs')).filter(([k]) => key === 'movies' || ['English', 'Russian', 'French', 'German'].includes(k));
  filterRow(t('f_lang'), [['', t('all')], ...langs], f.l || '', (v) => go('l', v));
  const sk = skeleton();
  const docs = await archive({collection, subject: f.g || '', rows: 60, sort: f.sort, decade: f.d || '', language: f.l || ''}).catch(() => []);
  sk.remove();
  const title = [t('sorts')[f.sort], f.g && t('genres')[f.g], f.d && f.d + 's', f.l && t('ialangs')[f.l]].filter(Boolean).join(' · ');
  const g = section(title, docs.length);
  docs.forEach((x) => g.append(iaCard(x)));
  if (!docs.length) empty(g);
}
const pageMovies = (arg) => browse('movies', arg, 'feature_films', '/discover/movie');
const pageSeries = (arg) => browse('tv', arg, 'classic_tv', '/discover/tv');
async function pageLive(list) {
  list = LISTS[list] ? list : cfg.live;
  page('live');
  chips(Object.entries(t('lists')), list, (k) => { location.hash = '#/live/' + k; });
  const sk = skeleton();
  const items = await channels(list).catch(() => []);
  sk.remove();
  const g = section(t('lists')[list], items.length);
  items.forEach((c) => g.append(chCard(c)));
  if (!items.length) empty(g);
}
async function pageRadio(cc) {
  const tag = cc.startsWith('tag:') ? cc.slice(4) : '';
  if (!tag) cc = t('countries')[cc] ? cc : cfg.radio;
  page('radio');
  filterRow(t('f_country'), Object.entries(t('countries')), tag ? '' : cc,
            (k) => { location.hash = '#/radio/' + k; });
  filterRow(t('f_style'), Object.entries(t('rtags')), tag, (k) => { location.hash = '#/radio/tag:' + encodeURIComponent(k); });
  const sk = skeleton();
  const list = await (tag ? stations('', '', tag) : stations(cc)).catch(() => []);
  sk.remove();
  const g = section(tag ? t('rtags')[tag] : t('countries')[cc], list.length);
  list.forEach((s) => g.append(radioCard(s)));
  if (!list.length) empty(g);
}
function pageFavs() {
  page('favs');
  const all = favs();
  if (!all.length) { view.insertAdjacentHTML('beforeend', `<p class="msg">${esc(t('favs_none'))}</p>`); return; }
  for (const kind of ['movies', 'tv', 'live', 'radio']) {
    const mine = all.filter((f) => f.kind === kind);
    if (!mine.length) continue;
    const g = section(t(kind), mine.length);
    mine.forEach((f) => {
      const d = f.data || {};
      const open = f.key.startsWith('tmdb:') ? () => openTitle(d.type, d.id) : f.key.startsWith('ia:') ? () => openArchive(d)
        : f.key.startsWith('ch:') ? () => openChannel(d) : () => playRadio(d);
      g.append(card(f.img || 'icon.png', f.title, '', open, kind === 'live' ? 'wide' : kind === 'radio' ? 'square' : ''));
    });
  }
}
function pageBn() {
  page('bn');
  view.insertAdjacentHTML('beforeend', `<div class="panel bnpanel"><img src="icon.png" alt=""><p>${esc(t('bn_txt'))}</p></div>
    <div class="links">
      <a class="btn" href="${SITE}repository.nova-1.0.0.zip">${esc(t('bn_kodi'))}</a>
      <a class="btn ghost" href="${REL}BN-Stream-21.3-arm64-v8a.apk">${esc(t('bn_android'))}</a>
      <a class="btn ghost" href="${REL}BN-Stream-21.3-armeabi-v7a.apk">${esc(t('bn_android32'))}</a>
      <a class="btn ghost" href="https://github.com/bennymat93/novatv/releases/latest">${esc(t('bn_win'))}</a>
      <a class="btn ghost" href="${SITE}guide.html">${esc(t('bn_guide'))}</a>
    </div><p class="hint" dir="auto">${esc(t('bn_kodi_how'))}</p>`);
}
function pageSettings() {
  page('settings');
  const opt = (pairs, cur) => pairs.map(([v, n]) => `<option value="${esc(v)}"${v === cur ? ' selected' : ''}>${esc(n)}</option>`).join('');
  view.insertAdjacentHTML('beforeend', `<div class="panel settings">
    <label>${esc(t('s_lang'))}<select id="s_lang">${opt([['he', 'עברית'], ['en', 'English'], ['ru', 'Русский']], cfg.lang)}</select></label>
    <label>${esc(t('s_theme'))}<select id="s_theme">${opt([['auto', t('t_auto')], ['dark', t('t_dark')], ['light', t('t_light')]], cfg.theme)}</select></label>
    <label>${esc(t('s_live'))}<select id="s_live">${opt(Object.entries(t('lists')), cfg.live)}</select></label>
    <label>${esc(t('s_radio'))}<select id="s_radio">${opt(Object.entries(t('countries')), cfg.radio)}</select></label>
    <div class="row"><b>${esc(t('s_family'))}</b><span>${esc(t('s_family_txt'))}</span></div>
    <div class="row"><button class="btn ghost" id="s_clear">${esc(t('s_clear'))}</button><span id="s_done"></span></div>
    <p class="hint">${esc(t('s_store'))}</p></div>`);
  for (const k of ['lang', 'theme', 'live', 'radio']) {
    $('#s_' + k).onchange = (e) => { cfg[k] = e.target.value; put('cfg', cfg); applyCfg(); if (k === 'lang') { shell(); pageSettings(); } };
  }
  $('#s_clear').onclick = () => { put('favs', []); $('#s_done').textContent = t('s_cleared'); };
}
async function pageSearch(q) {
  $('#q').value = q;
  page('', `${t('results')} “${q}”`);
  const ql = q.toLowerCase();
  // every source in parallel; each section appears as soon as its source answers
  const jobs = [
    tmdb('/search/multi', {query: q}).then((d) => {
      const r = (d.results || []).filter((x) => x.media_type === 'movie' || x.media_type === 'tv');
      if (r.length) { const g = section(t('titles'), r.length); r.forEach((x) => g.append(tmdbCard(x))); }
      return r.length;
    }).catch(() => 0),
    archive({q}).then((docs) => {
      if (docs.length) { const g = section(t('ia'), docs.length); docs.forEach((d) => g.append(iaCard(d))); }
      return docs.length;
    }).catch(() => 0),
    Promise.all(['il', 'he', 'ru', 'en'].map((l) => channels(l).catch(() => []))).then((all) => {
      const seen = new Set();
      const hit = all.flat().filter((c) => c.name.toLowerCase().includes(ql) && !seen.has(c.url) && seen.add(c.url)).slice(0, 40);
      if (hit.length) { const g = section(t('ch'), hit.length); hit.forEach((c) => g.append(chCard(c))); }
      return hit.length;
    }),
    stations('', q).then((list) => {
      if (list.length) { const g = section(t('radio'), list.length); list.forEach((s) => g.append(radioCard(s))); }
      return list.length;
    }).catch(() => 0),
  ];
  const n = (await Promise.all(jobs)).reduce((a, b) => a + b, 0);
  if (!n) view.insertAdjacentHTML('beforeend', `<p class="msg">${t('none')}</p>`);
}

// ---------------------------------------------------------------- shell
function applyCfg() {
  if (cfg.theme === 'auto') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', cfg.theme);
}
function shell() {
  document.documentElement.lang = cfg.lang;
  document.documentElement.dir = cfg.lang === 'he' ? 'rtl' : 'ltr';
  $('#q').placeholder = t('search');
  $('#foot').textContent = t('foot');
  $('#nav').innerHTML = `<a href="#/" data-p="">${esc(t('home'))}</a>` + MENU.map(([k]) => `<a href="#/${k}" data-p="${k}">${esc(t(k))}</a>`).join('');
}
function markNav(p) { document.querySelectorAll('#nav a').forEach((a) => a.classList.toggle('on', a.dataset.p === p)); }
function route() {
  closeModal();
  const [, p = '', arg = ''] = location.hash.split('/');
  const a = decodeURIComponent(arg);
  markNav(p);
  if (p !== 'search') $('#q').value = '';
  ({movies: () => pageMovies(a), tv: () => pageSeries(a), live: () => pageLive(a), radio: () => pageRadio(a), favs: pageFavs,
    bn: pageBn, settings: pageSettings, search: () => pageSearch(a)}[p] || pageHome)();
  window.scrollTo(0, 0);
}
$('#search').onsubmit = (e) => {
  e.preventDefault();
  const q = $('#q').value.trim();
  if (q) location.hash = '#/search/' + encodeURIComponent(q);
};
window.addEventListener('hashchange', route);
applyCfg(); shell(); route();
