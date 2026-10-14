// Builds the review deck (.pptx), structured on the eight report chapters.
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const SKILL = "C:/Users/ASUS/.claude/skills/synced/a91a50eb-c89c-4299-a728-6b5c0014c991_9fe1857a-4361-4e5e-8205-259efda2333d/pptx";
const { applyTheme } = require(path.join(SKILL, "scripts", "apply_theme.js"));

const ROOT = path.join(__dirname, "..");
const FIG = path.join(ROOT, "figures");
const N = JSON.parse(fs.readFileSync(path.join(ROOT, "numbers.json"), "utf8"));

const THEME = {
  name: "Flow IDS Review",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1A1A1A", lt1: "FFFFFF", dk2: "14213D", lt2: "F3F5F9",
    accent1: "2A78D6", accent2: "EB6834", accent3: "1BAF7A", accent4: "EDA100",
    accent5: "4A3AA7", accent6: "E34948", hlink: "2A78D6", folHlink: "4A3AA7",
  },
};
const HEX = { navy: "14213D", ink: "1A1A1A", ink2: "52514E", muted: "898781", grid: "E1E0D9", light: "F3F5F9", blue: "2A78D6", orange: "EB6834", aqua: "1BAF7A", white: "FFFFFF" };

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Behavioral Classification of Encrypted Malicious Network Traffic Using Flow-Based Metadata";
pres.author = "Gaurav Bakshi, Anshveer Singh, Dev Acharya Menon";
const C = pres.SchemeColor;
const W = 13.333, MX = 0.6;

// ------------------------------------------------------------------ layouts
pres.defineSlideMaster({
  title: "TITLE", background: { color: HEX.navy },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 2.0, w: W - 2 * MX, h: 1.9, fontFace: "Cambria", fontSize: 40, bold: true, color: C.background1, valign: "bottom", align: "left" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: MX, y: 4.1, w: W - 2 * MX, h: 2.6, fontFace: "Calibri", fontSize: 18, color: C.background2, valign: "top" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT", background: { color: HEX.white },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 0.72, w: W - 2 * MX, h: 0.85, fontFace: "Cambria", fontSize: 32, bold: true, color: C.text2, valign: "top", margin: 0, align: "left" }, text: "" } },
    { text: { text: "Behavioral Classification of Encrypted Malicious Network Traffic", options: { x: MX, y: 7.05, w: 8, h: 0.3, fontFace: "Calibri", fontSize: 10, color: HEX.muted, margin: 0 } } },
  ],
  slideNumber: { x: W - MX - 0.6, y: 7.05, w: 0.6, h: 0.3, fontFace: "Calibri", fontSize: 10, color: HEX.muted, align: "right" },
});

function tag(slide, num, label) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: MX, y: 0.32, w: 0.55, h: 0.3, rectRadius: 0.08, fill: { color: C.accent2 }, line: { color: C.accent2 }, objectName: "chapter number" });
  slide.addText(String(num).padStart(2, "0"), { x: MX, y: 0.32, w: 0.55, h: 0.3, align: "center", valign: "middle", fontFace: "Calibri", fontSize: 12, bold: true, color: C.background1, margin: 0, isTextBox: true, objectName: "chapter number text" });
  slide.addText(label.toUpperCase(), { x: MX + 0.7, y: 0.32, w: 8, h: 0.3, valign: "middle", fontFace: "Calibri", fontSize: 12, bold: true, color: C.accent2, charSpacing: 2, margin: 0, isTextBox: true, objectName: "chapter label" });
}
let curSection = "";
function content(chapterNo, chapter, title, notes) {
  if (chapter !== curSection) { pres.addSection({ title: `${chapterNo}. ${chapter}` }); curSection = chapter; }
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: `${chapterNo}. ${chapter}` });
  tag(s, chapterNo, chapter);
  s.addText(title, { placeholder: "title" });
  if (notes) s.addNotes(notes);
  return s;
}
const bullets = (items, opts = {}) => items.map((t, i) => ({ text: t, options: { bullet: { indent: 18 }, breakLine: i < items.length - 1, paraSpaceAfter: opts.gap ?? 8 } }));
function textBox(slide, items, x, y, w, h, opts = {}) {
  slide.addText(bullets(items, opts), { x, y, w, h, fontFace: "Calibri", fontSize: opts.size || 16, color: C.text1, valign: "top", margin: 0.05, isTextBox: true, objectName: opts.name || "body text" });
}
function card(slide, x, y, w, h, head, body, opts = {}) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: opts.fill || HEX.light }, line: { color: opts.fill || HEX.light }, objectName: `card ${head}` });
  slide.addText(head, { x: x + 0.2, y: y + 0.15, w: w - 0.4, h: 0.45, fontFace: "Cambria", fontSize: opts.headSize || 18, bold: true, color: C.text2, margin: 0, valign: "top", isTextBox: true, objectName: `card head ${head}` });
  slide.addText(body, { x: x + 0.2, y: y + 0.65, w: w - 0.4, h: h - 0.8, fontFace: "Calibri", fontSize: opts.size || 14, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: `card body ${head}` });
}
function stat(slide, x, y, w, value, label, color) {
  slide.addText(value, { x, y, w, h: 0.9, fontFace: "Calibri", fontSize: 44, bold: true, color: color || C.accent1, margin: 0, isTextBox: true, objectName: `stat ${label}` });
  slide.addText(label, { x, y: y + 0.9, w, h: 0.75, fontFace: "Calibri", fontSize: 14, color: HEX.ink2, margin: 0, valign: "top", isTextBox: true, objectName: `stat label ${label}` });
}
function pngSize(file) { const b = fs.readFileSync(file); return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) }; }
function image(slide, name, x, y, maxW, maxH, alt) {
  const f = path.join(FIG, name + ".png");
  const { w, h } = pngSize(f);
  let iw = maxW, ih = maxW * h / w;
  if (ih > maxH) { ih = maxH; iw = maxH * w / h; }
  slide.addImage({ path: f, x: x + (maxW - iw) / 2, y, w: iw, h: ih, altText: alt, objectName: name });
}
function eqImage(slide, name, x, y, maxW, maxH) {
  const f = path.join(FIG, "eq", name + ".png");
  const { w, h } = pngSize(f);
  let ih = maxH, iw = maxH * w / h;
  if (iw > maxW) { iw = maxW; ih = maxW * h / w; }
  slide.addImage({ path: f, x, y, w: iw, h: ih, altText: name.replace("eq_", "equation: "), objectName: name });
  return ih;
}
function eqPanel(slide, items, x, y, w) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 5.05, rectRadius: 0.08, fill: { color: HEX.light }, line: { color: HEX.light }, objectName: "equation panel" });
  let cy = y + 0.2;
  items.forEach(([label, name, maxH]) => {
    slide.addText(label, { x: x + 0.25, y: cy, w: w - 0.5, h: 0.32, fontFace: "Calibri", fontSize: 13, bold: true, color: HEX.ink2, margin: 0, isTextBox: true, objectName: `label ${label}` });
    const ih = eqImage(slide, name, x + 0.25, cy + 0.36, w - 0.5, maxH);
    cy += 0.36 + ih + 0.22;
  });
}
function steps(slide, items, x, y, w, h) {
  slide.addText(items.map((t, i, a) => ({ text: t, options: { bullet: { type: "number" }, breakLine: i < a.length - 1, paraSpaceAfter: 7 } })),
    { x, y, w, h, fontFace: "Calibri", fontSize: 15, color: C.text1, valign: "top", margin: 0.05, isTextBox: true, objectName: "algorithm steps" });
}
function caption(slide, text, x, y, w) {
  slide.addText(text, { x, y, w, h: 0.35, fontFace: "Calibri", fontSize: 11, italic: true, color: HEX.muted, margin: 0, isTextBox: true, objectName: "caption" });
}
const tableOpts = (x, y, w, colW, size = 12) => ({ x, y, w, colW, fontFace: "Calibri", fontSize: size, color: HEX.ink, border: { type: "solid", pt: 0.5, color: "C3C2B7" }, valign: "middle", margin: 0.05, autoPage: false });
const th = (t) => ({ text: t, options: { bold: true, fill: { color: "E8EEF7" }, color: HEX.navy } });
const chartBase = { catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt",
  catAxisLabelColor: HEX.ink2, valAxisLabelColor: HEX.ink2, catAxisLabelFontSize: 11, valAxisLabelFontSize: 11, legendFontSize: 11,
  valGridLine: { color: HEX.grid, size: 0.75 }, catGridLine: { style: "none" }, catAxisLineColor: "C3C2B7", valAxisLineShow: false };

