/* =====================================================================
   Haik.io — interface web
   Sections : outils communs · navigation · landing · webcam · dessin · image
   API attendue côté serveur :
     POST /analyser  (FormData « image »)            -> { objets: [{ boite:[x,y,l,h], forme, couleur, confiance }] }
     POST /decrire   (JSON { objets, largeur, hauteur }) -> { phrase }
   ===================================================================== */

/* ---------- Outils communs ---------- */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

const COULEURS_CSS = {
  rouge: '#e5484d', bleu: '#2f7bff', vert: '#3ecf8e', jaune: '#ffc83d', orange: '#ff8a3d',
  violet: '#7c4dff', rose: '#ff6bb5', noir: '#14213d', blanc: '#ffffff', gris: '#8a94a6',
  marron: '#7a4b2a', cyan: '#00bcd4', turquoise: '#1fc8b8'
};
function couleurCss(nom = '') {
  const n = nom.toLowerCase();
  for (const k in COULEURS_CSS) if (n.includes(k)) return COULEURS_CSS[k];
  return '#cfd6e6';
}

let toastTimer;
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('visible'), 2600);
}

function chargerHist(cle) {
  try { return JSON.parse(localStorage.getItem(cle)) || []; } catch { return []; }
}
function sauverHist(cle, liste) {
  for (;;) {
    try { localStorage.setItem(cle, JSON.stringify(liste)); return; }
    catch {                                   // quota dépassé : on retire le plus ancien
      if (liste.length <= 1) return;
      liste.pop();
    }
  }
}

function quand(ts) {
  return new Date(ts).toLocaleString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

/* ---------- Appels au modèle ---------- */
async function analyserBlob(blob) {
  const form = new FormData();
  form.append('image', blob, 'image.jpg');
  const rep = await fetch('/analyser', { method: 'POST', body: form });
  if (!rep.ok) throw new Error('Erreur ' + rep.status);
  return (await rep.json()).objets || [];
}

async function decrire(objets, largeur, hauteur) {
  const rep = await fetch('/decrire', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ objets, largeur, hauteur })
  });
  if (!rep.ok) throw new Error('Erreur ' + rep.status);
  return (await rep.json()).phrase;
}

function rendrePuces(conteneur, objets) {
  conteneur.innerHTML = '';
  objets.forEach(o => {
    const p = document.createElement('span');
    p.className = 'puce';
    const pastille = document.createElement('i');
    pastille.style.background = couleurCss(o.couleur);
    const txt = document.createElement('span');
    txt.textContent = ((o.forme || '') + ' ' + (o.couleur || '')).trim();
    const pc = document.createElement('b');
    pc.textContent = Math.round((o.confiance || 0) * 100) + '%';
    p.append(pastille, txt, pc);
    conteneur.appendChild(p);
  });
}

function dessinerBoites(canvas, objets, w, h) {
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, w, h);
  const taille = Math.max(14, Math.round(w / 40));
  ctx.font = `600 ${taille}px sans-serif`;
  ctx.lineJoin = 'round';
  objets.forEach(o => {
    const [x, y, bw, bh] = o.boite;
    const t = ((o.forme || '') + ' ' + (o.couleur || '')).trim() + ' (' + Math.round((o.confiance || 0) * 100) + '%)';
    ctx.lineWidth = 3; ctx.strokeStyle = '#2f7bff'; ctx.strokeRect(x, y, bw, bh);
    const ty = Math.max(y - 8, taille + 2);
    ctx.lineWidth = 5; ctx.strokeStyle = '#fff'; ctx.strokeText(t, x, ty);
    ctx.fillStyle = '#0d1b3d'; ctx.fillText(t, x, ty);
  });
}

/* =====================================================================
   NAVIGATION
   ===================================================================== */
const landing = $('#landing');
const demo = $('#demo');
let pageCourante = 'webcam';

function afficherVue(nom) {
  landing.classList.toggle('active', nom === 'landing');
  demo.classList.toggle('active', nom === 'demo');
  window.scrollTo({ top: 0, behavior: 'instant' });
  if (nom === 'landing') arreterCamera();
}

