// Builds the BCSE410L project report (.docx) following the VIT template.
// Numbers are taken from ../numbers.json (generated from the saved experiment outputs).
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, ImageRun, Table, TableRow,
  TableCell, WidthType, BorderStyle, ShadingType, Footer, PageNumber, NumberFormat, TabStopType, Tab,
  LevelFormat, VerticalAlign, Math: OMath, MathRun, MathFraction, MathRadical, MathSubScript,
  MathSuperScript, MathSum, PageBreak,
} = require("docx");

const ROOT = path.join(__dirname, "..");
const FIG = path.join(ROOT, "figures");
const N = JSON.parse(fs.readFileSync(path.join(ROOT, "numbers.json"), "utf8"));
const FONT = "Times New Roman";
const TEXT_W = 9026; // A4 width 11906 - 2*1440

// ------------------------------------------------------------------ inline markup
// *italic*  **bold**  _{sub}  ^{sup}
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|_\{[^}]+\}|\^\{[^}]+\})/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), font: FONT, ...base }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), font: FONT, ...base, bold: true }));
    else if (t.startsWith("*")) out.push(new TextRun({ text: t.slice(1, -1), font: FONT, ...base, italics: true }));
    else if (t.startsWith("_{")) out.push(new TextRun({ text: t.slice(2, -1), font: FONT, ...base, subScript: true }));
    else out.push(new TextRun({ text: t.slice(2, -1), font: FONT, ...base, superScript: true }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), font: FONT, ...base }));
  return out;
}

const P = (text, opts = {}) => new Paragraph({
  children: runs(text, opts.run || {}),
  alignment: opts.align || AlignmentType.JUSTIFIED,
  indent: opts.noIndent ? undefined : { firstLine: 720 },
  spacing: { after: opts.after ?? 120, before: opts.before ?? 0, line: 276 },
  keepNext: opts.keepNext,
});
const H1 = (text, first = false) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text, font: FONT })], pageBreakBefore: !first });
const H2 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text, font: FONT })], keepNext: true });
const H3 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun({ text, font: FONT })], keepNext: true });
const SH = (text) => new Paragraph({ keepNext: true, spacing: { before: 160, after: 80, line: 276 }, children: runs(text, { bold: true, italics: true }) });
const bullet = (text, level = 0) => new Paragraph({
  children: runs(text), numbering: { reference: "bullets", level }, alignment: AlignmentType.JUSTIFIED,
  spacing: { after: 80, line: 276 },
});
const numbered = (text, ref = "numbers") => new Paragraph({
  children: runs(text), numbering: { reference: ref, level: 0 }, alignment: AlignmentType.JUSTIFIED,
  spacing: { after: 80, line: 276 },
});

// ------------------------------------------------------------------ figures & tables
let figNo = 0, tabNo = 0, eqNo = 0;
function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
function figure(name, caption, widthPx = 600) {
  figNo += 1;
  const file = path.join(FIG, name + ".png");
  const { w, h } = pngSize(file);
  const height = Math.round(widthPx * h / w);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
      children: [new ImageRun({ type: "png", data: fs.readFileSync(file), transformation: { width: widthPx, height },
        altText: { title: caption, description: caption, name } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200, line: 276 },
      children: runs(`Fig. ${figNo}. ${caption}`, { size: 22 }) }),
  ];
}
const border = { style: BorderStyle.SINGLE, size: 4, color: "8C8C8C" };
const borders = { top: border, bottom: border, left: border, right: border };
function table(caption, header, rows, widths, opts = {}) {
  tabNo += 1;
  const total = widths.reduce((a, b) => a + b, 0);
  const size = opts.size || 20;
  const mk = (cells, isHead) => new TableRow({
    tableHeader: isHead,
    cantSplit: true,
    children: cells.map((c, i) => new TableCell({
      borders, width: { size: widths[i], type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
      shading: isHead ? { fill: "E8EEF7", type: ShadingType.CLEAR, color: "auto" } : undefined,
      margins: { top: 50, bottom: 50, left: 90, right: 90 },
      children: [new Paragraph({ alignment: (i === 0 || opts.leftAll) ? AlignmentType.LEFT : (opts.align || AlignmentType.CENTER),
        spacing: { after: 0, line: 240 }, children: runs(String(c), { size, bold: isHead }) })],
    })),
  });
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 160, after: 80 }, keepNext: true,
      children: runs(`Table ${tabNo}. ${caption}`, { size: 22 }) }),
    new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: widths,
      rows: [mk(header, true), ...rows.map((r) => mk(r, false))] }),
    new Paragraph({ spacing: { after: 120 }, children: [] }),
  ];
}

// ------------------------------------------------------------------ equations
const mr = (t) => new MathRun(t);
const frac = (n, d) => new MathFraction({ numerator: n, denominator: d });
const sub = (b, s) => new MathSubScript({ children: b, subScript: s });
const sup = (b, s) => new MathSuperScript({ children: b, superScript: s });
const sqrt = (c) => new MathRadical({ children: c });
function eq(children) {
  eqNo += 1;
  return new Paragraph({
    tabStops: [{ type: TabStopType.CENTER, position: TEXT_W / 2 }, { type: TabStopType.RIGHT, position: TEXT_W }],
    spacing: { before: 100, after: 140 },
    children: [new TextRun({ children: [new Tab()] }), new OMath({ children }),
      new TextRun({ children: [new Tab(), `(${eqNo})`], font: FONT })],
  });
}
function algorithm(title, lines) {
  const cellChildren = [new Paragraph({ spacing: { after: 80 }, children: runs(title, { bold: true, size: 22 }) })]
    .concat(lines.map((l, i) => new Paragraph({ spacing: { after: 20, line: 260 },
      indent: { left: 360 + (l.indent || 0) * 360, hanging: 360 },
      children: runs(`${i + 1}:\t${l.t}`, { size: 22 }), tabStops: [{ type: TabStopType.LEFT, position: 360 + (l.indent || 0) * 360 }] })));
  return [new Table({ width: { size: TEXT_W, type: WidthType.DXA }, columnWidths: [TEXT_W], rows: [new TableRow({ cantSplit: true,
    children: [new TableCell({ width: { size: TEXT_W, type: WidthType.DXA }, borders,
      shading: { fill: "F5F7FA", type: ShadingType.CLEAR, color: "auto" }, margins: { top: 120, bottom: 120, left: 160, right: 160 },
      children: cellChildren })] })] }), new Paragraph({ spacing: { after: 120 }, children: [] })];
}

// ------------------------------------------------------------------ helpers for numbers
const f3 = (x) => x.toFixed(3), f4 = (x) => x.toFixed(4), pct = (x, d = 2) => (100 * x).toFixed(d) + "%";
const big = (x) => x.toLocaleString("en-US");
const e2 = N.exp002, e4 = N.exp004, e3 = N.exp003, e7 = N.exp007, e8 = N.exp008, e6 = N.exp006, d17 = N.data_2017;

// =================================================================== COVER
const cover = [];
const C = (text, size, opts = {}) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: opts.after ?? 0, before: opts.before ?? 0, line: 360 },
  children: [new TextRun({ text, font: FONT, size: size * 2, bold: !!opts.bold, italics: !!opts.italics })] });
cover.push(C("", 12, { after: 400 }));
cover.push(C("BCSE410L – Cyber Security Project", 18, { bold: true, after: 600 }));
cover.push(C("BEHAVIORAL CLASSIFICATION OF ENCRYPTED", 16, { bold: true }));
cover.push(C("MALICIOUS NETWORK TRAFFIC USING", 16, { bold: true }));
cover.push(C("FLOW-BASED METADATA", 16, { bold: true, after: 500 }));
const noB = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const noBorders = { top: noB, bottom: noB, left: noB, right: noB };
const students = [["23BCE0546", "GAURAV BAKSHI"], ["23BCE0703", "ANSHVEER SINGH"], ["23BCE0717", "DEV ACHARYA MENON"]];
cover.push(new Table({ width: { size: 5600, type: WidthType.DXA }, columnWidths: [1900, 3700], alignment: AlignmentType.CENTER,
  borders: { top: noB, bottom: noB, left: noB, right: noB, insideHorizontal: noB, insideVertical: noB },
  rows: students.map(([r, n]) => new TableRow({ children: [
    new TableCell({ borders: noBorders, width: { size: 1900, type: WidthType.DXA }, children: [new Paragraph({ spacing: { line: 360 }, children: [new TextRun({ text: r, font: FONT, size: 26, bold: true })] })] }),
    new TableCell({ borders: noBorders, width: { size: 3700, type: WidthType.DXA }, children: [new Paragraph({ spacing: { line: 360 }, children: [new TextRun({ text: n, font: FONT, size: 26, bold: true })] })] }),
  ] })) }));
cover.push(C("", 12, { after: 400 }));
cover.push(C("Under the Supervision of", 14, { after: 160 }));
cover.push(C("Dr Anto S", 13, { bold: true, after: 120 }));
cover.push(C("School of Computer Science and Engineering (SCOPE)", 13, { after: 700 }));
cover.push(C("B.Tech.", 14, { bold: true }));
cover.push(C("in", 14, { italics: true }));
cover.push(C("Computer Science and Engineering", 14, { bold: true, after: 300 }));
cover.push(C("School of Computer Science and Engineering", 16, { bold: true, after: 400 }));
const logo = path.join(ROOT, "assets", "vit_logo_0.png");
cover.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 },
  children: [new ImageRun({ type: "png", data: fs.readFileSync(logo), transformation: { width: 380, height: Math.round(380 * 70 / 253) },
    altText: { title: "VIT logo", description: "Vellore Institute of Technology logo", name: "vit_logo" } })] }));
cover.push(C("October 2026", 13));

// =================================================================== FRONT MATTER
const front = [];
front.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: "ABSTRACT", font: FONT })] }));
const abstractText = [
  "Flow statistics such as packet sizes, inter-arrival times and flag counts remain observable when traffic is encrypted, so classifiers trained on them can detect malicious activity without decryption. On CICIDS2017 such classifiers report near-perfect scores, and the gap to operational performance is usually attributed to leakage through duplicated or correlated records or to change in traffic over time. This project builds a leakage-aware evaluation system for a two-stage detector, which separates malicious from benign flows and then attributes each alert to an attack family, and uses it to test both explanations.",
  `With pipeline, features and models fixed, five split protocols are compared on the timestamped release of CICIDS2017. Removing exact duplicates and grouping flows by connection or by 1–15 minute blocks change malicious-class F_{1} by at most 0.004. A per-class chronological split lowers it from 0.997 to 0.903 and raises the benign false-positive rate from 0.07% to 2.90%. An audit by endpoint and time shows that 98.8% of these false positives are benign-labelled flows between known attack endpoints, around the DDoS attack and the Bot command-and-control channel. With them excluded from both protocols, the false-positive rates are equal (0.037%) and only a recall loss remains, 85% of it in DoS Hulk. The integrity audit finds ${d17.conflicting_groups} feature vectors with conflicting labels, and Bot attribution F_{1} falls from 1.00 to 0.41 once detection errors are included.`,
  "Matched-family transfer from CICIDS2017 to CSE-CIC-IDS2018 collapses to a DoS recall of 0.0003, is unchanged without test-set deduplication and is not recovered by four label-free normalisations, although a model trained on 2018 data reaches a DoS recall of 1.000. Unit identities hold, while 50 of 75 DoS-Hulk features shift with a Kolmogorov–Smirnov statistic above 0.5. A time-aware split therefore needs an inspection of its errors before its drop is attributed to drift.",
];
abstractText.forEach((t) => front.push(P(t)));
front.push(new Paragraph({ spacing: { before: 200 }, alignment: AlignmentType.JUSTIFIED,
  children: runs("*Keywords – Intrusion detection, Flow features, Encrypted traffic, Evaluation methodology, Label noise, Dataset shift.*") }));

