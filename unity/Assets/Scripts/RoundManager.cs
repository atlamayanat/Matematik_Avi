using System.Collections;
using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// Owns the whole flow as a small state machine:
///   ATTRACT  -> the StartScreen is shown; the player picks a difficulty (KOLAY /
///               ORTA / ZOR) with the lens + a fist, which also starts the round.
///   PLAYING  -> 5 questions at the chosen difficulty, one 120 s countdown (last 10 s
///               red); a RESET button (top-right, under the timer) returns to ATTRACT.
/// On launch and after every round it returns to ATTRACT, so a fresh player always
/// picks their level again.
///
/// LensHunt calls OnAnswer(bool) on each fist selection. The difficulty buttons call
/// StartGame(level) and RESET calls ResetToStart, bound in Start().
/// </summary>
public class RoundManager : MonoBehaviour
{
    enum GameState { Attract, Playing }

    [SerializeField] LensHunt lens;
    [SerializeField] MathField field;

    [Header("UI (UnityEngine.UI.Text)")]
    [SerializeField] Text promptText;
    [SerializeField] Text timerText;
    [SerializeField] Text progressText;
    [SerializeField] Text correctText;
    [SerializeField] Text resultText;

    [Header("Start screen + buttons")]
    [SerializeField] StartScreen startScreen;
    [SerializeField] GestureButton easyButton;
    [SerializeField] GestureButton mediumButton;
    [SerializeField] GestureButton hardButton;
    [SerializeField] GestureButton resetButton;

    [Header("Rules")]
    [SerializeField] int totalQuestions = 5;
    [SerializeField] float roundSeconds = 120f;
    [SerializeField] int correctCopies = 3;
    [SerializeField] int totalTokens = 36;
    [SerializeField] int decoyVariety = 14;
    [SerializeField] float lowTimeThreshold = 10f;
    [SerializeField] float resolveDelay = 0.85f;  // pause after an answer so the lens close + result read
    [SerializeField] float endSummarySeconds = 4f;

    readonly QuestionGenerator _gen = new QuestionGenerator();
    MathProblem _problem;
    GameState _state = GameState.Attract;
    Difficulty _difficulty = Difficulty.Easy;
    int _qNum, _correct;
    float _timeLeft;
    bool _running;

    void Awake()
    {
#if UNITY_EDITOR
        // Editor: no vSync + uncapped so the Game view shows the true (high) fps. NOTE the
        // editor's own present-wait can still halve the on-screen number when the Game view
        // is NOT maximized — that's an editor artifact, not real load (Maximize to see true).
        QualitySettings.vSyncCount = 0;
        Application.targetFrameRate = -1;
#else
        // Standalone build (the exhibit): sync to the display so frames are evenly paced and
        // run at the monitor's refresh (60 / 144 / 240...). A targetFrameRate-only cap uses a
        // sleep limiter that JUDDERS in a build; vSync=1 paces cleanly.
        QualitySettings.vSyncCount = 1;
        Application.targetFrameRate = -1;
#endif
        EnsureHandReceiver();
    }

    void Start()
    {
        if (easyButton != null)   easyButton.Bind(()   => StartGame(Difficulty.Easy));
        if (mediumButton != null) mediumButton.Bind(() => StartGame(Difficulty.Medium));
        if (hardButton != null)   hardButton.Bind(()   => StartGame(Difficulty.Hard));
        if (resetButton != null)
        {
            resetButton.Bind(ResetToStart);
            resetButton.SetGate(() => lens == null || !lens.HasArmed); // never reset mid-answer
        }
        EnterAttract();
    }

    void EnsureHandReceiver()
    {
        if (Object.FindAnyObjectByType<HandReceiver>() == null)
        {
            var go = new GameObject("HandReceiver");
            go.AddComponent<HandReceiver>();
        }
    }

    // ---------------------------------------------------------------- states
    void EnterAttract()
    {
        _state = GameState.Attract;
        _running = false;
        StopAllCoroutines();
        if (field != null) field.Clear();
        if (lens != null) lens.SetTokens(null);
        SetGameUiVisible(false);
        HideResult();
        if (resetButton != null) resetButton.gameObject.SetActive(false);
        if (startScreen != null) startScreen.Show();
    }