function afficherPage(nom) {
  pageCourante = nom;
  $$('.onglet').forEach(b => {
    const actif = b.dataset.page === nom;
    b.classList.toggle('active', actif);
    b.setAttribute('aria-selected', actif);
  });
  $$('.page').forEach(p => p.classList.toggle('active', p.id === 'page-' + nom));
  if (nom !== 'webcam') arreterCamera();
}

$$('[data-demo]').forEach(el => el.addEventListener('click', e => {
  e.preventDefault();
  afficherVue('demo');
  afficherPage(el.dataset.demo || 'webcam');
}));
$$('[data-home]').forEach(el => el.addEventListener('click', e => { e.preventDefault(); afficherVue('landing'); }));
$$('.onglet').forEach(b => b.addEventListener('click', () => afficherPage(b.dataset.page)));
$$('[data-scroll]').forEach(a => a.addEventListener('click', e => {
  e.preventDefault();
  const cible = document.getElementById(a.dataset.scroll);
  if (cible) cible.scrollIntoView({ behavior: 'smooth', block: 'start' });
}));
document.addEventListener('visibilitychange', () => { if (document.hidden) arreterCamera(); });

/* =====================================================================
   LANDING : apparitions, compteurs, newsletter
   ===================================================================== */
(function animationsLanding() {
  const reveals = $$('.reveal');
  if (!('IntersectionObserver' in window)) { reveals.forEach(r => r.classList.add('visible')); return; }
  const obs = new IntersectionObserver(entrees => {
    entrees.forEach(en => {
      if (!en.isIntersecting) return;
      en.target.classList.add('visible');
      $$('[data-count]', en.target).forEach(compter);
      obs.unobserve(en.target);
    });
  }, { threshold: 0.15 });
  reveals.forEach(r => obs.observe(r));
})();

function compter(el) {
  const fin = +el.dataset.count, duree = 1200, t0 = performance.now();
  (function pas(t) {
    const k = Math.min((t - t0) / duree, 1);
    el.textContent = Math.round(fin * (1 - Math.pow(1 - k, 3)));
    if (k < 1) requestAnimationFrame(pas);
  })(t0);
}

$('#nl-form').addEventListener('submit', e => {
  e.preventDefault();
  const msg = $('#nl-msg');
  msg.textContent = 'Merci ! Tu es bien inscrit(e).';
  msg.classList.add('ok');
  e.target.reset();
});

/* =====================================================================
   WEBCAM (suivi des objets dans le temps)
   ===================================================================== */
const video = $('#video');
const sur = $('#sur');
const phrase = $('#phrase');
const voix = $('#voix');
const camBtn = $('#cam-toggle');
const camEtat = $('#cam-etat');
const capture = document.createElement('canvas');
capture.width = 640; capture.height = 480;
sur.width = 640; sur.height = 480;

// Plus stable = confirmer / historique plus grands ; plus réactif = plus petits
const PARAM = { confirmer: 2, absenceMax: 4, historique: 8, lissage: 0.35, iou: 0.25 };

let flux = null, timerAnalyse = null, timerPhrase = null, rafId = 0;
let occupe = false, pistes = [], prochainId = 1;
let cleCandidate = '', cleAffichee = null, depuis = 0;

async function demarrerCamera() {
  camBtn.disabled = true;
  try {
    flux = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
    video.srcObject = flux;
    $('#scene-cam').classList.add('active');
    camBtn.textContent = 'Arrêter la caméra';
    camBtn.classList.replace('btn-primary', 'btn-ghost');
    camEtat.textContent = 'En direct'; camEtat.classList.add('actif');
    phrase.textContent = 'Analyse en cours…';
    cleCandidate = ''; cleAffichee = null;
    timerAnalyse = setInterval(analyserFlux, 300);
    timerPhrase = setInterval(verifierPhrase, 200);
    rafId = requestAnimationFrame(boucle);
  } catch (e) {
    phrase.textContent = 'Caméra inaccessible : ' + e.message;
  }
  camBtn.disabled = false;
}

