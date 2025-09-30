console.log("RMG script loaded");

/* ===== TMDb config ===== */
const TMDB_V4_BEARER =
  "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJhMDc3OWI2MWZlMzQwOTVlZTAzZTc3ZjBmODg1YTQzNyIsIm5iZiI6MTc1ODg5OTk2Mi4wMzYsInN1YiI6IjY4ZDZhZWZhY2Y4ZmU5MTE1ODA5NWZlNCIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.M1LRr7Ob6VDSeChUWNdit_41GEhBJRCngzGGAkzxawQ";
const TMDB_BASE = "https://api.themoviedb.org/3";
const IMG_500 = "https://image.tmdb.org/t/p/w500";

/* ===== App constants ===== */
const GENRES = [
  "Horror","Drama","Comedy","Thriller","Mystery","Superhero","Science Fiction",
  "Western","Fantasy","Action","Rom com","Musical","Children's animation","Teen movies"
];
const GENRE_MAP = {
  Horror: 27, Drama: 18, Comedy: 35, Thriller: 53, Mystery: 9648,
  "Science Fiction": 878, Western: 37, Fantasy: 14,
  Action: 28, Adventure: 12, "Rom com": 10749,
  Musical: 10402, "Children's animation": 16, "Teen movies": 35
};
const SUPERHERO_KEYWORD_ID = 9715;

/* Weighted decades: prioritize 1960-2020s, occasionally 40s/50s */
const DECADES_WEIGHTED = [
  "1960s","1960s","1960s",
  "1970s","1970s","1970s",
  "1980s","1980s","1980s",
  "1990s","1990s","1990s",
  "2000s","2000s","2000s",
  "2010s","2010s","2010s",
  "2020s","2020s",
  "1950s",
  "1940s"
];

/* Film reel placeholder names for the spin only */
const FILM_SCROLL = [
  "Psycho","Moonlight","Rear Window","The Dark Knight","Fury Road","The Matrix","Alien","Die Hard",
  "Toy Story","Spirited Away","The Godfather","The Exorcist","La La Land","Heat","Oldboy","Blade Runner"
];

/* ===== Helpers ===== */
function decadeRange(dec){ const s=parseInt(dec.slice(0,4),10); return {start:s,end:s+9}; }
function posterBG(title,w=600,h=900){
  const safe = (title || "No Poster").replace(/&/g,"&amp;");
  const svg = encodeURIComponent(
`<svg xmlns='http://www.w3.org/2000/svg' width='${w}' height='${h}' viewBox='0 0 ${w} ${h}'>
  <rect width='100%' height='100%' fill='#111'/>
  <text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle'
        font-family='Inter, Arial' font-size='28' fill='#eee' font-weight='800'>${safe}</text>
</svg>`);
  return `url("${"data:image/svg+xml," + svg}")`;
}
function setPoster(el, bgUrl){
  el.style.backgroundImage = bgUrl;
  el.style.backgroundColor = "#111";
}

/* ===== Robot theme ===== */
function applyRobotTheme(name){
  const body = document.body;
  const tag = document.querySelector(".brand .tag");
  body.classList.remove("theme-mandy","theme-pp","theme-charkins","theme-lpk");
  switch(name){
    case "PP": body.classList.add("theme-pp"); break;
    case "Charkins": body.classList.add("theme-charkins"); break;
    case "LPK": body.classList.add("theme-lpk"); break;
    default: body.classList.add("theme-mandy");
  }
  if (tag) tag.textContent = name;
}

/* ===== TMDb fetch ===== */
async function tmdb(url, paramsObj){
  const u = new URL(url);
  if (paramsObj){
    for (const k in paramsObj) {
      if (Object.prototype.hasOwnProperty.call(paramsObj, k)) {
        u.searchParams.set(k, paramsObj[k]);
      }
    }
  }
  const res = await fetch(u.toString(), {
    headers: { Authorization: "Bearer " + TMDB_V4_BEARER }
  });
  if (!res.ok) {
    console.error("TMDb error", res.status);
    throw new Error("TMDb error " + res.status);
  }
  return res.json();
}

