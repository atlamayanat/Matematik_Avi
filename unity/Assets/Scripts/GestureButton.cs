using System;
using System.Collections;
using UnityEngine;

/// <summary>
/// A world-space PILL button the player selects with the LENS: move the lens over
/// it (it highlights + grows), then make a FIST to press it. Used for "BAŞLA" and
/// the in-game "RESET" button.
///
/// The label is rendered crisp (high fontSize) and AUTO-FIT to the pill width at
/// runtime, so any text length fits without overflowing. Visuals are generated at
/// runtime (no art assets). An optional gate (SetGate) can veto a press — RESET
/// uses it so it never fires on the same fist that confirms an answer token.
/// </summary>
[DisallowMultipleComponent]
public class GestureButton : MonoBehaviour
{
    [Header("Set by the builder")]
    [SerializeField] string labelText = "BAŞLA";
    [SerializeField] string subLabel = "";       // optional caption under the pill (e.g. "5-10 yaş")
    [SerializeField] Color color = new Color(0.30f, 0.80f, 0.45f);
    [SerializeField] float radius = 1.7f;        // lens centre within this = hovered
    [SerializeField] float bodyScale = 1.3f;     // pill HEIGHT in world units
    [SerializeField] float bodyAspect = 2.8f;    // width / height (pill stretch)
    [SerializeField] float labelSize = 0.10f;    // base TextMesh characterSize (auto-fit shrinks it)
    [SerializeField] SpotlightController spot;

    [Header("Corner pin (optional) - hug the camera's top-right corner on ANY aspect ratio")]
    [SerializeField] bool pinTopRight = false;   // RESET uses this so it sits in the true corner regardless of screen/projector shape
    [SerializeField] float pinMargin = 0.3f;     // world-unit gap kept between the pill body and the screen edges
    [SerializeField] Camera pinCamera;

    [Header("Feel")]
    [SerializeField] float idlePulse = 0.05f;
    [SerializeField] float pulseSpeed = 2.4f;
    [SerializeField] float hoverGrow = 0.18f;
    [SerializeField] bool closeLensOnPress = true;

    Action _onSelect;
    Func<bool> _gate;
    Transform _scaleRoot, _labelGO, _subGO;
    SpriteRenderer _glow, _body;
    Renderer _labelRenderer, _subRenderer;
    float _hover, _press;
    bool _prevFist, _busy, _built;
    float _cooldown;

    void Awake() { if (Application.isPlaying) Build(); }  // never build at edit time

    void OnEnable()
    {
        // (Re)entering active state must always leave the button usable, even if a
        // previous press coroutine was killed by the object being hidden mid-press.
        _busy = false;
        _press = 0f;
        _prevFist = true;
        _cooldown = 0.25f;
        // Re-fit the label on every (re)activation. The very first activation is
        // deactivated again in RoundManager.Start() the same frame, which kills the
        // fit coroutine before it can measure; running it here means the label is
        // always correctly sized by the time the button is actually shown.
        if (_built && Application.isPlaying) StartCoroutine(FitLabel());
    }

    public void Bind(Action onSelect) => _onSelect = onSelect;
    public void SetGate(Func<bool> gate) => _gate = gate;

    void Build()
    {
        if (_built) return;
        _built = true;

        var root = new GameObject("Visual");
        root.transform.SetParent(transform, false);
        _scaleRoot = root.transform;
        _scaleRoot.localScale = Vector3.one * bodyScale;

        var g = new GameObject("Glow");
        g.transform.SetParent(_scaleRoot, false);
        g.transform.localScale = new Vector3(bodyAspect * 1.5f, 1.5f, 1f);
        _glow = g.AddComponent<SpriteRenderer>();
        _glow.sprite = Gfx.SoftCircle(96);
        _glow.color = new Color(color.r, color.g, color.b, 0f);
        _glow.sortingOrder = 60;

        var b = new GameObject("Body");
        b.transform.SetParent(_scaleRoot, false);
        b.transform.localScale = new Vector3(bodyAspect, 1f, 1f);
        _body = b.AddComponent<SpriteRenderer>();
        _body.sprite = Gfx.Disc(128);
        _body.color = color;
        _body.sortingOrder = 61;

        var rim = new GameObject("Rim");
        rim.transform.SetParent(_scaleRoot, false);
        rim.transform.localScale = new Vector3(bodyAspect * 1.04f, 1.04f, 1f);
        var rimSr = rim.AddComponent<SpriteRenderer>();
        rimSr.sprite = Gfx.Ring(128, 0.05f);
        rimSr.color = new Color(1f, 1f, 1f, 0.85f);
        rimSr.sortingOrder = 62;

        var t = new GameObject("Label");
        t.transform.SetParent(_scaleRoot, false);
        t.transform.localPosition = new Vector3(0f, 0f, -0.01f);
        _labelGO = t.transform;
        var label = t.AddComponent<TextMesh>();
        label.font = GameFont.Get();
        label.text = labelText;
        label.anchor = TextAnchor.MiddleCenter;
        label.alignment = TextAlignment.Center;
        label.fontSize = 140;             // high res atlas -> crisp when scaled up
        label.fontStyle = FontStyle.Bold;
        label.characterSize = labelSize;
        label.color = Color.white;
        _labelRenderer = t.GetComponent<MeshRenderer>();
        _labelRenderer.sharedMaterial = label.font.material;
        ((MeshRenderer)_labelRenderer).sortingOrder = 63;

        // Optional caption UNDER the pill (e.g. an age/level hint). Parented to the
        // button root (not _scaleRoot) so it stays put while the pill pulses/grows.
        if (!string.IsNullOrEmpty(subLabel))
        {
            var s = new GameObject("SubLabel");
            s.transform.SetParent(transform, false);
            s.transform.localPosition = new Vector3(0f, -(bodyScale * 0.5f + 0.34f), -0.01f);
            _subGO = s.transform;
            var sub = s.AddComponent<TextMesh>();
            sub.font = GameFont.Get();
            sub.text = subLabel;
            sub.anchor = TextAnchor.MiddleCenter;
            sub.alignment = TextAlignment.Center;
            sub.fontSize = 96;
            sub.characterSize = 0.07f;
            sub.color = new Color(1f, 1f, 1f, 0.82f);
            _subRenderer = s.GetComponent<MeshRenderer>();
            _subRenderer.sharedMaterial = sub.font.material;
            ((MeshRenderer)_subRenderer).sortingOrder = 63;
        }
        // FitLabel is kicked off from OnEnable (which runs right after Build), so the
        // label (+ caption) are re-fitted every time the button is shown — not just here.
    }

