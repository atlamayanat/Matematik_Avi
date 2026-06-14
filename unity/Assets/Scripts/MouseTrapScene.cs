using System.Collections;
using UnityEngine;

// ============================================================================
//  MouseTrapScene.cs  (GestureExhibit'e bağlanmış sürüm)
//  Peynir yiyen fare + fare kapanı, TAMAMEN prosedürel sahne.
//
//  Kurulum:
//    1) Boş bir GameObject oluştur (GameObject > Create Empty).
//    2) Bu script'i o objeye ekle (Add Component).
//    3) Play'e bas. Hiçbir hazır görsel/asset gerekmez; her şeyi kod çizer.
//
//  Etkileşim (EL ile):
//    - Elini KAPAT (yumruk)  -> kapan kapanır.  (açıp tekrar kapatınca yeni tur)
//    - Fare peyniri yiyorken yumruk yaparsan: YAKALANIR (endişeli yüz + yukarı çekilir).
//    - Fare daha peynire varmadan yumruk yaparsan: ISKALARSIN (fare kaçar).
//    - Kapan her turun sonunda KENDİNİ OTOMATİK yeniden kurar.
//    - (Test için fare tıklaması da çalışır.)
//
//  Girdi, Python detektöründen gelen OSC /hand mesajını okuyan HandReceiver
//  üzerinden alınır. Sahnede HandReceiver yoksa otomatik oluşturulur.
// ============================================================================

[DisallowMultipleComponent]
public class MouseTrapScene : MonoBehaviour
{
    [Header("Zamanlama (saniye)")]
    public float approachDuration = 1.6f;   // farenin içeri girme süresi
    public float catchRise = 0.5f;           // yukarı çekilme süresi
    public float fleeDuration = 0.5f;        // kaçma süresi
    public float rearmDelay = 1.8f;          // yakalandıktan sonra yeniden kurulmaya kadar bekleme
    public float barSnapTime = 0.12f;        // kolun kapanma hızı
    public float barArmTime = 0.4f;          // kolun yeniden kurulma hızı

    [Header("Konumlar (dünya birimi)")]
    public Vector2 cheesePos    = new Vector2(0f, -1.4f);
    public Vector2 mouseEatPos  = new Vector2(0.95f, -0.85f);
    public Vector2 mouseStartPos = new Vector2(7f, -0.85f);
    public Vector2 mouseUpPos   = new Vector2(0f, 2.0f);
    public Vector2 mouseFleePos = new Vector2(8f, -0.85f);

    [Header("Kapan kolu açıları (derece)")]
    public float barArmedAngle = 118f;   // kurulu (yukarı kalkık)
    public float barSnappedAngle = 0f;   // kapalı (yatık)

    enum State { Approach, Eat, Caught, Missed }
    State state = State.Approach;

    Sprite circle, box;
    Transform mouseRoot, mouseBob, barPivot;
    GameObject faceNormal, faceWorried, caughtFx, impactFx;
    Coroutine roundCo;

    bool _prevFist;   // el aç/kapa kenar algısı

    // ---------------------------------------------------------------- yaşam döngüsü
    void Awake()
    {
        EnsureHandReceiver();
        circle = MakeCircleSprite(64);
        box = MakeBoxSprite();
        SetupCamera();
        BuildStatic();
        BuildTrap();
        BuildMouse();
        BuildImpact();
    }

    void Start()
    {
        StartRound();
    }

    void Update()
    {
        AnimateBob();
        if (TriggerThisFrame()) HandleClick();
    }

    // ---------------------------------------------------------------- girdi (EL / yumruk)
    // Asıl tetik: el KAPANINCA (açık -> yumruk geçişi). Test için fare tıklaması da çalışır.
    bool TriggerThisFrame()
    {
        var hr = HandReceiver.Instance;
        bool fist = hr != null && hr.Present && hr.IsFist;
        bool handFired = fist && !_prevFist;   // yükselen kenar = "eli kapat"
        _prevFist = fist;
        if (handFired) return true;

#if ENABLE_LEGACY_INPUT_MANAGER
        if (Input.GetMouseButtonDown(0)) return true;
        if (Input.touchCount > 0 && Input.GetTouch(0).phase == TouchPhase.Began) return true;
#endif
        return false;
    }