/* Fallbacks for sparse decades (not for Superhero) */
const RELATED_FALLBACKS = {
  Action:       [["Action"],["Adventure"],["Action","Adventure"]],
  Thriller:     [["Thriller"],["Crime"],["Thriller","Crime"]],
  Comedy:       [["Comedy"],["Rom com"],["Comedy","Rom com"]],
  Mystery:      [["Mystery"],["Thriller"],["Mystery","Thriller"]],
  "Science Fiction": [["Science Fiction"],["Adventure"],["Science Fiction","Adventure"]],
  Western:      [["Western"],["Adventure"],["Western","Adventure"]],
  Fantasy:      [["Fantasy"],["Adventure"],["Fantasy","Adventure"]],
  Drama:        [["Drama"],["Rom com"],["Drama","Rom com"]],
  Musical:      [["Musical"],["Rom com"],["Musical","Rom com"]],
  "Children's animation": [["Children's animation"]],
  "Teen movies":[["Teen movies"]],
  "Rom com":[["Rom com"]]
};
function buildGenreParam(genArr){ return genArr.map(g => GENRE_MAP[g]).filter(Boolean).join(","); }
function filterPoolByDecade(pool, decade){
  const r=decadeRange(decade);
  return pool.filter(m=>{
    const y = m && m.release_date ? parseInt(m.release_date.slice(0,4),10) : null;
    return y && y >= r.start && y <= r.end;
  });
}

/* Decade rules */
function validDecadesForGenre(genre){
  if (genre === "Superhero") return ["1980s","1990s","2000s","2010s","2020s"];      // 1980+
  if (genre === "Rom com") return ["1980s","1990s","2000s","2010s","2020s"];       // 1980+
  if (genre === "Teen movies") return ["1990s","2000s","2010s","2020s"];           // 1990+
  if (genre === "Science Fiction") return ["1960s","1970s","1980s","1990s","2000s","2010s","2020s"]; // 1960+
  if (genre === "Musical") return ["1960s","1970s","1980s","1990s","2000s","2010s","2020s"];         // 1960+
  if (genre === "Action") return ["1950s","1960s","1970s","1980s","1990s","2000s","2010s","2020s"];  // 1950+
  return DECADES_WEIGHTED; // default weighting 1960+ with occasional 40s/50s
}

/* Discover with stronger support for 40s–50s when sparse.
   Superhero uses only keyword and no fallback. */
async function fetchMoviesBySpec(chosenGenre, chosenDecade){
  const r = decadeRange(chosenDecade);
  const start = Math.max(r.start, 1940);
  const end = r.end;

  let voteFloors = [500];
  const sparse = (start === 1940 || start === 1950);
  if (sparse) voteFloors = [500, 250, 100];

  const base = {
    language: "en-US",
    include_adult: "false",
    with_original_language: "en",
    "with_runtime.gte": "60",
    "primary_release_date.gte": start + "-01-01",
    "primary_release_date.lte": end + "-12-31",
    page: "1"
  };

  const tryOne = async (genresArr, voteFloor, sort) => {
    const params = Object.assign({}, base, {
      "vote_count.gte": String(voteFloor),
      sort_by: sort || "popularity.desc"
    });

    if (chosenGenre === "Superhero"){
      const kwParams = Object.assign({}, params, { with_keywords: String(SUPERHERO_KEYWORD_ID) });
      const dataKW = await tmdb(`${TMDB_BASE}/discover/movie`, kwParams);
      return dataKW.results || [];
    }

    const gid = buildGenreParam(genresArr);
    const res = await tmdb(`${TMDB_BASE}/discover/movie`, Object.assign({}, params, { with_genres: gid }));
    return res.results || [];
  };

  let order = (chosenGenre === "Superhero") ? [["Superhero"]] : (RELATED_FALLBACKS[chosenGenre] || [[chosenGenre]]);
  if (chosenGenre === "Action" && (!order.some(set => set.join(",") === "Action,Adventure"))){
    order.push(["Action","Adventure"]);
  }

  for (let v=0; v<voteFloors.length; v++){
    const vf = voteFloors[v];
    for (let i=0; i<order.length; i++){
      const gset = order[i];
      let pool = await tryOne(gset, vf, "popularity.desc");
      pool = filterPoolByDecade(pool, chosenDecade);
      if (pool.length) return pool;
    }
    if (sparse && chosenGenre !== "Superhero"){
      for (let i=0; i<order.length; i++){
        const gset = order[i];
        let pool = await tryOne(gset, vf, "vote_count.desc");
        pool = filterPoolByDecade(pool, chosenDecade);
        if (pool.length) return pool;
      }
    }
  }

  const last = await tmdb(`${TMDB_BASE}/discover/movie`, Object.assign({}, base, {
    "vote_count.gte": sparse ? "50" : "200",
    sort_by: sparse ? "vote_count.desc" : "popularity.desc"
  }));
  return filterPoolByDecade(last.results || [], chosenDecade);
}

