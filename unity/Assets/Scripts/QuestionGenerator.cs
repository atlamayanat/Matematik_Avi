using System.Collections.Generic;
using UnityEngine;

/// <summary>Difficulty tiers chosen on the start screen.</summary>
public enum Difficulty { Easy, Medium, Hard }

/// <summary>A math problem: a display prompt, its answer, and optional targeted decoys.</summary>
public class MathProblem
{
    public string Prompt;            // e.g. "7 × 8"
    public string Answer;            // e.g. "56" (or a fraction glyph like "½")
    public List<string> Distractors; // optional "common mistake" decoys seeded first

    public MathProblem(string prompt, string answer, List<string> distractors = null)
    {
        Prompt = prompt; Answer = answer; Distractors = distractors;
    }
}

/// <summary>
/// Generates random math problems by difficulty, each with a SHORT string answer
/// (an integer or a simple unicode fraction) plus plausible decoy strings.
///
///   Easy   (ages 5-10): the elementary set — times tables, add/sub, exact division,
///                       small squares/roots, ¼ ½ ¾ fractions.
///   Medium (ortaokul-lise): bigger products, squares/roots, cubes, order-of-operations,
///                       negative results.
///   Hard   (lise-üniversite): solve-for-x, x²=n, big squares/roots, factorials,
///                       power sums, parenthesised order-of-operations — still solvable
///                       at a single glance.
///
/// The file is UTF-8; the symbol glyphs below are literal unicode. Every glyph used
/// (× ÷ − √ ² ³ ¼ ½ ¾ ( ) ! and the digits) is present in the patched FredokaGame
/// font (see GameFont) — verified, so nothing renders as a box.
/// </summary>
public class QuestionGenerator
{
    const string MUL = "×", DIV = "÷", MINUS = "−", SQRT = "√", SUP2 = "²", SUP3 = "³";
    const string HALF = "½", QUART = "¼", TQRT = "¾";

    public MathProblem Next(Difficulty d)
    {
        switch (d)
        {
            case Difficulty.Medium: return Medium();
            case Difficulty.Hard:   return Hard();
            default:                return Easy();
        }
    }

    public MathProblem Next() => Next(Difficulty.Easy); // safety overload

    // ------------------------------------------------------------------ EASY
    MathProblem Easy()
    {
        switch (Random.Range(0, 6))
        {
            case 0:  return Mul();
            case 1:  return Add();
            case 2:  return Sub();
            case 3:  return DivExact();
            case 4:  return SquareOrRoot();
            default: return Fraction();
        }
    }

    MathProblem Mul()
    {
        int a = Random.Range(2, 13), b = Random.Range(2, 13);
        return new MathProblem($"{a} {MUL} {b}", (a * b).ToString());
    }

    MathProblem Add()
    {
        int a = Random.Range(5, 50), b = Random.Range(5, 50);
        return new MathProblem($"{a} + {b}", (a + b).ToString());
    }

    MathProblem Sub()
    {
        int a = Random.Range(12, 60), b = Random.Range(2, a);
        return new MathProblem($"{a} {MINUS} {b}", (a - b).ToString());
    }

    MathProblem DivExact()
    {
        int b = Random.Range(2, 10), c = Random.Range(2, 10);
        return new MathProblem($"{b * c} {DIV} {b}", c.ToString());
    }

    MathProblem SquareOrRoot()
    {
        int a = Random.Range(2, 13);
        if (Random.value < 0.5f) return new MathProblem($"{a}{SUP2}", (a * a).ToString());
        return new MathProblem($"{SQRT}{a * a}", a.ToString());
    }

    MathProblem Fraction()
    {
        (string prompt, string ans)[] table =
        {
            ($"{QUART} + {QUART}", HALF),
            ($"{HALF} + {QUART}",  TQRT),
            ($"{QUART} + {HALF}",  TQRT),
            ($"{TQRT} {MINUS} {QUART}", HALF),
            ($"{HALF} {MINUS} {QUART}", QUART),
            ($"{TQRT} {MINUS} {HALF}",  QUART),
        };
        var pick = table[Random.Range(0, table.Length)];
        return new MathProblem(pick.prompt, pick.ans);
    }

    // ---------------------------------------------------------------- MEDIUM
    MathProblem Medium()
    {
        switch (Random.Range(0, 6))
        {
            case 0:  return MedMul();
            case 1:  return MedSquare();
            case 2:  return MedRoot();
            case 3:  return MedCube();
            case 4:  return MedOrder();
            default: return MedNegative();
        }
    }

    MathProblem MedMul()
    {
        int a = Random.Range(11, 20), b = Random.Range(3, 10);
        return new MathProblem($"{a} {MUL} {b}", (a * b).ToString());
    }

    MathProblem MedSquare()
    {
        int a = Random.Range(5, 16);
        return new MathProblem($"{a}{SUP2}", (a * a).ToString());
    }

    MathProblem MedRoot()
    {
        int a = Random.Range(6, 16);
        return new MathProblem($"{SQRT}{a * a}", a.ToString());
    }

    MathProblem MedCube()
    {
        int a = Random.Range(2, 7);                 // 8, 27, 64, 125, 216
        return new MathProblem($"{a}{SUP3}", (a * a * a).ToString());
    }

    MathProblem MedOrder()
    {
        int a = Random.Range(2, 10), b = Random.Range(2, 10), c = Random.Range(2, 10);
        // a + b × c  — the classic trap answer is the left-to-right (a+b)×c
        int ans = a + b * c;
        var trap = ((a + b) * c).ToString();
        return new MathProblem($"{a} + {b} {MUL} {c}", ans.ToString(), new List<string> { trap });
    }

