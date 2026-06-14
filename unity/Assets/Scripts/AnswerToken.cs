using System.Collections;
using UnityEngine;

/// <summary>
/// One answer token in the dark field. Renders a math glyph (a world-space
/// TextMesh, so we can fade its alpha) that:
///   - fades IN by proximity to the lens (manual "spotlight" reveal), and
///   - grows + glows + shows a halo when it is the ARMED token (the one the
///     next fist will select).
///
/// We use TextMesh (not UI.Text / TMP) because the glyph lives in WORLD space and
/// its alpha must be driven per-frame for the proximity reveal. The font (passed in
/// by MathField, i.e. GameFont/FredokaGame) renders the needed glyphs (0-9, × ÷ √ ² ¼ ½ ¾).
///
/// All visual decisions are driven from outside (LensHunt calls SetReveal /
/// SetArmed each frame); this component only eases toward those targets so the
/// highlight never pops.
/// </summary>
[DisallowMultipleComponent]
public class AnswerToken : MonoBehaviour
{
    public string Value { get; private set; }
    public bool IsCorrect { get; private set; }
    public Vector3 WorldPos => transform.position;

    [Header("Tuning")]
    public float armedScale = 1.35f;  // armed token grows to this * base
    public float haloScale = 0.95f;   // halo disc size (world units, * arm)
    public float revealLerp = 16f;    // how fast reveal alpha eases
    public float armLerp = 18f;       // how fast arm grow/glow eases

    static readonly Color BaseColor  = new Color(0.93f, 0.96f, 1f, 1f);  // soft white
    static readonly Color ArmedColor = new Color(1f, 0.86f, 0.32f, 1f);  // warm gold
    static readonly Color HaloColor  = new Color(1f, 0.80f, 0.24f, 1f);

    TextMesh _text;
    MeshRenderer _textMR;
    SpriteRenderer _halo;
    Transform _scaleRoot;

    float _litTarget, _lit;   // 0..1 proximity reveal
    float _armTarget, _arm;   // 0..1 armed amount
    bool _confirming;
    bool _dirty = true;       // only re-apply (rebuilds the TextMesh) when something changed

    /// <summary>Build the visual once. value=glyph, font/halo are shared assets.</summary>
    public void Init(string value, bool correct, Font font, Sprite halo)
    {
        Value = value;
        IsCorrect = correct;

        var root = new GameObject("Scale");
        root.transform.SetParent(transform, false);
        _scaleRoot = root.transform;

        var h = new GameObject("Halo");
        h.transform.SetParent(_scaleRoot, false);
        h.transform.localScale = Vector3.one * haloScale;
        _halo = h.AddComponent<SpriteRenderer>();
        _halo.sprite = halo;
        _halo.color = new Color(HaloColor.r, HaloColor.g, HaloColor.b, 0f);
        _halo.sortingOrder = 20;

        var g = new GameObject("Glyph");
        g.transform.SetParent(_scaleRoot, false);
        _text = g.AddComponent<TextMesh>();
        _text.font = font;
        _text.text = value;
        _text.anchor = TextAnchor.MiddleCenter;
        _text.alignment = TextAlignment.Center;
        _text.fontSize = 48;
        _text.characterSize = 0.115f;  // a bit bigger so it reads when wall-projected
        _text.color = new Color(BaseColor.r, BaseColor.g, BaseColor.b, 0f);
        _textMR = g.GetComponent<MeshRenderer>();
        _textMR.sharedMaterial = font.material;  // required for TextMesh built via script
        _textMR.sortingOrder = 21;

        ApplyVisual();
    }

    public void SetReveal(float lit)
    {
        if (_confirming) return;
        lit = Mathf.Clamp01(lit);
        if (lit != _litTarget) { _litTarget = lit; _dirty = true; }
    }

    public void SetArmed(bool armed)
    {
        if (_confirming) return;
        float a = armed ? 1f : 0f;
        if (a != _armTarget) { _armTarget = a; _dirty = true; }
    }

    void Update()
    {
        if (_confirming || !_dirty) return;   // idle tokens (far from the lens) cost nothing

        float dt = Mathf.Max(Time.deltaTime, 1e-4f);
        _lit = Mathf.Lerp(_lit, _litTarget, 1f - Mathf.Exp(-revealLerp * dt));
        _arm = Mathf.Lerp(_arm, _armTarget, 1f - Mathf.Exp(-armLerp * dt));

        // Once we've eased close enough, snap to target and stop rebuilding.
        if (Mathf.Abs(_lit - _litTarget) < 0.004f && Mathf.Abs(_arm - _armTarget) < 0.004f)
        {
            _lit = _litTarget;
            _arm = _armTarget;
            _dirty = false;
        }

        ApplyVisual();
    }

    void ApplyVisual()
    {
        // The armed token stays fully lit even if it drifts slightly off-centre.
        float vis = Mathf.Max(_lit, _arm);

        if (_text != null)
        {
            Color tc = Color.Lerp(BaseColor, ArmedColor, _arm);
            tc.a = vis;
            _text.color = tc;
        }
        if (_halo != null)
        {
            Color hc = HaloColor;
            hc.a = _arm * 0.7f * Mathf.Max(vis, 0.0001f);
            _halo.color = hc;
        }
        if (_scaleRoot != null)
            _scaleRoot.localScale = Vector3.one * Mathf.Lerp(1f, armedScale, _arm);
    }

    /// <summary>Play a quick punch + colour flash; token is destroyed soon after.</summary>
    public void Confirm(bool correct)
    {
        if (_confirming) return;
        _confirming = true;
        StartCoroutine(ConfirmRoutine(correct));
    }

    IEnumerator ConfirmRoutine(bool correct)
    {
        Color flash = correct ? new Color(0.45f, 1f, 0.55f) : new Color(1f, 0.45f, 0.45f);
        float t = 0f;
        const float dur = 0.5f;
        while (t < dur)
        {
            t += Time.deltaTime;
            float k = Mathf.Clamp01(t / dur);
            float s = armedScale * (1f + 0.45f * Mathf.Sin(k * Mathf.PI));
            if (_scaleRoot != null) _scaleRoot.localScale = Vector3.one * s;
            float a = 1f - k;
            if (_text != null) { var c = flash; c.a = a; _text.color = c; }
            if (_halo != null) { var c = flash; c.a = a * 0.7f; _halo.color = c; }
            yield return null;
        }
        if (_text != null) { var c = _text.color; c.a = 0f; _text.color = c; }
        if (_halo != null) { var c = _halo.color; c.a = 0f; _halo.color = c; }
    }
}