    IEnumerator FitLabel()
    {
        // Reset to base scale first so repeated runs are idempotent, then wait for the
        // text meshes to (re)generate and shrink the label + caption to fit.
        if (_labelGO == null || _labelRenderer == null) yield break;
        _labelGO.localScale = Vector3.one;
        if (_subGO != null) _subGO.localScale = Vector3.one;
        yield return null;
        yield return null;
        if (_labelGO != null && _labelRenderer != null)
        {
            float w = _labelRenderer.bounds.size.x;
            float target = bodyAspect * bodyScale * 0.78f; // 78% of the pill width
            if (w > 0.001f && w > target) _labelGO.localScale = Vector3.one * (target / w);
        }
        if (_subGO != null && _subRenderer != null)
        {
            float w = _subRenderer.bounds.size.x;
            float target = bodyAspect * bodyScale * 1.5f;  // caption may be a touch wider than the pill
            if (w > 0.001f && w > target) _subGO.localScale = Vector3.one * (target / w);
        }
    }

    void Update()
    {
        float dt = Mathf.Max(Time.deltaTime, 1e-4f);
        if (_cooldown > 0f) _cooldown -= dt;

        if (pinTopRight && pinCamera != null) PinToCorner();

        var hr = HandReceiver.Instance;
        bool fist = hr != null && hr.Present && hr.IsFist;
        bool over = false;

        if (!_busy && hr != null && spot != null && hr.Present)
        {
            Vector3 c = spot.SelectionPosition; c.z = 0f;
            Vector3 p = transform.position; p.z = 0f;
            over = Vector2.Distance(c, p) <= radius;

            if (_cooldown <= 0f && over && fist && !_prevFist && (_gate == null || _gate()))
                Press();
        }

        _hover = Mathf.Lerp(_hover, over ? 1f : 0f, 1f - Mathf.Exp(-12f * dt));
        ApplyVisual();
        _prevFist = fist;
    }

    // Place the button so the pill body sits a fixed margin from the camera's
    // top-right corner. Because it is derived from the live ortho size + aspect, it
    // lands in the corner on every screen shape (16:9 projector, ultrawide editor...).
    void PinToCorner()
    {
        float halfW = pinCamera.orthographicSize * pinCamera.aspect;
        float halfH = pinCamera.orthographicSize;
        float bodyHalfW = bodyScale * bodyAspect * 0.5f;
        float bodyHalfH = bodyScale * 0.5f;
        Vector3 p = transform.position;
        p.x = halfW - bodyHalfW - pinMargin;
        p.y = halfH - bodyHalfH - pinMargin;
        p.z = 0f;
        transform.position = p;
    }

    void ApplyVisual()
    {
        if (_scaleRoot == null) return;
        float pulse = 1f + idlePulse * Mathf.Sin(Time.time * pulseSpeed);
        _scaleRoot.localScale = Vector3.one * (bodyScale * (pulse + _hover * hoverGrow + _press));

        if (_glow != null)
        {
            var gc = color; gc.a = 0.18f + 0.55f * _hover;
            _glow.color = gc;
        }
        if (_body != null)
            _body.color = Color.Lerp(color, Color.Lerp(color, Color.white, 0.25f), _hover);
    }

    void Press()
    {
        _busy = true;
        _cooldown = 0.6f;
        if (closeLensOnPress && spot != null) spot.PlaySelect(transform.position);
        StartCoroutine(PressRoutine());
    }

    IEnumerator PressRoutine()
    {
        float t = 0f;
        while (t < 0.16f)
        {
            t += Time.deltaTime;
            _press = 0.30f * Mathf.Sin(Mathf.Clamp01(t / 0.16f) * Mathf.PI);
            ApplyVisual();
            yield return null;
        }
        _press = 0f;
        _busy = false;
        _prevFist = true;
        ApplyVisual();
        _onSelect?.Invoke();   // may deactivate us; flags already cleared
    }
}