const e2 = N.exp002, e3 = N.exp003, e4 = N.exp004, e7 = N.exp007, e6 = N.exp006, e8 = N.exp008, d17 = N.data_2017;
const f3 = (x) => x.toFixed(3);

// =================================================================== slides
// 1 Title
pres.addSection({ title: "Title" });
let s = pres.addSlide({ masterName: "TITLE", sectionTitle: "Title" });
s.addText("Behavioral Classification of Encrypted Malicious Network Traffic Using Flow-Based Metadata", { placeholder: "title" });
s.addText([
  { text: "A leakage-aware evaluation of flow-based intrusion detection on CICIDS2017 and CSE-CIC-IDS2018", options: { breakLine: true, italic: true } },
  { text: " ", options: { breakLine: true, fontSize: 10 } },
  { text: "Gaurav Bakshi (23BCE0546)   ·   Anshveer Singh (23BCE0703)   ·   Dev Acharya Menon (23BCE0717)", options: { breakLine: true } },
  { text: "Supervisor: Dr Anto S   ·   BCSE410L Cyber Security Project   ·   SCOPE, VIT   ·   October 2026" },
], { placeholder: "body" });
s.addNotes("Final review. The project evaluates how much of the near-perfect performance reported for flow-based intrusion detectors survives stricter evaluation protocols, and what the errors that appear under those protocols consist of.");