    void HandleClick()
    {
        if (state == State.Eat) DoCatch();
        else if (state == State.Approach) DoMiss();
        // Caught / Missed sırasında tetik yok sayılır; kapan kendini kurar.
    }

    void EnsureHandReceiver()
    {
        if (HandReceiver.Instance == null)
        {
            var go = new GameObject("HandReceiver");
            go.AddComponent<HandReceiver>();   // UDP 9000'i dinler (config.json -> osc.port)
        }
    }

    // ---------------------------------------------------------------- bob / sallanma
    void AnimateBob()
    {
        if (mouseBob == null) return;
        float t = Time.time;
        switch (state)
        {
            case State.Approach:
                mouseBob.localPosition = new Vector3(0f, Mathf.Abs(Mathf.Sin(t * 16f)) * 0.05f, 0f);
                mouseBob.localRotation = Quaternion.identity;
                break;
            case State.Eat:
                mouseBob.localPosition = new Vector3(0f, Mathf.Sin(t * 13f) * 0.02f, 0f);
                mouseBob.localRotation = Quaternion.identity;
                break;
            case State.Missed:
                mouseBob.localPosition = new Vector3(0f, Mathf.Abs(Mathf.Sin(t * 20f)) * 0.06f, 0f);
                mouseBob.localRotation = Quaternion.identity;
                break;
            case State.Caught:
                mouseBob.localPosition = Vector3.zero;
                mouseBob.localRotation = Quaternion.Euler(0f, 0f, Mathf.Sin(t * 5f) * 7f); // asılı sallanma
                break;
        }
    }

    // ---------------------------------------------------------------- akış / state makinesi
    void StartRound()
    {
        if (roundCo != null) StopCoroutine(roundCo);
        roundCo = StartCoroutine(RoundRoutine());
    }

    IEnumerator RoundRoutine()
    {
        state = State.Approach;
        faceNormal.SetActive(true);
        faceWorried.SetActive(false);
        caughtFx.SetActive(false);
        impactFx.SetActive(false);

        // kapan yeniden kurulur (kol yukarı kalkar)
        yield return RotateBar(barArmedAngle, barArmTime, EaseOutCubic);

        // fare dışarıdan girer ve peynire yaklaşır
        mouseRoot.localPosition = new Vector3(mouseStartPos.x, mouseStartPos.y, 0f);
        yield return MoveRoot(mouseStartPos, mouseEatPos, approachDuration, EaseOutCubic);

        state = State.Eat; // artık yakalanabilir
    }

    void DoCatch()
    {
        if (roundCo != null) StopCoroutine(roundCo);
        StartCoroutine(CatchRoutine());
    }

    IEnumerator CatchRoutine()
    {
        state = State.Caught;
        faceNormal.SetActive(false);
        faceWorried.SetActive(true);  // endişeli yüz
        caughtFx.SetActive(true);     // ter + şok + yukarı hareket çizgileri

        StartCoroutine(RotateBar(barSnappedAngle, barSnapTime, EaseOutBack)); // kol takırdayarak kapanır
        StartCoroutine(FlashImpact());

        // fare yukarı çekilir
        Vector2 from = mouseRoot.localPosition;
        yield return MoveRoot(from, mouseUpPos, catchRise, EaseOutBack);

        // bir süre asılı kalır, sonra OTOMATİK yeniden kurulur
        yield return new WaitForSeconds(rearmDelay);
        StartRound();
    }

    void DoMiss()
    {
        if (roundCo != null) StopCoroutine(roundCo);
        StartCoroutine(MissRoutine());
    }

