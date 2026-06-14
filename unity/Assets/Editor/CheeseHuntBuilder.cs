// Auto-assembles the Cheese-Hunt gesture game scene so nobody has to do the
// manual Unity-README steps by hand. Run from the menu (Tools > Cheese Hunt >
// Build Scene) or from the command line:
//
//   Unity.exe -batchmode -quit -projectPath <proj> -executeMethod CheeseHuntBuilder.Build
//
// Reveal mechanic: ONE SpriteMask (the soft circle) follows the hand; the mouse
// and net SpriteRenderers use maskInteraction = VisibleInsideMask, so they only
// show inside the circle. The visible glowing ring is a normal SpriteRenderer.
// This avoids fragile custom Sorting Layer editing entirely.

using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

public static class CheeseHuntBuilder
{
    const string ArtDir = "Assets/Art";
    const string ScenePath = "Assets/Scenes/CheeseHunt.unity";

    [MenuItem("Tools/Cheese Hunt/Build Scene")]
    public static void Build()
    {
        Debug.Log("[CheeseHuntBuilder] Building scene...");

        ImportSprite($"{ArtDir}/spotlight_circle.png");
        ImportSprite($"{ArtDir}/spotlight_ring.png");
        ImportSprite($"{ArtDir}/bg_reveal.png");

        Sprite circle = Load($"{ArtDir}/spotlight_circle.png");
        Sprite ring   = Load($"{ArtDir}/spotlight_ring.png");
        Sprite bgS    = Load($"{ArtDir}/bg_reveal.png");
        // Fare ve ag artik prosedurel (CheeseMouseVisual / NetVisual) - png yuklenmiyor.

        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        // ---- Camera: orthographic, black background = "invisible" on a projector.
        var camGO = new GameObject("Main Camera");
        camGO.tag = "MainCamera";
        var cam = camGO.AddComponent<Camera>();
        cam.orthographic = true;
        cam.orthographicSize = 5f;
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = Color.black;
        camGO.transform.position = new Vector3(0f, 0f, -10f);
        camGO.AddComponent<AudioListener>();

        // ---- Spotlight: SpotlightController moves this GO. A child "Visuals" holds
        // the mask + revealed background + ring, and gets toggled OFF whenever no
        // hand is present, so the whole screen goes black in the idle/attract state.
        var spotGO = new GameObject("Spotlight");
        spotGO.transform.localScale = new Vector3(0.85f, 0.85f, 1f);
        var spotCtrl = spotGO.AddComponent<SpotlightController>();

        var visuals = new GameObject("Visuals");
        visuals.transform.SetParent(spotGO.transform, false);
        var mask = visuals.AddComponent<SpriteMask>();
        mask.sprite = circle;

        // Pale-blue revealed "world" shown inside the circle, behind the mouse.
        var bgGO = new GameObject("RevealBG");
        bgGO.transform.SetParent(visuals.transform, false);
        bgGO.transform.localScale = new Vector3(1.06f, 1.06f, 1f);
        var bgSR = bgGO.AddComponent<SpriteRenderer>();
        bgSR.sprite = bgS;
        bgSR.maskInteraction = SpriteMaskInteraction.VisibleInsideMask;
        bgSR.sortingOrder = -1;

        // Visible glowing ring (always visible, drawn on top).
        var ringGO = new GameObject("Ring");
        ringGO.transform.SetParent(visuals.transform, false);
        var ringSR = ringGO.AddComponent<SpriteRenderer>();
        ringSR.sprite = ring;
        ringSR.maskInteraction = SpriteMaskInteraction.None;
        ringSR.sortingOrder = 10;

        // ---- Mouse: logical parent (moved on respawn) + prosedurel "peynir yiyen
        // fare" gorseli (CheeseMouseVisual). Tum parcalar VisibleInsideMask -> sadece
        // spotlight icinde gorunur. Yakalaninca CheeseMouseVisual.Caught() endiseli
        // yuze gecirir. Konum/respawn MouseController'da.
        var mouseGO = new GameObject("Mouse");
        var mouseCtrl = mouseGO.AddComponent<MouseController>();

        var visualGO = new GameObject("Visual");
        visualGO.transform.SetParent(mouseGO.transform, false);
        visualGO.transform.localPosition = new Vector3(0f, 0.27f, 0f); // sanat merkezini fare orijinine hizala
        visualGO.transform.localScale = new Vector3(0.55f, 0.55f, 1f);  // spotlight cemberine sigacak boyut
        var mouseVisual = visualGO.AddComponent<CheeseMouseVisual>();

        // ---- Net (drops on a catch); prosedurel NetVisual (eski net.png yerine).
        // Maskelenmez -> her yerde gorunur; parcalar sortingOrder ~21-24 ile farenin
        // onunde cizilir, yani agin ustune dustugu okunur. NetCatch Transform'u
        // yukaridan indirir. NetVisual cizimi ilk aktif olusta (Awake) kurulur.
        var netGO = new GameObject("Net");
        netGO.transform.localScale = new Vector3(0.95f, 0.95f, 1f);
        netGO.AddComponent<NetVisual>();
        netGO.SetActive(false); // NetCatch toggles it during a catch

        // ---- Score UI (top-left).
        var canvasGO = new GameObject("Canvas");
        var canvas = canvasGO.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvasGO.AddComponent<CanvasScaler>();
        canvasGO.AddComponent<GraphicRaycaster>();

        var textGO = new GameObject("ScoreText");
        textGO.transform.SetParent(canvasGO.transform, false);
        var txt = textGO.AddComponent<Text>();
        txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        txt.fontSize = 48;
        txt.color = Color.white;
        txt.text = "Skor: 0";
        var rt = txt.rectTransform;
        rt.anchorMin = new Vector2(0f, 1f);
        rt.anchorMax = new Vector2(0f, 1f);
        rt.pivot = new Vector2(0f, 1f);
        rt.anchoredPosition = new Vector2(24f, -20f);
        rt.sizeDelta = new Vector2(500f, 90f);

        if (Object.FindFirstObjectByType<UnityEngine.EventSystems.EventSystem>() == null)
        {
            var es = new GameObject("EventSystem");
            es.AddComponent<UnityEngine.EventSystems.EventSystem>();
            es.AddComponent<UnityEngine.EventSystems.StandaloneInputModule>();
        }

        // ---- Game systems (logic holders).
        var sysGO = new GameObject("GameSystems");
        sysGO.AddComponent<HandReceiver>();           // port defaults to 9000
        var score = sysGO.AddComponent<ScoreManager>();
        var net = sysGO.AddComponent<NetCatch>();

        // ---- Wire serialized (private) fields via SerializedObject.
        var soSpot = new SerializedObject(spotCtrl);
        soSpot.FindProperty("targetCamera").objectReferenceValue = cam;
        soSpot.FindProperty("flipY").boolValue = true;
        soSpot.FindProperty("followSpeed").floatValue = 25f;          // smooth 30fps -> 60fps
        soSpot.FindProperty("predictionSeconds").floatValue = 0.015f; // small lead, clamped by maxLead
        soSpot.FindProperty("visualRoot").objectReferenceValue = visuals;
        soSpot.ApplyModifiedPropertiesWithoutUndo();

        var soMouse = new SerializedObject(mouseCtrl);
        soMouse.FindProperty("targetCamera").objectReferenceValue = cam;
        soMouse.FindProperty("marginX").floatValue = 0.16f;
        soMouse.FindProperty("marginY").floatValue = 0.16f;
        soMouse.ApplyModifiedPropertiesWithoutUndo();

        var soScore = new SerializedObject(score);
        soScore.FindProperty("label").objectReferenceValue = txt;
        soScore.FindProperty("prefix").stringValue = "Skor: ";
        soScore.ApplyModifiedPropertiesWithoutUndo();

        var soNet = new SerializedObject(net);
        soNet.FindProperty("spotlight").objectReferenceValue = spotCtrl;
        soNet.FindProperty("mouse").objectReferenceValue = mouseCtrl;
        soNet.FindProperty("score").objectReferenceValue = score;
        soNet.FindProperty("netVisual").objectReferenceValue = netGO.transform;
        soNet.FindProperty("catchRadius").floatValue = 1.5f;
        soNet.FindProperty("reactions").objectReferenceValue = mouseVisual;
        soNet.ApplyModifiedPropertiesWithoutUndo();

        // ---- Save the scene and register it as the build/startup scene.
        System.IO.Directory.CreateDirectory(Application.dataPath + "/Scenes");
        EditorSceneManager.MarkSceneDirty(scene);
        bool saved = EditorSceneManager.SaveScene(scene, ScenePath);
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();

        Debug.Log($"[CheeseHuntBuilder] Done. Scene saved={saved} at {ScenePath}");
    }