async function pickFilm(chosenGenre, chosenDecade){
  const pool = await fetchMoviesBySpec(chosenGenre, chosenDecade);
  if (!pool || pool.length === 0){
    alert("No movies found for " + chosenGenre + " in " + chosenDecade + ". Try another.");
    return null;
  }
  const m = pool[Math.floor(Math.random() * pool.length)];
  const title = m && (m.title || m.name) ? (m.title || m.name) : "Untitled";
  const year = m && m.release_date ? m.release_date.slice(0,4) : "Unknown";
  const rating = m && typeof m.vote_average === "number" ? m.vote_average.toFixed(1) : "N/A";
  const poster = m && m.poster_path ? IMG_500 + m.poster_path : null;
  return { title, year, rating, posterCSS: poster ? `url(${poster})` : posterBG(title) };
}

/* ===== Reel ===== */
class Reel{
  constructor(list, outerEl, cellsEl, speedPxPerFrame){
    this.list=list; this.outerEl=outerEl; this.cellsEl=cellsEl;
    this.spinning=false; this.offset=0; this.cellH=56; this.speed=speedPxPerFrame||24;
    this._raf=null; this._stopTimeout=null;
  }
  build(){
    const seq=this.list.concat(this.list, this.list);
    this.cellsEl.innerHTML="";
    for (let i=0;i<seq.length;i++){
      const d=document.createElement("div"); d.className="cell"; d.textContent=seq[i];
      this.cellsEl.appendChild(d);
    }
    this.offset=0; this.cellsEl.style.transform="translateY(0px)";
    this.outerEl.classList.remove("stopped");
  }
  start(){
    if (this.spinning) return;
    this.build();
    this.spinning=true;
    const step=()=>{
      this.offset -= this.speed;
      if (-this.offset >= this.cellH){
        this.cellsEl.appendChild(this.cellsEl.firstElementChild);
        this.offset += this.cellH;
      }
      this.cellsEl.style.transform = "translateY(" + Math.round(this.offset) + "px)";
      this._raf = requestAnimationFrame(step);
    };
    this._raf = requestAnimationFrame(step);
    this._stopTimeout = setTimeout(()=>this.stop(), 30000);
  }
  stop(){
    if (!this.spinning) return null;
    this.spinning=false;
    cancelAnimationFrame(this._raf);
    clearTimeout(this._stopTimeout);
    const val = this.list[Math.floor(Math.random() * this.list.length)];
    this.cellsEl.innerHTML="";
    const d=document.createElement("div"); d.className="cell"; d.textContent=val;
    this.cellsEl.appendChild(d);
    this.cellsEl.style.transform="translateY(0px)";
    this.outerEl.classList.add("stopped");
    return val;
  }
}

/* ===== DOM ===== */
const btnGenre = document.getElementById("btnGenre");
const btnDecade = document.getElementById("btnDecade");
const btnFilm = document.getElementById("btnFilm");
const genreOuter = document.getElementById("genreReel");
const decadeOuter = document.getElementById("decadeReel");
const filmOuter = document.getElementById("filmReel");
const genreCells = document.getElementById("genreCells");
const decadeCells = document.getElementById("decadeCells");
const filmCells = document.getElementById("filmCells");