    IEnumerator MissRoutine()
    {
        state = State.Missed;
        StartCoroutine(RotateBar(barSnappedAngle, barSnapTime, EaseOutBack)); // boşa kapanır
        StartCoroutine(FlashImpact());

        Vector2 from = mouseRoot.localPosition;
        yield return MoveRoot(from, mouseFleePos, fleeDuration, EaseInCubic); // fare kaçar

        yield return new WaitForSeconds(rearmDelay * 0.7f);
        StartRound();
    }

    IEnumerator FlashImpact()
    {
        impactFx.SetActive(true);
        yield return new WaitForSeconds(0.18f);
        impactFx.SetActive(false);
    }

    // ---------------------------------------------------------------- hareket yardımcıları
    IEnumerator MoveRoot(Vector2 from, Vector2 to, float dur, System.Func<float, float> ease)
    {
        float e = 0f;
        while (e < dur)
        {
            e += Time.deltaTime;
            float k = ease(Mathf.Clamp01(e / dur));
            Vector2 p = Vector2.LerpUnclamped(from, to, k);
            mouseRoot.localPosition = new Vector3(p.x, p.y, 0f);
            yield return null;
        }
        mouseRoot.localPosition = new Vector3(to.x, to.y, 0f);
    }

    IEnumerator RotateBar(float targetZ, float dur, System.Func<float, float> ease)
    {
        float startZ = Mathf.DeltaAngle(0f, barPivot.localEulerAngles.z);
        float e = 0f;
        while (e < dur)
        {
            e += Time.deltaTime;
            float k = ease(Mathf.Clamp01(e / dur));
            float z = Mathf.LerpUnclamped(startZ, targetZ, k);
            barPivot.localRotation = Quaternion.Euler(0f, 0f, z);
            yield return null;
        }
        barPivot.localRotation = Quaternion.Euler(0f, 0f, targetZ);
    }

    static float EaseOutCubic(float x) => 1f - Mathf.Pow(1f - x, 3f);
    static float EaseInCubic(float x) => x * x * x;
    static float EaseOutBack(float x)
    {
        const float c1 = 1.70158f;
        const float c3 = c1 + 1f;
        return 1f + c3 * Mathf.Pow(x - 1f, 3f) + c1 * Mathf.Pow(x - 1f, 2f);
    }

    // ---------------------------------------------------------------- kamera
    void SetupCamera()
    {
        Camera cam = Camera.main;
        if (cam == null)
        {
            var go = new GameObject("Main Camera") { tag = "MainCamera" };
            cam = go.AddComponent<Camera>();
        }
        cam.orthographic = true;
        cam.orthographicSize = 3.2f;
        cam.transform.position = new Vector3(0f, 0f, -10f);
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = Hex("#fdf6ec");
    }

    // ---------------------------------------------------------------- sahne kurulumu
    void BuildStatic()
    {
        MakeSprite("Golge", transform, circle, new Color(0f, 0f, 0f, 0.12f), new Vector3(0f, -2.05f, 0f), new Vector2(5.6f, 0.5f), 0);

        MakeSprite("Plank", transform, box, Hex("#b5743a"), new Vector3(0f, -2f, 0f), new Vector2(5.2f, 0.55f), 2);
        MakeSprite("Damar1", transform, box, Hex("#8a5526"), new Vector3(0f, -1.92f, 0f), new Vector2(4.6f, 0.04f), 3);
        MakeSprite("Damar2", transform, box, Hex("#8a5526"), new Vector3(0f, -2.08f, 0f), new Vector2(4.6f, 0.04f), 3);
        MakeSprite("Pedal", transform, box, Hex("#c79a52"), new Vector3(0f, -1.66f, 0f), new Vector2(0.5f, 0.16f), 3);

        // yuvarlak peynir + delikler
        MakeSprite("Peynir", transform, circle, Hex("#f6c233"), new Vector3(cheesePos.x, cheesePos.y, 0f), new Vector2(0.95f, 0.8f), 4);
        MakeSprite("Delik1", transform, circle, Hex("#e2a417"), new Vector3(cheesePos.x - 0.12f, cheesePos.y + 0.08f, 0f), new Vector2(0.12f, 0.12f), 5);
        MakeSprite("Delik2", transform, circle, Hex("#e2a417"), new Vector3(cheesePos.x + 0.14f, cheesePos.y - 0.05f, 0f), new Vector2(0.10f, 0.10f), 5);
        MakeSprite("Delik3", transform, circle, Hex("#e2a417"), new Vector3(cheesePos.x + 0.02f, cheesePos.y + 0.18f, 0f), new Vector2(0.08f, 0.08f), 5);
    }

