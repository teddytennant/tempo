//! Rust port of net/features.py + net/model.py — featurize an observation and run the policy/value
//! net, so the net guides MCTS at full Rust speed. Must match the Python featurizer exactly.

use ndarray::{Array1, Array2};
use ndarray_npy::NpzReader;
use serde::Deserialize;
use std::collections::HashMap;
use std::fs::File;

pub const CARDF: usize = 17;
pub const GLOBAL_DIM: usize = 74;
pub const OPT_DIM: usize = 68;
const N_OPTYPE: usize = 17;
const N_AREA: usize = 13;
const CTX_LIST: [i64; 16] = [0, 7, 21, 8, 4, 1, 3, 22, 30, 41, 2, 5, 13, 37, 35, 11];

// ── card static features ─────────────────────────────────────────────────────
#[derive(Deserialize)]
struct CardRow {
    #[serde(rename = "cardId")] id: i64,
    #[serde(rename = "cardType", default)] card_type: i64,
    #[serde(default)] hp: i64,
    #[serde(default)] ex: bool,
    #[serde(rename = "megaEx", default)] mega_ex: bool,
    #[serde(default)] basic: bool,
    #[serde(default)] stage1: bool,
    #[serde(default)] stage2: bool,
    #[serde(rename = "energyType", default)] energy_type: i64,
    #[serde(rename = "retreatCost", default)] retreat: i64,
    #[serde(default)] attacks: Vec<i64>,
}
#[derive(Deserialize)]
struct AtkRow2 { #[serde(rename = "attackId")] id: i64, #[serde(default)] damage: i64, #[serde(default)] energies: Vec<i64> }

pub struct Cards {
    feat: HashMap<i64, [f32; CARDF]>,
    atk: HashMap<i64, (f32, f32)>,   // attackId -> (damage/300, cost_len/5)
}
impl Cards {
    pub fn build(allcard: &str, allattack: &str) -> Cards {
        let atks: Vec<AtkRow2> = serde_json::from_str(allattack).unwrap_or_default();
        let mut dmg: HashMap<i64, (i64, usize)> = HashMap::new();
        let mut atk: HashMap<i64, (f32, f32)> = HashMap::new();
        for a in &atks {
            dmg.insert(a.id, (a.damage, a.energies.len()));
            atk.insert(a.id, (a.damage as f32 / 300.0, a.energies.len() as f32 / 5.0));
        }
        let cards: Vec<CardRow> = serde_json::from_str(allcard).unwrap_or_default();
        let mut feat = HashMap::new();
        for c in &cards {
            let mut v = [0f32; CARDF];
            if (0..7).contains(&c.card_type) { v[c.card_type as usize] = 1.0; }
            v[7] = c.hp as f32 / 300.0;
            v[8] = c.ex as i32 as f32;
            v[9] = c.mega_ex as i32 as f32;
            v[10] = c.basic as i32 as f32;
            v[11] = c.stage1 as i32 as f32;
            v[12] = c.stage2 as i32 as f32;
            v[13] = c.energy_type as f32 / 11.0;
            v[14] = c.retreat as f32 / 4.0;
            let maxd = c.attacks.iter().filter_map(|a| dmg.get(a)).map(|x| x.0).max().unwrap_or(0);
            let maxc = c.attacks.iter().filter_map(|a| dmg.get(a)).map(|x| x.1).max().unwrap_or(0);
            v[15] = maxd as f32 / 300.0;
            v[16] = maxc as f32 / 5.0;
            feat.insert(c.id, v);
        }
        Cards { feat, atk }
    }
    fn cv(&self, id: i64) -> [f32; CARDF] { *self.feat.get(&id).unwrap_or(&[0f32; CARDF]) }
}

// ── observation parse (fuller than the MCTS one) ─────────────────────────────
#[derive(Deserialize, Default)]
pub struct FObs {
    pub select: Option<FSel>,
    pub current: Option<FState>,
    #[serde(rename = "search_begin_input")] pub sbi: Option<String>,
}
#[derive(Deserialize)]
pub struct FState {
    pub turn: i64,
    #[serde(rename = "yourIndex")] pub yi: i64,
    pub result: i64,
    #[serde(rename = "supporterPlayed", default)] sup: bool,
    #[serde(rename = "stadiumPlayed", default)] stad: bool,
    #[serde(rename = "energyAttached", default)] ener: bool,
    #[serde(default)] retreated: bool,
    #[serde(default)] stadium: Vec<IdC>,
    pub players: Vec<FPlayer>,
}
#[derive(Deserialize)]
pub struct FPlayer {
    #[serde(default)] active: Vec<Option<Poke>>,
    #[serde(default)] bench: Vec<Poke>,
    #[serde(default)] discard: Vec<IdC>,
    #[serde(default)] prize: Vec<serde_json::Value>,
    #[serde(rename = "deckCount", default)] deck_count: i64,
    #[serde(rename = "handCount", default)] hand_count: i64,
    #[serde(default)] hand: Option<Vec<IdC>>,
}
#[derive(Deserialize)]
struct Poke { id: i64, #[serde(default)] hp: i64, #[serde(rename = "maxHp", default)] max_hp: i64, #[serde(default)] energies: Vec<i64> }
#[derive(Deserialize)]
struct IdC { id: i64 }
#[derive(Deserialize)]
pub struct FSel {
    pub context: i64,
    #[serde(rename = "minCount")] pub min: i64,
    #[serde(rename = "maxCount")] pub max: i64,
    pub option: Vec<FOpt>,
    #[serde(default)] deck: Option<Vec<IdC>>,
}
#[derive(Deserialize)]
pub struct FOpt {
    #[serde(rename = "type")] pub t: i64,
    pub area: Option<i64>,
    pub index: Option<i64>,
    #[serde(rename = "inPlayArea")] ipa: Option<i64>,
    #[serde(rename = "inPlayIndex")] ipi: Option<i64>,
    #[serde(rename = "attackId")] attack_id: Option<i64>,
    #[serde(rename = "playerIndex")] pi: Option<i64>,
}

impl FObs {
    pub fn terminal(&self) -> Option<i64> {
        self.current.as_ref().and_then(|c| if c.result != -1 { Some(c.result) } else { None })
    }
    pub fn yi(&self) -> i64 { self.current.as_ref().map(|c| c.yi).unwrap_or(0) }
    pub fn n_opts(&self) -> usize { self.select.as_ref().map(|s| s.option.len()).unwrap_or(0) }
    pub fn max_count(&self) -> i64 { self.select.as_ref().map(|s| s.max).unwrap_or(0) }
    pub fn searchable(&self) -> bool {
        match (&self.current, &self.select) {
            (Some(c), Some(s)) => s.context == 0 && s.max == 1 && s.min <= 1
                && s.option.len() > 1 && c.result == -1 && (c.yi == 0 || c.yi == 1),
            _ => false,
        }
    }
    /// Option index of a KO attack if the active opponent can be lethaled (single-select), else None.
    pub fn lethal_pick(&self, atk: &HashMap<i64, i64>) -> Option<i32> {
        let st = self.current.as_ref()?;
        let sel = self.select.as_ref()?;
        if sel.max != 1 { return None; }
        let opp = 1 - st.yi as usize;
        let hp = st.players.get(opp)?.active.get(0)?.as_ref()?.hp;
        if hp <= 0 { return None; }
        for (i, o) in sel.option.iter().enumerate() {
            if o.t == 13 {
                if let Some(aid) = o.attack_id {
                    if *atk.get(&aid).unwrap_or(&0) >= hp { return Some(i as i32); }
                }
            }
        }
        None
    }
}

fn get_card(st: &FState, sel: &FSel, area: Option<i64>, index: Option<i64>, pi: usize) -> Option<i64> {
    let (a, i) = (area?, index?);
    if i < 0 { return None; }
    let i = i as usize;
    let p = st.players.get(pi)?;
    match a {
        2 => p.hand.as_ref()?.get(i).map(|c| c.id),
        4 => p.active.get(i)?.as_ref().map(|x| x.id),
        5 => p.bench.get(i).map(|x| x.id),
        3 => p.discard.get(i).map(|c| c.id),
        1 => sel.deck.as_ref()?.get(i).map(|c| c.id),
        7 => st.stadium.get(i).map(|c| c.id),
        _ => None,
    }
}

fn active_block(p: &FPlayer, cards: &Cards, out: &mut [f32]) {
    if let Some(Some(a)) = p.active.get(0) {
        out[0] = 1.0;
        out[1..1 + CARDF].copy_from_slice(&cards.cv(a.id));
        out[1 + CARDF] = a.hp as f32 / (a.max_hp.max(1) as f32);
        out[2 + CARDF] = a.energies.len() as f32 / 5.0;
    }
}

pub fn featurize(obs: &FObs, cards: &Cards) -> (Vec<f32>, Vec<Vec<f32>>) {
    let st = obs.current.as_ref().unwrap();
    let sel = obs.select.as_ref().unwrap();
    let yi = st.yi as usize;
    let me = &st.players[yi];
    let op = &st.players[1 - yi];
    let mut g = vec![0f32; GLOBAL_DIM];
    let mut k = 0;
    g[k] = st.turn as f32 / 30.0; k += 1;
    g[k] = yi as f32; k += 1;
    g[k] = sel.min as f32 / 5.0; k += 1;
    g[k] = sel.max as f32 / 5.0; k += 1;
    let ci = CTX_LIST.iter().position(|&c| c == sel.context).unwrap_or(CTX_LIST.len());
    g[k + ci] = 1.0; k += CTX_LIST.len() + 1;
    g[k] = st.sup as i32 as f32; g[k + 1] = st.stad as i32 as f32;
    g[k + 2] = st.ener as i32 as f32; g[k + 3] = st.retreated as i32 as f32; k += 4;
    let bench = |p: &FPlayer| p.bench.len() as f32 / 5.0;  // bench elems are non-null pokemon
    g[k] = me.prize.len() as f32 / 6.0; g[k + 1] = me.deck_count as f32 / 60.0;
    g[k + 2] = me.hand_count as f32 / 15.0; g[k + 3] = bench(me); k += 4;
    g[k] = op.prize.len() as f32 / 6.0; g[k + 1] = op.deck_count as f32 / 60.0;
    g[k + 2] = op.hand_count as f32 / 15.0; g[k + 3] = bench(op); k += 4;
    active_block(me, cards, &mut g[k..k + 1 + CARDF + 2]); k += 1 + CARDF + 2;
    active_block(op, cards, &mut g[k..k + 1 + CARDF + 2]); k += 1 + CARDF + 2;
    g[k] = if st.stadium.is_empty() { 0.0 } else { 1.0 };

    let mut opts = Vec::with_capacity(sel.option.len());
    for o in &sel.option {
        let mut v = vec![0f32; OPT_DIM];
        let mut j = 0;
        if (0..N_OPTYPE as i64).contains(&o.t) { v[o.t as usize] = 1.0; }
        j += N_OPTYPE;
        if let Some(a) = o.area { if (0..N_AREA as i64).contains(&a) { v[j + a as usize] = 1.0; } }
        j += N_AREA;
        let pi = o.pi.unwrap_or(yi as i64);
        if let Some(id) = get_card(st, sel, o.area, o.index, pi.max(0) as usize) {
            v[j..j + CARDF].copy_from_slice(&cards.cv(id));
        }
        j += CARDF;
        v[j] = if o.pi.map_or(false, |p| p != yi as i64) { 1.0 } else { 0.0 };
        j += 1;
        if let Some(aid) = o.attack_id {
            if let Some(&(d, c)) = cards.atk.get(&aid) { v[j] = d; v[j + 1] = c; }
        }
        j += 2;
        if let Some(id) = get_card(st, sel, o.ipa, o.ipi, yi) {
            v[j..j + CARDF].copy_from_slice(&cards.cv(id));
        }
        opts.push(v);
    }
    (g, opts)
}

// ── net ──────────────────────────────────────────────────────────────────────
pub struct Net {
    g0w: Array2<f32>, g0b: Array1<f32>, g2w: Array2<f32>, g2b: Array1<f32>,
    o0w: Array2<f32>, o0b: Array1<f32>,
    s0w: Array2<f32>, s0b: Array1<f32>, s2w: Array2<f32>, s2b: Array1<f32>,
    v0w: Array2<f32>, v0b: Array1<f32>, v2w: Array2<f32>, v2b: Array1<f32>,
}
fn relu(mut a: Array1<f32>) -> Array1<f32> { a.mapv_inplace(|x| x.max(0.0)); a }

impl Net {
    pub fn load(path: &str) -> Option<Net> {
        let mut z = NpzReader::new(File::open(path).ok()?).ok()?;
        let w = |z: &mut NpzReader<File>, n: &str| -> Option<Array2<f32>> { z.by_name(&format!("{n}.npy")).ok() };
        let b = |z: &mut NpzReader<File>, n: &str| -> Option<Array1<f32>> { z.by_name(&format!("{n}.npy")).ok() };
        Some(Net {
            g0w: w(&mut z, "g.0.weight")?, g0b: b(&mut z, "g.0.bias")?,
            g2w: w(&mut z, "g.2.weight")?, g2b: b(&mut z, "g.2.bias")?,
            o0w: w(&mut z, "o.0.weight")?, o0b: b(&mut z, "o.0.bias")?,
            s0w: w(&mut z, "score.0.weight")?, s0b: b(&mut z, "score.0.bias")?,
            s2w: w(&mut z, "score.2.weight")?, s2b: b(&mut z, "score.2.bias")?,
            v0w: w(&mut z, "val.0.weight")?, v0b: b(&mut z, "val.0.bias")?,
            v2w: w(&mut z, "val.2.weight")?, v2b: b(&mut z, "val.2.bias")?,
        })
    }

    pub fn forward(&self, g: &[f32], opts: &[Vec<f32>]) -> (Vec<f32>, f32) {
        let gx = Array1::from(g.to_vec());
        let gg = relu(self.g0w.dot(&gx) + &self.g0b);
        let gg = relu(self.g2w.dot(&gg) + &self.g2b);          // (128)
        let mut scores = Vec::with_capacity(opts.len());
        for o in opts {
            let ox = Array1::from(o.clone());
            let oo = relu(self.o0w.dot(&ox) + &self.o0b);       // (128)
            let cat = ndarray::concatenate![ndarray::Axis(0), gg, oo]; // (256)
            let s = relu(self.s0w.dot(&cat) + &self.s0b);
            scores.push((self.s2w.dot(&s) + &self.s2b)[0]);
        }
        let m = scores.iter().cloned().fold(f32::MIN, f32::max);
        let exps: Vec<f32> = scores.iter().map(|s| (s - m).exp()).collect();
        let sum: f32 = exps.iter().sum();
        let priors = exps.iter().map(|e| e / sum).collect();
        let vv = relu(self.v0w.dot(&gg) + &self.v0b);
        let value = (self.v2w.dot(&vv) + &self.v2b)[0].tanh();
        (priors, value)
    }
}
