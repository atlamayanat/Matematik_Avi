using System.Collections;
using UnityEngine;

/// <summary>
/// The attract / start screen: a layered colourful backdrop with many drifting
/// math symbols, a crisp glowing title + hint. The "BAŞLA" button is a separate
/// GestureButton child (added by the builder). Show()/Hide() toggle the screen.
/// Shown on launch and after a reset; hidden while playing.
/// </summary>
[DisallowMultipleComponent]
public class StartScreen : MonoBehaviour
{
    [SerializeField] int symbolCount = 40;
    [SerializeField] float areaX = 9.4f;
    [SerializeField] float areaY = 5.6f;

    static readonly string[] Glyphs =
    {
        "+", "−", "×", "÷", "=", "√", "π", "²", "½", "¼", "¾", "%", "∞",
        "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    };
    static readonly Color[] Palette =
    {
        new Color(0.40f, 0.70f, 1.00f),  // blue
        new Color(0.45f, 0.95f, 0.85f),  // teal
        new Color(0.80f, 0.65f, 1.00f),  // purple
        new Color(1.00f, 0.82f, 0.35f),  // gold
        new Color(1.00f, 0.55f, 0.70f),  // pink
        new Color(0.65f, 1.00f, 0.60f),  // green
        new Color(1.00f, 0.68f, 0.40f),  // orange
        new Color(0.55f, 0.85f, 1.00f),  // sky
        new Color(0.95f, 0.95f, 1.00f),  // near-white
    };

    Font _font;
    Transform[] _sym;
    TextMesh[] _tm;
    Vector2[] _vel;
    float[] _phase, _spin, _baseA;
    TextMesh _title, _hint;
    Transform _titleGlow;

    void Awake()
    {
        if (!Application.isPlaying) return;  // never build at edit time
        _font = GameFont.Get();
        BuildBackdrop();
        BuildTitle();
        BuildSymbols();
        StartCoroutine(FitTexts());          // shrink title/hint to the actual screen width
    }

    void BuildBackdrop()
    {
        // base dark fill + a few large soft colour glows = a layered "nebula" space
        Glow(new Vector3(0f, 0f, 0f), new Vector3(46f, 28f, 1f), new Color(0.07f, 0.10f, 0.22f, 0.85f), 2);
        Glow(new Vector3(-5.5f, 2.8f, 0f), new Vector3(16f, 16f, 1f), new Color(0.20f, 0.35f, 0.85f, 0.22f), 3);
        Glow(new Vector3(6.0f, -2.5f, 0f), new Vector3(18f, 18f, 1f), new Color(0.55f, 0.30f, 0.85f, 0.20f), 3);
        Glow(new Vector3(2.0f, 3.5f, 0f), new Vector3(13f, 13f, 1f), new Color(0.25f, 0.75f, 0.75f, 0.16f), 3);
    }

    GameObject Glow(Vector3 pos, Vector3 scale, Color col, int order)
    {
        var go = new GameObject("Glow");
        go.transform.SetParent(transform, false);
        go.transform.localPosition = pos;
        go.transform.localScale = scale;
        var sr = go.AddComponent<SpriteRenderer>();
        sr.sprite = Gfx.SoftCircle(64);
        sr.color = col;
        sr.sortingOrder = order;
        return go;
    }

    void BuildTitle()
    {
        // soft glow plate behind the title
        _titleGlow = Glow(new Vector3(0f, 3.55f, 0f), new Vector3(11f, 3.2f, 1f), new Color(1f, 0.85f, 0.40f, 0.18f), 48).transform;
        _title = Make("MATEMATİK AVI", new Vector3(0f, 3.55f, 0f), 0.115f, 220,
             new Color(1f, 0.90f, 0.50f), 50, FontStyle.Bold);
        // "pick your level" prompt above the difficulty buttons (the buttons are added
        // by the builder as children of this screen).
        Make("Seviyeni seç", new Vector3(0f, 1.75f, 0f), 0.075f, 180,
             new Color(1f, 0.96f, 0.86f, 0.96f), 50, FontStyle.Bold);
        _hint = Make("Merceği bir seviyeye getir ve elini kapat", new Vector3(0f, -3.5f, 0f), 0.05f, 160,
             new Color(0.88f, 0.94f, 1f, 0.95f), 50, FontStyle.Normal);
    }

    // Shrink the title + hint so they never spill past the screen edges, on ANY
    // resolution/aspect. World width = orthoSize * aspect * 2; we measure the rendered
    // text and scale it down to a fraction of that. Runs once after the meshes build.
    IEnumerator FitTexts()
    {
        yield return null;   // let the text meshes generate so bounds are valid
        var cam = Camera.main;
        if (cam == null) yield break;
        float worldW = cam.orthographicSize * cam.aspect * 2f;
        float f = FitWidth(_title, worldW * 0.88f);
        if (_titleGlow != null && f < 1f) _titleGlow.localScale *= f;  // keep the plate proportional
        FitWidth(_hint, worldW * 0.92f);
    }

    static float FitWidth(TextMesh tm, float maxWorldWidth)
    {
        if (tm == null) return 1f;
        var mr = tm.GetComponent<MeshRenderer>();
        if (mr == null) return 1f;
        float w = mr.bounds.size.x;
        if (w > 0.001f && w > maxWorldWidth)
        {
            float f = maxWorldWidth / w;
            tm.transform.localScale *= f;
            return f;
        }
        return 1f;
    }

    TextMesh Make(string text, Vector3 pos, float size, int fontSize, Color col, int order, FontStyle style)
    {
        var go = new GameObject("Text");
        go.transform.SetParent(transform, false);
        go.transform.localPosition = pos;
        var tm = go.AddComponent<TextMesh>();
        tm.font = _font;
        tm.text = text;
        tm.anchor = TextAnchor.MiddleCenter;
        tm.alignment = TextAlignment.Center;
        tm.fontSize = fontSize;          // high -> crisp atlas
        tm.fontStyle = style;
        tm.characterSize = size;
        tm.color = col;
        var mr = go.GetComponent<MeshRenderer>();
        mr.sharedMaterial = _font.material;
        mr.sortingOrder = order;
        return tm;
    }

    void BuildSymbols()
    {
        int n = symbolCount;
        _sym = new Transform[n];
        _tm = new TextMesh[n];
        _vel = new Vector2[n];
        _phase = new float[n];
        _spin = new float[n];
        _baseA = new float[n];

        for (int i = 0; i < n; i++)
        {
            var g = Glyphs[Random.Range(0, Glyphs.Length)];
            var col = Palette[Random.Range(0, Palette.Length)];
            float size = Random.Range(0.05f, 0.16f);
            float fs = size > 0.11f ? 160 : 96;  // bigger symbols get a crisper atlas

            var tm = Make(g, new Vector3(Random.Range(-areaX, areaX), Random.Range(-areaY, areaY), 0f),
                          size, (int)fs, col, 30, FontStyle.Normal);
            tm.gameObject.name = "Sym";
            _sym[i] = tm.transform;
            _tm[i] = tm;
            _vel[i] = new Vector2(Random.Range(-0.18f, 0.18f), Random.Range(0.22f, 0.70f));
            _phase[i] = Random.Range(0f, 6.28f);
            _spin[i] = Random.Range(-18f, 18f);
            _baseA[i] = Random.Range(0.16f, 0.42f);
        }
    }

    void Update()
    {
        if (_sym == null) return;
        float t = Time.time;
        float dt = Time.deltaTime;
        int frame = Time.frameCount;
        for (int i = 0; i < _sym.Length; i++)
        {
            var tr = _sym[i];
            Vector3 p = tr.localPosition;
            p.x += (_vel[i].x + 0.15f * Mathf.Sin(t * 0.6f + _phase[i])) * dt;
            p.y += _vel[i].y * dt;
            if (p.y > areaY + 0.6f) { p.y = -areaY - 0.6f; p.x = Random.Range(-areaX, areaX); }
            if (p.x > areaX + 0.6f) p.x = -areaX - 0.6f;
            else if (p.x < -areaX - 0.6f) p.x = areaX + 0.6f;
            tr.localPosition = p;        // moving/rotating a TextMesh is cheap (no mesh rebuild)
            tr.localRotation = Quaternion.Euler(0f, 0f, _spin[i] * t * 0.12f);

            // Setting TextMesh.color REGENERATES the glyph mesh, so don't do all 40 every
            // frame — refresh a staggered 1/8 slice (each symbol still twinkles ~7x/sec).
            if ((i & 7) == (frame & 7))
            {
                var c = _tm[i].color;
                c.a = _baseA[i] * (0.7f + 0.3f * Mathf.Sin(t * 1.3f + _phase[i]));
                _tm[i].color = c;
            }
        }
    }

    public void Show() => gameObject.SetActive(true);
    public void Hide() => gameObject.SetActive(false);
}
