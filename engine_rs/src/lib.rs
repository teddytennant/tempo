//! Native determinized MCTS over the cg engine's C ABI (libcg.so).
//! The whole hot loop is Rust: FFI search_begin/step, targeted JSON parse, UCB tree, lethal rollout.
//! Exposes `init(lib_path)` and `choose(obs_json, deck, opp_model, budget_s, iters, c)`.

use libloading::{Library, Symbol};
use once_cell::sync::OnceCell;
use pyo3::prelude::*;
use rand::rngs::SmallRng;
use rand::{Rng, SeedableRng};
use serde::Deserialize;
use std::collections::HashMap;
use std::ffi::CStr;
use std::os::raw::{c_char, c_int, c_void};
use std::sync::Mutex;
use std::time::Instant;

mod net;

type FnVoid = unsafe extern "C" fn();
type FnAgentStart = unsafe extern "C" fn() -> *mut c_void;
type FnCharP = unsafe extern "C" fn() -> *const c_char;
type FnSearchBegin = unsafe extern "C" fn(
    *mut c_void, *const c_char, c_int,
    *const c_int, *const c_int, *const c_int, *const c_int, *const c_int, *const c_int, c_int,
) -> *const c_char;
type FnSearchStep = unsafe extern "C" fn(*mut c_void, i64, *const c_int, c_int) -> *const c_char;
type FnSearchEnd = unsafe extern "C" fn(*mut c_void);

struct Engine {
    _lib: Library,
    agent_ptr: *mut c_void,
    sb: FnSearchBegin,
    ss: FnSearchStep,
    se: FnSearchEnd,
    atk_dmg: HashMap<i64, i64>,
    basics: std::collections::HashSet<i64>,
    cards: net::Cards,
}
unsafe impl Send for Engine {}

static NET: OnceCell<net::Net> = OnceCell::new();
static NET2: OnceCell<net::Net> = OnceCell::new();

static ENGINE: OnceCell<Mutex<Engine>> = OnceCell::new();
static LAST_SIMS: std::sync::atomic::AtomicU32 = std::sync::atomic::AtomicU32::new(0);