// TOC (borderless table; page numbers filled after layout)
const tocEntries = [
  ["", "**Abstract**", "i", 0],
  ["1.", "**INTRODUCTION**", "", 1], ["", "1.1 Background", "", 2], ["", "1.2 Motivation", "", 2], ["", "1.3 Scope of the Project", "", 2],
  ["2.", "**PROJECT DESCRIPTION AND GOALS**", "", 1], ["", "2.1 Literature Review", "", 2], ["", "2.2 Research Gap", "", 2],
  ["", "2.3 Problem Statement", "", 2], ["", "2.4 Objectives", "", 2], ["", "2.5 Project Plan", "", 2],
  ["3.", "**TECHNICAL SPECIFICATION**", "", 1], ["", "3.1 Requirements", "", 2], ["", "3.1.1 Functional", "", 3], ["", "3.1.2 Non-Functional", "", 3],
  ["", "3.2 Feasibility Study", "", 2], ["", "3.2.1 Technical Feasibility", "", 3], ["", "3.2.2 Economic Feasibility", "", 3], ["", "3.2.3 Social Feasibility", "", 3],
  ["", "3.3 System Specification", "", 2], ["", "3.3.1 Hardware Specification", "", 3], ["", "3.3.2 Software Specification", "", 3],
  ["4.", "**DESIGN APPROACH AND DETAILS**", "", 1], ["", "4.1 System Architecture", "", 2], ["", "4.2 Design", "", 2],
  ["", "4.2.1 Algorithm 1: Leakage-Aware Hierarchical Evaluation", "", 3], ["", "4.2.2 Algorithm 2: Shift Diagnosis and Label-Free Mitigation", "", 3],
  ["5.", "**EXPERIMENTAL SETUP AND OUTPUT**", "", 1], ["", "5.1 Experimental Setup", "", 2], ["", "5.2 Output of the Proposed System", "", 2],
  ["6.", "**RESULT ANALYSIS**", "", 1], ["", "6.1 Comparison with Existing Systems", "", 2],
  ["7.", "**CONCLUSION AND FUTURE WORKS**", "", 1], ["8.", "**REFERENCES**", "", 1],
];
front.push(new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, children: [new TextRun({ text: "TABLE OF CONTENTS", font: FONT })] }));
const tw = [1000, 6826, 1200];
front.push(new Table({ width: { size: TEXT_W, type: WidthType.DXA }, columnWidths: tw,
  borders: { top: noB, bottom: noB, left: noB, right: noB, insideHorizontal: noB, insideVertical: noB },
  rows: [["Sl.No", "**Contents**", "**Page No.**", -1], ...tocEntries].map(([a, b, c, lvl]) => new TableRow({ children: [
    new TableCell({ borders: noBorders, width: { size: tw[0], type: WidthType.DXA }, children: [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { line: 360, after: 0 }, children: runs(lvl === -1 ? "**Sl.No**" : (a ? `**${a}**` : "")) })] }),
    new TableCell({ borders: noBorders, width: { size: tw[1], type: WidthType.DXA }, children: [new Paragraph({ indent: { left: lvl === 3 ? 360 : 0 }, alignment: lvl === -1 ? AlignmentType.CENTER : AlignmentType.LEFT, spacing: { line: 360, after: 0 }, children: runs(b) })] }),
    new TableCell({ borders: noBorders, width: { size: tw[2], type: WidthType.DXA }, children: [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { line: 360, after: 0 }, children: runs(lvl === -1 ? c : (lvl === 1 || lvl === 0 ? `**${c || "@@"}**` : (c || "@@"))) })] }),
  ] })) }));

// =================================================================== BODY
const B = [];
// ---------------- 1 INTRODUCTION
B.push(H1("1. INTRODUCTION", true));
B.push(H2("1.1 Background"));
B.push(P("Most traffic on enterprise networks is encrypted, which limits inspection to metadata unless TLS sessions are intercepted, and interception breaks end-to-end confidentiality while adding latency and legal exposure. Flow-level statistics are computed from packet headers and timing alone and remain available for encrypted sessions. A flow is the set of packets that share source and destination addresses, ports and protocol within a timeout; CICFlowMeter summarises each flow into roughly 80 numerical features describing packet lengths, inter-arrival times, flag counts and directional ratios."));
B.push(P("Supervised classifiers trained on these features are evaluated mostly on public benchmarks produced by the Canadian Institute for Cybersecurity, CICIDS2017 and CSE-CIC-IDS2018, where tree ensembles regularly exceed 99% accuracy. Audits have since documented labelling errors, duplicated records and flow-construction artefacts in these datasets, and cross-dataset studies report that models trained on one of them perform poorly on the other. This project measures how much of the reported performance survives stricter evaluation protocols, and examines what the errors that appear under those protocols consist of."));
B.push(H2("1.2 Motivation"));
B.push(P("A detector is deployed on traffic recorded after its training data and often on a different network. A random train/test split of one capture measures neither condition. If benchmark scores are inflated, results in the literature cannot be compared with each other or with operational requirements such as an acceptable false-positive rate. The two remedies usually proposed, removing duplicate records and grouping related records on one side of the split, both target leakage and neither targets change over time. When a time-aware split lowers the scores, the drop is usually read as drift; whether that reading holds, or whether the errors have another origin, decides whether the field needs temporal validation and model maintenance or cleaner labels."));
B.push(P("Attribution adds a second motivation. Analysts act on the attack type attached to an alert, yet attribution quality is normally reported on ground-truth attack flows, which excludes the false positives that analysts receive. Finally, an earlier phase of this project observed a model with F_{1} 0.997 on CICIDS2017 scoring 0.002 on CSE-CIC-IDS2018, and it had to be established whether that collapse was real or a pipeline error."));
B.push(H2("1.3 Scope of the Project"));
B.push(P("The project uses payload-independent flow features from CICFlowMeter output; packet payloads, TLS handshake fields and raw packet captures are outside its scope. CICIDS2017 is used in full (eight capture files, 2.83 million flows) together with its timestamped release. CSE-CIC-IDS2018 is represented by two capture days, 16 and 22 February 2018, which contain DoS-Hulk, DoS-SlowHTTPTest and web attacks. Detection is binary (benign versus malicious), and attribution uses a six-family and a twelve-class attack taxonomy."));
B.push(P("Models are tree ensembles (random forest and XGBoost); deep sequence models are not evaluated. The deliverable is an evaluation system with integrity auditing, five split protocols, an endpoint audit of false positives, hierarchical scoring, seed-variability estimates and shift diagnostics, together with a set of controlled experiments. Mitigations are restricted to transformations that use no labels from the target dataset. Adversarial evasion, early-flow detection and online deployment are not part of the final scope."));