function arreterCamera() {
  if (!flux) return;
  flux.getTracks().forEach(t => t.stop());
  flux = null; video.srcObject = null;
  clearInterval(timerAnalyse); clearInterval(timerPhrase); cancelAnimationFrame(rafId);
  pistes = []; occupe = false;
  sur.getContext('2d').clearRect(0, 0, sur.width, sur.height);
  $('#scene-cam').classList.remove('active');
  camBtn.textContent = 'Démarrer la caméra';
  camBtn.classList.replace('btn-ghost', 'btn-primary');
  camEtat.textContent = 'En attente'; camEtat.classList.remove('actif');
  phrase.textContent = 'Caméra arrêtée.';
  $('#cam-puces').innerHTML = '';
  speechSynthesis.cancel();
}

camBtn.addEventListener('click', () => (flux ? arreterCamera() : demarrerCamera()));

async function analyserFlux() {
  if (occupe || !flux || video.videoWidth === 0) return;
  occupe = true;
  capture.getContext('2d').drawImage(video, 0, 0, 640, 480);
  try {
    const blob = await new Promise(r => capture.toBlob(r, 'image/jpeg', 0.7));
    mettreAJour(await analyserBlob(blob));
  } catch (e) {
    if (flux) phrase.textContent = 'Serveur injoignable';
  }
  occupe = false;
}

function iou(a, b) {
  const x1 = Math.max(a[0], b[0]), y1 = Math.max(a[1], b[1]);
  const x2 = Math.min(a[0] + a[2], b[0] + b[2]), y2 = Math.min(a[1] + a[3], b[1] + b[3]);
  const inter = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
  return inter / (a[2] * a[3] + b[2] * b[3] - inter || 1);
}

function mettreAJour(objets) {
  const libres = new Set(pistes.map((_, i) => i));
  const paires = [];
  objets.forEach((o, j) => pistes.forEach((p, i) => {
    const v = iou(p.cible, o.boite);
    if (v > PARAM.iou) paires.push([v, i, j]);
  }));
  paires.sort((a, b) => b[0] - a[0]);

  const pris = new Set();
  for (const [, i, j] of paires) {
    if (!libres.has(i) || pris.has(j)) continue;
    libres.delete(i); pris.add(j);
    const p = pistes[i], o = objets[j];
    p.cible = o.boite; p.manque = 0; p.vus++;
    p.hist.push(o.forme + '|' + o.couleur);
    if (p.hist.length > PARAM.historique) p.hist.shift();
    p.confiance = 0.6 * p.confiance + 0.4 * o.confiance;
  }
  libres.forEach(i => pistes[i].manque++);
  objets.forEach((o, j) => {
    if (!pris.has(j)) pistes.push({
      id: prochainId++, cible: o.boite, affichee: o.boite.slice(),
      hist: [o.forme + '|' + o.couleur], vus: 1, manque: 0, confiance: o.confiance, etiquette: null
    });
  });
  pistes = pistes.filter(p => p.manque <= PARAM.absenceMax);
}

function majorite(p) {
  const c = {};
  p.hist.forEach(k => c[k] = (c[k] || 0) + 1);
  const meilleur = Object.entries(c).sort((a, b) => b[1] - a[1])[0][0];
  if (!p.etiquette || c[meilleur] > (c[p.etiquette] || 0) + 1) p.etiquette = meilleur;
  return p.etiquette;
}

function boucle() {
  const ctx = sur.getContext('2d');
  ctx.clearRect(0, 0, sur.width, sur.height);
  ctx.font = '600 18px sans-serif';
  for (const p of pistes) {
    if (p.vus < PARAM.confirmer) continue;
    for (let k = 0; k < 4; k++) p.affichee[k] += (p.cible[k] - p.affichee[k]) * PARAM.lissage;
    const [forme, couleur] = majorite(p).split('|');
    const [x, y, w, h] = p.affichee;
    const t = (forme + ' ' + couleur).trim() + ' (' + Math.round(p.confiance * 100) + '%)';
    ctx.globalAlpha = p.manque > 0 ? 0.45 : 1;
    ctx.lineWidth = 3; ctx.strokeStyle = '#2f7bff'; ctx.strokeRect(x, y, w, h);
    ctx.lineWidth = 4; ctx.strokeStyle = '#fff'; ctx.strokeText(t, x, Math.max(y - 8, 18));
    ctx.fillStyle = '#0d1b3d'; ctx.fillText(t, x, Math.max(y - 8, 18));
  }
  ctx.globalAlpha = 1;
  rafId = requestAnimationFrame(boucle);
}

