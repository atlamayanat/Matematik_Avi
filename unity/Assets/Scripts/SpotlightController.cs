using System.Collections;
using UnityEngine;

/// <summary>
/// Moves the circular "magnifier / flashlight" to the hand position each frame.
/// Attach to the GameObject that carries the circular SpriteMask (the reveal
/// circle). The mouse layer is drawn only inside this mask.
///
/// The camera only delivers ~30 hand updates/sec, so this renders at the display
/// rate by (a) exponentially smoothing toward the latest target (turns 30 fps
/// steps into fluid 60 fps motion) and (b) adding a small velocity-based
/// PREDICTION lead that cancels most of the perceived input lag. Python's One
/// Euro filter still removes jitter upstream.
/// </summary>
public class SpotlightController : MonoBehaviour
{
    [Tooltip("Orthographic camera that renders the projected scene.")]
    [SerializeField] Camera targetCamera;

    [Tooltip("Image Y is top-down but viewport Y is bottom-up; usually keep ON.")]
    [SerializeField] bool flipY = true;

    [Tooltip("World Z plane the spotlight sits on (2D: keep 0).")]
    [SerializeField] float zDepth = 0f;

    [Tooltip("Higher = snappier catch-up to the latest sample (smooths 30->60 fps). "
             + "Too high re-introduces stepping; too low feels laggy.")]
    [SerializeField] float followSpeed = 25f;

    [Tooltip("Seconds of velocity look-ahead. Cancels perceived input lag; too "
             + "much makes the circle overshoot when the hand stops.")]
    [SerializeField] float predictionSeconds = 0.015f;

    [Tooltip("Caps how far (world units) the prediction may lead, so a fast hand "
             + "reversal can't overshoot and 'tear'. ~0.3-0.4 is plenty.")]
    [SerializeField] float maxLead = 0.35f;

    [Tooltip("Optional object to hide while no player is present (e.g. the ring).")]
    [SerializeField] GameObject visualRoot;

    [Header("Input range expansion (reach the screen edges/corners safely)")]
    [Tooltip("The hand only reliably tracks in the CENTRE of the camera frame; the very "
             + "edge is where MediaPipe loses a half-out-of-frame hand. This maps the "
             + "comfortable centre band [margin, 1-margin] onto the full screen [0,1], so "
             + "the player reaches a screen edge while the hand is still well inside the "
             + "frame. 0 = off (1:1). ~0.08-0.12 makes the corners selectable.")]
    [SerializeField, Range(0f, 0.3f)] float edgeMarginX = 0.10f;
    [SerializeField, Range(0f, 0.3f)] float edgeMarginY = 0.10f;

    Camera Cam => targetCamera != null ? targetCamera : Camera.main;

    // Stretch a comfortable centre band of the input to the full [0,1] screen range.
    static float Expand(float v, float m)
    {
        if (m <= 0f) return Mathf.Clamp01(v);
        return Mathf.Clamp01((v - m) / (1f - 2f * m));
    }
    Vector3 _smooth;
    Vector3 _vel;
    bool _has;

    void Reset() { targetCamera = Camera.main; }

    void Update()
    {
        var hr = HandReceiver.Instance;
        if (hr == null) return;

        if (visualRoot != null && visualRoot.activeSelf != hr.Present)
            visualRoot.SetActive(hr.Present);

        Vector2 n = hr.Normalized;
        float nx = Expand(n.x, edgeMarginX);
        float ny = Expand(n.y, edgeMarginY);
        float vy = flipY ? 1f - ny : ny;
        Vector3 target = Cam.ViewportToWorldPoint(new Vector3(nx, vy, 1f));
        target.z = zDepth;

        if (!_has)
        {
            _smooth = target;
            _vel = Vector3.zero;
            _has = true;
            transform.position = target;
            return;
        }

        float dt = Mathf.Max(Time.deltaTime, 1e-4f);
        Vector3 prev = _smooth;

        // Frame-rate-independent exponential approach to the latest target.
        float k = followSpeed <= 0f ? 1f : 1f - Mathf.Exp(-followSpeed * dt);
        _smooth = Vector3.Lerp(_smooth, target, k);

        // Smoothed velocity of the eased point, then a short predictive lead.
        Vector3 instVel = (_smooth - prev) / dt;
        _vel = Vector3.Lerp(_vel, instVel, 1f - Mathf.Exp(-12f * dt));

        Vector3 lead = Vector3.ClampMagnitude(_vel * predictionSeconds, maxLead);
        transform.position = _smooth + lead;
    }

    /// <summary>Current spotlight centre in world space (used by NetCatch).</summary>
    public Vector3 WorldPosition => transform.position;

    /// <summary>
    /// Spotlight centre WITHOUT the predictive lead - the stable smoothed hand
    /// position. Aiming/selection logic (LensHunt) should use THIS: the predictive
    /// lead is a visual-only trick to hide input lag and would bias which token is
    /// "nearest" when the hand is moving.
    /// </summary>
    public Vector3 SelectionPosition => _has ? _smooth : transform.position;

    // ---- Selection feedback: the lens iris CLOSES toward the chosen target ----
    [Header("Select feedback (iris close on a fist)")]
    [Tooltip("How far the lens shrinks on a pick (1 = none, 0 = fully closed). Not fully closed.")]
    [SerializeField] float selectCloseScale = 0.36f;
    [Tooltip("Fraction of the way the lens slides ONTO the picked target.")]
    [SerializeField] float selectAdvance = 0.8f;
    [SerializeField] float selectCloseDur = 0.16f;
    [SerializeField] float selectHoldDur = 0.10f;
    [SerializeField] float selectOpenDur = 0.24f;

    Coroutine _selectCo;

    /// <summary>
    /// Play the "you picked THIS" feedback: as the hand closes, the lens circle
    /// contracts and slides onto <paramref name="targetWorld"/>, holds, then
    /// reopens. Animates only the Visuals child's local transform, so it never
    /// disturbs the hand-follow or SelectionPosition (selection already fired).
    /// </summary>
    public void PlaySelect(Vector3 targetWorld)
    {
        if (visualRoot == null) return;
        if (_selectCo != null) StopCoroutine(_selectCo);
        _selectCo = StartCoroutine(SelectAnim(targetWorld));
    }

    IEnumerator SelectAnim(Vector3 targetWorld)
    {
        Transform v = visualRoot.transform;
        Vector3 worldOffset = targetWorld - transform.position;
        Vector3 localTarget = (v.parent != null
            ? v.parent.InverseTransformVector(worldOffset)
            : worldOffset) * selectAdvance;
        Vector3 small = Vector3.one * selectCloseScale;

        yield return Tween(v, Vector3.zero, localTarget, Vector3.one, small, selectCloseDur);
        if (selectHoldDur > 0f) yield return new WaitForSeconds(selectHoldDur);
        yield return Tween(v, localTarget, Vector3.zero, small, Vector3.one, selectOpenDur);

        v.localPosition = Vector3.zero;
        v.localScale = Vector3.one;
        _selectCo = null;
    }

    static IEnumerator Tween(Transform v, Vector3 p0, Vector3 p1, Vector3 s0, Vector3 s1, float dur)
    {
        float t = 0f;
        while (t < dur)
        {
            t += Time.deltaTime;
            float k = 1f - Mathf.Pow(1f - Mathf.Clamp01(t / dur), 3f); // ease-out cubic
            v.localPosition = Vector3.LerpUnclamped(p0, p1, k);
            v.localScale = Vector3.LerpUnclamped(s0, s1, k);
            yield return null;
        }
        v.localPosition = p1;
        v.localScale = s1;
    }
}
