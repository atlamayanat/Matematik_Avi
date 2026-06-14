using UnityEngine;

/// <summary>
/// Gentle idle motion so the mouse looks alive ("eating") while it waits to be
/// found. Pure transform animation - no Animator or extra art needed. Attach to
/// the VISUAL child (its local transform), so it never fights MouseController,
/// which moves the logical parent on respawn.
/// </summary>
public class MouseIdle : MonoBehaviour
{
    [SerializeField] float bobAmplitude = 0.07f;   // vertical bob (local units)
    [SerializeField] float bobSpeed = 3.2f;        // cycles-ish per second
    [SerializeField] float squash = 0.05f;         // breathing squash/stretch
    [SerializeField] float tiltDegrees = 4f;       // gentle rocking

    Vector3 _basePos;
    Vector3 _baseScale;
    float _phase;

    void OnEnable()
    {
        _basePos = transform.localPosition;
        _baseScale = transform.localScale;
        // Desync each spawn a little so repeated catches don't look mechanical.
        _phase = Mathf.Abs(transform.position.x) * 1.7f;
    }

    void Update()
    {
        float t = (Time.time + _phase) * bobSpeed;
        transform.localPosition = _basePos + new Vector3(0f, Mathf.Sin(t) * bobAmplitude, 0f);
        float s = Mathf.Sin(t * 2f) * squash;
        transform.localScale = new Vector3(_baseScale.x * (1f + s),
                                           _baseScale.y * (1f - s),
                                           _baseScale.z);
        transform.localRotation = Quaternion.Euler(0f, 0f, Mathf.Sin(t) * tiltDegrees);
    }
}