// ---------------- 2 PROJECT DESCRIPTION
B.push(H1("2. PROJECT DESCRIPTION AND GOALS"));
B.push(H2("2.1 Literature Review"));
B.push(P("The review covers four areas: benchmark construction and flow features for encrypted traffic, audits of the CIC datasets, evaluation methodology for machine learning in security, and cross-dataset generalisation. Table 1 summarises the papers."));
B.push(SH("Benchmarks and flow features"));
B.push(P("Sharafaldin, Lashkari and Ghorbani [1] generated CICIDS2017 over five working days with scripted benign user profiles and scheduled attacks (brute force, DoS, DDoS, web attacks, infiltration, botnet and port scanning) and extracted more than 80 flow features with CICFlowMeter. Draper-Gil *et al.* [2] showed that time-related flow features alone characterise encrypted and VPN traffic classes with decision-tree and nearest-neighbour classifiers. Anderson and McGrew [3] detected malware in TLS-encrypted traffic using flow metadata, packet-length and timing sequences, byte distributions and TLS handshake fields, and showed that DNS and HTTP context from the same host improves detection. In later work [4] they compared classifiers on enterprise traffic and studied the effect of noisy labels and of non-stationarity over time. Lin *et al.* [5] proposed ET-BERT, which pre-trains a Transformer on unlabelled encrypted datagrams and fine-tunes it for traffic classification. Ring *et al.* [6] surveyed network-based intrusion detection datasets and the properties that make them suitable for evaluation."));
B.push(SH("Audits of the CIC datasets"));
B.push(P("Engelen, Rimmer and Joosen [7] revisited the collection of CICIDS2017 and identified problems in flow construction and labelling. Rosay *et al.* [8] reported duplicated and miscalculated features, wrong protocol detection and inconsistent TCP termination in CICIDS2017, which led to the corrected LycoS-IDS2017 dataset. Liu *et al.* [9] reviewed CIC-IDS-2017 and CSE-CIC-IDS-2018, documented errors in attack orchestration, feature generation, documentation and labelling, argued that these errors challenge the findings of numerous publications, and released corrected labelling logic. Lanvin *et al.* [10] reported packet misordering, packet duplication and mislabelled attacks in CICIDS2017 and measured how the corrections change supervised detection results. Maseer *et al.* [11] benchmarked supervised and unsupervised algorithms on CICIDS2017 and reported accuracies above 99% for the best models. Pekar and Jozsa [12] compared detectors across the original and several refined versions of CICIDS2017 and found that random forests remain accurate regardless of dataset integrity, which can mask data flaws."));
B.push(SH("Evaluation methodology"));
B.push(P("Sommer and Paxson [13] explained why anomaly detection results in network security rarely transfer to operation, citing the cost of errors, the diversity of traffic and the difficulty of sound evaluation. Kaufman *et al.* [14] formalised leakage in data mining as information in training data that would not be available when the model is used. Pendlebury *et al.* [15] showed that temporal and spatial bias inflate malware classifiers and proposed constraints for realistic evaluation. Arp *et al.* [16] identified ten pitfalls in machine learning for security, among them sampling bias, label inaccuracy, data snooping and lab-only evaluation. Apruzzese *et al.* [17] systematised the assessment of machine-learning-based network intrusion detection and argued for evaluations that reflect operational deployment. Moczkodan and Ragab [18] re-evaluated sequence models on CICIDS2017 under random, time-based and conversation-grouped splits and found that split protocol and padding convention dominate architectural choice, with leakage-free evaluation revealing a 67-fold increase in a Transformer's false-alarm rate."));
B.push(SH("Cross-dataset generalisation"));
B.push(P("Cantone, Marrocco and Bria [19] trained four classifiers on CIC-IDS-2017, CSE-CIC-IDS2018 and two corrected variants. Same-dataset results were nearly perfect, while cross-dataset results were largely commensurate with random chance; for grouped binary detection from CIC-IDS-2017 to CSE-CIC-IDS2018 they report F_{1} between 0.26 and 0.39. On the corrected data they also found that some attacks were generated with different configurations in the two years, and that the 2018 DoS-SlowHTTPTest class consists of very few distinct records."));
B.push(...table("Summary of the reviewed literature", ["Ref.", "Year", "Approach", "Main finding", "Limitation for this project"], [
  ["[1] Sharafaldin", "2018", "Dataset generation, CICFlowMeter", "CICIDS2017 with 80+ flow features", "Random-split evaluation"],
  ["[2] Draper-Gil", "2016", "Time-related flow features", "Encrypted/VPN traffic separable", "Traffic-type classes, not attacks"],
  ["[3] Anderson", "2016", "Flow + TLS + DNS/HTTP context", "Contextual data improves malware detection", "Uses TLS fields, private data"],
  ["[4] Anderson", "2017", "Classifier comparison, label noise", "Noise and non-stationarity matter", "Private enterprise data"],
  ["[5] Lin", "2022", "Pre-trained Transformer", "Strong encrypted-traffic classification", "Not evaluated across datasets"],
  ["[6] Ring", "2019", "Dataset survey", "Dataset properties for evaluation", "No experiments on protocols"],
  ["[7] Engelen", "2021", "CICIDS2017 audit", "Flow-construction and label problems", "Effect on split protocols not studied"],
  ["[8] Rosay", "2022", "CICIDS2017 analysis", "Feature errors, LycoS-IDS2017", "Corrects data, not evaluation"],
  ["[9] Liu", "2022", "Audit of both datasets", "Orchestration and labelling errors", "Feature-level conflicts not counted"],
  ["[10] Lanvin", "2023", "CICIDS2017 corrections", "Corrections change detection results", "Single dataset, random splits"],
  ["[11] Maseer", "2021", "Algorithm benchmark", "Above 99% accuracy in-dataset", "No temporal or cross-dataset test"],
  ["[12] Pekar", "2024", "Detectors across data versions", "RF robust to integrity defects", "Temporal effects not isolated"],
  ["[13] Sommer", "2010", "Position paper", "Operational gap of anomaly detection", "No quantitative protocol study"],
  ["[14] Kaufman", "2012", "Leakage formalism", "Definition and avoidance of leakage", "Generic, not network data"],
  ["[15] Pendlebury", "2019", "Temporal/spatial bias", "Bias inflates malware detection", "Android malware, not flows"],
  ["[16] Arp", "2022", "Pitfall analysis", "Ten common pitfalls", "No flow-level quantification"],
  ["[17] Apruzzese", "2023", "SoK on ML-NIDS assessment", "Evaluate for deployment", "No CIC-specific decomposition"],
  ["[18] Moczkodan", "2026", "Sequence models, leakage-free splits", "Protocol dominates architecture", "Errors of time-aware splits not inspected"],
  ["[19] Cantone", "2024", "Cross-dataset transfer", "Transfer near chance", "No same-year reference or unit checks"],
], [1550, 650, 2200, 2350, 2276], { size: 18, leftAll: true }));
B.push(H2("2.2 Research Gap"));
B.push(P("The reviewed work establishes that the CIC datasets contain errors, that random splits can be optimistic and that cross-dataset transfer is poor. Five aspects remain open:", { keepNext: true }));
B.push(numbered("**Leakage versus chronological ordering.** No study separates, for flow-level detectors, the contribution of duplicated or correlated records from that of chronological ordering when a time-aware split lowers performance, or examines what the additional errors consist of."));
B.push(numbered("**Feature-level label conflicts.** The audits correct labels at the source, but the number of identical feature vectors that carry different labels, and the effect of duplicate-resolution policies on reported metrics, have not been quantified."));
B.push(numbered("**End-to-end attribution.** Attack-type classification is reported on ground-truth attack flows, which ignores the detection errors of a deployed two-stage system."));
B.push(numbered("**Diagnosed transfer failure.** Cross-dataset failure is reported without a same-year reference, a target-trained upper bound, a check of measurement units or an evaluation of mitigations."));
B.push(numbered("**Noise floor.** Seed variability is rarely reported, so small differences between configurations cannot be judged."));
B.push(H2("2.3 Problem Statement"));
B.push(P("Given payload-independent CICFlowMeter features, the project determines (a) how much the measured detection and attribution performance of a tree-ensemble detector on CICIDS2017 depends on the evaluation protocol, separating leakage between correlated records from the effect of chronological ordering and identifying what the additional errors consist of; (b) how duplicate records and label conflicts change the evaluated population and the reported metrics; (c) how much a hierarchical attribution stage degrades once detection errors are included; and (d) why zero-shot transfer from CICIDS2017 to CSE-CIC-IDS2018 fails and whether label-free normalisation repairs it. Every effect is judged against an explicit seed noise floor."));
B.push(H2("2.4 Objectives"));
B.push(numbered("Build an evaluation system that reproduces the baseline exactly (all metrics equal to within 10^{−9}), verifies row alignment between dataset releases (100%) and generates five split protocols, by the second week of October 2026.", "obj"));
B.push(numbered("Quantify the protocol effect with at least two seeds per protocol and five seeds for the main random-versus-chronological comparison, and classify every difference against a noise floor of 0.013.", "obj"));
B.push(numbered("Audit the false positives of the chronological split by endpoint and time, and re-score both protocols with the identified flows excluded identically.", "obj"));
B.push(numbered("Count duplicate and conflicting feature vectors per attack class, and compare four duplicate-resolution policies on a common test set.", "obj"));
B.push(numbered("Evaluate attribution in three scoring views (true attacks, flagged flows, end to end) with Wilson 95% intervals for per-class recall.", "obj"));
B.push(numbered("Run matched-family transfer from CICIDS2017 to CSE-CIC-IDS2018 with a same-year reference, a target-trained upper bound, the reverse direction and a no-deduplication control; diagnose the shift with three tests; and evaluate four label-free mitigations.", "obj"));
B.push(numbered("Keep each experiment within a 6 GB working set on a 16 GB laptop and complete the study before the final review in October 2026.", "obj"));
B.push(H2("2.5 Project Plan"));
B.push(P("Fig. 1 shows the project schedule. The first phase covered the literature survey, dataset acquisition, a flow-feature baseline and the cross-dataset and evasion tests presented at Review II. The second phase built the leakage-aware evaluation framework and ran the protocol, integrity, attribution, transfer and mitigation experiments."));
B.push(...figure("fig_gantt", "Gantt chart of the project", 600));

// ---------------- 3 TECHNICAL SPECIFICATION
B.push(H1("3. TECHNICAL SPECIFICATION"));
B.push(H2("3.1 Requirements"));
B.push(H3("3.1.1 Functional"));
[
  "**Data ingestion:** read CICFlowMeter flow records of both datasets and the timestamped CICIDS2017 release, strip column-name whitespace and repeated header rows.",
  "**Canonicalisation:** map raw labels of both years to a common vocabulary, align the 2018 feature names to the 2017 names through an alias table and remove records with missing or infinite values.",
  "**Integrity audit:** hash every feature vector, count duplicates and label conflicts per class and apply one of four resolution policies.",
  "**Split generation:** produce random, flow-identifier-grouped, time-block-grouped and per-class chronological splits (by timestamp and by row order), stratified by label.",
  "**False-positive audit:** group benign false positives by source address, destination address, destination port and hour, using identifier fields of the labelled release that are never used as features.",
  "**Hierarchical detection:** train a binary Stage-1 detector and a Stage-2 attribution model at family and fine-grained level.",
  "**Scoring:** report malicious-class F_{1}, precision, recall and benign false-positive rate, and attribution macro-F_{1} on true attacks, on flagged flows and end to end, with confusion matrices.",
  "**Statistics:** repeat configurations over seeds and report mean, standard deviation, range and Wilson intervals.",
  "**Shift diagnosis and mitigation:** verify unit identities, compute per-feature Kolmogorov–Smirnov statistics and adversarial-validation AUC, and evaluate label-free feature transformations.",
  "**Verification gates:** assert identical feature order at training and prediction, identical label encoding across datasets and exact reproduction of baseline metrics before a new data path is used.",
].forEach((t) => B.push(bullet(t)));
B.push(H3("3.1.2 Non-Functional"));
[
  "**Reproducibility:** every run records its configuration, seeds, code revision hash and dataset fingerprints; re-running a configuration reproduces its metrics exactly.",
  "**Memory bound:** each experiment stays within a 6 GB working set on a 16 GB machine; per-file cleaning before concatenation reduced the loader's peak from 8.63 GB to 4.13 GB with bit-identical output.",
  "**Integrity:** SHA-256 fingerprints of all source code, dataset files and frozen baseline results are checked after every experiment.",
  "**Robust unattended execution:** experiments run strictly one at a time with a memory guard, per-step time limits and incremental saving of every completed run.",
  "**Privacy:** no payload is read and no address or port is used as a feature; addresses are read only to audit errors.",
  "**Maintainability:** loading, auditing, splitting and scoring are shared by all experiments, so a protocol change is made in one place.",
].forEach((t) => B.push(bullet(t)));
B.push(H2("3.2 Feasibility Study"));
B.push(H3("3.2.1 Technical Feasibility"));
[
  "Both datasets are public; CICIDS2017 (0.84 GB of flow records and 0.28 GB of compressed timestamped records) and two days of CSE-CIC-IDS2018 (0.68 GB) fit on a laptop.",
  "Tree ensembles train on 1.7 million flows in about two to three minutes on an 8-core CPU, so a study of about 80 experiment runs completes in a few hours.",
  "All algorithms rely on mature open-source libraries; no GPU is required.",
  "The two CICIDS2017 releases align row for row, which makes true timestamps available for the processed flow records.",
].forEach((t) => B.push(bullet(t)));
B.push(H3("3.2.2 Economic Feasibility"));
[
  "No licence costs: the software stack is open source and the datasets are freely available.",
  "Compute cost is a few CPU-hours on an existing laptop; no cloud resources are needed.",
  "For an operator, protocol comparison together with an audit of the errors shows whether a reported false-positive rate is optimistic and whether a higher one reflects the detector or the labels, which translates into analyst workload.",
].forEach((t) => B.push(bullet(t)));
B.push(H3("3.2.3 Social Feasibility"));
[
  "The approach works on flow metadata and never decrypts traffic, which respects end-to-end confidentiality.",
  "The study creates no new attack capability; it evaluates detectors on public, documented datasets.",
  "Realistic false-positive estimates help security teams size triage effort and avoid alert fatigue.",
  "Reporting recommendations improve the comparability of published intrusion-detection results.",
].forEach((t) => B.push(bullet(t)));
B.push(H2("3.3 System Specification"));
B.push(H3("3.3.1 Hardware Specification"));
[
  "**Processor:** AMD Ryzen 7 7735HS, 8 cores, 16 threads.",
  "**Memory (RAM):** 16 GB (15.2 GB usable); peak working set per experiment 4.1–5.7 GB.",
  "**Storage:** SSD; about 1.8 GB for datasets and under 50 MB for results.",
  "**Graphics Processing Unit (GPU):** NVIDIA GeForce RTX 4050 Laptop GPU, present but not required; all training ran on the CPU.",
  "**Monitor:** standard laptop display; no special requirement.",
].forEach((t) => B.push(bullet(t)));
B.push(H3("3.3.2 Software Specification"));
[
  "**Operating System:** Microsoft Windows 11 Home (build 26200).",
  "**Programming Language:** Python 3.13.1.",
  "**Development Environment:** Visual Studio Code with Jupyter for exploration; command-line execution for experiments.",
  "**Libraries and Frameworks:** pandas 2.2.3, NumPy 2.2.6, scikit-learn 1.6.1, XGBoost 3.4.1, SciPy 1.15.3, Matplotlib 3.10.3, psutil 7.2.2.",
  "**Database:** none; flow records are columnar files processed as in-memory data frames.",
  "**Security Tools:** CICFlowMeter (feature extraction used to produce both datasets); SHA-256 hashing for integrity verification.",
].forEach((t) => B.push(bullet(t)));