// ── JSON (only the fields MCTS needs) ────────────────────────────────────────
#[derive(Deserialize)]
struct ApiResult { state: Option<SState>, error: i64 }
#[derive(Deserialize)]
struct SState { observation: Obs, #[serde(rename = "searchId")] search_id: i64 }
#[derive(Deserialize, Default)]
struct Obs {
    select: Option<Sel>,
    current: Option<Cur>,
    #[serde(rename = "search_begin_input")] sbi: Option<String>,
}
#[derive(Deserialize)]
struct Sel {
    context: i64,
    #[serde(rename = "minCount")] min: i64,
    #[serde(rename = "maxCount")] max: i64,
    option: Vec<Opt>,
}
#[derive(Deserialize)]
struct Opt {
    #[serde(rename = "type")] t: i64,
    #[serde(rename = "attackId")] attack_id: Option<i64>,
}
#[derive(Deserialize)]
struct Cur {
    #[serde(rename = "yourIndex")] yi: i64,
    result: i64,
    players: Vec<Player>,
}
#[derive(Deserialize)]
struct Player {
    #[serde(default)] active: Vec<Option<Pokemon>>,
    #[serde(rename = "deckCount", default)] deck_count: i64,
    #[serde(default)] prize: Vec<serde_json::Value>,
    #[serde(rename = "handCount", default)] hand_count: i64,
}
#[derive(Deserialize)]
struct Pokemon { id: i64, hp: i64 }

#[derive(Deserialize)]
struct AtkRow { #[serde(rename = "attackId")] id: i64, #[serde(default)] damage: i64 }
#[derive(Deserialize)]
struct CardRow {
    #[serde(rename = "cardId")] id: i64,
    #[serde(rename = "cardType", default)] card_type: i64,
    #[serde(default)] basic: bool,
}

fn cstr(p: *const c_char) -> String {
    if p.is_null() { return String::new(); }
    unsafe { CStr::from_ptr(p).to_string_lossy().into_owned() }
}

// ── FFI wrappers ─────────────────────────────────────────────────────────────
fn do_begin(e: &Engine, sbi: &str, d: &Det) -> Option<(i64, Obs)> {
    let cs = std::ffi::CString::new(sbi).ok()?;
    let json = unsafe {
        cstr((e.sb)(
            e.agent_ptr, cs.as_ptr(), sbi.len() as c_int,
            d.your_deck.as_ptr(), d.your_prize.as_ptr(), d.opp_deck.as_ptr(),
            d.opp_prize.as_ptr(), d.opp_hand.as_ptr(), d.opp_active.as_ptr(),
            0,
        ))
    };
    parse_result(&json)
}
fn do_step(e: &Engine, sid: i64, sel: &[i32]) -> Option<(i64, Obs)> {
    let json = unsafe { cstr((e.ss)(e.agent_ptr, sid, sel.as_ptr(), sel.len() as c_int)) };
    parse_result(&json)
}
fn parse_result(json: &str) -> Option<(i64, Obs)> {
    let r: ApiResult = serde_json::from_str(json).ok()?;
    if r.error != 0 { return None; }
    let s = r.state?;
    Some((s.search_id, s.observation))
}

// Full-observation variants (for net-guided PUCT: need the whole board to featurize).
#[derive(Deserialize)]
struct FApiResult { state: Option<FSW>, error: i64 }
#[derive(Deserialize)]
struct FSW { observation: net::FObs, #[serde(rename = "searchId")] search_id: i64 }
fn parse_full(json: &str) -> Option<(i64, net::FObs)> {
    let r: FApiResult = serde_json::from_str(json).ok()?;
    if r.error != 0 { return None; }
    let s = r.state?;
    Some((s.search_id, s.observation))
}
fn do_begin_f(e: &Engine, sbi: &str, d: &Det) -> Option<(i64, net::FObs)> {
    let cs = std::ffi::CString::new(sbi).ok()?;
    let json = unsafe {
        cstr((e.sb)(e.agent_ptr, cs.as_ptr(), sbi.len() as c_int,
            d.your_deck.as_ptr(), d.your_prize.as_ptr(), d.opp_deck.as_ptr(),
            d.opp_prize.as_ptr(), d.opp_hand.as_ptr(), d.opp_active.as_ptr(), 0))
    };
    parse_full(&json)
}
fn do_step_f(e: &Engine, sid: i64, sel: &[i32]) -> Option<(i64, net::FObs)> {
    let json = unsafe { cstr((e.ss)(e.agent_ptr, sid, sel.as_ptr(), sel.len() as c_int)) };
    parse_full(&json)
}

// ── determinization ──────────────────────────────────────────────────────────
struct Det {
    your_deck: Vec<c_int>, your_prize: Vec<c_int>,
    opp_deck: Vec<c_int>, opp_prize: Vec<c_int>, opp_hand: Vec<c_int>, opp_active: Vec<c_int>,
}
fn take(src: &[i32], n: i64) -> Vec<c_int> {
    let n = n.max(0) as usize;
    if src.is_empty() { return vec![0; n]; }
    (0..n).map(|i| src[i % src.len()] as c_int).collect()
}

// ── MCTS ─────────────────────────────────────────────────────────────────────
struct Node {
    n: u32,
    children: HashMap<i32, usize>,
    visits: HashMap<i32, u32>,
    wins: HashMap<i32, f64>,
    p: HashMap<i32, f32>,
    expanded: bool,
}
impl Node {
    fn new() -> Self {
        Node { n: 0, children: HashMap::new(), visits: HashMap::new(), wins: HashMap::new(),
               p: HashMap::new(), expanded: false }
    }
    fn expand_net(&mut self, nopt: usize, priors: &[f32]) {
        self.expanded = true;
        for i in 0..nopt {
            self.p.insert(i as i32, priors.get(i).copied().unwrap_or(0.0));
            self.visits.entry(i as i32).or_insert(0);
            self.wins.entry(i as i32).or_insert(0.0);
        }
    }
    fn puct_pick(&self, nopt: usize, c: f64) -> i32 {
        let total: u32 = (0..nopt as i32).map(|i| self.visits.get(&i).copied().unwrap_or(0)).sum();
        let sq = ((total + 1) as f64).sqrt();
        let mut best = 0i32; let mut bv = f64::MIN;
        for i in 0..nopt as i32 {
            let v = self.visits.get(&i).copied().unwrap_or(0);
            let q = if v > 0 { self.wins[&i] / v as f64 } else { 0.0 };
            let u = c * (*self.p.get(&i).unwrap_or(&1e-3) as f64) * sq / (1.0 + v as f64);
            if q + u > bv { bv = q + u; best = i; }
        }
        best
    }
}

const MAIN_CTX: i64 = 0;
const ATTACK_OPT: i64 = 13;

fn searchable(cur: &Cur, sel: &Sel) -> bool {
    sel.context == MAIN_CTX && sel.max == 1 && sel.min <= 1 && sel.option.len() > 1 && cur.result == -1
        && (cur.yi == 0 || cur.yi == 1)
}

fn term_value(result: i64, our: i64) -> f64 {
    if result == our { 1.0 } else if result == 2 { 0.5 } else { 0.0 }
}

fn pick_default(e: &Engine, obs: &Obs, rng: &mut SmallRng) -> Vec<i32> {
    let sel = match &obs.select { Some(s) => s, None => return vec![] };
    let n = sel.option.len();
    if n == 0 || sel.max <= 0 { return vec![]; }
    // lethal: take a KO attack if available (single-select)
    if sel.max == 1 {
        if let Some(cur) = &obs.current {
            let opp = 1 - cur.yi as usize;
            let hp = cur.players.get(opp)
                .and_then(|p| p.active.get(0)).and_then(|a| a.as_ref()).map(|a| a.hp).unwrap_or(0);
            if hp > 0 {
                for (i, o) in sel.option.iter().enumerate() {
                    if o.t == ATTACK_OPT {
                        if let Some(aid) = o.attack_id {
                            if *e.atk_dmg.get(&aid).unwrap_or(&0) >= hp { return vec![i as i32]; }
                        }
                    }
                }
            }
        }
    }
    // random selection of max distinct indices
    let k = (sel.max as usize).min(n);
    let mut idx: Vec<i32> = (0..n as i32).collect();
    for i in 0..k { let j = rng.gen_range(i..n); idx.swap(i, j); }
    idx[..k].to_vec()
}

fn rollout(e: &Engine, mut sid: i64, mut obs: Obs, our: i64, rng: &mut SmallRng, cap: u32) -> f64 {
    for _ in 0..cap {
        if let Some(c) = &obs.current { if c.result != -1 { return term_value(c.result, our); } }
        if obs.select.is_none() { return 0.5; }
        let pick = pick_default(e, &obs, rng);
        match do_step(e, sid, &pick) { Some((s, o)) => { sid = s; obs = o; } None => return 0.5 }
    }
    0.5
}

fn ucb_pick(node: &Node, nopt: usize, c: f64) -> i32 {
    let logn = ((node.n + 1) as f64).ln();
    let mut best = 0i32; let mut bv = f64::MIN;
    for i in 0..nopt as i32 {
        let v = *node.visits.get(&i).unwrap_or(&0);
        if v == 0 { return i; }
        let q = node.wins[&i] / v as f64;
        let u = q + c * (logn / v as f64).sqrt();
        if u > bv { bv = u; best = i; }
    }
    best
}

fn iterate(e: &Engine, sbi: &str, det: &Det, our: i64, arena: &mut Vec<Node>, c: f64, rng: &mut SmallRng, cap: u32) {
    let (mut sid, mut obs) = match do_begin(e, sbi, det) { Some(x) => x, None => return };
    let mut path: Vec<(usize, i32)> = Vec::new();
    let mut cur_node = 0usize;
    let value: f64;
    loop {
        if let Some(c0) = &obs.current { if c0.result != -1 { value = term_value(c0.result, our); break; } }
        let is_search = match (&obs.current, &obs.select) {
            (Some(c0), Some(s)) => searchable(c0, s), _ => false,
        };
        if !is_search {
            let pick = pick_default(e, &obs, rng);
            match do_step(e, sid, &pick) { Some((s, o)) => { sid = s; obs = o; continue; } None => { value = 0.5; break; } }
        }
        let nopt = obs.select.as_ref().unwrap().option.len();
        let untried: Vec<i32> = (0..nopt as i32).filter(|i| !arena[cur_node].children.contains_key(i)).collect();
        if !untried.is_empty() {
            let chosen = untried[rng.gen_range(0..untried.len())];
            let child = arena.len(); arena.push(Node::new());
            let nd = &mut arena[cur_node];
            nd.children.insert(chosen, child);
            nd.visits.entry(chosen).or_insert(0);
            nd.wins.entry(chosen).or_insert(0.0);
            path.push((cur_node, chosen));
            match do_step(e, sid, &[chosen]) {
                Some((s, o)) => { value = rollout(e, s, o, our, rng, cap); break; }
                None => { value = 0.5; break; }
            }
        } else {
            let chosen = ucb_pick(&arena[cur_node], nopt, c);
            path.push((cur_node, chosen));
            cur_node = arena[cur_node].children[&chosen];
            match do_step(e, sid, &[chosen]) { Some((s, o)) => { sid = s; obs = o; } None => { value = 0.5; break; } }
        }
    }
    for (ni, oi) in path {
        let nd = &mut arena[ni];
        nd.n += 1;
        *nd.visits.entry(oi).or_insert(0) += 1;
        *nd.wins.entry(oi).or_insert(0.0) += value;
    }
    // free this iteration's engine search states (our stats live in the Rust arena);
    // the next search_begin reuses the memory — prevents the native search pool filling up.
    unsafe { (e.se)(e.agent_ptr); }
}

fn net_default_pick(e: &Engine, obs: &net::FObs, rng: &mut SmallRng) -> Vec<i32> {
    let n = obs.n_opts();
    let k = obs.max_count();
    if n == 0 || k <= 0 { return vec![]; }
    if k == 1 {
        if let Some(i) = obs.lethal_pick(&e.atk_dmg) { return vec![i]; }
    }
    let kk = (k as usize).min(n);
    let mut idx: Vec<i32> = (0..n as i32).collect();
    for i in 0..kk { let j = rng.gen_range(i..n); idx.swap(i, j); }
    idx[..kk].to_vec()
}

// AlphaZero-style: net priors + value-at-leaf (no rollout). Faster than UCB+rollout AND guided.
fn iterate_net(e: &Engine, netw: &net::Net, sbi: &str, det: &Det, our: i64,
               arena: &mut Vec<Node>, c: f64, rng: &mut SmallRng) {
    let (mut sid, mut obs) = match do_begin_f(e, sbi, det) { Some(x) => x, None => return };
    let mut node = 0usize;
    let mut path: Vec<(usize, i32)> = Vec::new();
    let value: f64;
    loop {
        if let Some(r) = obs.terminal() {
            value = if r == our { 1.0 } else if r == 2 { 0.5 } else { 0.0 };
            break;
        }
        if obs.select.is_none() { value = 0.5; break; }
        if !obs.searchable() {
            let pick = net_default_pick(e, &obs, rng);
            match do_step_f(e, sid, &pick) { Some((s, o)) => { sid = s; obs = o; continue; } None => { value = 0.5; break; } }
        }
        let nopt = obs.n_opts();
        if !arena[node].expanded {
            let (g, opts) = net::featurize(&obs, &e.cards);
            let (priors, v) = netw.forward(&g, &opts);
            arena[node].expand_net(nopt, &priors);
            value = if obs.yi() == our { ((v + 1.0) / 2.0) as f64 } else { ((1.0 - v) / 2.0) as f64 };
            break;
        }
        let chosen = arena[node].puct_pick(nopt, c);
        path.push((node, chosen));
        let child = match arena[node].children.get(&chosen) {
            Some(&ci) => ci,
            None => { let ci = arena.len(); arena.push(Node::new()); arena[node].children.insert(chosen, ci); ci }
        };
        node = child;
        match do_step_f(e, sid, &[chosen]) { Some((s, o)) => { sid = s; obs = o; } None => { value = 0.5; break; } }
    }
    for (ni, oi) in path {
        let nd = &mut arena[ni];
        nd.n += 1;
        *nd.visits.entry(oi).or_insert(0) += 1;
        *nd.wins.entry(oi).or_insert(0.0) += value;
    }
    unsafe { (e.se)(e.agent_ptr); }
}

// ── PyO3 ─────────────────────────────────────────────────────────────────────
#[pyfunction]
fn init(lib_path: &str) -> PyResult<bool> {
    if ENGINE.get().is_some() { return Ok(true); }
    let eng = unsafe {
        let lib = Library::new(lib_path).map_err(|e| pyerr(&e.to_string()))?;
        // NB: GameInitialize() is already called by Python's `import cg` (cg/sim.py) on the same
        // shared library — calling it again double-inits a capacity-limited pool and aborts. Skip it.
        let astart: Symbol<FnAgentStart> = lib.get(b"AgentStart\0").map_err(|e| pyerr(&e.to_string()))?;
        let agent_ptr = astart();
        let allatk: Symbol<FnCharP> = lib.get(b"AllAttack\0").map_err(|e| pyerr(&e.to_string()))?;
        let atk_json = cstr(allatk());
        let allcard: Symbol<FnCharP> = lib.get(b"AllCard\0").map_err(|e| pyerr(&e.to_string()))?;
        let card_json = cstr(allcard());
        let atk_dmg = parse_atk(&atk_json);
        let basics = parse_basics(&card_json);
        let cards = net::Cards::build(&card_json, &atk_json);
        let sb: FnSearchBegin = *lib.get(b"SearchBegin\0").map_err(|e| pyerr(&e.to_string()))?;
        let ss: FnSearchStep = *lib.get(b"SearchStep\0").map_err(|e| pyerr(&e.to_string()))?;
        let se: FnSearchEnd = *lib.get(b"SearchEnd\0").map_err(|e| pyerr(&e.to_string()))?;
        Engine { _lib: lib, agent_ptr, sb, ss, se, atk_dmg, basics, cards }
    };
    let _ = ENGINE.set(Mutex::new(eng));
    Ok(true)
}

fn parse_atk(json: &str) -> HashMap<i64, i64> {
    serde_json::from_str::<Vec<AtkRow>>(json).map(|v| v.into_iter().map(|r| (r.id, r.damage)).collect()).unwrap_or_default()
}
fn parse_basics(json: &str) -> std::collections::HashSet<i64> {
    serde_json::from_str::<Vec<CardRow>>(json)
        .map(|v| v.into_iter().filter(|c| c.basic && c.card_type == 0).map(|c| c.id).collect())
        .unwrap_or_default()
}
fn pyerr(m: &str) -> PyErr { pyo3::exceptions::PyRuntimeError::new_err(m.to_string()) }

fn do_root(obs_json: &str, deck: Vec<i32>, opp_model: Vec<i32>, budget_s: f64, max_iters: u32, c: f64, seed: u64, use_net: bool, slot: u32) -> PyResult<(Vec<i32>, Vec<f32>)> {
    let m = ENGINE.get().ok_or_else(|| pyerr("engine not init"))?;
    let e = m.lock().map_err(|_| pyerr("lock"))?;
    let obs: Obs = serde_json::from_str(obs_json).map_err(|e| pyerr(&e.to_string()))?;
    let cur = obs.current.as_ref().ok_or_else(|| pyerr("no current"))?;
    let sel = obs.select.as_ref().ok_or_else(|| pyerr("no select"))?;
    if !searchable(cur, sel) { return Ok(((0..sel.min.max(0) as i32).collect(), vec![])); }
    let sbi = obs.sbi.clone().ok_or_else(|| pyerr("no sbi"))?;
    let our = cur.yi;
    let me = &cur.players[our as usize];
    let op = &cur.players[(1 - our) as usize];
    let opp_active = match op.active.get(0) {
        Some(None) | None if op.active.is_empty() => vec![],
        Some(None) => vec![*opp_model.iter().find(|id| e.basics.contains(&(**id as i64))).unwrap_or(&opp_model[0])],
        _ => vec![],
    };
    let det = Det {
        your_deck: take(&deck, me.deck_count), your_prize: take(&deck, me.prize.len() as i64),
        opp_deck: take(&opp_model, op.deck_count), opp_prize: take(&opp_model, op.prize.len() as i64),
        opp_hand: take(&opp_model, op.hand_count), opp_active,
    };
    let nopt = sel.option.len();
    let mut arena = vec![Node::new()];
    let mut rng = SmallRng::seed_from_u64(seed ^ (cur.yi as u64).wrapping_mul(0x9E3779B97F4A7C15));
    let netw = if use_net { if slot == 1 { NET2.get() } else { NET.get() } } else { None };
    let deadline = Instant::now();
    let mut done = 0u32;
    while done < max_iters && deadline.elapsed().as_secs_f64() < budget_s {
        match netw {
            Some(nw) => iterate_net(&e, nw, &sbi, &det, our, &mut arena, c, &mut rng),
            None => iterate(&e, &sbi, &det, our, &mut arena, c, &mut rng, 200),
        }
        done += 1;
    }
    unsafe { (e.se)(e.agent_ptr); }
    LAST_SIMS.store(done, std::sync::atomic::Ordering::Relaxed);
    // best root option by visits
    let root = &arena[0];
    let mut best = 0i32; let mut bv = -1i64;
    for i in 0..nopt as i32 {
        let v = *root.visits.get(&i).unwrap_or(&0) as i64;
        if v > bv { bv = v; best = i; }
    }
    let total: u32 = (0..nopt as i32).map(|i| *root.visits.get(&i).unwrap_or(&0)).sum();
    let policy: Vec<f32> = if total > 0 {
        (0..nopt as i32).map(|i| *root.visits.get(&i).unwrap_or(&0) as f32 / total as f32).collect()
    } else { vec![1.0 / nopt as f32; nopt] };
    Ok((vec![best], policy))
}

#[pyfunction]
#[pyo3(signature = (obs_json, deck, opp_model, budget_s=8.0, max_iters=100000, c=1.4, seed=0, use_net=true, slot=0))]
fn choose(obs_json: &str, deck: Vec<i32>, opp_model: Vec<i32>, budget_s: f64, max_iters: u32, c: f64, seed: u64, use_net: bool, slot: u32) -> PyResult<Vec<i32>> {
    do_root(obs_json, deck, opp_model, budget_s, max_iters, c, seed, use_net, slot).map(|(s, _)| s)
}

#[pyfunction]
#[pyo3(signature = (obs_json, deck, opp_model, budget_s=8.0, max_iters=100000, c=1.4, seed=0, use_net=true, slot=0))]
fn choose_policy(obs_json: &str, deck: Vec<i32>, opp_model: Vec<i32>, budget_s: f64, max_iters: u32, c: f64, seed: u64, use_net: bool, slot: u32) -> PyResult<(Vec<i32>, Vec<f32>)> {
    do_root(obs_json, deck, opp_model, budget_s, max_iters, c, seed, use_net, slot)
}

#[pyfunction]
fn init_net2(npz_path: &str) -> PyResult<bool> {
    match net::Net::load(npz_path) { Some(n) => { let _ = NET2.set(n); Ok(true) } None => Ok(false) }
}

#[pyfunction]
fn last_sims() -> u32 { LAST_SIMS.load(std::sync::atomic::Ordering::Relaxed) }

#[pyfunction]
fn init_net(npz_path: &str) -> PyResult<bool> {
    match net::Net::load(npz_path) {
        Some(n) => { let _ = NET.set(n); Ok(true) }
        None => Ok(false),
    }
}

#[pyfunction]
fn featurize_debug(obs_json: &str) -> PyResult<(Vec<f32>, Vec<Vec<f32>>)> {
    let m = ENGINE.get().ok_or_else(|| pyerr("engine not init"))?;
    let e = m.lock().map_err(|_| pyerr("lock"))?;
    let obs: net::FObs = serde_json::from_str(obs_json).map_err(|e| pyerr(&e.to_string()))?;
    if obs.current.is_none() || obs.select.is_none() { return Err(pyerr("no current/select")); }
    Ok(net::featurize(&obs, &e.cards))
}

#[pyfunction]
fn policy_value_debug(obs_json: &str) -> PyResult<(Vec<f32>, f32)> {
    let m = ENGINE.get().ok_or_else(|| pyerr("engine not init"))?;
    let e = m.lock().map_err(|_| pyerr("lock"))?;
    let netw = NET.get().ok_or_else(|| pyerr("net not init"))?;
    let obs: net::FObs = serde_json::from_str(obs_json).map_err(|e| pyerr(&e.to_string()))?;
    if obs.current.is_none() || obs.select.is_none() { return Err(pyerr("no")); }
    let (g, opts) = net::featurize(&obs, &e.cards);
    Ok(netw.forward(&g, &opts))
}

#[pymodule]
fn engine_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(init, m)?)?;
    m.add_function(wrap_pyfunction!(choose, m)?)?;
    m.add_function(wrap_pyfunction!(choose_policy, m)?)?;
    m.add_function(wrap_pyfunction!(last_sims, m)?)?;
    m.add_function(wrap_pyfunction!(init_net, m)?)?;
    m.add_function(wrap_pyfunction!(init_net2, m)?)?;
    m.add_function(wrap_pyfunction!(featurize_debug, m)?)?;
    m.add_function(wrap_pyfunction!(policy_value_debug, m)?)?;
    Ok(())
}