function objetsStables() {
  return pistes.filter(p => p.vus >= PARAM.confirmer && p.manque <= 1).map(p => {
    const [forme, couleur] = majorite(p).split('|');
    return { forme, couleur, confiance: p.confiance, boite: p.cible.map(Math.round) };
  });
}

function verifierPhrase() {
  const stables = objetsStables();
  const cle = stables.map(o => o.forme + '|' + o.couleur).sort().join(';');
  const maintenant = Date.now();
  if (cle !== cleCandidate) { cleCandidate = cle; depuis = maintenant; return; }
  if (cle !== cleAffichee && maintenant - depuis > 600) {
    cleAffichee = cle;
    demanderPhrase(stables);
  }
}

async function demanderPhrase(stables) {
  try {
    const texte = await decrire(stables, 640, 480);
    if (!flux) return;
    phrase.textContent = texte;
    rendrePuces($('#cam-puces'), stables);
    if (voix.checked && stables.length) {
      const u = new SpeechSynthesisUtterance(texte);
      u.lang = 'fr-FR';
      speechSynthesis.cancel(); speechSynthesis.speak(u);
    }
  } catch (e) { /* on garde la dernière phrase */ }
}

/* =====================================================================
   DESSIN
   ===================================================================== */
const CLE_DESSINS = 'haik.dessins';
const toile = $('#toile'), toileAp = $('#toile-ap');
const ctx = toile.getContext('2d'), ctxAp = toileAp.getContext('2d');
const PALETTE = ['#e5484d', '#ff8a3d', '#ffc83d', '#3ecf8e', '#00bcd4', '#2f7bff',
                 '#7c4dff', '#ff6bb5', '#7a4b2a', '#8a94a6', '#14213d', '#ffffff'];

const etatD = {
  outil: 'stylo', couleur: '#2f6bff', epaisseur: 6, remplir: true,
  trace: false, debut: null, dernier: null, pile: [], historique: chargerHist(CLE_DESSINS),
  edition: null, envoi: false
};

function toileBlanche() {
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, toile.width, toile.height);
  ctxAp.clearRect(0, 0, toileAp.width, toileAp.height);
}
function instantane() {
  etatD.pile.push(ctx.getImageData(0, 0, toile.width, toile.height));
  if (etatD.pile.length > 30) etatD.pile.shift();
}
function toileVide() {
  const d = ctx.getImageData(0, 0, toile.width, toile.height).data;
  for (let i = 0; i < d.length; i += 4) if (d[i] < 250 || d[i + 1] < 250 || d[i + 2] < 250) return false;
  return true;
}

// Palette
PALETTE.forEach(c => {
  const b = document.createElement('button');
  b.className = 'pastille'; b.style.background = c; b.title = c; b.dataset.c = c;
  b.addEventListener('click', () => choisirCouleur(c));
  $('#palette').appendChild(b);
});
function choisirCouleur(c) {
  etatD.couleur = c;
  $('#couleur').value = c;
  $$('.pastille').forEach(p => p.classList.toggle('active', p.dataset.c.toLowerCase() === c.toLowerCase()));
  if (etatD.outil === 'gomme') choisirOutil('stylo');
}
$('#couleur').addEventListener('input', e => choisirCouleur(e.target.value));
$('#epaisseur').addEventListener('input', e => { etatD.epaisseur = +e.target.value; $('#epaisseur-val').textContent = e.target.value; });
$('#remplir').addEventListener('change', e => etatD.remplir = e.target.checked);

// Outils
function choisirOutil(nom) {
  etatD.outil = nom;
  $$('.outil[data-outil]').forEach(b => b.classList.toggle('active', b.dataset.outil === nom));
  $$('.outil[data-forme]').forEach(b => b.classList.toggle('active', b.dataset.forme === nom));
}
$$('.outil[data-outil]').forEach(b => b.addEventListener('click', () => choisirOutil(b.dataset.outil)));
$$('.outil[data-forme]').forEach(b => b.addEventListener('click', () =>
  choisirOutil(etatD.outil === b.dataset.forme ? 'stylo' : b.dataset.forme)));

// Coordonnées dans le repère du canvas
function pos(e) {
  const r = toile.getBoundingClientRect();
  return [(e.clientX - r.left) * toile.width / r.width, (e.clientY - r.top) * toile.height / r.height];
}