// ---------------- 4 DESIGN
B.push(H1("4. DESIGN APPROACH AND DETAILS"));
B.push(H2("4.1 System Architecture"));
B.push(...figure("fig_architecture", "System architecture", 600));
B.push(P("The system is organised in six layers (Fig. 2). Each layer consumes only the outputs of the layers above it, so a change in one layer, for example a new split protocol, leaves the others untouched."));
[
  "**Data layer.** CICIDS2017 flow records (eight capture files, 2.83 million flows), the timestamped CICIDS2017 release with flow identifiers, and two days of CSE-CIC-IDS2018 (2.10 million flows).",
  "**Canonicalisation layer.** Normalises labels into raw, fine-grained and family taxonomies; aligns 2018 column names to 2017 names (75 shared statistics); removes records with missing or infinite values; and attaches true timestamps after verifying that both CICIDS2017 releases list the same flows in the same order.",
  "**Integrity-audit layer.** Hashes every feature vector, builds duplicate groups and the conflict set, applies a resolution policy, runs the equivalence gates on feature order, label encoding and loader output, and audits false positives by endpoint and time.",
  "**Evaluation-protocol layer.** Generates random, flow-identifier-grouped, time-block-grouped and per-class chronological partitions, and the matched-family cross-dataset partition.",
  "**Hierarchical-detector layer.** Stage 1 separates benign from malicious flows; Stage 2 attributes flagged flows to a family or fine-grained type; predictions are scored in three views.",
  "**Statistical-analysis layer.** Repeats configurations over seeds, computes intervals and the noise-floor rule, diagnoses dataset shift and evaluates label-free mitigation.",
].forEach((t) => B.push(bullet(t)));
B.push(H2("4.2 Design"));
B.push(H3("4.2.1 Algorithm 1: Leakage-Aware Hierarchical Evaluation"));
B.push(P("Let the dataset be D = {(**x**_{i}, y_{i}, t_{i})}, i = 1…N, with feature vector **x**_{i} of dimension d, raw label y_{i} and start time t_{i}. A 64-bit hash h(**x**) of the single-precision feature vector defines duplicate groups G_{h} = {i : h(**x**_{i}) = h} and the conflict set", { keepNext: true }));
B.push(eq([mr("C = {h : |{"), sub([mr("y")], [mr("i")]), mr(" : i ∈ "), sub([mr("G")], [mr("h")]), mr("}| ≥ 2}")]));
B.push(P("A group in C contains flows that no deterministic classifier over these features can label correctly in full. Four resolution policies are defined: drop-conflicts removes every group in C and keeps the first record of every other group; keep-first keeps the first record of every group; majority keeps one record per group with the group's most frequent label; none keeps all records."));
B.push(P("All splits are stratified by raw label with a test fraction of 0.2. For a class ℓ with n_{ℓ} records, the chronological split orders records by t_{i} (or by capture-file row order), assigns the latest n_{ℓ} − ⌊0.8 n_{ℓ}⌋ to the test set and purges the ⌊0.01 n_{ℓ}⌋ records immediately before the cut. Each class is cut at its own time, so there is no global cutoff and the split does not simulate deployment after a fixed date; a global cutoff is not feasible on CICIDS2017 because each attack occupies a single interval (Section 5.2). Grouped splits move whole groups (flow identifiers, or time blocks) to the test side until at least 0.2 n_{ℓ} records are covered, keeping at least one group in training. Time blocks are", { keepNext: true }));
B.push(eq([sub([mr("b")], [mr("i")]), mr(" = ⌊ "), frac([sub([mr("t")], [mr("i")])], [mr("60 W")]), mr(" ⌋,   W ∈ {1, 5, 15} minutes")]));
B.push(P("The hierarchical prediction combines a binary detector f_{1} and an attribution model f_{2} trained on malicious flows only:", { keepNext: true }));
B.push(eq([mr("ŷ(x) = "), sub([mr("f")], [mr("2")]), mr("(x)  if  "), sub([mr("f")], [mr("1")]), mr("(x) = 1;   ŷ(x) = Benign  otherwise")]));
B.push(P("Attribution is scored with macro-averaged F_{1} over the class set K and detection with the benign false-positive rate:", { keepNext: true }));
B.push(eq([mr("Macro-"), sub([mr("F")], [mr("1")]), mr(" = "), frac([mr("1")], [mr("|K|")]), new MathSum({ children: [sub([mr("F")], [mr("1,k")])], subScript: [mr("k∈K")] }), mr(",   "),
  sub([mr("F")], [mr("1,k")]), mr(" = "), frac([mr("2 "), sub([mr("P")], [mr("k")]), mr(" "), sub([mr("R")], [mr("k")])], [sub([mr("P")], [mr("k")]), mr(" + "), sub([mr("R")], [mr("k")])])]));
B.push(eq([mr("FPR = "), frac([mr("FP")], [mr("FP + TN")])]));
B.push(P("A proportion p̂ = k/n receives a Wilson 95% interval (z = 1.96):", { keepNext: true }));
B.push(eq([frac([mr("p̂ + "), frac([sup([mr("z")], [mr("2")])], [mr("2n")]), mr(" ± z"), sqrt([frac([mr("p̂(1 − p̂)")], [mr("n")]), mr(" + "), frac([sup([mr("z")], [mr("2")])], [mr("4"), sup([mr("n")], [mr("2")])])])],
  [mr("1 + "), frac([sup([mr("z")], [mr("2")])], [mr("n")])])]));
B.push(P("The noise floor σ = 0.013 is the largest model-seed standard deviation among headline metrics (family macro-F_{1} under the row-order chronological split, five seeds). A difference Δ between configurations a and b is called material when", { keepNext: true }));
B.push(eq([mr("|Δ| > max(0.013, 2"), sqrt([sup([sub([mr("s")], [mr("a")])], [mr("2")]), mr(" + "), sup([sub([mr("s")], [mr("b")])], [mr("2")])]), mr(")")]));
B.push(...algorithm("Algorithm 1. Leakage-aware hierarchical evaluation", [
  { t: "**Input:** flows D, policy π, protocol P, seeds S.  **Output:** metrics per scoring view with seed variability." },
  { t: "Remove records with missing or infinite feature values." },
  { t: "Compute h(**x**_{i}) for every record; build groups G_{h} and the conflict set C." },
  { t: "D_{π} ← Resolve(D, C, π)." },
  { t: "**for** each seed s in S **do**" },
  { t: "(T_{train}, T_{test}) ← P(D_{π}, s), stratified 80/20 per label.", indent: 1 },
  { t: "Assert that the feature order of T_{test} equals that of T_{train}.", indent: 1 },
  { t: "Train f_{1} on T_{train}; train f_{2} on the malicious part of T_{train}.", indent: 1 },
  { t: "Score f_{1}: malicious F_{1}, precision, recall, benign FPR, confusion matrix.", indent: 1 },
  { t: "Score f_{2} on true attacks, on flows flagged by f_{1} and end to end.", indent: 1 },
  { t: "**end for**" },
  { t: "**return** mean, standard deviation and range over S; Wilson intervals per class." },
]));
B.push(P("Steps 2–4 make every later comparison independent of how duplicates were handled, because the policy is applied once and recorded. The assertion in step 7 rules out a silent column permutation, which would otherwise produce a collapse that looks like dataset shift. Scoring in step 10 separates the quality of the attribution model from the errors it inherits from the detector."));
B.push(P("The endpoint audit inspects the errors of a protocol. Addresses and ports are never features, but the labelled release retains them. Benign test flows predicted malicious are grouped by source address, destination address, destination port and hour; endpoint sets that collect most of the false positives are recorded, and the false-positive rate is recomputed with the benign flows on those sets removed from every protocol's test set alike. With A the union of the sets and B the benign test flows,", { keepNext: true }));
B.push(eq([sub([mr("FPR")], [mr("A")]), mr(" = "), frac([mr("|{ i ∈ B \\ A : "), sub([mr("f")], [mr("1")]), mr("("), sub([mr("x")], [mr("i")]), mr(") = 1 }|")], [mr("| B \\ A |")])]));
B.push(P("Attack-labelled flows are never removed. Because the sets are identified from the errors they explain, the audited metrics describe what the errors consist of; they are not a corrected benchmark."));
B.push(H3("4.2.2 Algorithm 2: Shift Diagnosis and Label-Free Mitigation"));
B.push(P("The transfer study restricts both datasets to the families present in the two 2018 days (Benign, DoS/DDoS and Web Attack), trains on the training partition of the CICIDS2017 row-order chronological split and scores on the matching CICIDS2017 test partition and on all 2018 flows. If flow duration D is measured in microseconds and rates per second, the CICFlowMeter definitions imply three identities, where B and P are byte and packet totals in the forward (f) and backward (b) directions, R_{b} and R_{p} the byte and packet rates and μ_{IAT} the mean inter-arrival time:", { keepNext: true }));
B.push(eq([frac([mr("D "), sub([mr("R")], [mr("b")])], [sub([mr("B")], [mr("f")]), mr(" + "), sub([mr("B")], [mr("b")])]), mr(" = "), sup([mr("10")], [mr("6")]), mr(",   "),
  frac([mr("D "), sub([mr("R")], [mr("p")])], [sub([mr("P")], [mr("f")]), mr(" + "), sub([mr("P")], [mr("b")])]), mr(" = "), sup([mr("10")], [mr("6")]), mr(",   "),
  frac([sub([mr("μ")], [mr("IAT")]), mr(" ("), sub([mr("P")], [mr("f")]), mr(" + "), sub([mr("P")], [mr("b")]), mr(" − 1)")], [mr("D")]), mr(" = 1")]));