    void BuildTrap()
    {
        var pivotGO = new GameObject("KapanKolPivot");
        pivotGO.transform.SetParent(transform, false);
        pivotGO.transform.localPosition = new Vector3(-2.35f, -1.72f, 0f);
        barPivot = pivotGO.transform;

        MakeSprite("Yay", barPivot, circle, Hex("#c2c8d2"), Vector3.zero, new Vector2(0.24f, 0.24f), 6);          // yay/menteşe
        MakeSprite("Kol", barPivot, box, Hex("#aeb6c2"), new Vector3(1.4f, 0f, 0f), new Vector2(2.8f, 0.16f), 5); // kol pivottan +X uzanır
        MakeSprite("KolUc", barPivot, box, Hex("#aeb6c2"), new Vector3(2.75f, 0f, 0f), new Vector2(0.16f, 0.5f), 5);

        barPivot.localRotation = Quaternion.Euler(0f, 0f, barArmedAngle);
    }

    void BuildMouse()
    {
        var rootGO = new GameObject("Fare");
        rootGO.transform.SetParent(transform, false);
        rootGO.transform.localPosition = new Vector3(mouseStartPos.x, mouseStartPos.y, 0f);
        mouseRoot = rootGO.transform;

        var bobGO = new GameObject("Bob");
        bobGO.transform.SetParent(mouseRoot, false);
        mouseBob = bobGO.transform;

        // kuyruk + ayaklar (gövdenin arkasında)
        MakeTail(mouseBob);
        MakeSprite("ArkaAyak", mouseBob, circle, Hex("#82868f"), new Vector3(0.25f, -0.95f, 0f), new Vector2(0.34f, 0.2f), 6);
        MakeSprite("OnAyak", mouseBob, circle, Hex("#82868f"), new Vector3(-0.30f, -0.97f, 0f), new Vector2(0.30f, 0.18f), 6);

        // gövde + kafa (sola bakar)
        MakeSprite("Govde", mouseBob, circle, Hex("#a9adb6"), new Vector3(0.10f, -0.45f, 0f), new Vector2(1.30f, 0.95f), 7);
        MakeSprite("Kafa", mouseBob, circle, Hex("#a9adb6"), new Vector3(-0.50f, -0.42f, 0f), new Vector2(0.74f, 0.74f), 8);
        MakeSprite("KulakDis", mouseBob, circle, Hex("#9a9ea7"), new Vector3(-0.42f, -0.14f, 0f), new Vector2(0.44f, 0.44f), 8);
        MakeSprite("KulakIc", mouseBob, circle, Hex("#e8b6c0"), new Vector3(-0.41f, -0.16f, 0f), new Vector2(0.24f, 0.24f), 9);
        MakeSprite("Burun", mouseBob, circle, Hex("#b6bcc4"), new Vector3(-0.80f, -0.50f, 0f), new Vector2(0.36f, 0.30f), 9);
        MakeSprite("BurunUcu", mouseBob, circle, Hex("#3a3d44"), new Vector3(-0.95f, -0.50f, 0f), new Vector2(0.14f, 0.14f), 10);

        MakeWhisker(mouseBob, new Vector3(-1.00f, -0.46f, 0f), 8f);
        MakeWhisker(mouseBob, new Vector3(-1.02f, -0.52f, 0f), 0f);
        MakeWhisker(mouseBob, new Vector3(-1.00f, -0.58f, 0f), -8f);

        // ---- normal yüz (sakin) ----
        faceNormal = NewGroup("YuzNormal", mouseBob);
        MakeSprite("Goz", faceNormal.transform, circle, Hex("#2f323a"), new Vector3(-0.52f, -0.34f, 0f), new Vector2(0.10f, 0.12f), 11);

        // ---- endişeli yüz ----
        faceWorried = NewGroup("YuzEndise", mouseBob);
        MakeSprite("GozAk", faceWorried.transform, circle, Color.white, new Vector3(-0.52f, -0.33f, 0f), new Vector2(0.20f, 0.24f), 11);
        MakeSprite("GozBebek", faceWorried.transform, circle, Hex("#2f323a"), new Vector3(-0.52f, -0.37f, 0f), new Vector2(0.09f, 0.09f), 12);
        var brow = MakeSprite("Kas", faceWorried.transform, box, Hex("#4a4d55"), new Vector3(-0.50f, -0.18f, 0f), new Vector2(0.22f, 0.035f), 12);
        brow.transform.localRotation = Quaternion.Euler(0f, 0f, 18f);
        MakeSprite("Agiz", faceWorried.transform, circle, Hex("#2f323a"), new Vector3(-0.78f, -0.62f, 0f), new Vector2(0.13f, 0.17f), 11);
        faceWorried.SetActive(false);

        // ---- yakalanma efektleri ----
        caughtFx = NewGroup("YakalamaFX", mouseBob);
        MakeSprite("TerDamla", caughtFx.transform, circle, Hex("#7ec8f2"), new Vector3(-0.20f, -0.12f, 0f), new Vector2(0.12f, 0.17f), 12);
        var sh1 = MakeSprite("Sok1", caughtFx.transform, box, Hex("#f0a91e"), new Vector3(-0.78f, -0.08f, 0f), new Vector2(0.18f, 0.03f), 12);
        sh1.transform.localRotation = Quaternion.Euler(0f, 0f, 40f);
        var sh2 = MakeSprite("Sok2", caughtFx.transform, box, Hex("#f0a91e"), new Vector3(-0.55f, 0.00f, 0f), new Vector2(0.18f, 0.03f), 12);
        sh2.transform.localRotation = Quaternion.Euler(0f, 0f, -30f);
        // yukarı çekilmeyi vurgulayan hız çizgileri (gövdenin altında)
        Color speed = new Color(0.60f, 0.64f, 0.69f, 0.7f);
        MakeSprite("Hiz1", caughtFx.transform, box, speed, new Vector3(-0.20f, -1.15f, 0f), new Vector2(0.04f, 0.30f), 6);
        MakeSprite("Hiz2", caughtFx.transform, box, speed, new Vector3(0.15f, -1.20f, 0f), new Vector2(0.04f, 0.34f), 6);
        MakeSprite("Hiz3", caughtFx.transform, box, speed, new Vector3(0.50f, -1.15f, 0f), new Vector2(0.04f, 0.30f), 6);
        caughtFx.SetActive(false);
    }