function polygone(c, cx, cy, r, n, rot = -Math.PI / 2, interieur = 1) {
  c.beginPath();
  const total = interieur === 1 ? n : n * 2;
  for (let i = 0; i < total; i++) {
    const rayon = interieur === 1 ? r : (i % 2 === 0 ? r : r * interieur);
    const a = rot + i * 2 * Math.PI / total;
    const x = cx + rayon * Math.cos(a), y = cy + rayon * Math.sin(a);
    i ? c.lineTo(x, y) : c.moveTo(x, y);
  }
  c.closePath();
}

function tracerForme(c, forme, a, b) {
  let x = Math.min(a[0], b[0]), y = Math.min(a[1], b[1]);
  let w = Math.abs(b[0] - a[0]), h = Math.abs(b[1] - a[1]);
  if (w < 3 && h < 3) return false;
  if (forme === 'carre' || forme === 'cercle') {       // proportions imposées
    const s = Math.max(w, h);
    x = b[0] < a[0] ? a[0] - s : a[0]; y = b[1] < a[1] ? a[1] - s : a[1]; w = h = s;
  }
  const cx = x + w / 2, cy = y + h / 2, r = Math.min(w, h) / 2;
  c.lineJoin = 'round';
  c.lineWidth = etatD.epaisseur; c.strokeStyle = c.fillStyle = etatD.couleur;
  switch (forme) {
    case 'rectangle': case 'carre': c.beginPath(); c.rect(x, y, w, h); break;
    case 'cercle': c.beginPath(); c.arc(cx, cy, w / 2, 0, Math.PI * 2); break;
    case 'triangle': c.beginPath(); c.moveTo(cx, y); c.lineTo(x + w, y + h); c.lineTo(x, y + h); c.closePath(); break;
    case 'losange': c.beginPath(); c.moveTo(cx, y); c.lineTo(x + w, cy); c.lineTo(cx, y + h); c.lineTo(x, cy); c.closePath(); break;
    case 'etoile': polygone(c, cx, cy, r, 5, -Math.PI / 2, 0.42); break;
    case 'pentagone': polygone(c, cx, cy, r, 5); break;
    case 'hexagone': polygone(c, cx, cy, r, 6, 0); break;
  }
  if (etatD.remplir) c.fill();
  c.stroke();
  return true;
}

// Dessin à la souris / au doigt / au stylet
toile.addEventListener('pointerdown', e => {
  if (e.button > 0) return;
  toile.setPointerCapture(e.pointerId);
  ctxAp.clearRect(0, 0, toileAp.width, toileAp.height);   // efface les cadres de la dernière réponse
  instantane();
  etatD.trace = true; etatD.debut = etatD.dernier = pos(e);
  if (etatD.outil === 'stylo' || etatD.outil === 'gomme') {
    ctx.fillStyle = etatD.outil === 'gomme' ? '#fff' : etatD.couleur;
    ctx.beginPath();
    ctx.arc(etatD.debut[0], etatD.debut[1], (etatD.outil === 'gomme' ? etatD.epaisseur * 1.5 : etatD.epaisseur) / 2, 0, Math.PI * 2);
    ctx.fill();
  }
});

toile.addEventListener('pointermove', e => {
  if (!etatD.trace) return;
  const p = pos(e);
  if (etatD.outil === 'stylo' || etatD.outil === 'gomme') {
    ctx.lineCap = ctx.lineJoin = 'round';
    ctx.strokeStyle = etatD.outil === 'gomme' ? '#fff' : etatD.couleur;
    ctx.lineWidth = etatD.outil === 'gomme' ? etatD.epaisseur * 1.5 : etatD.epaisseur;
    ctx.beginPath(); ctx.moveTo(...etatD.dernier); ctx.lineTo(...p); ctx.stroke();
    etatD.dernier = p;
  } else {
    ctxAp.clearRect(0, 0, toileAp.width, toileAp.height);
    tracerForme(ctxAp, etatD.outil, etatD.debut, p);
  }
});