B.push(P("A change of units between tool versions would violate these ratios in one dataset. Per-feature shift between years for a matched class is measured with the two-sample Kolmogorov–Smirnov statistic,", { keepNext: true }));
B.push(eq([sub([mr("D")], [mr("KS")]), mr(" = "), sub([mr("sup")], [mr("x")]), mr(" | "), sub([mr("F̂")], [mr("2017")]), mr("(x) − "), sub([mr("F̂")], [mr("2018")]), mr("(x) |")]));
B.push(P("and joint separability with adversarial validation: a random forest trained to tell 2017 records from 2018 records, scored by its held-out area under the ROC curve. The share of the transfer gap recovered by a transformation T is", { keepNext: true }));
B.push(eq([mr("G(T) = "), frac([sub([mr("F")], [mr("cross")]), mr("(T) − "), sub([mr("F")], [mr("cross")]), mr("(∅)")], [sub([mr("F")], [mr("ref")]), mr("(∅) − "), sub([mr("F")], [mr("cross")]), mr("(∅)")])]));
B.push(...algorithm("Algorithm 2. Shift diagnosis and label-free mitigation", [
  { t: "**Input:** source D_{2017}, target D_{2018}, shared families F." },
  { t: "Align features through the alias table; map labels of both years to F." },
  { t: "**for** class c in {Benign, DoS Hulk} and each year **do**" },
  { t: "Verify the three unit identities on records with D > 0.", indent: 1 },
  { t: "**end for**" },
  { t: "Compute D_{KS}(j, c) for every feature j and class c on 100 000-row samples." },
  { t: "Compute adversarial-validation AUC for all records, for Benign and for DoS Hulk." },
  { t: "**for** T in {none, signed log, robust scaling, quantile mapping, drop 10, drop 25} **do**" },
  { t: "Fit T on the 2017 training partition and, separately, on unlabelled 2018 data.", indent: 1 },
  { t: "Train f_{1} and f_{2} on T(D_{2017}^{train}).", indent: 1 },
  { t: "Score on T(D_{2017}^{test}) and T(D_{2018}); compute G(T).", indent: 1 },
  { t: "**end for**" },
]));
B.push(P("The transformations are the signed logarithm sgn(x)·log(1 + |x|), per-dataset robust scaling (x − median)/IQR, per-dataset quantile mapping to the uniform distribution, and removal of the 10 or 25 features with the largest D_{KS} between 2017 training data and unlabelled 2018 data. None of them uses 2018 labels; because 2018 statistics are computed on all 2018 flows, they are transductive. Three controls complete the design: a model trained and tested on 2018 (upper bound), the reverse direction from 2018 to 2017, and scoring of the 2018 data without deduplication."));

// ---------------- 5 EXPERIMENTAL SETUP AND OUTPUT
B.push(H1("5. EXPERIMENTAL SETUP AND OUTPUT"));
B.push(H2("5.1 Experimental Setup"));
B.push(P(`Table 2 lists the data after cleaning. Identifiers and topology-dependent fields (flow identifier, IP addresses, ports, protocol and timestamp) and flow duration are excluded from the features, leaving 76 statistics for CICIDS2017 and 75 statistics shared with CSE-CIC-IDS2018. The 2017 timestamps use a 12-hour clock without an AM/PM marker; hours below 8 were shifted by 12 hours (${big(N.exp004.pm_corrected_rows)} records), after which all records fall between 08:42 and 17:10. The two CICIDS2017 releases agree on flow duration, forward packet count and label for 100% of rows in all eight files.`));
B.push(...table("Datasets after cleaning", ["Item", "CICIDS2017", "CSE-CIC-IDS2018 (2 days)"], [
  ["Raw flows", big(d17.rows_raw), big(e3.load_2018.rows_raw)],
  ["After removing NaN/±Inf", big(d17.rows_after_nan_inf), big(e3.load_2018.rows_after_nan_inf_drop)],
  ["Unique feature vectors", big(d17.unique_vectors), big(e3.conflicts_2018.unique_feature_rows)],
  ["Exact-duplicate share", pct(d17.duplicate_rate), pct(e3.conflicts_2018.duplicate_rate_keep_first)],
  ["Conflicting vectors (rows)", `${d17.conflicting_groups} (${big(d17.rows_in_conflicting_groups)})`, `${e3.conflicts_2018.conflicting_groups} (${e3.conflicts_2018.rows_in_conflicting_groups})`],
  ["Records after drop-conflicts", big(d17.rows_after_dedup), "1,420,219"],
  ["Features used", "76", "75 (aligned)"],
], [3400, 2813, 2813]));
B.push(P(`Fine-grained attribution keeps every raw attack label with at least 500 records after deduplication, giving 12 attack classes; SQL injection (21 records), Infiltration (36) and Heartbleed (11) are merged into Other/Rare. The family taxonomy has six attack classes: DoS/DDoS, PortScan, Brute Force, Web Attack, Bot and Other/Rare. Under the default split the training set holds ${big(d17.split_rows.train_rows)} records and the test set ${big(d17.split_rows.test_rows)}, with ${big(d17.split_rows.purged_rows)} records purged at the boundary. Table 3 gives the model settings and Table 4 the experiment matrix.`));
B.push(...table("Model configuration", ["Component", "Setting"], [
  ["Stage 1 and Stage 2 (primary)", "Random forest, 100 trees, maximum depth 20, balanced class weights"],
  ["Stage 1 and Stage 2 (robustness)", "XGBoost, 300 trees, depth 6, learning rate 0.1, histogram method, positive-class weight = class ratio"],
  ["Feature scaling", "None (tree models are invariant to monotone scaling)"],
  ["Test fraction / purge", "0.2 per label / 1% of each label before the cut (chronological splits)"],
  ["Noise floor", "0.013 (SD of family macro-F_{1}, row-order chronological split, 5 model seeds)"],
], [3000, 6026], { leftAll: true }));
B.push(...table("Experiment matrix", ["Exp.", "Question", "Factor varied", "Runs", "Time", "Peak RAM"], [
  ["E1", "Baseline", "Random vs row-order split", "2", "7 min", "–"],
  ["E2", "Seed variability", "Split seed, model seed", "14", "35 min", "8.6 GB"],
  ["E3", "Matched-family transfer", "Train 2017, test 2017/2018", "5 seeds", "17 min", "≥ 5.6 GB"],
  ["E4", "Leakage vs chronological ordering", "Five split protocols", "14", "27 min", "4.4 GB"],
  ["E5", "Duplicate policies", "Four policies, common test set", "9", "21 min", "5.5 GB"],
  ["E6", "Shift diagnosis", "Identities, KS, adversarial AUC", "1", "5 min", "5.7 GB"],
  ["E7", "Mitigation and controls", "Six transforms, upper bound, reverse", "30", "57 min", "5.5 GB"],
  ["E8", "Test-set deduplication", "Three 2018 test populations", "3 seeds", "8 min", "–"],
  ["E9", "Split composition", "Time windows; global cutoffs", "–", "2 min", "–"],
  ["E10", "False-positive audit", "Endpoint sets excluded or kept", "2", "4 min", "–"],
], [700, 2000, 2700, 1100, 1100, 1426]));
B.push(P("Before any new data path was used, its output was required to reproduce the baseline metrics exactly; the memory-bounded loader passed this gate with all data statistics and five F_{1} values identical. Every experiment asserts that its population matches the one it is compared with, for example that the 2018 test set of E6 and E7 equals that of E3."));

B.push(H2("5.2 Output of the Proposed System"));
B.push(SH("Integrity audit"));
B.push(P(`Of the ${big(d17.rows_after_nan_inf)} valid CICIDS2017 records, ${big(d17.unique_vectors)} are unique feature vectors. The conflict set contains ${d17.conflicting_groups} vectors covering ${big(d17.rows_in_conflicting_groups)} rows, and every conflicting vector is labelled benign in at least one occurrence (Table 5). PortScan's 76,265 conflicting rows stem from only 106 distinct vectors; the largest single group holds ${big(d17.largest_conflict_group_rows)} rows. Duplication is concentrated in specific classes (Fig. 3): 98.8% of PortScan rows and 100.0% of 2018 SlowHTTPTest rows are duplicates, against 0.0% of DDoS rows.`));
B.push(...table("Label conflicts in CICIDS2017 by attack label", ["Label", "Conflicting vectors", "Rows in conflicting groups"], [
  ["BENIGN (all groups)", "309", big(d17.conflict_rows_by_label.BENIGN)],
  ["DoS Hulk", "158", big(d17.conflict_rows_by_label["DoS Hulk"])],
  ["PortScan", "106", big(d17.conflict_rows_by_label.PortScan)],
  ["Bot", "40", big(d17.conflict_rows_by_label.Bot)],
  ["DDoS", "3", big(d17.conflict_rows_by_label.DDoS)],
  ["DoS slowloris", "2", big(d17.conflict_rows_by_label["DoS slowloris"])],
], [3600, 2713, 2713]));
B.push(...figure("fig_duplication", "Share of rows that are exact feature-vector duplicates, per raw label (row counts in parentheses)", 600));
B.push(SH("Split protocols"));
B.push(P("Table 6 and Fig. 4 compare the five protocols. The decomposition of the chronological-split drop into precision, recall and false-positive rate is shown in Fig. 5, and per-attack recall in Fig. 6."));
const sp = (s) => e4[s];
B.push(...table("Detection and attribution under five split protocols (mean of 2 seeds)", ["Protocol", "Mal. F_{1}", "Precision", "Recall", "Benign FPR", "Family F_{1} (GT)", "Family F_{1} (E2E)"],
  [["Random", "random"], ["Flow-ID grouped", "flowid"], ["1-min blocks", "block1"], ["5-min blocks", "block5"], ["15-min blocks", "block15"], ["Chronological (timestamps)", "forward"], ["Chronological (row order)", "roworder"]]
    .map(([l, s]) => [l, f4(sp(s).mal_f1.mean), f4(sp(s).mal_precision.mean), f4(sp(s).mal_recall.mean), sp(s).benign_fpr_pct.mean.toFixed(3) + "%", f3(sp(s).fam_gt.mean), f3(sp(s).fam_e2e.mean)]),
  [2000, 1050, 1050, 1050, 1200, 1338, 1338]));
