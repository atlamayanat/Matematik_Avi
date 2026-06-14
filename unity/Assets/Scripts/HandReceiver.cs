using UnityEngine;
using OscJack;

/// <summary>
/// Receives the Python detector's /hand OSC messages and exposes the latest
/// hand state to the rest of the game.
///
/// OscJack delivers callbacks on its OWN background thread, so the callback only
/// writes to lock-guarded fields and NEVER touches Unity APIs. Game scripts read
/// the state through the thread-safe properties below.
///
/// OSC schema (must match net/osc_sender.py):
///   /hand  float nx, float ny, int present, string gesture("searching"|"fist")
/// </summary>
public class HandReceiver : MonoBehaviour
{
    public static HandReceiver Instance { get; private set; }

    [Tooltip("UDP port to listen on. Must equal config.json -> osc.port")]
    [SerializeField] int port = 9000;

    OscServer _server;
    readonly object _lock = new object();
    float _nx = 0.5f, _ny = 0.5f;
    int _present;
    string _gesture = "searching";

    void Awake()
    {
        if (Instance != null && Instance != this) { Destroy(gameObject); return; }
        Instance = this;
    }

    void OnEnable()
    {
        _server = new OscServer(port);                       // binds the UDP port
        _server.MessageDispatcher.AddCallback("/hand", OnHand);
        Debug.Log($"[HandReceiver] listening for /hand on UDP {port}");
    }

    void OnDisable()
    {
        if (_server != null) { _server.Dispose(); _server = null; } // stop thread + close socket
    }

    // ---- BACKGROUND (OscJack server) thread - do NOT call Unity APIs here ----
    void OnHand(string address, OscDataHandle data)
    {
        lock (_lock)
        {
            _nx = data.GetElementAsFloat(0);
            _ny = data.GetElementAsFloat(1);
            _present = data.GetElementAsInt(2);
            _gesture = data.GetElementAsString(3);
        }
    }

    // ---- Thread-safe accessors (safe to read from any Update) ----
    public Vector2 Normalized
    {
        get { lock (_lock) { return new Vector2(_nx, _ny); } }
    }

    public bool Present
    {
        get { lock (_lock) { return _present != 0; } }
    }

    public string Gesture
    {
        get { lock (_lock) { return _gesture; } }
    }

    public bool IsFist
    {
        get { lock (_lock) { return _gesture == "fist"; } }
    }
}
