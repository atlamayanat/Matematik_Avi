using System.Collections;
using UnityEngine;

// CheeseHunt'in faresi: prosedurel "peynir yiyen fare" (gelistirilmis cizim:
// golge + ust isik parlamasi + sevimli oranlar). MouseNetGame.cs'teki cizimden
// uyarlandi; SADECE gorsel + tepki - oyun mantigi CheeseHunt'ta (spotlight + yumruk).
// Tum parcalar VisibleInsideMask -> sadece spotlight icinde gorunur.
// Yakalaninca (NetCatch.Caught()) endiseli yuz + korku efektleri + titreme.
[DisallowMultipleComponent]
public class CheeseMouseVisual : MonoBehaviour
{
    [Tooltip("Idle hafif sallanma genligi (dunya birimi).")]
    public float bobAmount = 0.03f;

    [Tooltip("Yakalaninca endiseli yuzun ekranda kalma suresi (sn).")]
    public float worriedSeconds = 1.0f;

    Sprite circle, box, wedge;
    Transform bob;
    GameObject faceNormal, faceWorried, caughtFx;
    Coroutine worriedCo;
    bool _worried;

    void Awake()
    {
        circle = MakeCircleSprite(64);
        box = MakeBoxSprite();
        wedge = MakeWedgeSprite(96);
        Build();
        SetWorried(false);
    }

    void Update()
    {
        if (bob == null) return;
        float t = Time.time;
        if (_worried) // korkudan titreme + sallanma
        {
            bob.localPosition = new Vector3(Mathf.Sin(t * 40f) * 0.03f, 0f, 0f);
            bob.localRotation = Quaternion.Euler(0f, 0f, Mathf.Sin(t * 6f) * 8f);
        }
        else // sakin idle bob
        {
            bob.localPosition = new Vector3(0f, Mathf.Sin(t * 6f) * bobAmount, 0f);
            bob.localRotation = Quaternion.identity;
        }
    }

    // NetCatch yakalama aninda cagirir.
    public void Caught()
    {
        if (worriedCo != null) StopCoroutine(worriedCo);
        worriedCo = StartCoroutine(WorriedThenReset());
    }

    IEnumerator WorriedThenReset()
    {
        SetWorried(true);
        yield return new WaitForSeconds(worriedSeconds);
        SetWorried(false);
    }

    public void SetWorried(bool w)
    {
        _worried = w;
        if (faceNormal != null) faceNormal.SetActive(!w);
        if (faceWorried != null) faceWorried.SetActive(w);
        if (caughtFx != null) caughtFx.SetActive(w);
    }