B.push(...figure("fig_splits", "Detection and attribution under five split protocols; markers show the mean of two seeds and lines the range", 600));
B.push(...figure("fig_decomp", "Stage-1 precision and recall (left) and benign false-positive rate (right)", 430));
B.push(...figure("fig_class_recall", "Stage-1 recall per attack under three protocols (mean and range over two seeds)", 430));
B.push(P(`The five-seed replication confirms the size of the effect: under row order, malicious F_{1} is ${f4(e2.roworder_modelseed.mal_f1.mean)} ± ${f4(e2.roworder_modelseed.mal_f1.sd)} against ${f4(e2.random_modelseed.mal_f1.mean)} ± ${f4(e2.random_modelseed.mal_f1.sd)} under the random split, and family macro-F_{1} on true attacks ${f3(e2.roworder_modelseed.fam_gt.mean)} ± ${f3(e2.roworder_modelseed.fam_gt.sd)} against ${f3(e2.random_modelseed.fam_gt.mean)} ± ${f3(e2.random_modelseed.fam_gt.sd)}. Row order is chronological in the Thursday and Friday files (Spearman ρ ≈ 1.00) but not in the Monday, Tuesday and Wednesday files (ρ = 0.48, 0.47 and 0.66); even so, the row-order and timestamp chronological splits share 86% of their test flows and differ by at most 0.011 on any headline metric. DoS Hulk, whose test flows cover the last 11 minutes of its 24-minute attack interval, accounts for ${pct(N.exp004.forward_missed.seed42.hulk_share, 0)} of the missed attack flows (${big(N.exp004.forward_missed.seed42.by_label["DoS Hulk"])} of ${big(N.exp004.forward_missed.seed42.total)}, seed 42).`));
const e9 = N.exp009, x10 = N.exp010, fw10 = x10.forward, rn10 = x10.random;
B.push(SH("Time composition of the chronological split"));
B.push(P(`Each class is cut at its own time, so training flows of one class can be later than test flows of another. ${pct(e9.test_with_later_train_frac, 0)} of chronological test flows have at least one later training flow. The benign test flows run from Thursday 16:23 to Friday 17:02 (${pct(e9.benign_test_window.by_day["2017-07-07"] / e9.benign_test_window.n, 0)} on Friday), while ${big(e9.attack_train_in_benign_test_window)} of the ${big(e9.attack_train_total)} attack training flows (${pct(e9.attack_train_in_benign_test_window / e9.attack_train_total, 0)}; DDoS, PortScan and Bot) fall inside that period. A single global cutoff is not feasible: for cutoffs at the 50th to 90th percentiles of capture time at most two of the 14 attack classes have flows on both sides, and a cutoff at the start of Friday leaves none (11 classes only in training; Bot, DDoS and PortScan only in test).`));
B.push(SH("Endpoint audit of false positives"));
B.push(P(`Of the ${big(fw10.benign_fp)} benign false positives of the timestamp chronological split (seed 42; both protocols reproduce the stored results exactly), ${big(fw10.fp_on_ddos_pair)} (${pct(fw10.fp_on_ddos_pair / fw10.benign_fp, 1)}) lie on the pair formed by the DDoS victim 192.168.10.50 and the attacker address 172.16.0.1, and ${big(fw10.fp_on_bot_cc)} (${pct(fw10.fp_on_bot_cc / fw10.benign_fp, 1)}) on the Bot command-and-control (C&C) channel to 205.174.165.73, port 8080 (Table 7, Fig. 7).`));
B.push(bullet(`**Attacker–victim pair.** All but 3 of the ${big(N.data_2017.label_support_after_dedup.DDoS)} DDoS-labelled flows run from the attacker to the victim, and every DDoS test flow is addressed to port 80. The ${big(fw10.fp_on_ddos_pair_pred_ddos)} benign flows labelled DDoS by Stage 2 run in the opposite direction, from the victim to ports at or above 1024 of the attacker (${pct(fw10.fp_to_ddos_dst_port_ge_1024_frac)}), and ${big(fw10.fp_to_ddos_in_ddos_interval)} of them were recorded inside the labelled DDoS interval, 15:56–16:16 on Friday. Inside that interval the benign false-positive rate is ${pct(fw10.benign_fpr_inside_ddos_interval, 1)}; outside it, ${pct(fw10.benign_fpr_outside_ddos_interval)}.`));
B.push(bullet(`**Bot C&C channel.** ${big(fw10.fp_on_bot_cc_pred_bot)} of the ${big(fw10.fp_by_predicted_fine.Bot)} benign flows labelled Bot go from five internal hosts to 205.174.165.73 on port 8080, the hosts, address and port of all 280 Bot-labelled test flows. The last Bot-labelled flow was recorded at 12:59 on Friday; all but one of these benign flows were recorded between 13:00 and 17:00.`));
B.push(bullet(`**Mechanism.** The random split keeps about 80% of these flows in training under their benign labels and learns them (${rn10.fp_on_ddos_pair} false positives among ${big(rn10.benign_on_ddos_pair)} benign test flows on the pair). The chronological split places all of them in test, because they are the latest benign flows, while the matching attack flows remain in training. Over the five row-order seeds, flows assigned to DDoS make up ${pct(N.exp002.ddos_fp_share.roworder.min, 1)}–${pct(N.exp002.ddos_fp_share.roworder.max, 1)} of benign false positives, against ${pct(N.exp002.ddos_fp_share.random.min, 1)}–${pct(N.exp002.ddos_fp_share.random.max, 1)} under random splits.`));
const pr = (d) => `${f3(d.precision)} / ${f3(d.recall)}`;
B.push(...table("Endpoint audit of benign false positives (seed 42)", ["Quantity", "Random split", "Chronological split"], [
  ["Benign test flows", big(rn10.benign_test_flows), big(fw10.benign_test_flows)],
  ["   on attacker–victim pair", big(rn10.benign_on_ddos_pair), big(fw10.benign_on_ddos_pair)],
  ["   on Bot C&C channel", big(rn10.benign_on_bot_cc), big(fw10.benign_on_bot_cc)],
  ["Benign false positives", big(rn10.benign_fp), big(fw10.benign_fp)],
  ["   on attacker–victim pair", big(rn10.fp_on_ddos_pair), big(fw10.fp_on_ddos_pair)],
  ["   on Bot C&C channel", big(rn10.fp_on_bot_cc), big(fw10.fp_on_bot_cc)],
  ["   elsewhere", big(rn10.fp_other), big(fw10.fp_other)],
  ["Benign FPR, all benign flows", (100 * rn10.stage1_all.fpr).toFixed(3) + "%", (100 * fw10.stage1_all.fpr).toFixed(3) + "%"],
  ["Benign FPR, both sets removed (Wilson 95%)", `${(100 * rn10.stage1_excl_both_benign.fpr).toFixed(3)}% [${(100 * rn10.stage1_excl_both_benign.fpr_ci95[0]).toFixed(3)}, ${(100 * rn10.stage1_excl_both_benign.fpr_ci95[1]).toFixed(3)}]`,
    `${(100 * fw10.stage1_excl_both_benign.fpr).toFixed(3)}% [${(100 * fw10.stage1_excl_both_benign.fpr_ci95[0]).toFixed(3)}, ${(100 * fw10.stage1_excl_both_benign.fpr_ci95[1]).toFixed(3)}]`],
  ["Precision / recall, both sets removed", pr(rn10.stage1_excl_both_benign), pr(fw10.stage1_excl_both_benign)],
  ["Malicious F_{1}, all / both sets removed", `${f3(rn10.stage1_all.f1)} / ${f3(rn10.stage1_excl_both_benign.f1)}`, `${f3(fw10.stage1_all.f1)} / ${f3(fw10.stage1_excl_both_benign.f1)}`],
], [4026, 2500, 2500], { leftAll: false }));
B.push(...figure("fig_fp", "Benign false-positive rate of the random and chronological splits (seed 42): (a) all benign test flows, divided by the endpoint set of each false positive; (b) after removing benign flows on both endpoint sets from both test sets, with Wilson 95% intervals", 430));
B.push(P(`With the benign flows on both endpoint sets removed from both test sets, the false-positive rate is ${(100 * fw10.stage1_excl_both_benign.fpr).toFixed(3)}% under both protocols and precision is ${f3(fw10.stage1_excl_both_benign.precision)} for both. The malicious-F_{1} gap falls from ${f3(x10.f1_gap_all)} to ${f3(x10.f1_gap_excl)}, which still exceeds the noise floor and consists entirely of the recall difference (${f3(fw10.stage1_excl_both_benign.recall)} against ${f3(rn10.stage1_excl_both_benign.recall)}). The flows match the endpoints and times of the attacks and differ from them in direction or in time after the label window, which is consistent with the flow-construction and labelling defects reported for CICIDS2017 [7], [10]. The endpoint sets were identified from the errors they explain, so these figures are a diagnostic of one seed per protocol, not a corrected benchmark.`));
B.push(SH("Duplicate-resolution policies"));
const e5 = N.exp005;
B.push(...table("Duplicate-resolution policies (random forest, one seed; chronological = row-order chronological split)", ["Split", "Policy / test set", "n test", "Mal. F_{1}", "Benign FPR", "Family F_{1}"], [
  ["Random", "drop-conflicts / common", big(e5.random_drop_conflicts_model42.common_test.n_test), f4(e5.random_drop_conflicts_model42.common_test.mal_f1), e5.random_drop_conflicts_model42.common_test.benign_fpr_pct.toFixed(3) + "%", f3(e5.random_drop_conflicts_model42.common_test.fam_gt)],
  ["Random", "keep-first / common", big(e5.random_keep_first_model42.common_test.n_test), f4(e5.random_keep_first_model42.common_test.mal_f1), e5.random_keep_first_model42.common_test.benign_fpr_pct.toFixed(3) + "%", f3(e5.random_keep_first_model42.common_test.fam_gt)],
  ["Random", "majority / common", big(e5.random_majority_model42.common_test.n_test), f4(e5.random_majority_model42.common_test.mal_f1), e5.random_majority_model42.common_test.benign_fpr_pct.toFixed(3) + "%", f3(e5.random_majority_model42.common_test.fam_gt)],
  ["Random", "none / common", big(e5.random_none_model42.common_test.n_test), f4(e5.random_none_model42.common_test.mal_f1), e5.random_none_model42.common_test.benign_fpr_pct.toFixed(3) + "%", f3(e5.random_none_model42.common_test.fam_gt)],
  ["Random", "none, row-level split / own", big(e5.random_none_rowsplit_model42.own_test.n_test), f4(e5.random_none_rowsplit_model42.own_test.mal_f1), e5.random_none_rowsplit_model42.own_test.benign_fpr_pct.toFixed(3) + "%", f3(e5.random_none_rowsplit_model42.own_test.fam_gt)],
  ["Chronological", "drop-conflicts / common", big(e5.temporal_drop_conflicts_model42.common_test.n_test), f4(e5.temporal_drop_conflicts_model42.common_test.mal_f1), e5.temporal_drop_conflicts_model42.common_test.benign_fpr_pct.toFixed(3) + "%", f3(e5.temporal_drop_conflicts_model42.common_test.fam_gt)],
  ["Chronological", "keep-first / common", big(e5.temporal_keep_first_model42.common_test.n_test), f4(e5.temporal_keep_first_model42.common_test.mal_f1), e5.temporal_keep_first_model42.common_test.benign_fpr_pct.toFixed(3) + "%", f3(e5.temporal_keep_first_model42.common_test.fam_gt)],
  ["Chronological", "majority / common", big(e5.temporal_majority_model42.common_test.n_test), f4(e5.temporal_majority_model42.common_test.mal_f1), e5.temporal_majority_model42.common_test.benign_fpr_pct.toFixed(3) + "%", f3(e5.temporal_majority_model42.common_test.fam_gt)],
  ["Chronological", "none / common", big(e5.temporal_none_model42.common_test.n_test), f4(e5.temporal_none_model42.common_test.mal_f1), e5.temporal_none_model42.common_test.benign_fpr_pct.toFixed(3) + "%", f3(e5.temporal_none_model42.common_test.fam_gt)],
], [1700, 2500, 1200, 1200, 1200, 1226]));
B.push(P(`A naive row-level random split without deduplication leaves an exact duplicate in training for ${pct(e5.random_none_rowsplit_model42.straddle)} of test rows, yet malicious F_{1} differs from the hash-group split by only +0.0014; PortScan test support, however, grows from 370 to 31,761 rows.`));
B.push(SH("Hierarchical attribution"));
B.push(...figure("fig_hierarchy", "Family F_{1} of Stage 2 on true attacks only and end to end through Stage 1 (five seeds)", 430));
const hr = e2.hierarchy;
B.push(P(`Under the random split, Bot attribution reaches F_{1} ${f3(hr.random.Bot.gt_f1)} on true attacks and ${f3(hr.random.Bot.e2e_f1)} end to end; for seed 42 all ${rn10.fp_on_bot_cc_pred_bot} benign flows assigned to Bot lie on the C&C channel. Under the row-order chronological split the end-to-end value falls to ${f3(hr.roworder.Bot.e2e_f1)} with precision ${f3(hr.roworder.Bot.e2e_precision)}, and DoS/DDoS falls from ${f3(hr.roworder["DoS/DDoS"].gt_f1)} to ${f3(hr.roworder["DoS/DDoS"].e2e_f1)}; these false positives are the benign-labelled flows on the two endpoint sets of Table 7. Within the web-attack family, brute force and cross-site scripting reach fine-grained F_{1} of only ${f3(e2.fine_f1.random["Web Attack - Brute Force"].mean)} and ${f3(e2.fine_f1.random["Web Attack - XSS"].mean)} even under the random split.`));
B.push(SH("Cross-dataset transfer"));
const r7 = (k) => e7[k];
B.push(...table("Matched-family transfer (random forest)", ["Train → test", "Seeds", "E2E macro-F_{1}", "DoS recall", "Web recall", "Benign FPR"], [
  ["2017 → 2017", "5", `${f3(e3.reference.e2e.mean)} ± ${f3(e3.reference.e2e.sd)}`, f3(e3.reference["recall_DoS/DDoS"].mean), f3(e3.reference["recall_Web Attack"].mean), e3.reference.benign_fpr_pct.mean.toFixed(3) + "%"],
  ["2017 → 2018", "5", `${f3(e3.cross.e2e.mean)} ± ${f3(e3.cross.e2e.sd)}`, f4(e3.cross["recall_DoS/DDoS"].mean), f3(e3.cross["recall_Web Attack"].mean), e3.cross.benign_fpr_pct.mean.toFixed(3) + "%"],
  ["2017 → 2018, no deduplication", "3", `${f3(e8.none.e2e.mean)} ± ${f3(e8.none.e2e.sd)}`, f4(e8.none.dos.mean), "0.000", "0.011%"],
  ["2018 → 2018", "3", `${f3(r7("upper2018_rf").e2e.mean)} ± ${f3(r7("upper2018_rf").e2e.sd)}`, f3(r7("upper2018_rf").dos.mean), f3(r7("upper2018_rf").web.mean), r7("upper2018_rf").fpr_pct.mean.toFixed(4) + "%"],
  ["2018 → 2017", "1", f3(r7("reverse_none_rf").e2e.mean), f3(r7("reverse_none_rf").dos.mean), f3(r7("reverse_none_rf").web.mean), r7("reverse_none_rf").fpr_pct.mean.toFixed(3) + "%"],
], [2600, 800, 1650, 1300, 1300, 1376]));
B.push(...figure("fig_cross", "Matched-family recall and end-to-end macro-F_{1} for the same-year reference, zero-shot transfer and a target-trained model", 430));
B.push(...figure("fig_confusion", "Row-normalised end-to-end confusion matrices (seed 42)", 430));
B.push(SH("Shift diagnosis"));
const ui = e6.unit_identities;
B.push(...table("Unit identities (median over records with positive duration)", ["Dataset / class", "D·R_{b}/(B_{f}+B_{b})", "D·R_{p}/(P_{f}+P_{b})", "μ_{IAT}(P−1)/D", "Median duration"], Object.entries(ui).map(([k, v]) => [
  k.replace("/", " / "), v.duration_x_bytes_rate_over_bytes.median.toExponential(3), v.duration_x_pkt_rate_over_pkts.median.toExponential(3), v["iat_mean_x_(pkts-1)_over_duration"].median.toFixed(3), (v.flow_duration_median / 1e6).toFixed(3) + " s"]),
  [2300, 1800, 1800, 1550, 1576]));
