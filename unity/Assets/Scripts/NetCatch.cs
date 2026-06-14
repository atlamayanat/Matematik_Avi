using System.Collections;
using UnityEngine;

/// <summary>
/// The catch mechanic: when the player makes a FIST while the spotlight is over
/// the mouse, a net drops from above, the score increments, and the mouse
/// respawns elsewhere. Fires once per fist (edge-triggered), so holding a fist
/// does not chain catches.
/// </summary>
public class NetCatch : MonoBehaviour
{
    [SerializeField] SpotlightController spotlight;
    [SerializeField] MouseController mouse;
    [SerializeField] ScoreManager score;

    [Tooltip("Optional cheese-mouse visual - plays the 'caught' worried reaction.")]
    [SerializeField] CheeseMouseVisual reactions;

    [Tooltip("Net sprite, parked above; animated down on a catch. Optional.")]
    [SerializeField] Transform netVisual;

    [Tooltip("How close (world units) the spotlight centre must be to the mouse.")]
    [SerializeField] float catchRadius = 0.9f;

    // Ag maskeli (VisibleInsideMask) -> sadece mercek icinde gorunur. Bu yuzden
    // baslangic/bitis yuksekligini kisa tutuyoruz: ag mercegin ust kenarindan suzulup
    // iner, yakalar, yine mercek icinde yukari suzulup biter (siyah alandan gecmez).
    [SerializeField] float netDropHeight = 2.4f;
    [SerializeField] float netDropDuration = 0.35f;
    [SerializeField] float netHoldDuration = 0.18f;
    [SerializeField] float netRiseDuration = 0.32f;

    [Tooltip("Optional SFX played on a successful catch.")]
    [SerializeField] AudioSource catchSfx;

    bool _busy;
    bool _prevFist;

    void Update()
    {
        var hr = HandReceiver.Instance;
        if (hr == null) return;

        bool fist = hr.Present && hr.IsFist;
        if (!_busy && fist && !_prevFist && IsOverMouse())
            StartCoroutine(DoCatch());
        _prevFist = fist;
    }

    bool IsOverMouse()
    {
        if (spotlight == null || mouse == null) return false;
        Vector3 a = spotlight.WorldPosition; a.z = 0f;
        Vector3 b = mouse.WorldPosition;     b.z = 0f;
        return Vector3.Distance(a, b) <= catchRadius;
    }

    IEnumerator DoCatch()
    {
        _busy = true;
        if (reactions != null) reactions.Caught();   // mouse struggles
        Vector3 catchPos = mouse.WorldPosition;

        if (netVisual != null)
        {
            Vector3 top = catchPos + Vector3.up * netDropHeight;
            netVisual.position = top;
            netVisual.gameObject.SetActive(true);
            yield return Move(netVisual, top, catchPos, netDropDuration);
        }

        // Caught: score + respawn (mouse disappears under the net).
        if (catchSfx != null) catchSfx.Play();
        if (score != null) score.AddPoint();
        if (mouse != null) mouse.Respawn();

        if (netVisual != null)
        {
            yield return new WaitForSeconds(netHoldDuration);
            Vector3 top = catchPos + Vector3.up * netDropHeight;
            yield return Move(netVisual, catchPos, top, netRiseDuration);
            netVisual.gameObject.SetActive(false);
        }

        _busy = false;
        _prevFist = false; // require a fresh open->fist for the next catch
    }

    static IEnumerator Move(Transform tr, Vector3 from, Vector3 to, float dur)
    {
        float t = 0f;
        while (t < dur)
        {
            t += Time.deltaTime;
            float k = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(t / dur));
            tr.position = Vector3.Lerp(from, to, k);
            yield return null;
        }
        tr.position = to;
    }

#if UNITY_EDITOR
    void OnDrawGizmosSelected()
    {
        if (spotlight == null) return;
        Gizmos.color = Color.yellow;
        Gizmos.DrawWireSphere(spotlight.WorldPosition, catchRadius);
    }
#endif
}