    // ---------------------------------------------------------------- gorsel insa
    void Build()
    {
        var bobGO = new GameObject("Bob");
        bobGO.transform.SetParent(transform, false);
        bob = bobGO.transform;

        Color body = Hex("#8d93a3"), bodyShade = Hex("#6f7588cc"), bodyHi = Hex("#c6cbd88c");
        Color earOut = Hex("#82889a"), earBack = Hex("#767c8e"), earIn = Hex("#f2bac6");
        Color noseArea = Hex("#9aa0b1"), noseTip = Hex("#e89aa6"), tailCol = Hex("#d49aa6");

        // yer golgesi
        Spr("FareGolge", bob, circle, "#22455a3a", new Vector3(0.05f, -1.0f, 0f), new Vector2(1.55f, 0.4f), 3);

        // kuyruk (maskelenebilir segmentler - LineRenderer SpriteMask'a uymuyor)
        MakeTail(bob, tailCol);

        // arka kulak + arka ayak
        Spr("KulakArka", bob, circle, earBack, new Vector3(-0.16f, 0.04f, 0f), new Vector2(0.44f, 0.44f), 5);
        Spr("ArkaAyak", bob, circle, body, new Vector3(0.34f, -0.95f, 0f), new Vector2(0.42f, 0.24f), 6);

        // govde + golge + parlama
        Spr("Govde", bob, circle, body, new Vector3(0.08f, -0.45f, 0f), new Vector2(1.35f, 1.06f), 7);
        Spr("GovdeGolge", bob, circle, bodyShade, new Vector3(0.08f, -0.72f, 0f), new Vector2(1.02f, 0.5f), 8);
        Spr("GovdeParlak", bob, circle, bodyHi, new Vector3(-0.16f, -0.18f, 0f), new Vector2(0.55f, 0.4f), 9);

        // on el
        Spr("OnEl", bob, circle, body, new Vector3(-0.18f, -0.92f, 0f), new Vector2(0.32f, 0.2f), 8);

        // elinde kucuk peynir dilimi (CheeseHunt temasi)
        var ch = Spr("Peynir", bob, wedge, "#ffd64d", new Vector3(-0.42f, -0.78f, 0f), new Vector2(0.5f, 0.42f), 9);
        ch.transform.localRotation = Quaternion.Euler(0f, 0f, -8f);
        Spr("PeynirRind", bob, wedge, "#e3a31a", new Vector3(-0.42f, -0.80f, 0f), new Vector2(0.56f, 0.46f), 8)
            .transform.localRotation = Quaternion.Euler(0f, 0f, -8f);

        // kafa + parlama
        Spr("Kafa", bob, circle, body, new Vector3(-0.46f, -0.40f, 0f), new Vector2(0.84f, 0.84f), 10);
        Spr("KafaParlak", bob, circle, bodyHi, new Vector3(-0.62f, -0.24f, 0f), new Vector2(0.34f, 0.28f), 11);

        // on kulak + ic
        Spr("KulakOn", bob, circle, earOut, new Vector3(-0.46f, -0.02f, 0f), new Vector2(0.52f, 0.52f), 8);
        Spr("KulakIc", bob, circle, earIn, new Vector3(-0.46f, -0.05f, 0f), new Vector2(0.3f, 0.3f), 9);

        // burun + uc + parlama
        Spr("Burun", bob, circle, noseArea, new Vector3(-0.82f, -0.48f, 0f), new Vector2(0.42f, 0.34f), 12);
        Spr("BurunUc", bob, circle, noseTip, new Vector3(-0.99f, -0.49f, 0f), new Vector2(0.16f, 0.15f), 13);
        Spr("BurunParlak", bob, circle, "#ffffffcc", new Vector3(-1.02f, -0.45f, 0f), new Vector2(0.06f, 0.06f), 14);

        Whisker(bob, new Vector3(-1.00f, -0.45f, 0f), 10f);
        Whisker(bob, new Vector3(-1.02f, -0.51f, 0f), 0f);
        Whisker(bob, new Vector3(-1.00f, -0.57f, 0f), -10f);

        // --- normal yuz (sakin, parlak goz)
        faceNormal = Group("YuzNormal", bob);
        Spr("Goz", faceNormal.transform, circle, "#20232b", new Vector3(-0.50f, -0.31f, 0f), new Vector2(0.17f, 0.19f), 13);
        Spr("GozParlak", faceNormal.transform, circle, "#ffffffe6", new Vector3(-0.53f, -0.27f, 0f), new Vector2(0.06f, 0.06f), 14);

        // --- endiseli / korkmus yuz
        faceWorried = Group("YuzEndise", bob);
        Spr("GozAk", faceWorried.transform, circle, "#ffffff", new Vector3(-0.50f, -0.30f, 0f), new Vector2(0.26f, 0.30f), 13);
        Spr("GozBebek", faceWorried.transform, circle, "#20232b", new Vector3(-0.50f, -0.35f, 0f), new Vector2(0.12f, 0.12f), 14);
        Spr("GozParlak2", faceWorried.transform, circle, "#ffffffe6", new Vector3(-0.53f, -0.32f, 0f), new Vector2(0.05f, 0.05f), 15);
        var brow = Spr("Kas", faceWorried.transform, box, "#4a4d55", new Vector3(-0.49f, -0.13f, 0f), new Vector2(0.24f, 0.04f), 15);
        brow.transform.localRotation = Quaternion.Euler(0f, 0f, 20f);
        Spr("Agiz", faceWorried.transform, circle, "#5a3640", new Vector3(-0.78f, -0.62f, 0f), new Vector2(0.14f, 0.18f), 13);

        // --- korku efektleri (ter + sok cizgileri)
        caughtFx = Group("KorkuFX", bob);
        Spr("TerDamla", caughtFx.transform, circle, "#7ec8f2", new Vector3(-0.18f, -0.10f, 0f), new Vector2(0.13f, 0.18f), 16);
        var sk1 = Spr("Sok1", caughtFx.transform, box, "#f0a91e", new Vector3(-0.80f, -0.06f, 0f), new Vector2(0.2f, 0.035f), 16);
        sk1.transform.localRotation = Quaternion.Euler(0f, 0f, 42f);
        var sk2 = Spr("Sok2", caughtFx.transform, box, "#f0a91e", new Vector3(-0.56f, 0.02f, 0f), new Vector2(0.2f, 0.035f), 16);
        sk2.transform.localRotation = Quaternion.Euler(0f, 0f, -30f);
    }