// 2 Outline
pres.addSection({ title: "Outline" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Outline" });
s.addText("Outline", { placeholder: "title" });
const chapters = ["Introduction", "Project Description and Goals", "Technical Specification", "Design Approach and Details", "Experimental Setup and Output", "Result Analysis", "Conclusion and Future Works", "References"];
chapters.forEach((c, i) => {
  const col = i < 4 ? 0 : 1, row = i % 4;
  const x = MX + col * 6.2, y = 1.9 + row * 1.15;
  s.addShape(pres.shapes.OVAL, { x, y, w: 0.7, h: 0.7, fill: { color: i % 2 ? C.accent1 : C.text2 }, line: { color: i % 2 ? C.accent1 : C.text2 }, objectName: `outline circle ${i + 1}` });
  s.addText(String(i + 1), { x, y, w: 0.7, h: 0.7, align: "center", valign: "middle", fontFace: "Cambria", fontSize: 20, bold: true, color: C.background1, margin: 0, isTextBox: true, objectName: `outline number ${i + 1}` });
  s.addText(c, { x: x + 0.9, y, w: 5, h: 0.7, valign: "middle", fontFace: "Calibri", fontSize: 20, color: C.text1, margin: 0, isTextBox: true, objectName: `outline item ${i + 1}` });
});

// ---- 1 Introduction
s = content(1, "Introduction", "Flow metadata remains observable under encryption",
  "Background and motivation. Flow statistics survive encryption. Benchmarks report near-perfect scores, but audits found errors and cross-dataset studies report failure. Our earlier phase saw 0.997 F1 in-dataset and 0.002 cross-dataset, which had to be explained.");
textBox(s, [
  "Payload inspection of encrypted sessions requires TLS interception, which breaks end-to-end confidentiality",
  "A flow (addresses, ports, protocol, timeout) is summarised by CICFlowMeter into about 80 statistics: packet lengths, inter-arrival times, flags, directional ratios",
  "Tree ensembles exceed 99% accuracy on CICIDS2017, yet audits document label errors and duplicated records",
  "Open question: does the reported performance survive stricter evaluation, and what do the errors that appear consist of?",
], MX, 1.85, 7.2, 4.8);
card(s, 8.3, 1.85, 4.4, 4.6, "Starting point (Review II)", "", {});
stat(s, 8.55, 2.55, 4.0, "0.997", "Random forest F1 trained and tested on CICIDS2017", HEX.blue);
stat(s, 8.55, 4.3, 4.0, "0.002", "Same model tested on CSE-CIC-IDS2018: was the collapse real or a pipeline error?", HEX.orange);

s = content(1, "Introduction", "Scope of the project", "What is in and out of scope. Mitigations restricted to label-free transformations.");
card(s, MX, 1.85, 5.9, 4.8, "In scope", "• Payload-independent CICFlowMeter features (75–76 statistics)\n• CICIDS2017 in full (2.83 M flows) and its timestamped release\n• CSE-CIC-IDS2018, two days: DoS-Hulk, DoS-SlowHTTPTest, web attacks\n• Binary detection and attack attribution (6 families, 12 types)\n• Random forest and XGBoost\n• Label-free mitigation of dataset shift", { size: 16 });
card(s, 6.85, 1.85, 5.9, 4.8, "Out of scope", "• Packet payloads and TLS handshake fields\n• Raw packet captures and early-flow detection\n• Deep sequence models\n• Adversarial evasion experiments\n• Online deployment\n• Adaptation that uses target-dataset labels", { size: 16 });

// ---- 2 Project description
s = content(2, "Project Description and Goals", "Literature: errors are documented, their effect is not",
  "19 papers reviewed in the report. Key ones on the slide. Each leaves part of the evaluation question open.");
s.addTable([
  [th("Work"), th("Finding"), th("Open point addressed here")],
  ["Sharafaldin et al., 2018", "CICIDS2017 with 80+ CICFlowMeter features", "Random-split evaluation only"],
  ["Engelen 2021; Liu 2022; Lanvin 2023", "Label, capture and flow-construction errors", "Effect of feature-level conflicts on metrics"],
  ["Pekar & Jozsa, 2024", "Random forests robust to data-integrity defects", "Temporal effect not isolated"],
  ["Arp 2022; Pendlebury 2019", "Data snooping and temporal bias inflate security ML", "No flow-level quantification"],
  ["Moczkodan & Ragab, 2026", "Split protocol dominates; leakage-free FAR × 67", "What the errors of a time split consist of"],
  ["Cantone et al., 2024", "2017 → 2018 grouped binary F1 0.26–0.39", "No same-year reference or unit checks"],
], { ...tableOpts(MX, 1.85, W - 2 * MX, [3.4, 4.7, 4.03], 16), rowH: 0.62 });

s = content(2, "Project Description and Goals", "Research gap and problem statement",
  "Five gaps; the problem statement has four parts, all judged against a seed noise floor.");
[["Split errors", "Leakage and chronological ordering not separated; errors of time-aware splits not inspected"], ["Label conflicts", "Identical vectors with different labels not counted"],
 ["Attribution", "Attack type scored on true attacks only, not end to end"], ["Transfer failure", "Reported, not diagnosed or mitigated"],
 ["Noise floor", "Seed variability rarely reported"]].forEach(([h, b], i) => card(s, MX + i * 2.45, 1.85, 2.3, 2.0, h, b, { size: 14, headSize: 15 }));
s.addText("Problem statement", { x: MX, y: 4.15, w: 6, h: 0.4, fontFace: "Cambria", fontSize: 18, bold: true, color: C.text2, margin: 0, isTextBox: true });
textBox(s, [
  "(a) How much does measured performance depend on the protocol: leakage between correlated records or chronological ordering, and what do the extra errors consist of?",
  "(b) How do duplicates and label conflicts change the evaluated population and the metrics?",
  "(c) How much does attribution degrade once detection errors are included?",
  "(d) Why does zero-shot transfer to CSE-CIC-IDS2018 fail, and does label-free normalisation repair it?",
], MX, 4.6, W - 2 * MX, 2.3, { size: 15, gap: 4 });

s = content(2, "Project Description and Goals", "Objectives and project plan",
  "Six SMART objectives; Gantt chart from mid-July to mid-October 2026.");
textBox(s, [
  "O1  Reproduce the baseline exactly; verify 100% row alignment; five split protocols",
  "O2  ≥ 2 seeds per protocol, 5 for the main comparison; audit the chronological-split errors",
  "O3  Count duplicates and conflicts per class; compare four policies",
], MX, 1.75, 6.0, 1.9, { size: 15, gap: 6 });
textBox(s, [
  "O4  Attribution in three scoring views with Wilson intervals",
  "O5  Matched-family transfer with reference, upper bound, reverse, controls",
  "O6  ≤ 6 GB working set per experiment; finish before the final review",
], MX + 6.25, 1.75, 5.9, 1.9, { size: 15, gap: 6 });
image(s, "fig_gantt", MX, 3.75, W - 2 * MX, 3.15, "Gantt chart of the project");

// ---- 3 Technical specification
s = content(3, "Technical Specification", "Requirements", "Functional requirements define the evaluation system; non-functional ones make results reproducible and trustworthy.");
card(s, MX, 1.85, 5.9, 4.85, "Functional", "• Ingest both datasets and the timestamped release\n• Canonicalise labels; align 2018 features to 2017 names\n• Hash vectors; count duplicates and conflicts; apply a policy\n• Generate five split protocols; audit false positives by endpoint and time\n• Train Stage 1 and Stage 2; score three views\n• Seed statistics, Wilson intervals\n• Shift diagnosis and label-free mitigation\n• Gates: feature order, label encoding, exact reproduction", { size: 15 });
card(s, 6.85, 1.85, 5.9, 4.85, "Non-functional", "• Reproducibility: configuration, seeds, code hash and data fingerprints recorded per run\n• Memory: ≤ 6 GB working set; loader peak cut from 8.63 GB to 4.13 GB with bit-identical output\n• Integrity: SHA-256 checks of code, data and baseline after every experiment\n• Unattended execution: sequential runs, memory guard, incremental saving\n• Privacy: no payload; addresses and ports are never features, only used to audit errors", { size: 15 });

s = content(3, "Technical Specification", "Feasibility and system specification", "Public data, open-source stack, CPU-only laptop; total compute a few hours.");
card(s, MX, 1.85, 3.85, 2.0, "Technical", "Public datasets (1.8 GB); a random forest trains on 1.7 M flows in 2–3 min on 8 cores; no GPU needed", { size: 15 });
card(s, MX + 4.05, 1.85, 3.85, 2.0, "Economic", "No licence cost; a few CPU-hours on an existing laptop; realistic FPR estimates reduce triage workload", { size: 15 });
card(s, MX + 8.1, 1.85, 3.95, 2.0, "Social", "Metadata only, no decryption; no new attack capability; improves comparability of published results", { size: 15 });
s.addTable([
  [th("Hardware"), th(""), th("Software"), th("")],
  ["Processor", "AMD Ryzen 7 7735HS, 8C/16T", "OS", "Windows 11 Home (26200)"],
  ["Memory", "16 GB (peak use 4.1–5.7 GB)", "Language", "Python 3.13.1"],
  ["GPU", "RTX 4050 Laptop (not required)", "Libraries", "pandas 2.2.3, NumPy 2.2.6, scikit-learn 1.6.1"],
  ["Storage", "SSD, ~1.8 GB data", "", "XGBoost 3.4.1, SciPy 1.15.3, Matplotlib 3.10.3"],
], { ...tableOpts(MX, 4.15, W - 2 * MX, [1.6, 3.9, 1.6, 5.03], 15), rowH: 0.5 });

// ---- 4 Design
s = content(4, "Design Approach and Details", "System architecture", "Six layers; each consumes only the layers above. Integrity audit and evaluation protocols are the components varied in the experiments.");
image(s, "fig_architecture", MX, 1.75, W - 2 * MX, 5.2, "Layered system architecture");

s = content(4, "Design Approach and Details", "Algorithm 1: leakage-aware hierarchical evaluation",
  "Hash every vector, build the conflict set, resolve with a policy, split per label, train two stages, score three views over seeds. The feature-order assertion rules out a column permutation that would mimic dataset shift.");
steps(s, [
  "Remove records with missing or infinite values",
  "Hash every feature vector; build duplicate groups and the conflict set C",
  "Resolve duplicates with a policy: drop-conflicts, keep-first, majority or none",
  "For each seed, split 80/20 per label: random, Flow-ID groups, time blocks, per-class chronological",
  "Assert identical feature order at training and prediction",
  "Train Stage 1 (benign vs malicious) and Stage 2 (attack family / type)",
  "Score detection, and attribution on true attacks, on flagged flows and end to end",
  "Report mean, SD and range over seeds; Wilson intervals per class",
], MX, 1.8, 6.0, 5.0);
eqPanel(s, [["Conflict set", "eq_conflict", 0.36], ["Chronological split and purge, per label", "eq_forward", 0.36], ["Time blocks", "eq_block", 0.55],
  ["Hierarchical prediction", "eq_hier", 0.36], ["Material difference (noise floor 0.013)", "eq_noise", 0.45]], 6.85, 1.8, 5.88);

s = content(4, "Design Approach and Details", "Algorithm 2: shift diagnosis and label-free mitigation",
  "Three diagnostics: unit identities, per-feature KS, adversarial validation. Then six transformations that use no 2018 labels, scored by the share of the gap they recover.");
steps(s, [
  "Align 2018 features to 2017 names (75 shared); map labels to Benign, DoS/DDoS, Web Attack",
  "Verify the unit identities for Benign and DoS Hulk in both years",
  "Compute the KS statistic per feature and class on 100 000-row samples",
  "Adversarial validation: AUC of a classifier separating 2017 from 2018",
  "For each transformation T, fit on 2017 training data and on unlabelled 2018 data",
  "Train on T(2017), score on T(2017 test) and T(2018); compute G(T)",
  "Controls: train and test on 2018; reverse 2018 → 2017; score 2018 without deduplication",
], MX, 1.8, 6.0, 5.0);
eqPanel(s, [["Unit identities (µs, per second)", "eq_units", 0.62], ["Per-feature shift", "eq_ks", 0.42],
  ["Label-free transformations", "eq_transforms", 0.6], ["Share of the gap recovered", "eq_gap", 0.68]], 6.85, 1.8, 5.88);

// ---- 5 Experimental setup and output
s = content(5, "Experimental Setup and Output", "Experimental setup",
  "Data after cleaning and the eight experiments. Timestamps verified: both 2017 releases agree on 100% of rows.");
s.addTable([
  [th("Item"), th("CICIDS2017"), th("CSE-CIC-IDS2018")],
  ["Valid flows", d17.rows_after_nan_inf.toLocaleString("en-US"), e3.load_2018.rows_after_nan_inf_drop.toLocaleString("en-US")],
  ["Unique vectors", d17.unique_vectors.toLocaleString("en-US"), e3.conflicts_2018.unique_feature_rows.toLocaleString("en-US")],
  ["Duplicate share", (100 * d17.duplicate_rate).toFixed(2) + "%", (100 * e3.conflicts_2018.duplicate_rate_keep_first).toFixed(2) + "%"],
  ["Conflicting vectors", `${d17.conflicting_groups}`, `${e3.conflicts_2018.conflicting_groups}`],
  ["Features", "76", "75 aligned"],
], { ...tableOpts(MX, 1.85, 5.6, [2.1, 1.75, 1.75], 15), rowH: 0.48 });
s.addTable([
  [th("Exp."), th("Question"), th("Runs"), th("Peak RAM")],
  ["E2", "Seed variability", "14", "8.6 GB*"], ["E3", "Matched-family transfer", "5", "≥ 5.6 GB"],
  ["E4", "Leakage vs chronology (5 protocols)", "14", "4.4 GB"], ["E5", "Duplicate policies", "9", "5.5 GB"],
  ["E6", "Shift diagnosis", "1", "5.7 GB"], ["E7", "Mitigation and controls", "30", "5.5 GB"], ["E8", "Test-set deduplication", "3", "–"],
  ["E9–10", "Split composition; false-positive audit", "2", "–"],
], { ...tableOpts(6.6, 1.85, 6.13, [0.8, 3.13, 0.9, 1.3], 15), rowH: 0.42 });
card(s, MX, 5.2, 5.6, 1.6, "Models", "Random forest: 100 trees, depth 20, balanced weights\nXGBoost: 300 trees, depth 6, learning rate 0.1", { size: 14, headSize: 16 });
caption(s, "* before the memory-bounded loader, which reproduced every metric exactly at a 4.13 GB peak.", 6.6, 5.85, 6.13);

// split protocols (native markers-only chart)
s = content(5, "Experimental Setup and Output", "Output: only the chronological splits lower the scores",
  "Grouped splits remove correlated records but keep training and test periods interleaved. Only the per-class chronological splits, by timestamp and by row order, lower the scores. Values are means of two seeds.");
const SPL = ["random", "flowid", "block1", "block5", "block15", "forward", "roworder"];
const SPLL = ["Random", "Flow-ID", "1-min blocks", "5-min blocks", "15-min blocks", "Chron. (time)", "Chron. (rows)"];
s.addChart(pres.charts.LINE, [
  { name: "Stage-1 malicious F1", labels: SPLL, values: SPL.map((k) => +e4[k].mal_f1.mean.toFixed(4)) },
  { name: "Family macro-F1 (true attacks)", labels: SPLL, values: SPL.map((k) => +e4[k].fam_gt.mean.toFixed(4)) },
  { name: "End-to-end family macro-F1", labels: SPLL, values: SPL.map((k) => +e4[k].fam_e2e.mean.toFixed(4)) },
], { ...chartBase, x: MX, y: 1.75, w: 8.4, h: 5.1, lineSize: 0, lineDataSymbol: "circle", lineDataSymbolSize: 11,
  chartColors: [HEX.blue, HEX.orange, HEX.aqua], valAxisMinVal: 0.75, valAxisMaxVal: 1.0, valAxisMajorUnit: 0.05, valAxisLabelFormatCode: "0.00",
  showLegend: true, legendPos: "b", objectName: "split protocol chart" });
stat(s, 9.35, 2.0, 3.4, "≤ 0.004", "Change in malicious F1 from duplicates, sessions or time blocks", HEX.blue);
stat(s, 9.35, 4.05, 3.4, "0.903", "Malicious F1 under the per-class chronological split (random split: 0.997)", HEX.orange);

s = content(5, "Experimental Setup and Output", "Output: the drop is benign false positives",
  "Precision falls from 0.996 to 0.856; recall from 0.997 to 0.956. Holding recall fixed, precision alone gives F1 0.921. FPR rises about 44-fold. PortScan is the exception: its recall drops already under 5-minute grouping, an adjacency effect. The next two slides examine the split and its false positives.");
s.addChart(pres.charts.BAR, [{ name: "Benign false-positive rate (%)", labels: ["Random", "5-min blocks", "Chronological"],
  values: ["random", "block5", "forward"].map((k) => +e4[k].benign_fpr_pct.mean.toFixed(3)) }],
  { ...chartBase, x: MX, y: 1.8, w: 5.2, h: 4.9, barDir: "col", chartColors: [HEX.blue], showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "0.00\"%\"", dataLabelColor: HEX.ink, dataLabelFontSize: 12, valAxisLabelFormatCode: "0.0", valAxisMinVal: 0, valAxisMaxVal: 3.5,
    showLegend: false, showTitle: true, title: "Benign false-positive rate (%)", titleFontSize: 13, titleColor: HEX.ink2, titleFontFace: "+mn-lt", barGapWidthPct: 120, objectName: "fpr chart" });
image(s, "fig_class_recall", 6.1, 1.8, 6.6, 4.4, "Stage-1 recall per attack under three protocols");
caption(s, "Stage-1 recall per attack (mean and range over two seeds)", 6.1, 6.35, 6.6);

// time composition of the per-class chronological split and global-cutoff feasibility (E9)
const e9 = N.exp009, x10 = N.exp010, fw10 = x10.forward, rn10 = x10.random;
const DAY = { "2017-07-03": "Mon", "2017-07-04": "Tue", "2017-07-05": "Wed", "2017-07-06": "Thu", "2017-07-07": "Fri" };
const when = (t) => `${DAY[t.slice(0, 10)]} ${t.slice(11, 16)}`;
s = content(5, "Experimental Setup and Output", "Output: no global cutoff is possible on CICIDS2017",
  "The chronological split cuts each class at its own time. It is therefore not a simulation of deployment after a fixed date: training flows of one class can be later than test flows of another. A single global cutoff would leave almost every attack class on one side only, because each attack runs in one interval of minutes to hours.");
s.addTable([
  [th("Global cutoff"), th("Train share"), th("Attack classes on both sides"), th("Train only"), th("Test only")],
  ...["q50", "q60", "q70", "q80", "q90", "friday_start"].map((k) => {
    const g = e9.global_cutoff[k];
    return [k === "friday_start" ? "Fri 00:00" : `${when(g.cutoff)} (${k.slice(1)}th pct.)`, `${(100 * g.train_frac).toFixed(0)}%`,
      `${g.both} of 14`, String(g.train_only), String(g.test_only)];
  }),
], { ...tableOpts(MX, 1.85, 7.6, [2.3, 1.2, 1.9, 1.1, 1.1], 15), rowH: 0.5 });
caption(s, "Cutoffs at percentiles of capture time; 14 attack labels after deduplication", MX, 5.45, 7.6);
stat(s, 8.75, 1.85, 4.0, `${(100 * e9.test_with_later_train_frac).toFixed(0)}%`, "of chronological test flows have at least one later training flow", HEX.orange);
stat(s, 8.75, 3.85, 4.0, `${(100 * e9.attack_train_in_benign_test_window / e9.attack_train_total).toFixed(0)}%`,
  `of attack training flows (DDoS, PortScan, Bot) lie inside the benign test window, ${when(e9.benign_test_window.t_min)} to ${when(e9.benign_test_window.t_max)}`, HEX.orange);

// endpoint audit of the chronological-split false positives (E10)
s = content(5, "Experimental Setup and Output", "Output: the false positives are two attack sessions",
  `Seed 42, both protocols reproduced exactly. ${(100 * x10.endpoint_fp_share_forward).toFixed(1)}% of the chronological false positives lie on two endpoint sets. The DDoS ones run from the victim back to the attacker during the 20-minute attack; every DDoS-labelled flow runs the other way. The Bot ones are infected hosts talking to the C&C server on port 8080 after the last Bot-labelled flow. The random split keeps most of these flows in training under their benign labels and learns them. With them removed from both test sets the false-positive rates are equal. The sets were found from the errors they explain, so this is a diagnostic, not a corrected benchmark.`);
image(s, "fig_fp", MX, 1.8, 6.3, 4.6, "Benign false-positive rate by endpoint set, and after excluding both sets");
caption(s, "Seed 42. (b) shows Wilson 95% intervals.", MX, 6.45, 6.3);
stat(s, 7.2, 5.15, 5.53, `${(100 * x10.endpoint_fp_share_forward).toFixed(1)}%`, "of chronological-split false positives lie on the two endpoint sets", HEX.orange);
card(s, 7.2, 1.85, 5.53, 3.15, "Endpoint audit (seed 42)",
  `• DDoS victim ↔ attacker: ${fw10.fp_on_ddos_pair.toLocaleString("en-US")} of ${fw10.benign_fp.toLocaleString("en-US")} false positives; reverse direction, inside 15:56–16:16\n` +
  `• Bot C&C channel (port 8080): ${fw10.fp_on_bot_cc} false positives, after the last Bot label at 12:59\n` +
  `• Random split: ${rn10.fp_on_ddos_pair} false positives among ${rn10.benign_on_ddos_pair.toLocaleString("en-US")} benign flows on the same pair\n` +
  `• Both sets removed: FPR ${(100 * rn10.stage1_excl_both_benign.fpr).toFixed(3)}% vs ${(100 * fw10.stage1_excl_both_benign.fpr).toFixed(3)}%; F1 gap ${x10.f1_gap_all.toFixed(3)} → ${x10.f1_gap_excl.toFixed(3)}, recall only`, { size: 15 });

s = content(5, "Experimental Setup and Output", "Output: duplicates and label conflicts",
  "309 vectors carry conflicting labels, all involving benign traffic. Duplication is concentrated in probing attacks. Policy choice changes binary F1 by under 0.004 on a common test set but reshapes the test population.");
image(s, "fig_duplication", MX, 1.75, W - 2 * MX, 3.6, "Share of exact duplicates per label");
stat(s, MX, 5.45, 3.6, "309", "feature vectors with conflicting labels (82,704 rows), all involving BENIGN", HEX.blue);
stat(s, MX + 4.2, 5.45, 3.6, "98.8%", "of PortScan rows are exact duplicates (1,956 unique vectors)", HEX.orange);
stat(s, MX + 8.4, 5.45, 3.6, "< 0.004", "change in malicious F1 across four resolution policies", HEX.blue);

s = content(5, "Experimental Setup and Output", "Output: attribution must be scored end to end",
  "Stage 2 on true attacks looks perfect for Bot; end to end it inherits Stage-1 false positives. Web brute force and XSS are hard to separate even under a random split.");
image(s, "fig_hierarchy", MX, 1.8, 6.6, 4.9, "Family F1 on true attacks only vs end to end");
card(s, 7.6, 1.85, 5.13, 4.8, "Key numbers (5 seeds)", `• Bot: ${f3(e2.hierarchy.random.Bot.gt_f1)} → ${f3(e2.hierarchy.random.Bot.e2e_f1)} (random split)\n• Bot: ${f3(e2.hierarchy.roworder.Bot.gt_f1)} → ${f3(e2.hierarchy.roworder.Bot.e2e_f1)} (chronological), precision ${f3(e2.hierarchy.roworder.Bot.e2e_precision)}\n• DoS/DDoS: ${f3(e2.hierarchy.roworder["DoS/DDoS"].gt_f1)} → ${f3(e2.hierarchy.roworder["DoS/DDoS"].e2e_f1)} (chronological)\n• These end-to-end losses are the benign-labelled flows on the DDoS pair and the Bot C&C channel\n• Web brute force / XSS fine F1: ${f3(e2.fine_f1.random["Web Attack - Brute Force"].mean)} / ${f3(e2.fine_f1.random["Web Attack - XSS"].mean)} even with a random split`, { size: 16 });

s = content(5, "Experimental Setup and Output", "Output: zero-shot transfer collapses on matched families",
  "Same-year reference 0.949; transfer 0.322; 2018-trained model 0.949. Without deduplication malicious F1 is 0.0087 and SlowHTTPTest recall 0.000 over 139,890 rows. Reverse direction fails too.");
s.addChart(pres.charts.BAR, [
  { name: "Train 2017, test 2017", labels: ["DoS/DDoS recall", "Web Attack recall", "End-to-end macro-F1"], values: [e3.reference["recall_DoS/DDoS"].mean, e3.reference["recall_Web Attack"].mean, e3.reference.e2e.mean].map((v) => +v.toFixed(3)) },
  { name: "Train 2017, test 2018", labels: ["DoS/DDoS recall", "Web Attack recall", "End-to-end macro-F1"], values: [e3.cross["recall_DoS/DDoS"].mean, e3.cross["recall_Web Attack"].mean, e3.cross.e2e.mean].map((v) => +v.toFixed(3)) },
  { name: "Train 2018, test 2018", labels: ["DoS/DDoS recall", "Web Attack recall", "End-to-end macro-F1"], values: [e7.upper2018_rf.dos.mean, e7.upper2018_rf.web.mean, e7.upper2018_rf.e2e.mean].map((v) => +v.toFixed(3)) },
], { ...chartBase, x: MX, y: 1.75, w: 7.3, h: 5.1, barDir: "col", barGrouping: "clustered", chartColors: [HEX.blue, HEX.orange, HEX.aqua],
  showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", dataLabelColor: HEX.ink, dataLabelFontSize: 11,
  valAxisMinVal: 0, valAxisMaxVal: 1.1, valAxisMajorUnit: 0.25, valAxisLabelFormatCode: "0.00", showLegend: true, legendPos: "b", barGapWidthPct: 60, objectName: "transfer chart" });
image(s, "fig_confusion", 8.1, 2.0, 4.65, 3.4, "End-to-end confusion matrices, seed 42");
caption(s, "Row-normalised confusion, seed 42: 145,169 of 145,254 DoS flows labelled benign", 8.1, 5.6, 4.65);

s = content(5, "Experimental Setup and Output", "Output: units agree; DoS-Hulk traffic differs by year",
  "Unit identities hold in both years, so no unit mismatch. Benign shifts mildly; DoS Hulk shifts strongly on backward-direction features. The features that separate Hulk from benign in 2017 are absent in most 2018 Hulk flows.");
image(s, "fig_shift", MX, 1.75, 6.2, 5.0, "KS statistic between years");
card(s, 7.15, 1.85, 5.58, 4.8, "Diagnostics", `• Unit identities: 1.000×10⁶, 1.000×10⁶, 1.000 in both years\n• Adversarial AUC 2017 vs 2018: ${e6.adversarial_auc["all_2017_vs_all_2018 (label-free)"].toFixed(4)} (benign only ${e6.adversarial_auc["benign_2017_vs_benign_2018"].toFixed(4)})\n• DoS Hulk: ${e6.n_ks_gt_05.dos_hulk}/75 features with KS > 0.5; Benign: 0/75 (max 0.445)\n• Hulk flows with no backward payload: 9.5% (2017) → 82.3% (2018)\n• Median Hulk duration: 86.4 s → 0.051 s`, { size: 15 });

s = content(5, "Experimental Setup and Output", "Output: label-free normalisation does not recover the gap",
  "Random forest over three seeds recovers at most 0.5% of the gap. XGBoost with 10 features dropped recovers 15.5% (one seed), still with DoS recall 0. The globally shifted features are benign-driven; the Hulk-specific ones rank 35–46 and were never dropped.");
const TR = ["none", "slog", "robust_domain", "quantile_domain", "drop_k10", "drop_k25"];
const TRL = ["None", "Signed log", "Robust scaling", "Quantile", "Drop 10", "Drop 25"];
s.addChart(pres.charts.LINE, [
  { name: "Random forest (3 seeds)", labels: TRL, values: TR.map((t) => +e7[t + "_rf"].cross_e2e.mean.toFixed(3)) },
  { name: "XGBoost (1 seed)", labels: TRL, values: TR.map((t) => +e7[t + "_xgb"].cross_e2e.mean.toFixed(3)) },
], { ...chartBase, x: MX, y: 1.75, w: 7.6, h: 5.1, lineSize: 0, lineDataSymbol: "circle", lineDataSymbolSize: 11, chartColors: [HEX.blue, HEX.orange],
  valAxisMinVal: 0, valAxisMaxVal: 1.0, valAxisMajorUnit: 0.2, valAxisLabelFormatCode: "0.0", showLegend: true, legendPos: "b",
  showTitle: true, title: "End-to-end macro-F1 on 2018 (same-year reference 0.949)", titleFontSize: 13, titleColor: HEX.ink2, titleFontFace: "+mn-lt", objectName: "mitigation chart" });
stat(s, 8.6, 2.1, 4.1, "≤ 0.5%", "gap recovered by any label-free transformation (random forest, 3 seeds)", HEX.blue);
stat(s, 8.6, 4.1, 4.1, "1.000", "DoS recall when trained and tested on 2018: the features suffice within a year", HEX.aqua);

// ---- 6 Result analysis
s = content(6, "Result Analysis", "Leakage is small; the chronological gap is mostly labels",
  "Decomposition summary. Exact duplicates, sessions and minute blocks: at most 0.004 malicious F1. The per-class chronological split costs 0.09 F1 and multiplies false positives by 44, which would ordinarily be read as drift. The audit shows that almost all of those false positives are benign-labelled flows of two attack sessions. After removing them from both protocols, the gap is 0.020 F1, entirely recall, mostly the last 11 minutes of DoS Hulk.");
stat(s, MX, 2.0, 3.8, "≤ 0.004", "malicious-F1 change from duplicates, Flow-ID groups and 1–15 min blocks (within noise)", HEX.blue);
stat(s, MX + 4.2, 2.0, 3.8, `${(100 * x10.endpoint_fp_share_forward).toFixed(1)}%`, "of chronological-split false positives lie on two attack endpoint sets", HEX.orange);
stat(s, MX + 8.4, 2.0, 3.8, `${x10.f1_gap_all.toFixed(3)} → ${x10.f1_gap_excl.toFixed(3)}`, "malicious-F1 gap to the random split once both sets are removed (seed 42)", HEX.orange);
textBox(s, [
  "On this dataset the chronological split acts mainly as an audit of labels: it moves flows the random split memorises into the test set",
  "Residual effect: recall 0.997 → 0.957, 85% of it in DoS Hulk; its cause was not examined",
  "Deduplication is still required for a correct test population; PortScan shows adjacency can dominate one class",
  "Transfer failure is robust: 5 seeds, no-dedup control, reverse direction, XGBoost; not a unit artefact",
], MX, 4.4, W - 2 * MX, 2.4, { size: 16, gap: 6 });

s = content(6, "Result Analysis", "Comparison with existing systems",
  "Settings differ, so this compares evaluation coverage and the direction of findings. Our transfer result is more severe than Cantone et al.; deduplication does not explain it; the attack-subset explanation is plausible but untested.");
s.addTable([
  [th("Aspect"), th("Cantone et al. 2024"), th("Moczkodan & Ragab 2026"), th("Review II baseline"), th("This work")],
  ["Random-split binary score", "Nearly perfect", "–", "F1 0.997", "F1 0.9966 ± 0.0000"],
  ["Time-aware evaluation", "–", "FAR × 67 (Transformer)", "No", "F1 0.903, FPR × 44"],
  ["Time-split errors inspected", "–", "–", "No", "98.8% on 2 attack sessions"],
  ["Label conflicts counted", "No", "–", "No", "309 vectors, 82,704 rows"],
  ["Attribution end to end", "No", "–", "No", "Bot 1.00 → 0.41"],
  ["Transfer 2017 → 2018", "F1 0.26–0.39 (all attacks)", "–", "F1 0.002", "F1 0.0006 (matched families)"],
  ["Cause of failure", "Anomalies, attack configs", "–", "Hypothesised", "Units verified; 50/75 Hulk features shift"],
  ["Mitigation tested", "No", "No", "No", "4 label-free: ≤ 0.5% recovered"],
], { ...tableOpts(MX, 1.8, W - 2 * MX, [2.75, 2.45, 2.35, 1.85, 2.73], 15), rowH: 0.52 });

// ---- 7 Conclusion
s = content(7, "Conclusion and Future Works", "Conclusions and future work",
  "Five conclusions, five directions for future work. The central one: the chronological gap on CICIDS2017 is mainly a label artefact, so a time-aware split needs an audit of its errors before its drop is called drift.");
card(s, MX, 1.85, 6.35, 4.85, "Conclusions", "• Duplicates and correlated records explain at most 0.004 F1\n• The chronological gap is mainly a label artefact: 98.8% of its false positives are benign-labelled attack-session flows; without them FPR is equal and only a recall loss remains\n• A time-aware split needs an audit of its errors before its drop is called drift\n• Attribution must be reported end to end\n• 2017 → 2018 transfer fails; units hold, diagnostics point to changed attack traffic; label-free normalisation does not repair it", { size: 17 });
card(s, 7.15, 1.85, 5.58, 4.85, "Future work", "• Relabel the flows on the two endpoint sets and repeat the protocol comparison\n• Extend transfer to all CSE-CIC-IDS2018 attack days\n• Class-aware adaptation with a small labelled target sample\n• Same protocols on TLS-metadata captures and sequence models\n• More seeds for grouped protocols and the policy study", { size: 17 });

// ---- 8 References
s = content(8, "References", "Key references", "Full list of 25 references in the report.");
s.addText([
  "[1] I. Sharafaldin, A. H. Lashkari, A. A. Ghorbani, \"Toward generating a new intrusion detection dataset and intrusion traffic characterization,\" ICISSP, 2018.",
  "[2] G. Engelen, V. Rimmer, W. Joosen, \"Troubleshooting an intrusion detection dataset: the CICIDS2017 case study,\" IEEE SPW, 2021.",
  "[3] L. Liu, G. Engelen, T. Lynar, D. Essam, W. Joosen, \"Error prevalence in NIDS datasets: CIC-IDS-2017 and CSE-CIC-IDS-2018,\" IEEE CNS, 2022.",
  "[4] M. Lanvin et al., \"Errors in the CICIDS2017 dataset and the significant differences in detection performances it makes,\" CRiSIS 2022, Springer, 2023.",
  "[5] A. Pekar, R. Jozsa, \"Evaluating ML-based anomaly detection across datasets of varied integrity,\" Computer Networks, 2024.",
  "[6] M. Cantone, C. Marrocco, A. Bria, \"On the cross-dataset generalization of machine learning for network intrusion detection,\" IEEE Access, vol. 12, 2024.",
  "[7] Z. Moczkodan, H. Ragab, \"Do transformers actually help intrusion detection? A temporal sequence evaluation on CIC-IDS2017,\" arXiv:2606.11098, 2026.",
  "[8] D. Arp et al., \"Dos and don'ts of machine learning in computer security,\" USENIX Security, 2022.",
  "[9] F. Pendlebury et al., \"TESSERACT: Eliminating experimental bias in malware classification across space and time,\" USENIX Security, 2019.",
  "[10] B. Anderson, D. McGrew, \"Identifying encrypted malware traffic with contextual flow data,\" ACM AISec, 2016.",
  "[11] L. Breiman, \"Random forests,\" Machine Learning, 45(1), 2001;  T. Chen, C. Guestrin, \"XGBoost,\" ACM SIGKDD, 2016.",
].map((t, i, a) => ({ text: t, options: { breakLine: i < a.length - 1, paraSpaceAfter: 6 } })),
{ x: MX, y: 1.75, w: W - 2 * MX, h: 5.1, fontFace: "Calibri", fontSize: 13, color: C.text1, valign: "top", margin: 0, isTextBox: true, objectName: "references" });

// Closing
pres.addSection({ title: "Close" });
s = pres.addSlide({ masterName: "TITLE", sectionTitle: "Close" });
s.addText("Thank you", { placeholder: "title" });
s.addText([
  { text: "Questions and discussion", options: { breakLine: true } },
  { text: " ", options: { breakLine: true, fontSize: 10 } },
  { text: "Gaurav Bakshi · Anshveer Singh · Dev Acharya Menon   |   Supervisor: Dr Anto S" },
], { placeholder: "body" });

const out = path.join(ROOT, "Project_Review.pptx");
pres.writeFile({ fileName: out }).then(async () => { await applyTheme(out, THEME); console.log("wrote", out); });
