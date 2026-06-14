using UnityEngine;

// CheeseHunt yakalama agi: prosedurel cizim (MouseNetGame.cs'teki agdan uyarlandi).
// Eski net.png yerine gecer. NetCatch bu objenin Transform'unu yukaridan indirip
// fareyi yakalar; obje yakalama aninda aktif edilir (cizim Awake'te kurulur).
//
// ONEMLI: Tum parcalar VisibleInsideMask -> SADECE spotlight (mercek) icinde gorunur.
// Bu yuzden kavisler LineRenderer ile DEGIL, maskelenebilir KUTU SEGMENTLERIYLE
// ciziliyor (LineRenderer SpriteMask'a uymaz). Boylece ag siyah alanda gorunmez;
// merceğe ustten suzulerek iner, yakalar, yine mercek icinde yukari suzulup biter.
// sortingOrder ~21-24 -> fare (<=16) onunde cizilir.
[DisallowMultipleComponent]
public class NetVisual : MonoBehaviour
{
    Sprite circle, box;

    void Awake()
    {
        circle = MakeCircleSprite(64);
        box = MakeBoxSprite();
        Build();
    }

    void Build()
    {
        // origin ~ yakalama merkezi (fare govdesi). Kubbe yukari acilir, agiz asagida;
        // yShift origin'i kubbenin ortasina kaydirir ki fare icine girsin.
        Color net = new Color(0.90f, 0.95f, 0.99f, 0.94f);
        float r = 1.05f, ry = 1.20f;
        const float yShift = -0.45f;

        Transform p = transform;

        // dis kubbe + ic parlama (ust yay, alti acik)
        MakeArcSeg("Kubbe", p, r, ry, 0f, 180f, 30, 0.06f, net, yShift, 22);
        MakeArcSeg("KubbeParlak", p, r * 0.97f, ry * 0.97f, 20f, 160f, 22, 0.03f, Hex("#ffffff80"), yShift, 23);
        // agiz halkasi (on rim - sig alt elips, sepet agzi hissi)
        MakeArcSeg("Agiz", p, r, ry * 0.30f, 180f, 360f, 24, 0.05f, net, yShift, 24);

        // dikey teller (kubbe konturuna gore boylanir)
        float[] xs = { -0.7f, -0.35f, 0f, 0.35f, 0.7f };
        foreach (float x in xs)
        {
            float hgt = ry * Mathf.Sqrt(Mathf.Max(0f, 1f - (x / r) * (x / r)));
            if (hgt <= 0.02f) continue;
            Spr("Tel", p, box, net, new Vector3(x, hgt * 0.5f + yShift, 0f), new Vector2(0.028f, hgt), 22);
        }
        // yatay teller (elips genisligine gore)
        float[] ys = { 0.0f, 0.4f, 0.8f };
        foreach (float y in ys)
        {
            float halfw = r * Mathf.Sqrt(Mathf.Max(0f, 1f - (y / ry) * (y / ry)));
            if (halfw <= 0.02f) continue;
            Spr("TelY", p, box, net, new Vector3(0f, y + yShift, 0f), new Vector2(halfw * 2f, 0.028f), 22);
        }

        // sap + parlama + topuz (kisa tutuldu ki mercek icinde kalsin)
        Spr("Sap", p, box, Hex("#b07a3c"), new Vector3(0f, ry + 0.25f + yShift, 0f), new Vector2(0.08f, 0.6f), 21);
        Spr("SapParlak", p, box, Hex("#d8b070b0"), new Vector3(-0.025f, ry + 0.25f + yShift, 0f), new Vector2(0.03f, 0.6f), 21);
        Spr("Topuz", p, circle, Hex("#caa15a"), new Vector3(0f, ry + 0.55f + yShift, 0f), new Vector2(0.18f, 0.18f), 23);
    }

    // ---------------------------------------------------------------- yardimcilar
    // Kavisi kucuk kutu segmentlerinden cizer; her segment VisibleInsideMask -> maskelenir.
    void MakeArcSeg(string name, Transform parent, float rx, float ry, float fromDeg, float toDeg, int seg, float width, Color col, float yc, int order)
    {
        float step = (toDeg - fromDeg) / seg;
        Vector3 prev = ArcPt(fromDeg, rx, ry, yc);
        for (int i = 1; i <= seg; i++)
        {
            Vector3 cur = ArcPt(fromDeg + step * i, rx, ry, yc);
            Vector3 mid = (prev + cur) * 0.5f;
            Vector3 d = cur - prev;
            float len = d.magnitude;
            float ang = Mathf.Atan2(d.y, d.x) * Mathf.Rad2Deg;
            var g = Spr(name, parent, box, col, mid, new Vector2(len + width * 0.6f, width), order);
            g.transform.localRotation = Quaternion.Euler(0f, 0f, ang);
            prev = cur;
        }
    }

    static Vector3 ArcPt(float deg, float rx, float ry, float yc)
    {
        float a = deg * Mathf.Deg2Rad;
        return new Vector3(Mathf.Cos(a) * rx, Mathf.Sin(a) * ry + yc, 0f);
    }

    GameObject Spr(string name, Transform parent, Sprite sp, Color col, Vector3 localPos, Vector2 sizeUnits, int order)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        go.transform.localPosition = localPos;
        go.transform.localScale = new Vector3(sizeUnits.x, sizeUnits.y, 1f);
        var sr = go.AddComponent<SpriteRenderer>();
        sr.sprite = sp;
        sr.color = col;
        sr.sortingOrder = order;
        sr.maskInteraction = SpriteMaskInteraction.VisibleInsideMask; // sadece mercek icinde gorunur
        return go;
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

    static Color Hex(string h)
    {
        ColorUtility.TryParseHtmlString(h, out Color c);
        return c;
    }
}