function finTrace(e) {
  if (!etatD.trace) return;
  etatD.trace = false;
  if (etatD.outil !== 'stylo' && etatD.outil !== 'gomme') {
    ctxAp.clearRect(0, 0, toileAp.width, toileAp.height);
    if (!tracerForme(ctx, etatD.outil, etatD.debut, pos(e))) etatD.pile.pop();
  }
}
toile.addEventListener('pointerup', finTrace);
toile.addEventListener('pointercancel', finTrace);

$('#annuler').addEventListener('click', () => {
  const s = etatD.pile.pop();
  if (!s) return toast('Rien à annuler');
  ctx.putImageData(s, 0, 0);
  ctxAp.clearRect(0, 0, toileAp.width, toileAp.height);
});
$('#effacer').addEventListener('click', () => { instantane(); toileBlanche(); });
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z' && pageCourante === 'dessin' && demo.classList.contains('active')) {
    e.preventDefault(); $('#annuler').click();
  }
});

// Envoi, historique, édition
function blobToile() { return new Promise(r => toile.toBlob(r, 'image/jpeg', 0.85)); }

function majBoutonsEdition() {
  const ed = etatD.edition !== null;
  $('#dessin-titre').textContent = ed ? 'Modifier le dessin' : 'Nouveau dessin';
  $('#dessin-envoyer-txt').textContent = ed ? 'Renvoyer' : 'Envoyer';
  $('#dessin-sauver').hidden = !ed;
  $('#dessin-nouveau').hidden = !ed;
}

function nouveauDessin() {
  etatD.edition = null; etatD.pile = [];
  toileBlanche(); majBoutonsEdition(); rendreHistDessins();
  $('#dessin-phrase').textContent = 'Dessine quelque chose puis clique sur « Envoyer ».';
}

async function envoyerDessin() {
  if (etatD.envoi) return;
  if (toileVide()) return toast('Dessine d’abord quelque chose');
  etatD.envoi = true;
  const bouton = $('#dessin-envoyer'); bouton.disabled = true;
  const zone = $('.toile-cadre'); zone.classList.add('chargement');
  $('#dessin-phrase').textContent = 'Analyse en cours…';
  try {
    const blob = await blobToile();
    const objets = await analyserBlob(blob);
    const texte = await decrire(objets, toile.width, toile.height);
    $('#dessin-phrase').textContent = texte;
    dessinerBoites(toileAp, objets, toile.width, toile.height);
    const entree = { id: etatD.edition ?? Date.now(), img: toile.toDataURL('image/jpeg', 0.6), phrase: texte, date: Date.now() };
    const i = etatD.historique.findIndex(h => h.id === entree.id);
    if (i >= 0) etatD.historique.splice(i, 1);
    etatD.historique.unshift(entree);
    etatD.historique = etatD.historique.slice(0, 20);
    etatD.edition = entree.id;
    sauverHist(CLE_DESSINS, etatD.historique);
    majBoutonsEdition(); rendreHistDessins();
  } catch (e) {
    $('#dessin-phrase').textContent = 'Serveur injoignable, réessaie dans un instant.';
  }
  zone.classList.remove('chargement');
  bouton.disabled = false; etatD.envoi = false;
}
$('#dessin-envoyer').addEventListener('click', envoyerDessin);
$('#dessin-nouveau').addEventListener('click', nouveauDessin);

$('#dessin-sauver').addEventListener('click', () => {
  const h = etatD.historique.find(x => x.id === etatD.edition);
  if (!h) return;
  h.img = toile.toDataURL('image/jpeg', 0.6); h.date = Date.now();
  sauverHist(CLE_DESSINS, etatD.historique); rendreHistDessins();
  toast('Modifications enregistrées');
});

function ouvrirDessin(id) {
  const h = etatD.historique.find(x => x.id === id);
  if (!h) return;
  const img = new Image();
  img.onload = () => {
    toileBlanche(); ctx.drawImage(img, 0, 0, toile.width, toile.height);
    etatD.pile = []; etatD.edition = id;
    $('#dessin-phrase').textContent = h.phrase;
    majBoutonsEdition(); rendreHistDessins();
  };
  img.src = h.img;
}

function supprimerDessin(id) {
  etatD.historique = etatD.historique.filter(x => x.id !== id);
  sauverHist(CLE_DESSINS, etatD.historique);
  if (etatD.edition === id) nouveauDessin(); else rendreHistDessins();
}