    // kuyrugu maskelenebilir kutu segmentleriyle ciziyoruz (egri yaklasik)
    void MakeTail(Transform parent, Color col)
    {
        var a = Spr("Kuyruk1", parent, box, col, new Vector3(0.775f, -0.50f, 0f), new Vector2(0.40f, 0.11f), 5);
        a.transform.localRotation = Quaternion.Euler(0f, 0f, 16f);
        var b = Spr("Kuyruk2", parent, box, col, new Vector3(1.055f, -0.535f, 0f), new Vector2(0.30f, 0.09f), 5);
        b.transform.localRotation = Quaternion.Euler(0f, 0f, -39f);
        var c = Spr("Kuyruk3", parent, box, col, new Vector3(1.17f, -0.77f, 0f), new Vector2(0.32f, 0.07f), 5);
        c.transform.localRotation = Quaternion.Euler(0f, 0f, -86f);
        var d = Spr("Kuyruk4", parent, box, col, new Vector3(1.09f, -0.99f, 0f), new Vector2(0.24f, 0.055f), 5);
        d.transform.localRotation = Quaternion.Euler(0f, 0f, -142f);
    }

    // ---------------------------------------------------------------- yardimcilar
    GameObject Group(string name, Transform parent)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        return go;
    }

    GameObject Spr(string name, Transform parent, Sprite sp, Color col, Vector3 pos, Vector2 size, int order)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        go.transform.localPosition = pos;
        go.transform.localScale = new Vector3(size.x, size.y, 1f);
        var sr = go.AddComponent<SpriteRenderer>();
        sr.sprite = sp;
        sr.color = col;
        sr.sortingOrder = order;
        sr.maskInteraction = SpriteMaskInteraction.VisibleInsideMask; // spotlight icinde gorunur
        return go;
    }

    GameObject Spr(string name, Transform parent, Sprite sp, string hex, Vector3 pos, Vector2 size, int order)
        => Spr(name, parent, sp, Hex(hex), pos, size, order);

    void Whisker(Transform parent, Vector3 pos, float angle)
    {
        var go = Spr("Biyik", parent, box, "#6c7284", pos, new Vector2(0.34f, 0.02f), 12);
        go.transform.localRotation = Quaternion.Euler(0f, 0f, angle);
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
                tex.SetPixel(x, y, new Color(1f, 1f, 1f, Mathf.Clamp01(r - d)));
            }
        tex.Apply();
        return Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), size);
    }

    Sprite MakeBoxSprite()
    {
        var tex = new Texture2D(4, 4, TextureFormat.RGBA32, false);
        var px = new Color[16];
        for (int i = 0; i < px.Length; i++) px[i] = Color.white;
        tex.SetPixels(px);
        tex.Apply();
        return Sprite.Create(tex, new Rect(0, 0, 4, 4), new Vector2(0.5f, 0.5f), 4);
    }

    Sprite MakeWedgeSprite(int size)
    {
        var tex = new Texture2D(size, size, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp };
        Vector2 A = new Vector2(0.08f, 0.18f) * size, B = new Vector2(0.92f, 0.18f) * size, C = new Vector2(0.32f, 0.92f) * size;
        for (int y = 0; y < size; y++)
            for (int x = 0; x < size; x++)
            {
                Vector2 p = new Vector2(x + 0.5f, y + 0.5f);
                tex.SetPixel(x, y, PointInTri(p, A, B, C) ? Color.white : new Color(1, 1, 1, 0));
            }
        tex.Apply();
        return Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), size);
    }

    static bool PointInTri(Vector2 p, Vector2 a, Vector2 b, Vector2 c)
    {
        float d1 = Cross(p, a, b), d2 = Cross(p, b, c), d3 = Cross(p, c, a);
        bool neg = d1 < 0 || d2 < 0 || d3 < 0, pos = d1 > 0 || d2 > 0 || d3 > 0;
        return !(neg && pos);
    }
    static float Cross(Vector2 p1, Vector2 p2, Vector2 p3) => (p1.x - p3.x) * (p2.y - p3.y) - (p2.x - p3.x) * (p1.y - p3.y);

    static Color Hex(string h)
    {
        ColorUtility.TryParseHtmlString(h, out Color c);
        return c;
    }
}