    void StartGame(Difficulty d)   // bound to the KOLAY / ORTA / ZOR buttons
    {
        if (_state == GameState.Playing) return;
        _difficulty = d;
        if (startScreen != null) startScreen.Hide();
        SetGameUiVisible(true);
        if (resetButton != null) resetButton.gameObject.SetActive(true);
        BeginRound();
    }

    void ResetToStart()    // bound to the RESET button
    {
        EnterAttract();
    }

    void BeginRound()
    {
        _state = GameState.Playing;
        _qNum = 1;
        _correct = 0;
        _timeLeft = roundSeconds;
        _running = true;
        UpdateCorrect();
        UpdateTimerUI();
        HideResult();
        NextQuestion();
    }

    void NextQuestion()
    {
        _problem = _gen.Next(_difficulty);
        var decoys = _gen.MakeDecoys(_problem, decoyVariety);
        var tokens = field.Spawn(_problem, decoys, correctCopies, totalTokens);
        lens.SetTokens(tokens);
        if (promptText != null) promptText.text = _problem.Prompt;
        if (progressText != null) progressText.text = $"Soru {_qNum}/{totalQuestions}  ({DifficultyName(_difficulty)})";
        HideResult();
    }

    static string DifficultyName(Difficulty d)
    {
        switch (d)
        {
            case Difficulty.Medium: return "Orta";
            case Difficulty.Hard:   return "Zor";
            default:                return "Kolay";
        }
    }

    /// <summary>Called by LensHunt when the player fists on an armed token.</summary>
    public void OnAnswer(bool correct)
    {
        if (_state != GameState.Playing || !_running) return;
        if (correct)
        {
            _correct++;
            ShowResult("Doğru!", new Color(0.45f, 1f, 0.55f));
        }
        else
        {
            ShowResult("Yanlış", new Color(1f, 0.5f, 0.5f));
        }
        UpdateCorrect();
        StartCoroutine(AfterAnswer());
    }

    IEnumerator AfterAnswer()
    {
        yield return new WaitForSeconds(resolveDelay);
        if (_state != GameState.Playing || !_running) yield break; // reset/timeout during the pause
        _qNum++;
        if (_qNum > totalQuestions) EndRound(false);
        else NextQuestion();
    }

    void EndRound(bool timeout)
    {
        _running = false;
        if (lens != null) lens.SetTokens(null);
        if (field != null) field.Clear();
        if (promptText != null) promptText.text = "";
        string head = timeout ? "Süre doldu!" : "Bitti!";
        ShowResult($"{head}\nDoğru: {_correct}/{totalQuestions}", Color.white);
        StartCoroutine(EndThenAttract());
    }

    IEnumerator EndThenAttract()
    {
        yield return new WaitForSeconds(endSummarySeconds);
        EnterAttract();
    }

    void Update()
    {
        if (_state != GameState.Playing || !_running) return;
        _timeLeft -= Time.deltaTime;
        if (_timeLeft <= 0f)
        {
            _timeLeft = 0f;
            UpdateTimerUI();
            EndRound(true);
            return;
        }
        UpdateTimerUI();
    }

    // ---------------------------------------------------------------- UI
    void SetGameUiVisible(bool on)
    {
        if (promptText != null) promptText.gameObject.SetActive(on);
        if (timerText != null) timerText.gameObject.SetActive(on);
        if (progressText != null) progressText.gameObject.SetActive(on);
        if (correctText != null) correctText.gameObject.SetActive(on);
    }

    void UpdateTimerUI()
    {
        if (timerText == null) return;
        int s = Mathf.CeilToInt(_timeLeft);
        timerText.text = (s / 60) + ":" + (s % 60).ToString("00");
        bool low = _running && _timeLeft <= lowTimeThreshold;
        timerText.color = low ? new Color(1f, 0.25f, 0.25f) : Color.white;
        timerText.transform.localScale = low
            ? Vector3.one * (1f + 0.12f * Mathf.Sin(Time.time * 9f))
            : Vector3.one;
    }

    void UpdateCorrect()
    {
        if (correctText != null) correctText.text = $"Doğru: {_correct}";
    }

    void ShowResult(string msg, Color c)
    {
        if (resultText == null) return;
        resultText.text = msg;
        resultText.color = c;
        resultText.gameObject.SetActive(true);
    }

    void HideResult()
    {
        if (resultText != null)
        {
            resultText.text = "";
            resultText.gameObject.SetActive(false);
        }
    }
}
