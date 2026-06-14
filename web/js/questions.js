/* questions.js — QuestionGenerator.cs + MakeDecoys'un BİREBİR portu.
   Otorite: Unity MathLens (prototipin 8 sabit sorusu DEĞİL). Prosedürel üretim. */
(function () {
  const MA = (window.MA = window.MA || {});

  // Unicode glyph'ler (FredokaGame/Baloo 2 kapsıyor)
  const MUL = "×", DIV = "÷", MINUS = "−", SQRT = "√", SUP2 = "²", SUP3 = "³";
  const HALF = "½", QUART = "¼", TQRT = "¾";

  // Unity Random.Range(int,int) = [min, max)  (max hariç)
  const ri = (min, max) => Math.floor(Math.random() * (max - min)) + min;
  const rv = () => Math.random();

  const prob = (prompt, answer, distractors) => ({ prompt, answer, distractors: distractors || null });

  // ---------------- EASY ----------------
  function Mul()  { const a = ri(2,13), b = ri(2,13); return prob(`${a} ${MUL} ${b}`, String(a*b)); }
  function Add()  { const a = ri(5,50), b = ri(5,50); return prob(`${a} + ${b}`, String(a+b)); }
  function Sub()  { const a = ri(12,60), b = ri(2,a); return prob(`${a} ${MINUS} ${b}`, String(a-b)); }
  function DivExact() { const b = ri(2,10), c = ri(2,10); return prob(`${b*c} ${DIV} ${b}`, String(c)); }
  function SquareOrRoot() {
    const a = ri(2,13);
    return rv() < 0.5 ? prob(`${a}${SUP2}`, String(a*a)) : prob(`${SQRT}${a*a}`, String(a));
  }
  function Fraction() {
    const table = [
      [`${QUART} + ${QUART}`, HALF],
      [`${HALF} + ${QUART}`,  TQRT],
      [`${QUART} + ${HALF}`,  TQRT],
      [`${TQRT} ${MINUS} ${QUART}`, HALF],
      [`${HALF} ${MINUS} ${QUART}`, QUART],
      [`${TQRT} ${MINUS} ${HALF}`,  QUART],
    ];
    const p = table[ri(0, table.length)];
    return prob(p[0], p[1]);
  }
  function Easy() {
    switch (ri(0,6)) {
      case 0: return Mul();
      case 1: return Add();
      case 2: return Sub();
      case 3: return DivExact();
      case 4: return SquareOrRoot();
      default: return Fraction();
    }
  }

  // ---------------- MEDIUM ----------------
  function MedMul()    { const a = ri(11,20), b = ri(3,10); return prob(`${a} ${MUL} ${b}`, String(a*b)); }
  function MedSquare() { const a = ri(5,16); return prob(`${a}${SUP2}`, String(a*a)); }
  function MedRoot()   { const a = ri(6,16); return prob(`${SQRT}${a*a}`, String(a)); }
  function MedCube()   { const a = ri(2,7);  return prob(`${a}${SUP3}`, String(a*a*a)); }
  function MedOrder() {
    const a = ri(2,10), b = ri(2,10), c = ri(2,10);
    const ans = a + b*c, trap = (a+b)*c;             // klasik soldan-sağa tuzağı
    return prob(`${a} + ${b} ${MUL} ${c}`, String(ans), [String(trap)]);
  }
  function MedNegative() {
    const a = ri(3,10), b = ri(11,19);
    const ans = a - b;                                // her zaman negatif
    return prob(`${a} ${MINUS} ${b}`, String(ans), [String(b-a)]); // işaret-yoksay tuzağı
  }
  function Medium() {
    switch (ri(0,6)) {
      case 0: return MedMul();
      case 1: return MedSquare();
      case 2: return MedRoot();
      case 3: return MedCube();
      case 4: return MedOrder();
      default: return MedNegative();
    }
  }

  // ---------------- HARD ----------------
  function HardSolveX()  { const a = ri(2,10), x = ri(2,13); return prob(`${a}x = ${a*x}`, String(x), [String(a*x)]); }
  function HardSolveXPlus() {
    const a = ri(2,7), x = ri(2,10), b = ri(1,10); const c = a*x + b;
    return prob(`${a}x + ${b} = ${c}`, String(x));
  }
  function HardXSquared() {
    const n = ri(2,13);
    return prob(`x${SUP2} = ${n*n}`, String(n), [String(n*n), String(2*n)]);
  }
  function HardBigSquareOrRoot() {
    const a = ri(11,21);
    return rv() < 0.5 ? prob(`${a}${SUP2}`, String(a*a)) : prob(`${SQRT}${a*a}`, String(a));
  }
  function HardFactorial() {
    const n = ri(3,7); let f = 1; for (let i = 2; i <= n; i++) f *= i;
    return prob(`${n}!`, String(f));
  }
  function HardPowerSum() {
    const a = ri(2,7), b = ri(2,7);
    return rv() < 0.5
      ? prob(`${a}${SUP3} + ${b}${SUP2}`, String(a*a*a + b*b))
      : prob(`${a}${SUP2} + ${b}${SUP3}`, String(a*a + b*b*b));
  }
  function HardOrderParen() {
    const a = ri(3,10), b = ri(2,9), c = ri(2,8);
    const ans = (a+b)*c, trap = a + b*c;             // parantez-düşür tuzağı
    return prob(`(${a} + ${b}) ${MUL} ${c}`, String(ans), [String(trap)]);
  }
  function Hard() {
    switch (ri(0,7)) {
      case 0: return HardSolveX();
      case 1: return HardSolveXPlus();
      case 2: return HardXSquared();
      case 3: return HardBigSquareOrRoot();
      case 4: return HardFactorial();
      case 5: return HardPowerSum();
      default: return HardOrderParen();
    }
  }

  function next(difficulty) {
    if (difficulty === "orta") return Medium();
    if (difficulty === "zor")  return Hard();
    return Easy();
  }

  function shuffle(list) {
    for (let i = list.length - 1; i > 0; i--) {
      const j = ri(0, i + 1);
      [list[i], list[j]] = [list[j], list[i]];
    }
    return list;
  }

  // ---------------- DECOYS (MakeDecoys.cs portu) ----------------
  function makeDecoys(p, wanted) {
    const forced = [];
    if (p.distractors) {
      for (const d of p.distractors) {
        if (d && d !== p.answer && !forced.includes(d)) forced.push(d);
      }
    }
    const set = new Set(forced);

    if (p.answer === HALF || p.answer === QUART || p.answer === TQRT) {
      for (const s of [HALF, QUART, TQRT, "1", "2", "0", "1" + HALF, "1" + QUART]) {
        if (s !== p.answer) set.add(s);
      }
    } else if (/^-?\d+$/.test(p.answer)) {
      const v = parseInt(p.answer, 10);
      const allowNeg = v < 0;   // sadece gerçekten negatif cevaplara negatif decoy
      const offs = [1, -1, 2, -2, 3, -3, 4, 5, -5, 9, 10, -10];
      for (const o of offs) { const w = v + o; if ((w >= 0 || allowNeg) && w !== v) set.add(String(w)); }

      if (v >= 10) { // rakam-değiştir yakın-ıska (56 -> 65)
        const sv = String(v).split("");
        [sv[0], sv[sv.length - 1]] = [sv[sv.length - 1], sv[0]];
        const sw = sv.join("").replace(/^0+/, "");
        if (sw.length > 0 && sw !== p.answer) set.add(sw);
      }

      const span = Math.max(6, Math.floor(Math.abs(v) / 2));
      let guard = 0;
      while (set.size < wanted + 4 && guard++ < 80) {
        const w = v + ri(-span, span + 1);
        if ((w >= 0 || allowNeg) && w !== v) set.add(String(w));
      }
    }

    set.delete(p.answer);

    const others = [];
    for (const s of set) if (!forced.includes(s)) others.push(s);
    shuffle(others);

    let list = forced.concat(others);
    if (list.length > wanted) list = list.slice(0, wanted);
    return list;
  }

  const DIFF_NAME = { kolay: "Kolay", orta: "Orta", zor: "Zor" };

  MA.questions = { next, makeDecoys, shuffle, ri, rv, DIFF_NAME };
})();