$('#dessin-vider').addEventListener('click', () => {
  if (!etatD.historique.length) return;
  if (!confirm('Supprimer tout l’historique des dessins ?')) return;
  etatD.historique = []; sauverHist(CLE_DESSINS, []); nouveauDessin();
});

function carteHistorique(h, actif, ouvrir, supprimer) {
  const el = document.createElement('div');
  el.className = 'hist-item' + (actif ? ' active' : '');
  el.tabIndex = 0;
  const img = document.createElement('img'); img.src = h.img; img.alt = h.phrase || 'Élément de l’historique';
  const info = document.createElement('div'); info.className = 'hist-info';
  const t = document.createElement('strong'); t.textContent = h.phrase || '—';
  const d = document.createElement('span'); d.textContent = quand(h.date);
  info.append(t, d);
  const act = document.createElement('div'); act.className = 'hist-actions';
  const mod = document.createElement('button'); mod.title = 'Ouvrir / modifier';
  mod.innerHTML = '<svg class="ico"><use href="#i-edit"/></svg>';
  const sup = document.createElement('button'); sup.className = 'sup'; sup.title = 'Supprimer';
  sup.innerHTML = '<svg class="ico"><use href="#i-trash"/></svg>';
  mod.addEventListener('click', e => { e.stopPropagation(); ouvrir(); });
  sup.addEventListener('click', e => { e.stopPropagation(); supprimer(); });
  act.append(mod, sup);
  el.append(img, info, act);
  el.addEventListener('click', ouvrir);
  el.addEventListener('keydown', e => { if (e.key === 'Enter') ouvrir(); });
  return el;
}

function rendreHistDessins() {
  const liste = $('#dessin-hist'); liste.innerHTML = '';
  if (!etatD.historique.length) { liste.innerHTML = '<p class="hist-vide">Tes dessins envoyés apparaîtront ici.</p>'; return; }
  etatD.historique.forEach(h => liste.appendChild(
    carteHistorique(h, h.id === etatD.edition, () => ouvrirDessin(h.id), () => supprimerDessin(h.id))));
}

toileBlanche();
choisirCouleur('#2f7bff');
rendreHistDessins();

/* =====================================================================
   IMAGE
   ===================================================================== */
const CLE_IMAGES = 'haik.images';
const depot = $('#depot'), fichier = $('#img-fichier'), apercu = $('#img-apercu'), imgSur = $('#img-sur');
const etatI = { blob: null, historique: chargerHist(CLE_IMAGES), edition: null, envoi: false };

function montrerImage(url, blob) {
  etatI.blob = blob;
  apercu.onload = () => { positionnerSurImage(); };
  apercu.src = url;
  $('#depot-vide').hidden = true; $('#img-scene').hidden = false;
  depot.classList.add('rempli');
  $('#img-reset').hidden = false; $('#img-envoyer').disabled = false;
  imgSur.getContext('2d').clearRect(0, 0, imgSur.width, imgSur.height);
  $('#img-puces').innerHTML = '';
}
function positionnerSurImage() {
  Object.assign(imgSur.style, {
    left: apercu.offsetLeft + 'px', top: apercu.offsetTop + 'px',
    width: apercu.clientWidth + 'px', height: apercu.clientHeight + 'px'
  });
}
window.addEventListener('resize', positionnerSurImage);

function reinitialiserImage() {
  etatI.blob = null; etatI.edition = null; fichier.value = '';
  $('#depot-vide').hidden = false; $('#img-scene').hidden = true;
  depot.classList.remove('rempli');
  $('#img-reset').hidden = true; $('#img-envoyer').disabled = true;
  $('#img-phrase').textContent = 'Choisis une image pour l’analyser.';
  $('#img-puces').innerHTML = '';
  rendreHistImages();
}

function choisirFichier(f) {
  if (!f) return;
  if (!f.type.startsWith('image/')) return toast('Ce fichier n’est pas une image');
  etatI.edition = null;
  montrerImage(URL.createObjectURL(f), f);
  $('#img-phrase').textContent = 'Image prête. Clique sur « Envoyer ».';
  rendreHistImages();
}
fichier.addEventListener('change', () => choisirFichier(fichier.files[0]));
depot.addEventListener('click', e => { if (depot.classList.contains('rempli')) e.preventDefault(); });
['dragenter', 'dragover'].forEach(n => depot.addEventListener(n, e => { e.preventDefault(); depot.classList.add('survol'); }));
['dragleave', 'drop'].forEach(n => depot.addEventListener(n, e => { e.preventDefault(); depot.classList.remove('survol'); }));
depot.addEventListener('drop', e => choisirFichier(e.dataTransfer.files[0]));
$('#img-reset').addEventListener('click', reinitialiserImage);