    static void ImportSprite(string path)
    {
        var ti = AssetImporter.GetAtPath(path) as TextureImporter;
        if (ti == null)
        {
            Debug.LogError($"[CheeseHuntBuilder] No importer for {path} (missing file?)");
            return;
        }
        ti.textureType = TextureImporterType.Sprite;
        ti.spriteImportMode = SpriteImportMode.Single;
        ti.alphaIsTransparency = true;
        ti.mipmapEnabled = false;
        ti.filterMode = FilterMode.Bilinear;
        ti.textureCompression = TextureImporterCompression.Uncompressed; // crisp soft gradients
        ti.maxTextureSize = 2048;
        ti.spritePixelsPerUnit = 200; // art is now 1024px; keep the same world size, 2x crisper
        ti.SaveAndReimport();
    }

    static Sprite Load(string path)
    {
        var s = AssetDatabase.LoadAssetAtPath<Sprite>(path);
        if (s == null) Debug.LogError($"[CheeseHuntBuilder] Could not load sprite at {path}");
        return s;
    }

    [System.Serializable]
    class RigInfo { public int[] canvas; public float[] neck_pivot; public int neck_y; }

    /// <summary>Neck pivot (x from left, y from bottom) written by process_mouse_rig.py.</summary>
    static Vector2 ReadNeckPivot()
    {
        try
        {
            string p = Application.dataPath + "/Art/mouse/rig.json";
            var info = JsonUtility.FromJson<RigInfo>(System.IO.File.ReadAllText(p));
            if (info != null && info.neck_pivot != null && info.neck_pivot.Length == 2)
                return new Vector2(info.neck_pivot[0], info.neck_pivot[1]);
        }
        catch (System.Exception e)
        {
            Debug.LogWarning("[CheeseHuntBuilder] rig.json read failed: " + e.Message);
        }
        return new Vector2(0.5f, 0.55f);
    }

    static void ImportSpriteCustomPivot(string path, Vector2 pivot)
    {
        var ti = AssetImporter.GetAtPath(path) as TextureImporter;
        if (ti == null) { Debug.LogError($"[CheeseHuntBuilder] No importer for {path}"); return; }
        ti.textureType = TextureImporterType.Sprite;
        ti.spriteImportMode = SpriteImportMode.Single;
        ti.alphaIsTransparency = true;
        ti.mipmapEnabled = false;
        ti.textureCompression = TextureImporterCompression.Uncompressed;
        ti.maxTextureSize = 2048;
        var s = new TextureImporterSettings();
        ti.ReadTextureSettings(s);
        s.spriteAlignment = (int)SpriteAlignment.Custom;
        s.spritePivot = pivot;
        ti.SetTextureSettings(s);
        ti.SaveAndReimport();
    }
}