B.push(...figure("fig_shift", "Kolmogorov–Smirnov statistic between years for the 14 most shifted DoS-Hulk features and the benign statistic for the same features", 430));
B.push(P(`Adversarial validation separates the two years with AUC ${e6.adversarial_auc["all_2017_vs_all_2018 (label-free)"].toFixed(4)} on all records and ${e6.adversarial_auc["benign_2017_vs_benign_2018"].toFixed(4)} on benign records alone. For DoS Hulk, ${e6.n_ks_gt_05.dos_hulk} of 75 features have D_{KS} > 0.5 (maximum 0.911); for benign traffic none exceeds 0.445. In 2018, 82.3% of Hulk flows carry no backward payload against 9.5% in 2017, the median backward initial window changes from 235 to −1, and the median duration falls from 86.4 s to 0.051 s.`));
B.push(SH("Label-free mitigation"));
const T = [["None", "none"], ["Signed logarithm", "slog"], ["Robust scaling", "robust_domain"], ["Quantile mapping", "quantile_domain"], ["Drop 10 shifted features", "drop_k10"], ["Drop 25 shifted features", "drop_k25"]];
B.push(...table("Transfer after label-free transformations (2017 → 2018)", ["Transformation", "RF E2E F_{1} (3 seeds)", "RF gap recovered", "XGB E2E F_{1} (1 seed)", "XGB gap recovered"],
  T.map(([l, t]) => [l, `${f3(e7[t + "_rf"].cross_e2e.mean)}`, `${e7[t + "_rf"].gap_recovered_pct.toFixed(1)}%`, f3(e7[t + "_xgb"].cross_e2e.mean), `${e7[t + "_xgb"].gap_recovered_pct.toFixed(1)}%`]),
  [2700, 1650, 1550, 1650, 1476]));
B.push(...figure("fig_mitigation", "End-to-end macro-F_{1} on 2018 after label-free transformations", 430));

// ---------------- 6 RESULT ANALYSIS
B.push(H1("6. RESULT ANALYSIS"));
B.push(P("**Leakage versus chronological ordering.** Grouping by flow identifier changes malicious F_{1} by −0.0002, grouping into 1-, 5- and 15-minute blocks by −0.0039, −0.0013 and −0.0012, and removing exact duplicates by 0.0014; all are within the noise floor. Moving from interleaved blocks to the timestamp chronological split lowers malicious F_{1} by 0.089–0.092, family macro-F_{1} on true attacks by 0.116–0.133 and end-to-end family macro-F_{1} by 0.113–0.153, seven to eleven times the noise floor. Duplicated and correlated records therefore explain little of the random-split optimism on CICIDS2017. PortScan is the exception: its recall drops from 0.993 to 0.830 under 5-minute grouping and stays at 0.826 under the chronological split, so its high random-split score is an adjacency effect."));
B.push(P("**Precision, not recall.** Under the chronological split precision falls from 0.996 to 0.856 and recall from 0.997 to 0.956. Holding recall at its random-split value, the observed precision alone gives F_{1} = 0.921; holding precision, the observed recall alone gives 0.976. The benign false-positive rate rises about 44-fold (2.92% against 0.066% over five seeds)."));
B.push(P("**What the chronological split measures.** A 44-fold rise in false positives under a time-aware split would ordinarily be read as drift. The audit shows that 98.8% of the false positives are benign-labelled flows of two attack sessions, which a random split learns from training data and a per-class chronological split moves into the test set. On this dataset the split acts mainly as an audit of labels. After the audit the false-positive rates coincide (0.037%), and the residual effect is a recall loss of 0.040, 85% of it in the last 11 minutes of DoS Hulk; whether that loss reflects a change in the attack tool or another labelling effect was not examined."));
B.push(P("**Integrity.** Duplicate-resolution policy changes binary detection by less than 0.004 on a common test set, which agrees with the observation of Pekar and Jozsa [12] that random forests tolerate integrity defects. The policy does change the evaluated population, most visibly for PortScan, so it must be reported."));
B.push(P("**Attribution.** End-to-end attribution is lower than ground-truth attribution for every family, and the gap is largest for small classes that receive benign false positives (Bot 1.000 → 0.411). On CICIDS2017 those false positives include label defects, which end-to-end scoring exposes and ground-truth scoring hides."));
B.push(P("**Transfer.** The 2017 → 2018 collapse is reproduced over five seeds, survives scoring of all 2.09 million 2018 rows, holds in the reverse direction and for XGBoost, and is not caused by a unit mismatch. The features suffice within each year (2018 → 2018 DoS recall 1.000). The DoS-Hulk traffic of the two years differs on the backward-direction features that separate Hulk from benign traffic in 2017, and the four label-free transformations recover at most 0.5% of the gap with random forests. These diagnostics are correlational: they are consistent with a change in the attack traffic but do not establish which features cause the failure."));
B.push(H2("6.1 Comparison with Existing Systems"));
B.push(P("Table 12 compares the outputs of this work with published results and with the project's Review II baseline. The settings differ (feature sets, attack subsets, models), so the comparison is about evaluation coverage and the direction of the findings rather than a ranking of detectors."));
B.push(...table("Comparison with existing systems", ["Aspect", "Cantone et al. [19]", "Moczkodan & Ragab [18]", "Review II baseline", "This work"], [
  ["Same-dataset binary score (random split)", "Nearly perfect", "–", "F_{1} 0.997", "F_{1} 0.9966 ± 0.0000"],
  ["Time-aware / leakage-free evaluation", "–", "Time and conversation splits; FAR × 67 (Transformer)", "No", "Per-class chronological split: F_{1} 0.903, FPR × 44"],
  ["Errors of the time-aware split inspected", "–", "–", "No", "Yes: 98.8% of false positives on two attack endpoint sets; FPR equal after exclusion"],
  ["Leakage separated from chronological ordering", "No", "Padding vs split", "No", "Yes: leakage ≤ 0.004 F_{1}"],
  ["Label conflicts counted", "No", "–", "No", "309 vectors, 82,704 rows"],
  ["Attribution scored end to end", "No", "–", "No", "Yes: Bot 1.00 → 0.41"],
  ["Transfer 2017 → 2018", "Grouped binary F_{1} 0.26–0.39", "–", "F_{1} 0.002", "Malicious F_{1} 0.0006 (matched families)"],
  ["Cause of transfer failure", "Data anomalies, different attack configurations", "–", "Hypothesised shift", "Units verified; 50/75 Hulk features with D_{KS} > 0.5"],
  ["Mitigation evaluated", "No", "No", "No", "4 label-free transforms; ≤ 0.5% gap recovered"],
], [2000, 1750, 1750, 1500, 2026], { size: 18 }));
B.push(P("Our transfer result is more severe than that of Cantone *et al.* [19]. Deduplication does not explain the difference (Table 9). Their 2018 test data covers all attack days, while ours covers DoS Hulk, SlowHTTPTest and web attacks only; this attack-subset explanation is plausible but was not tested. The Review II baseline reported a cross-dataset F_{1} of 0.002 without diagnosis; this work confirms the collapse with seed estimates, controls and a mechanism."));

