using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Builds the dark field of answer tokens for one question. Tokens are placed on
/// a JITTERED GRID (never free-random) so two answers can never overlap and there
/// is always a clear "nearest" for the lens to arm. The correct answer is placed
/// as several well-spread copies (so the game is not too hard), the rest are
/// decoys. Returns the live token list for LensHunt to drive.
/// </summary>
public class MathField : MonoBehaviour
{
    [SerializeField] Transform tokenParent;

    [Header("Field rect (world units) - leaves the top band for the question banner")]
    [SerializeField] float xMin = -7.5f;
    [SerializeField] float xMax = 7.5f;
    [SerializeField] float yMin = -4.3f;
    [SerializeField] float yMax = 3.0f;
    [SerializeField] float cell = 1.6f;     // grid spacing
    [SerializeField] float jitter = 0.42f;  // per-cell random offset (keeps min spacing safe)
    [SerializeField] Vector2 exclusionCenter = new Vector2(7.5f, 4.2f); // keep tokens clear of the RESET button
    [SerializeField] float exclusionRadius = 2.4f;

    Font _font;
    Sprite _halo;
    readonly List<AnswerToken> _live = new List<AnswerToken>();

    void Awake()
    {
        _font = GameFont.Get();
        _halo = MakeSoftCircle(96);
        if (tokenParent == null) tokenParent = transform;
    }

    /// <summary>Clear the field and spawn a new one for the given problem.</summary>
    public List<AnswerToken> Spawn(MathProblem problem, List<string> decoys, int correctCopies, int totalTokens)
    {
        Clear();
        if (_font == null) _font = GameFont.Get();
        if (_halo == null) _halo = MakeSoftCircle(96);

        // jittered grid cells
        var cells = new List<Vector2>();
        for (float x = xMin; x <= xMax + 0.001f; x += cell)
            for (float y = yMin; y <= yMax + 0.001f; y += cell)
            {
                Vector2 cp = new Vector2(x, y) + Random.insideUnitCircle * jitter;
                if (Vector2.Distance(cp, exclusionCenter) < exclusionRadius) continue; // clear zone for RESET
                cells.Add(cp);
            }
        Shuffle(cells);

        int count = Mathf.Min(totalTokens, cells.Count);
        int correctN = Mathf.Clamp(correctCopies, 1, count);
        var chosen = cells.GetRange(0, count);

        // pick well-spread positions for the correct copies (farthest-point sampling)
        var correctIdx = PickSpread(chosen, correctN);

        int decoyPtr = 0;
        for (int i = 0; i < count; i++)
        {
            bool isCorrect = correctIdx.Contains(i);
            string val = isCorrect
                ? problem.Answer
                : (decoys != null && decoys.Count > 0 ? decoys[decoyPtr++ % decoys.Count] : "?");

            var go = new GameObject(isCorrect ? "Token(correct)" : "Token");
            go.transform.SetParent(tokenParent, false);
            go.transform.position = new Vector3(chosen[i].x, chosen[i].y, 0f);
            var at = go.AddComponent<AnswerToken>();
            at.Init(val, isCorrect, _font, _halo);
            _live.Add(at);
        }
        return new List<AnswerToken>(_live);
    }

    public void Clear()
    {
        for (int i = 0; i < _live.Count; i++)
            if (_live[i] != null) Destroy(_live[i].gameObject);
        _live.Clear();
    }

    // Greedy farthest-point sampling: pick a random seed, then repeatedly add the
    // candidate that is farthest from everything chosen so far. Spreads copies out.
    static List<int> PickSpread(List<Vector2> pts, int k)
    {
        var result = new List<int>();
        if (k <= 0 || pts.Count == 0) return result;
        result.Add(Random.Range(0, pts.Count));
        while (result.Count < k)
        {
            int best = -1;
            float bestD = -1f;
            for (int i = 0; i < pts.Count; i++)
            {
                if (result.Contains(i)) continue;
                float dmin = float.MaxValue;
                for (int r = 0; r < result.Count; r++)
                    dmin = Mathf.Min(dmin, Vector2.Distance(pts[i], pts[result[r]]));
                if (dmin > bestD) { bestD = dmin; best = i; }
            }
            if (best < 0) break;
            result.Add(best);
        }
        return result;
    }

    static void Shuffle<T>(IList<T> list)
    {
        for (int i = list.Count - 1; i > 0; i--)
        {
            int j = Random.Range(0, i + 1);
            (list[i], list[j]) = (list[j], list[i]);
        }
    }

    // Soft radial disc (1 unit base via PPU = size) used as the armed-token halo.
    static Sprite MakeSoftCircle(int size)
    {
        var tex = new Texture2D(size, size, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp };
        float r = size * 0.5f;
        var c = new Vector2(r, r);
        for (int y = 0; y < size; y++)
            for (int x = 0; x < size; x++)
            {
                float d = Vector2.Distance(new Vector2(x + 0.5f, y + 0.5f), c) / r; // 0 centre .. 1 edge
                float a = Mathf.Clamp01(1f - d);
                a *= a; // soft falloff
                tex.SetPixel(x, y, new Color(1f, 1f, 1f, a));
            }
        tex.Apply();
        return Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), size);
    }
}
