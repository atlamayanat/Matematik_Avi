using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// The selection brain ("Math Lens-Hunt"). The lens is a wide search beam, but
/// the actual selection target is the SINGLE token nearest the lens CENTRE — that
/// token is "armed" (LensHunt tells AnswerToken to glow/grow). A FIST confirms the
/// armed token. Ambiguity is therefore resolved BEFORE the fist.
///
/// Robustness against jittery, distant hand tracking comes from three hysteresis
/// layers so the armed token feels magnetically locked:
///   1. switchMargin  - a challenger must be CLEARLY closer (deadband), not just tie
///   2. switchDwell    - and stay the winner for a short time before we switch
///   3. arm/disarm radii - asymmetric Schmitt-trigger gate (harder to leave than enter)
///
/// Uses only the fixed input contract: SpotlightController.SelectionPosition (the
/// smoothed hand position WITHOUT the visual predictive lead) + the fist edge.
/// Nothing is added to the Python side.
/// </summary>
public class LensHunt : MonoBehaviour
{
    [SerializeField] SpotlightController spotlight;
    [SerializeField] RoundManager round;

    [Header("Reveal (manual spotlight falloff)")]
    [SerializeField] float revealRadius = 1.8f;  // tokens start fading in within this dist of the lens centre
    [SerializeField] float revealFull   = 0.5f;  // fully lit within this dist

    [Header("Arming / selection")]
    [SerializeField] float armRadius    = 1.05f; // a token must be this close to the centre to arm
    [SerializeField] float disarmRadius = 1.30f; // armed token only drops past here (> armRadius = hysteresis)
    [SerializeField] float switchMargin = 0.35f; // challenger must beat the armed one by this (world units)
    [SerializeField] float switchDwell  = 0.12f; // ...and hold that lead this long before we switch
    [SerializeField] float disarmGrace  = 0.10f; // grace before an out-of-range armed token drops

    readonly List<AnswerToken> _tokens = new List<AnswerToken>();
    AnswerToken _armed;
    float _switchTimer, _disarmTimer, _cooldown;
    bool _prevFist;
    bool _suspended = true; // dormant until the first SetTokens

    /// <summary>True while a token is currently armed (used to veto the RESET button mid-answer).</summary>
    public bool HasArmed => _armed != null;

    /// <summary>Hand the controller the current question's tokens (null = clear/suspend).</summary>
    public void SetTokens(List<AnswerToken> tokens)
    {
        _tokens.Clear();
        if (tokens != null) _tokens.AddRange(tokens);
        _armed = null;
        _switchTimer = 0f;
        _disarmTimer = 0f;
        _cooldown = 0.2f;       // brief settle before the first selection is accepted
        _prevFist = true;       // require a fresh open->fist after a (re)spawn
        _suspended = _tokens.Count == 0;
    }

    void Update()
    {
        if (_suspended) return;

        var hr = HandReceiver.Instance;
        if (hr == null || spotlight == null) return;

        if (_cooldown > 0f) _cooldown -= Time.deltaTime;

        // No player present -> keep the field dark and disarmed (attract mode).
        if (!hr.Present)
        {
            for (int i = 0; i < _tokens.Count; i++)
            {
                var t = _tokens[i];
                if (t != null) { t.SetReveal(0f); t.SetArmed(false); }
            }
            _armed = null;
            _switchTimer = 0f;
            _disarmTimer = 0f;
            _prevFist = false;
            return;
        }

        Vector3 c = spotlight.SelectionPosition; c.z = 0f;

        // Pass 1: reveal every token by proximity, find the nearest + the armed distance.
        AnswerToken nearest = null;
        float dN = float.MaxValue;
        float dA = float.MaxValue;
        for (int i = 0; i < _tokens.Count; i++)
        {
            var t = _tokens[i];
            if (t == null) continue;
            Vector3 p = t.WorldPos; p.z = 0f;
            float d = Vector2.Distance(c, p);
            t.SetReveal(Mathf.InverseLerp(revealRadius, revealFull, d)); // 0 far -> 1 near
            t.SetArmed(false);
            if (d < dN) { dN = d; nearest = t; }
            if (t == _armed) dA = d;
        }

        // Pass 2: arming hysteresis (frozen while cooling down).
        if (_cooldown <= 0f)
        {
            if (_armed != null && dA > disarmRadius)
            {
                _disarmTimer += Time.deltaTime;
                if (_disarmTimer >= disarmGrace) { _armed = null; _switchTimer = 0f; }
            }
            else _disarmTimer = 0f;

            if (_armed == null)
            {
                if (nearest != null && dN <= armRadius) { _armed = nearest; _switchTimer = 0f; }
            }
            else if (nearest != null && nearest != _armed && dN <= armRadius)
            {
                if (dN < dA - switchMargin) _switchTimer += Time.deltaTime;
                else _switchTimer = 0f;
                if (_switchTimer >= switchDwell) { _armed = nearest; _switchTimer = 0f; }
            }
        }

        if (_armed != null) _armed.SetArmed(true);

        // Confirm on the fist rising edge.
        bool fist = hr.Present && hr.IsFist;
        if (_cooldown <= 0f && fist && !_prevFist)
        {
            if (_armed != null)
            {
                bool ok = _armed.IsCorrect;
                _armed.Confirm(ok);
                if (spotlight != null) spotlight.PlaySelect(_armed.WorldPos);  // lens iris-closes onto the pick
                _armed = null;
                _suspended = true;                    // freeze until the next question
                if (round != null) round.OnAnswer(ok);
            }
            else
            {
                _cooldown = 0.15f;                    // harmless fist over empty dark space
            }
        }
        _prevFist = fist;
    }

#if UNITY_EDITOR
    void OnDrawGizmosSelected()
    {
        if (spotlight == null) return;
        Vector3 c = Application.isPlaying ? spotlight.SelectionPosition : spotlight.transform.position;
        Gizmos.color = Color.cyan;                       Gizmos.DrawWireSphere(c, armRadius);
        Gizmos.color = new Color(0f, 1f, 1f, 0.4f);      Gizmos.DrawWireSphere(c, disarmRadius);
        Gizmos.color = new Color(1f, 0.9f, 0.2f, 0.5f);  Gizmos.DrawWireSphere(c, revealRadius);
    }
#endif
}
