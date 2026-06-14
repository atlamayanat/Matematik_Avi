using UnityEngine;

/// <summary>
/// The hidden mouse (eating cheese). It is only visible when the spotlight mask
/// passes over it. Spawns at a random spot inside the play area, and Respawn()
/// moves it to a new random spot after each catch.
///
/// Put this object's SpriteRenderer(s) on the masked sort layer so it is
/// revealed only inside the SpriteMask (see Unity README).
/// </summary>
public class MouseController : MonoBehaviour
{
    [SerializeField] Camera targetCamera;

    [Tooltip("Keep the mouse away from the edges (fraction of viewport).")]
    [SerializeField, Range(0f, 0.45f)] float marginX = 0.14f;
    [SerializeField, Range(0f, 0.45f)] float marginY = 0.14f;

    [SerializeField] float zDepth = 0f;

    [Tooltip("Optional Animator playing the idle 'eating cheese' loop.")]
    [SerializeField] Animator animator;

    [Tooltip("Don't respawn closer than this (viewport fraction) to the last "
             + "spot, so it visibly moves.")]
    [SerializeField, Range(0f, 0.5f)] float minMoveFraction = 0.25f;

    Camera Cam => targetCamera != null ? targetCamera : Camera.main;
    Vector2 _lastViewport = new Vector2(0.5f, 0.5f);

    public Vector3 WorldPosition => transform.position;

    void Start() => Respawn();

    public void Respawn()
    {
        Vector2 vp = _lastViewport;
        // Try a few times to land far enough from the previous position.
        for (int i = 0; i < 8; i++)
        {
            vp = new Vector2(Random.Range(marginX, 1f - marginX),
                             Random.Range(marginY, 1f - marginY));
            if (Vector2.Distance(vp, _lastViewport) >= minMoveFraction) break;
        }
        _lastViewport = vp;

        Vector3 w = Cam.ViewportToWorldPoint(new Vector3(vp.x, vp.y, 1f));
        w.z = zDepth;
        transform.position = w;

        if (animator != null) animator.Play(0, 0, 0f); // restart idle anim
    }
}
