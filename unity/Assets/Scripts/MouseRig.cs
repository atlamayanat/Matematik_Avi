using UnityEngine;

/// <summary>
/// Drives the 2-part mouse rig (separate HEAD + BODY sprites that share the neck
/// pivot) with smooth, continuous skeletal motion - NOT frame swapping.
///
/// States blend smoothly:
///   Idle  : gentle breathing (body squash) + soft head bob & chew nod.
///   Panic : head lifts and looks up, faster trembling - when the spotlight is
///           hovering near the mouse (the player is about to grab it).
///   Caught: a short, strong struggle (shake + squash) triggered on the catch,
///           while NetCatch lifts the whole mouse away.
///
/// All motion is real rig movement around the neck joint, so it reads like a
/// rigged cartoon character. Amplitudes are inspector-tunable.
/// </summary>
public class MouseRig : MonoBehaviour
{
    [SerializeField] Transform head;
    [SerializeField] Transform body;
    [SerializeField] SpotlightController spotlight;
    [SerializeField] Transform mouseRoot;          // logical mouse position
    [SerializeField] float panicDistance = 1.6f;   // world units to start panic

    [Header("Idle")]
    [SerializeField] float breatheAmp = 0.22f;     // head bob (local units)
    [SerializeField] float breatheSpeed = 2.2f;
    [SerializeField] float chewAmp = 0.10f;
    [SerializeField] float chewSpeed = 7f;
    [SerializeField] float chewRotDeg = 2.5f;
    [SerializeField] float bodyBreatheSquash = 0.03f;

    [Header("Panic")]
    [SerializeField] float panicHeadUp = 0.7f;
    [SerializeField] float panicLookUpDeg = -12f;
    [SerializeField] float panicTrembleSpeed = 26f;

    [Header("Caught")]
    [SerializeField] float caughtDuration = 0.9f;
    [SerializeField] float caughtShake = 0.5f;

    Vector3 _headRest, _bodyScaleRest, _bodyPosRest;
    float _t, _intensity, _caught;

    void Start()
    {
        if (head) _headRest = head.localPosition;
        if (body) { _bodyScaleRest = body.localScale; _bodyPosRest = body.localPosition; }
    }

    /// <summary>Trigger the struggle reaction (called by NetCatch on a catch).</summary>
    public void Caught() => _caught = caughtDuration;

    void Update()
    {
        float dt = Time.deltaTime;
        _t += dt;

        bool present = HandReceiver.Instance != null && HandReceiver.Instance.Present;
        bool near = false;
        if (present && spotlight != null && mouseRoot != null)
        {
            Vector3 a = spotlight.WorldPosition; a.z = 0f;
            Vector3 b = mouseRoot.position; b.z = 0f;
            near = Vector3.Distance(a, b) <= panicDistance;
        }
        if (_caught > 0f) _caught -= dt;
        _intensity = Mathf.MoveTowards(_intensity, near ? 1f : 0f, dt * 4f);

        float breath = Mathf.Sin(_t * breatheSpeed);
        float chew = Mathf.Sin(_t * chewSpeed);

        float headY = breath * breatheAmp + chew * chewAmp;
        float headRot = chew * chewRotDeg;
        float squash = breath * bodyBreatheSquash;
        float shakeX = 0f;

        if (_intensity > 0.001f)
        {
            float tr = Mathf.Sin(_t * panicTrembleSpeed);
            headY = Mathf.Lerp(headY, panicHeadUp + tr * 0.06f, _intensity);
            headRot = Mathf.Lerp(headRot, panicLookUpDeg + tr * 5f, _intensity);
            squash = Mathf.Lerp(squash, tr * 0.05f, _intensity);
        }

        if (_caught > 0f)
        {
            float c = Mathf.Clamp01(_caught / Mathf.Max(0.01f, caughtDuration));
            headY += Mathf.Sin(_t * 40f) * 0.25f * c;
            headRot += Mathf.Sin(_t * 40f) * 14f * c;
            squash += Mathf.Sin(_t * 38f) * 0.08f * c;
            shakeX = Mathf.Sin(_t * 47f) * caughtShake * c;
        }

        if (head != null)
        {
            head.localPosition = _headRest + new Vector3(shakeX, headY, 0f);
            head.localRotation = Quaternion.Euler(0f, 0f, headRot);
        }
        if (body != null)
        {
            body.localScale = new Vector3(_bodyScaleRest.x * (1f - squash),
                                          _bodyScaleRest.y * (1f + squash),
                                          _bodyScaleRest.z);
            body.localPosition = _bodyPosRest + new Vector3(shakeX * 0.5f, 0f, 0f);
        }
    }
}
