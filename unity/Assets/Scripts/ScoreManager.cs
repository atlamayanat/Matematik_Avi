using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// Score counter shown top-left. Uses a UnityEngine.UI.Text by default.
/// To use TextMeshPro instead: add a using TMPro; field "TMP_Text label" and
/// set it from the inspector (and remove the UI.Text field).
/// </summary>
public class ScoreManager : MonoBehaviour
{
    [SerializeField] Text label;
    [SerializeField] string prefix = "";

    public int Score { get; private set; }

    void Start() => Refresh();

    public void AddPoint()
    {
        Score++;
        Refresh();
    }

    public void ResetScore()
    {
        Score = 0;
        Refresh();
    }

    void Refresh()
    {
        if (label != null) label.text = prefix + Score;
    }
}