const filmPoster = document.getElementById("filmPoster");
const filmTitle = document.getElementById("filmTitle");
const filmMeta = document.getElementById("filmMeta");

const lineupEl = document.getElementById("lineup");
const lineupInfo = document.getElementById("lineupInfo");
const shuffleCaption = document.getElementById("shuffleCaption");
const resetBtn = document.getElementById("resetBtn");
const robotSelect = document.getElementById("robot");

/* ===== Reels init ===== */
const genreReel = new Reel(GENRES, genreOuter, genreCells, 28);
const decadeReel = new Reel(DECADES_WEIGHTED, decadeOuter, decadeCells, 28);
const filmReel = new Reel(FILM_SCROLL, filmOuter, filmCells, 30);
genreReel.build(); decadeReel.build(); filmReel.build();

let chosenGenre=null;
let chosenDecade=null;
let lineupFilms=[];
let shuffledFilms=[];
let fetching=false;
let holdingInRoulette=false;

/* Robot theme handler */
applyRobotTheme("Mandy");
robotSelect.addEventListener("change", e => applyRobotTheme(e.target.value));

/* ===== Buttons ===== */
btnGenre.addEventListener("click", ()=>{
  if (holdingInRoulette || fetching) return;
  if (!genreReel.spinning){ btnGenre.textContent="Stop"; genreReel.start(); }
  else { chosenGenre=genreReel.stop(); btnGenre.disabled=true; btnDecade.disabled=false; }
});

btnDecade.addEventListener("click", ()=>{
  if (holdingInRoulette || fetching) return;
  if (!chosenGenre) return;
  if (!decadeReel.spinning){
    const allowed = validDecadesForGenre(chosenGenre);
    const weighted = DECADES_WEIGHTED.filter(d => allowed.includes(d));
    decadeReel.list = weighted.length ? weighted : allowed;
    decadeReel.build();
    btnDecade.textContent="Stop";
    decadeReel.start();
  } else {
    chosenDecade=decadeReel.stop();
    btnDecade.disabled=true; btnFilm.disabled=false;
  }
});

btnFilm.addEventListener("click", async ()=>{
  if (holdingInRoulette || fetching) return;
  if (!chosenGenre || !chosenDecade) return;

  if (!filmReel.spinning){
    btnFilm.textContent="Stop";
    filmReel.start();
  } else {
    filmReel.stop();
    btnFilm.disabled = true;
    fetching = true;

    try{
      const film = await pickFilm(chosenGenre, chosenDecade);
      if (!film){
        btnFilm.disabled=false; btnFilm.textContent="Spin"; filmReel.build();
        fetching = false;
        return;
      }

      // set real title into film reel display
      filmCells.innerHTML = "";
      const fixed = document.createElement("div");
      fixed.className = "cell";
      fixed.textContent = film.title;
      filmCells.appendChild(fixed);
      filmOuter.classList.add("stopped");

      // preview in the roulette area for 3 seconds
      setPoster(filmPoster, film.posterCSS);
      filmTitle.textContent = film.title;
      filmMeta.textContent = film.year + " • " + film.rating + "/10";

      holdingInRoulette = true;
      btnGenre.disabled = true;
      btnDecade.disabled = true;

      setTimeout(function(){
        placeFilmIntoLineup({
          title: film.title,
          year: film.year,
          rating: parseFloat(film.rating),
          poster: film.posterCSS
        });

        holdingInRoulette = false;

        if (lineupFilms.length < 3){
          chosenGenre=null; chosenDecade=null;
          genreReel.build(); decadeReel.build(); filmReel.build();
          btnGenre.textContent="Spin"; btnDecade.textContent="Spin"; btnFilm.textContent="Spin";
          btnGenre.disabled=false; btnDecade.disabled=true; btnFilm.disabled=true;
        }

      }, 3000);

    } catch(err){
      console.error(err);
      alert("Could not fetch from TMDb. Open DevTools Console to see errors.");
      btnFilm.disabled=false; btnFilm.textContent="Spin"; filmReel.build();
    } finally {
      fetching = false;
    }
  }
});