    MathProblem MedNegative()
    {
        int a = Random.Range(3, 10), b = Random.Range(11, 19);
        int ans = a - b;                            // always negative
        // common mistake: ignoring the sign (answering b − a)
        return new MathProblem($"{a} {MINUS} {b}", ans.ToString(), new List<string> { (b - a).ToString() });
    }

    // ------------------------------------------------------------------ HARD
    MathProblem Hard()
    {
        switch (Random.Range(0, 7))
        {
            case 0:  return HardSolveX();
            case 1:  return HardSolveXPlus();
            case 2:  return HardXSquared();
            case 3:  return HardBigSquareOrRoot();
            case 4:  return HardFactorial();
            case 5:  return HardPowerSum();
            default: return HardOrderParen();
        }
    }

    MathProblem HardSolveX()
    {
        int a = Random.Range(2, 10), x = Random.Range(2, 13);
        // a·x = c  ->  x ;  trap: the product c itself
        return new MathProblem($"{a}x = {a * x}", x.ToString(), new List<string> { (a * x).ToString() });
    }

    MathProblem HardSolveXPlus()
    {
        int a = Random.Range(2, 7), x = Random.Range(2, 10), b = Random.Range(1, 10);
        int c = a * x + b;                          // a·x + b = c  ->  x
        return new MathProblem($"{a}x + {b} = {c}", x.ToString());
    }

    MathProblem HardXSquared()
    {
        int n = Random.Range(2, 13);
        // x² = n²  ->  n ; traps: n² (the right side) and 2n (doubling instead of rooting)
        return new MathProblem($"x{SUP2} = {n * n}", n.ToString(),
            new List<string> { (n * n).ToString(), (2 * n).ToString() });
    }

    MathProblem HardBigSquareOrRoot()
    {
        int a = Random.Range(11, 21);               // 121 .. 400
        if (Random.value < 0.5f) return new MathProblem($"{a}{SUP2}", (a * a).ToString());
        return new MathProblem($"{SQRT}{a * a}", a.ToString());
    }

    MathProblem HardFactorial()
    {
        int n = Random.Range(3, 7);                 // 3!..6! = 6, 24, 120, 720
        int f = 1; for (int i = 2; i <= n; i++) f *= i;
        return new MathProblem($"{n}!", f.ToString());
    }

    MathProblem HardPowerSum()
    {
        int a = Random.Range(2, 7), b = Random.Range(2, 7);
        bool cubeFirst = Random.value < 0.5f;
        if (cubeFirst)
            return new MathProblem($"{a}{SUP3} + {b}{SUP2}", (a * a * a + b * b).ToString());
        return new MathProblem($"{a}{SUP2} + {b}{SUP3}", (a * a + b * b * b).ToString());
    }

    MathProblem HardOrderParen()
    {
        int a = Random.Range(3, 10), b = Random.Range(2, 9), c = Random.Range(2, 8);
        // (a + b) × c  — trap: dropping the parentheses -> a + b×c
        int ans = (a + b) * c;
        var trap = (a + b * c).ToString();
        return new MathProblem($"({a} + {b}) {MUL} {c}", ans.ToString(), new List<string> { trap });
    }

    // ---------------------------------------------------------------- DECOYS
    /// <summary>Up to <paramref name="wanted"/> distinct decoy strings, never equal to the
    /// answer. Any targeted Distractors are kept first, then near-misses fill the rest.</summary>
    public List<string> MakeDecoys(MathProblem p, int wanted)
    {
        // forced "common mistake" decoys are kept even if we trim later
        var forced = new List<string>();
        if (p.Distractors != null)
            foreach (var d in p.Distractors)
                if (!string.IsNullOrEmpty(d) && d != p.Answer && !forced.Contains(d)) forced.Add(d);

        var set = new HashSet<string>(forced);

        if (p.Answer == HALF || p.Answer == QUART || p.Answer == TQRT)
        {
            foreach (var s in new[] { HALF, QUART, TQRT, "1", "2", "0", $"1{HALF}", $"1{QUART}" })
                if (s != p.Answer) set.Add(s);
        }
        else if (int.TryParse(p.Answer, out int v))
        {
            bool allowNeg = v < 0;    // only genuinely-negative answers get negative-number decoys
            int[] offs = { 1, -1, 2, -2, 3, -3, 4, 5, -5, 9, 10, -10 };
            foreach (int o in offs) { int w = v + o; if ((w >= 0 || allowNeg) && w != v) set.Add(w.ToString()); }

            if (v >= 10) // digit-swap near-miss (positive multi-digit only), e.g. 56 -> 65
            {
                string sv = v.ToString();
                char[] ch = sv.ToCharArray();
                (ch[0], ch[ch.Length - 1]) = (ch[ch.Length - 1], ch[0]);
                string sw = new string(ch).TrimStart('0');
                if (sw.Length > 0 && sw != p.Answer) set.Add(sw);
            }

            int span = Mathf.Max(6, Mathf.Abs(v) / 2);
            int guard = 0;
            while (set.Count < wanted + 4 && guard++ < 80)
            {
                int w = v + Random.Range(-span, span + 1);
                if ((w >= 0 || allowNeg) && w != v) set.Add(w.ToString());
            }
        }

        set.Remove(p.Answer);

        // keep forced decoys at the front, shuffle the rest, then trim
        var others = new List<string>();
        foreach (var s in set) if (!forced.Contains(s)) others.Add(s);
        Shuffle(others);

        var list = new List<string>(forced);
        list.AddRange(others);
        if (list.Count > wanted) list = list.GetRange(0, wanted);
        return list;
    }

    static void Shuffle<T>(IList<T> list)
    {
        for (int i = list.Count - 1; i > 0; i--)
        {
            int j = Random.Range(0, i + 1);
            (list[i], list[j]) = (list[j], list[i]);
        }
    }
}