// Réduit les grandes photos avant l'envoi (plus rapide) et renvoie aussi une miniature
async function preparerImage(blob) {
  const bmp = await createImageBitmap(blob);
  const echelle = Math.min(1, 1280 / Math.max(bmp.width, bmp.height));
  const c = document.createElement('canvas');
  c.width = Math.round(bmp.width * echelle); c.height = Math.round(bmp.height * echelle);
  const cx = c.getContext('2d');
  cx.fillStyle = '#fff'; cx.fillRect(0, 0, c.width, c.height);
  cx.drawImage(bmp, 0, 0, c.width, c.height);
  const envoi = await new Promise(r => c.toBlob(r, 'image/jpeg', 0.85));
  const e2 = Math.min(1, 640 / Math.max(c.width, c.height));
  const m = document.createElement('canvas');
  m.width = Math.round(c.width * e2); m.height = Math.round(c.height * e2);
  m.getContext('2d').drawImage(c, 0, 0, m.width, m.height);
  return { envoi, w: c.width, h: c.height, miniature: m.toDataURL('image/jpeg', 0.7) };
}

async function envoyerImage() {
  if (etatI.envoi || !etatI.blob) return;
  etatI.envoi = true;
  const bouton = $('#img-envoyer'); bouton.disabled = true;
  depot.classList.add('chargement');
  $('#img-phrase').textContent = 'Analyse en cours…';
  try {
    const p = await preparerImage(etatI.blob);
    const objets = await analyserBlob(p.envoi);
    const texte = await decrire(objets, p.w, p.h);
    $('#img-phrase').textContent = texte;
    rendrePuces($('#img-puces'), objets);
    positionnerSurImage();
    dessinerBoites(imgSur, objets, p.w, p.h);
    const entree = { id: etatI.edition ?? Date.now(), img: p.miniature, phrase: texte, date: Date.now() };
    const i = etatI.historique.findIndex(h => h.id === entree.id);
    if (i >= 0) etatI.historique.splice(i, 1);
    etatI.historique.unshift(entree);
    etatI.historique = etatI.historique.slice(0, 20);
    etatI.edition = entree.id;
    sauverHist(CLE_IMAGES, etatI.historique); rendreHistImages();
  } catch (e) {
    $('#img-phrase').textContent = 'Serveur injoignable, réessaie dans un instant.';
  }
  depot.classList.remove('chargement');
  bouton.disabled = false; etatI.envoi = false;
}
$('#img-envoyer').addEventListener('click', envoyerImage);

async function ouvrirImage(id) {
  const h = etatI.historique.find(x => x.id === id);
  if (!h) return;
  const blob = await (await fetch(h.img)).blob();
  montrerImage(h.img, blob);
  etatI.edition = id;
  $('#img-phrase').textContent = h.phrase;
  rendreHistImages();
}

function supprimerImage(id) {
  etatI.historique = etatI.historique.filter(x => x.id !== id);
  sauverHist(CLE_IMAGES, etatI.historique);
  if (etatI.edition === id) reinitialiserImage(); else rendreHistImages();
}

$('#img-vider').addEventListener('click', () => {
  if (!etatI.historique.length) return;
  if (!confirm('Supprimer tout l’historique des images ?')) return;
  etatI.historique = []; sauverHist(CLE_IMAGES, []); reinitialiserImage();
});

function rendreHistImages() {
  const liste = $('#img-hist'); liste.innerHTML = '';
  if (!etatI.historique.length) { liste.innerHTML = '<p class="hist-vide">Tes images envoyées apparaîtront ici.</p>'; return; }
  etatI.historique.forEach(h => liste.appendChild(
    carteHistorique(h, h.id === etatI.edition, () => ouvrirImage(h.id), () => supprimerImage(h.id))));
}
rendreHistImages();