/* ===== Lineup and choose A/B/C in place ===== */
function placeFilmIntoLineup(f){
  if (lineupFilms.length >= 3) return;
  const slot = lineupEl.querySelector('.slot[data-slot="' + lineupFilms.length + '"]');
  lineupFilms.push(f);
  slot.querySelector(".head span:last-child").textContent="Ready";
  const p=slot.querySelector(".poster");
  p.classList.remove("blank");
  setPoster(p, f.poster);
  slot.querySelector(".title").textContent=f.title;
  lineupInfo.textContent="Filled " + lineupFilms.length + " of 3";
  if (lineupFilms.length === 3) prepareABC();
}

function prepareABC(){
  btnGenre.disabled = btnDecade.disabled = btnFilm.disabled = true;
  shuffledFilms = [].concat(lineupFilms).sort(() => Math.random() - 0.5);

  shuffleCaption.style.display = "block";
  shuffleCaption.textContent = "The films have been randomly re-ordered, please select A, B or C.";

  ["A","B","C"].forEach((L, i)=>{
    const slot = lineupEl.querySelector('.slot[data-slot="' + i + '"]');
    const head = slot.querySelector(".head");
    head.querySelector(".label").textContent = L;
    head.querySelector("span:last-child").textContent = "Shuffled";

    const poster = slot.querySelector(".poster");
    poster.classList.add("bigChoice");
    poster.style.backgroundImage = "";
    poster.innerHTML = "<span>"+L+"</span>";
    poster.onclick = () => handleChoice(L);

    slot.querySelector(".title").textContent = "";
  });
}

function handleChoice(letter){
  ["A","B","C"].forEach((L, i)=>{
    const slot = lineupEl.querySelector('.slot[data-slot="' + i + '"]');
    const poster = slot.querySelector(".poster");
    poster.onclick = null;
    poster.classList.remove("bigChoice");
    poster.innerHTML = "";
  });

  const idx = {A:0,B:1,C:2}[letter];
  const winner = shuffledFilms[idx];

  const winSlot = lineupEl.querySelector('.slot[data-slot="' + idx + '"]');
  setPoster(winSlot.querySelector(".poster"), winner.poster);
  winSlot.querySelector(".title").textContent =
    `${winner.title} - ${winner.year} • ${winner.rating.toFixed(1)}/10`;

  setTimeout(()=>{
    for (let i=0;i<3;i++){
      if (i===idx) continue;
      const f = shuffledFilms[i];
      const slot = lineupEl.querySelector('.slot[data-slot="' + i + '"]');
      setPoster(slot.querySelector(".poster"), f.poster);
      slot.querySelector(".title").textContent =
        `${f.title} - ${f.year} • ${f.rating.toFixed(1)}/10`;
    }
  }, 5000);
}

/* ===== Reset ===== */
function resetAll(){
  chosenGenre=null; chosenDecade=null; lineupFilms=[]; shuffledFilms=[];
  genreReel.build(); decadeReel.build(); filmReel.build();

  filmPoster.style.backgroundImage = "";
  filmTitle.textContent = "";
  filmMeta.textContent = "";

  btnGenre.textContent="Spin";
  btnDecade.textContent="Spin";
  btnFilm.textContent="Spin";
  btnGenre.disabled=false; btnDecade.disabled=true; btnFilm.disabled=true;

  for (let i=0;i<3;i++){
    const slot=lineupEl.querySelector('.slot[data-slot="'+i+'"]');
    slot.querySelector(".head .label").textContent="Slot "+(i+1);
    slot.querySelector(".head span:last-child").textContent="Empty";
    const p=slot.querySelector(".poster");
    p.classList.add("blank");
    p.style.backgroundImage = "";
    p.classList.remove("bigChoice");
    p.innerHTML = "";
    slot.querySelector(".title").textContent="";
  }

  shuffleCaption.style.display="none";
}
resetBtn.addEventListener("click", resetAll);