// ---------------- 7 CONCLUSION
B.push(H1("7. CONCLUSION AND FUTURE WORKS"));
B.push(P("On CICIDS2017, duplicates, sessions and minute-scale adjacency together account for at most 0.004 of malicious-class F_{1}. A per-class chronological split lowers F_{1} from 0.997 to 0.903 and raises the false-positive rate from 0.07% to 2.90%, but 98.8% of those false positives are benign-labelled flows between known attack endpoints that a random split learns from its training data. With these flows excluded identically from both protocols, the false-positive rates coincide and the gap falls to a recall difference of 0.040, mostly in DoS Hulk. The chronological gap on this dataset is therefore mainly a label artefact, not evidence of temporal drift. The integrity audit found 309 conflicting feature vectors, all involving benign traffic, and duplication concentrated in probing attacks, so deduplication reshapes the evaluated class mix. Attribution scored end to end is markedly lower than attribution scored on true attacks for small classes, and the difference includes label defects."));
B.push(P("Zero-shot transfer from CICIDS2017 to CSE-CIC-IDS2018 fails on matched families with a DoS recall of 0.0003, independent of deduplication and model family. Unit checks exclude a measurement artefact; the per-feature diagnostics are consistent with a change in the DoS-Hulk traffic, and label-free normalisation does not repair the failure. The study recommends reporting a time-aware split with its cutoff rule and an audit of its errors, the benign false-positive rate with its denominator, duplicate and conflict counts per class, end-to-end attribution, and a same-year reference with every cross-dataset result."));
B.push(P("**Limitations.** The chronological splits cut each class at its own time and do not simulate deployment after a fixed date; a global cutoff is not feasible on CICIDS2017. The endpoint sets were identified from the errors they explain, so the audited metrics are a post-hoc diagnostic of one seed per protocol, and the affected flows were not relabelled. One dataset pair and two 2018 days are used; the protocol comparison has two seeds per split and several controls a single seed; only tree ensembles are evaluated."));
B.push(P("**Future work.**", { noIndent: true, after: 60 }));
[
  "Relabel the flows on the identified endpoint sets and repeat the protocol comparison on the corrected labels.",
  "Extend the transfer analysis to all CSE-CIC-IDS2018 attack days and test whether the attack subset explains the difference to published transfer results.",
  "Evaluate class-aware adaptation that uses a small labelled sample of target traffic.",
  "Apply the same protocols to encrypted-traffic captures with TLS handshake metadata and to sequence models.",
  "Increase the number of seeds for the grouped protocols and the policy study.",
].forEach((t) => B.push(bullet(t)));

// ---------------- 8 REFERENCES
B.push(H1("8. REFERENCES"));
const refHead = (t) => new Paragraph({ spacing: { before: 160, after: 80 }, children: runs(`**${t}**`) });
const ref = (n, t) => new Paragraph({ spacing: { after: 80, line: 276 }, indent: { left: 540, hanging: 540 }, alignment: AlignmentType.JUSTIFIED,
  tabStops: [{ type: TabStopType.LEFT, position: 540 }], children: runs(`[${n}]\t${t}`) });
B.push(refHead("Journals and conferences (IEEE format)"));
[
  "I. Sharafaldin, A. H. Lashkari, and A. A. Ghorbani, \"Toward generating a new intrusion detection dataset and intrusion traffic characterization,\" in *Proc. 4th Int. Conf. Information Systems Security and Privacy (ICISSP)*, 2018, pp. 108–116.",
  "G. Draper-Gil, A. H. Lashkari, M. S. I. Mamun, and A. A. Ghorbani, \"Characterization of encrypted and VPN traffic using time-related features,\" in *Proc. 2nd Int. Conf. Information Systems Security and Privacy (ICISSP)*, 2016, pp. 407–414.",
  "B. Anderson and D. McGrew, \"Identifying encrypted malware traffic with contextual flow data,\" in *Proc. ACM Workshop on Artificial Intelligence and Security (AISec)*, 2016, pp. 35–46.",
  "B. Anderson and D. McGrew, \"Machine learning for encrypted malware traffic classification: Accounting for noisy labels and non-stationarity,\" in *Proc. 23rd ACM SIGKDD Int. Conf. Knowledge Discovery and Data Mining*, 2017, pp. 1723–1732.",
  "X. Lin, G. Xiong, G. Gou, Z. Li, J. Shi, and J. Yu, \"ET-BERT: A contextualized datagram representation with pre-training transformers for encrypted traffic classification,\" in *Proc. ACM Web Conference (WWW)*, 2022, pp. 633–642.",
  "M. Ring, S. Wunderlich, D. Scheuring, D. Landes, and A. Hotho, \"A survey of network-based intrusion detection data sets,\" *Computers & Security*, vol. 86, pp. 147–167, 2019.",
  "G. Engelen, V. Rimmer, and W. Joosen, \"Troubleshooting an intrusion detection dataset: the CICIDS2017 case study,\" in *Proc. IEEE Security and Privacy Workshops (SPW)*, 2021, doi: 10.1109/SPW53761.2021.00009.",
  "A. Rosay, E. Cheval, F. Carlier, and P. Leroux, \"Network intrusion detection: A comprehensive analysis of CIC-IDS2017,\" in *Proc. 8th Int. Conf. Information Systems Security and Privacy (ICISSP)*, 2022.",
  "L. Liu, G. Engelen, T. Lynar, D. Essam, and W. Joosen, \"Error prevalence in NIDS datasets: A case study on CIC-IDS-2017 and CSE-CIC-IDS-2018,\" in *Proc. IEEE Conf. Communications and Network Security (CNS)*, 2022, pp. 254–263, doi: 10.1109/CNS56114.2022.9947235.",
  "M. Lanvin, P.-F. Gimenez, Y. Han, F. Majorczyk, L. Mé, and É. Totel, \"Errors in the CICIDS2017 dataset and the significant differences in detection performances it makes,\" in *Risks and Security of Internet and Systems (CRiSIS 2022)*, Lecture Notes in Computer Science, Springer, 2023, pp. 18–33.",
  "Z. K. Maseer, R. Yusof, N. Bahaman, S. A. Mostafa, and C. F. M. Foozy, \"Benchmarking of machine learning for anomaly based intrusion detection systems in the CICIDS2017 dataset,\" *IEEE Access*, vol. 9, pp. 22351–22370, 2021.",
  "A. Pekar and R. Jozsa, \"Evaluating ML-based anomaly detection across datasets of varied integrity: A case study,\" *Computer Networks*, 2024, arXiv:2401.16843.",
  "R. Sommer and V. Paxson, \"Outside the closed world: On using machine learning for network intrusion detection,\" in *Proc. IEEE Symp. Security and Privacy*, 2010, pp. 305–316.",
  "S. Kaufman, S. Rosset, C. Perlich, and O. Stitelman, \"Leakage in data mining: Formulation, detection, and avoidance,\" *ACM Trans. Knowledge Discovery from Data*, vol. 6, no. 4, 2012.",
  "F. Pendlebury, F. Pierazzi, R. Jordaney, J. Kinder, and L. Cavallaro, \"TESSERACT: Eliminating experimental bias in malware classification across space and time,\" in *Proc. 28th USENIX Security Symp.*, 2019.",
  "D. Arp, E. Quiring, F. Pendlebury, A. Warnecke, F. Pierazzi, C. Wressnegger, L. Cavallaro, and K. Rieck, \"Dos and don'ts of machine learning in computer security,\" in *Proc. 31st USENIX Security Symp.*, 2022.",
  "G. Apruzzese, P. Laskov, and J. Schneider, \"SoK: Pragmatic assessment of machine learning for network intrusion detection,\" in *Proc. IEEE European Symp. Security and Privacy (EuroS&P)*, 2023.",
  "Z. Moczkodan and H. Ragab, \"Do transformers actually help intrusion detection? A temporal sequence evaluation on CIC-IDS2017,\" arXiv:2606.11098, 2026.",
  "M. Cantone, C. Marrocco, and A. Bria, \"On the cross-dataset generalization of machine learning for network intrusion detection,\" *IEEE Access*, vol. 12, pp. 144489–144508, 2024.",
  "L. Breiman, \"Random forests,\" *Machine Learning*, vol. 45, no. 1, pp. 5–32, 2001.",
  "T. Chen and C. Guestrin, \"XGBoost: A scalable tree boosting system,\" in *Proc. 22nd ACM SIGKDD Int. Conf. Knowledge Discovery and Data Mining*, 2016, pp. 785–794.",
  "E. B. Wilson, \"Probable inference, the law of succession, and statistical inference,\" *J. American Statistical Association*, vol. 22, no. 158, pp. 209–212, 1927.",
].forEach((t, i) => B.push(ref(i + 1, t)));
B.push(refHead("Book"));
B.push(ref(23, "J. Quiñonero-Candela, M. Sugiyama, A. Schwaighofer, and N. D. Lawrence, Eds., *Dataset Shift in Machine Learning*. Cambridge, MA, USA: MIT Press, 2009."));
B.push(refHead("Weblinks"));
B.push(ref(24, "Canadian Institute for Cybersecurity, \"Intrusion detection evaluation dataset (CIC-IDS2017).\" https://www.unb.ca/cic/datasets/ids-2017.html"));
B.push(ref(25, "Canadian Institute for Cybersecurity, \"CSE-CIC-IDS2018 on AWS.\" https://www.unb.ca/cic/datasets/ids-2018.html"));

// =================================================================== DOCUMENT
const footer = (fmt) => new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
  children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 22 })] })] });
const pageProps = { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } };
const doc = new Document({
  creator: "Gaurav Bakshi, Anshveer Singh, Dev Acharya Menon",
  title: "Behavioral Classification of Encrypted Malicious Network Traffic Using Flow-Based Metadata",
  styles: {
    default: { document: { run: { font: FONT, size: 24 }, paragraph: { spacing: { line: 276 } } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 28, bold: true, color: "000000" },
        paragraph: { alignment: AlignmentType.CENTER, spacing: { before: 0, after: 240, line: 360 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 26, bold: true, color: "000000" },
        paragraph: { spacing: { before: 240, after: 120, line: 360 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 24, bold: true, italics: true, color: "000000" },
        paragraph: { spacing: { before: 180, after: 80, line: 360 }, outlineLevel: 2 } },
    ],
  },
  numbering: { config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "●", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 720, hanging: 360 } }, run: { size: 18 } } }] },
    { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    { reference: "obj", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "O%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 720, hanging: 540 } } } }] },
  ] },
  sections: [
    { properties: { page: pageProps }, children: cover },
    { properties: { page: { ...pageProps, pageNumbers: { start: 1, formatType: NumberFormat.LOWER_ROMAN } } },
      footers: { default: footer() }, children: front },
    { properties: { page: { ...pageProps, pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL } } },
      footers: { default: footer() }, children: B },
  ],
});
const out = path.join(ROOT, "Project_Report.docx");
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(out, buf); console.log("wrote", out, "figures", figNo, "tables", tabNo, "equations", eqNo); });