    void BuildImpact()
    {
        var impact = new GameObject("Carpma");
        impact.transform.SetParent(transform, false);
        impact.transform.localPosition = new Vector3(-0.5f, -1.5f, 0f);
        for (int i = 0; i < 6; i++)
        {
            float ang = i * 60f;
            var l = MakeSprite("Isin", impact.transform, box, Hex("#ffd23f"), Vector3.zero, new Vector2(0.45f, 0.06f), 11);
            l.transform.localRotation = Quaternion.Euler(0f, 0f, ang);
            l.transform.localPosition = Quaternion.Euler(0f, 0f, ang) * (Vector3.right * 0.2f);
        }
        impact.SetActive(false);
        impactFx = impact;
    }

    // ---------------------------------------------------------------- küçük yardımcılar
    GameObject NewGroup(string name, Transform parent)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        return go;
    }

    GameObject MakeSprite(string name, Transform parent, Sprite sp, Color col, Vector3 localPos, Vector2 sizeUnits, int order)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        go.transform.localPosition = localPos;
        go.transform.localScale = new Vector3(sizeUnits.x, sizeUnits.y, 1f);
        var sr = go.AddComponent<SpriteRenderer>();
        sr.sprite = sp;
        sr.color = col;
        sr.sortingOrder = order;
        return go;
    }

    void MakeWhisker(Transform parent, Vector3 pos, float angle)
    {
        var go = MakeSprite("Biyik", parent, box, Hex("#5d616a"), pos, new Vector2(0.32f, 0.02f), 10);
        go.transform.localRotation = Quaternion.Euler(0f, 0f, angle);
    }

    void MakeTail(Transform parent)
    {
        var go = new GameObject("Kuyruk");
        go.transform.SetParent(parent, false);
        var lr = go.AddComponent<LineRenderer>();
        lr.useWorldSpace = false;
        lr.positionCount = 4;
        lr.SetPositions(new[]
        {
            new Vector3(0.62f, -0.40f, 0f),
            new Vector3(0.95f, -0.32f, 0f),
            new Vector3(1.12f, -0.55f, 0f),
            new Vector3(1.00f, -0.82f, 0f),
        });
        lr.widthMultiplier = 0.09f;
        lr.numCapVertices = 4;
        lr.numCornerVertices = 4;
        lr.material = new Material(Shader.Find("Sprites/Default"));
        lr.startColor = lr.endColor = Hex("#82868f");
        lr.sortingOrder = 6;
    }

    Sprite MakeCircleSprite(int size)
    {
        var tex = new Texture2D(size, size, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp };
        float r = size * 0.5f;
        Vector2 c = new Vector2(r, r);
        for (int y = 0; y < size; y++)
            for (int x = 0; x < size; x++)
            {
                float d = Vector2.Distance(new Vector2(x + 0.5f, y + 0.5f), c);
                float a = Mathf.Clamp01(r - d); // ~1px yumuşak kenar
                tex.SetPixel(x, y, new Color(1f, 1f, 1f, a));
            }
        tex.Apply();
        return Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), size); // PPU=size -> taban 1 birim
    }

    Sprite MakeBoxSprite()
    {
        var tex = new Texture2D(4, 4, TextureFormat.RGBA32, false);
        var px = new Color[16];
        for (int i = 0; i < px.Length; i++) px[i] = Color.white;
        tex.SetPixels(px);
        tex.Apply();
        return Sprite.Create(tex, new Rect(0, 0, 4, 4), new Vector2(0.5f, 0.5f), 4); // PPU=4 -> taban 1 birim
    }

    static Color Hex(string h)
    {
        ColorUtility.TryParseHtmlString(h, out Color c);
        return c;
    }

    // İsteğe bağlı: ekran üstü durum yazısı (Canvas gerektirmez).
    void OnGUI()
    {
        string msg =
            state == State.Approach ? "Fare geliyor..." :
            state == State.Eat ? "Fare peyniri yiyor — yakalamak için elini KAPAT (yumruk)!" :
            state == State.Caught ? "Yakalandı! Fare endişeyle yukarı çekildi." :
            "Iskaladın! Fare kaçtı.";

        var title = new GUIStyle(GUI.skin.label) { fontSize = 20, alignment = TextAnchor.MiddleCenter, fontStyle = FontStyle.Bold };
        title.normal.textColor = new Color(0.18f, 0.16f, 0.14f);
        GUI.Label(new Rect(0, 18, Screen.width, 30), msg, title);

        var hint = new GUIStyle(GUI.skin.label) { fontSize = 13, alignment = TextAnchor.MiddleCenter };
        hint.normal.textColor = new Color(0.45f, 0.42f, 0.40f);
        GUI.Label(new Rect(0, 50, Screen.width, 22), "Elini aç/kapat ile oyna: doğru anda yumruk yap. Çok erken kapatırsan ıskalarsın.", hint);
    }
}
