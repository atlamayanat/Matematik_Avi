// Auto-assembles the "Math Lens-Hunt" gesture game scene so nobody has to wire it
// by hand. Run from the menu (Tools > Math Lens > Build Scene) or the CLI:
//
//   Unity.exe -batchmode -quit -projectPath <proj> -executeMethod MathLensBuilder.Build
//
// Reveal mechanic: unlike CheeseHunt there is NO SpriteMask. A soft "light pool"
// (bg_reveal) + glowing ring follow the hand, and each AnswerToken self-reveals by
// its distance to the lens centre (LensHunt drives it). This lets the tokens be
// world-space TextMesh glyphs (which a SpriteMask cannot clip) while still giving
// the flashlight feel.

using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.UI;

public static class MathLensBuilder
{
    const string ArtDir = "Assets/Art";
    const string ScenePath = "Assets/Scenes/MathLens.unity";

    [MenuItem("Tools/Math Lens/Build Scene")]
    public static void Build()
    {
        Debug.Log("[MathLensBuilder] Building scene...");

        // Make sure the patched game font is imported so GameFont.Get() (Resources.Load)
        // resolves it while building the UI text.
        AssetDatabase.ImportAsset("Assets/Resources/FredokaGame.ttf");

        ImportSprite($"{ArtDir}/spotlight_ring.png");
        ImportSprite($"{ArtDir}/bg_reveal.png");
        Sprite ring = Load($"{ArtDir}/spotlight_ring.png");
        Sprite bgS  = Load($"{ArtDir}/bg_reveal.png");

        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        // ---- Camera: orthographic, solid black = dark field on the projector.
        var camGO = new GameObject("Main Camera");
        camGO.tag = "MainCamera";
        var cam = camGO.AddComponent<Camera>();
        cam.orthographic = true;
        cam.orthographicSize = 5f;
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = Color.black;
        camGO.transform.position = new Vector3(0f, 0f, -10f);
        camGO.AddComponent<AudioListener>();

        // ---- Spotlight: SpotlightController moves this GO. Child "Visuals" carries
        // the soft light pool + ring and is toggled OFF when no hand is present.
        var spotGO = new GameObject("Spotlight");
        spotGO.transform.localScale = new Vector3(0.85f, 0.85f, 1f);
        var spotCtrl = spotGO.AddComponent<SpotlightController>();

        var visuals = new GameObject("Visuals");
        visuals.transform.SetParent(spotGO.transform, false);

        var poolGO = new GameObject("LightPool");
        poolGO.transform.SetParent(visuals.transform, false);
        poolGO.transform.localScale = new Vector3(1.15f, 1.15f, 1f);
        var poolSR = poolGO.AddComponent<SpriteRenderer>();
        poolSR.sprite = bgS;
        poolSR.color = new Color(0.78f, 0.88f, 1f, 0.45f);
        poolSR.maskInteraction = SpriteMaskInteraction.None;
        poolSR.sortingOrder = -10;

        var ringGO = new GameObject("Ring");
        ringGO.transform.SetParent(visuals.transform, false);
        var ringSR = ringGO.AddComponent<SpriteRenderer>();
        ringSR.sprite = ring;
        ringSR.maskInteraction = SpriteMaskInteraction.None;
        ringSR.sortingOrder = -5;

        // ---- Tokens live under this parent (spawned at runtime by MathField).
        var tokensGO = new GameObject("Tokens");

        // ---- Start screen (attract): animated math backdrop + three difficulty
        // buttons (KOLAY / ORTA / ZOR). Picking one (lens + fist) starts the round at
        // that level. Plus a small RESET button top-right (under the timer).
        var startGO = new GameObject("StartScreen");
        var startScreen = startGO.AddComponent<StartScreen>();

        Color cEasy = new Color(0.30f, 0.80f, 0.45f);   // green
        Color cMed  = new Color(0.96f, 0.70f, 0.25f);   // amber
        Color cHard = new Color(0.92f, 0.36f, 0.34f);   // red
        var easyBtn = MakeButton(startGO.transform, new Vector3(-5.0f, -0.2f, 0f),
            "KOLAY", "ilkokul - ortaokul", cEasy, 1.45f, 1.05f, 2.2f, 0.11f, spotCtrl);
        var medBtn = MakeButton(startGO.transform, new Vector3(0f, -0.2f, 0f),
            "ORTA", "ortaokul - lise", cMed, 1.45f, 1.05f, 2.2f, 0.11f, spotCtrl);
        var hardBtn = MakeButton(startGO.transform, new Vector3(5.0f, -0.2f, 0f),
            "ZOR", "lise - üniversite", cHard, 1.45f, 1.05f, 2.2f, 0.11f, spotCtrl);

        var resetBtn = MakeButton(null, new Vector3(7.5f, 4.2f, 0f),
            "RESET", "", new Color(0.95f, 0.45f, 0.35f), 1.3f, 0.92f, 2.4f, 0.085f, spotCtrl);  // pill, top-right
        var soReset = new SerializedObject(resetBtn);                 // pin it to the true top-right corner on any aspect
        soReset.FindProperty("pinTopRight").boolValue = true;
        soReset.FindProperty("pinCamera").objectReferenceValue = cam;
        soReset.FindProperty("pinMargin").floatValue = 0.3f;
        soReset.ApplyModifiedPropertiesWithoutUndo();

        // ---- UI (top banner + counters + centre result).
        var canvasGO = new GameObject("Canvas");
        var canvas = canvasGO.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        var scaler = canvasGO.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1920f, 1080f);
        canvasGO.AddComponent<GraphicRaycaster>();

        Text prompt = MakeText(canvasGO.transform, "Prompt", 96, TextAnchor.UpperCenter,
            new Vector2(0.5f, 1f), new Vector2(0.5f, 1f), new Vector2(0f, -24f), new Vector2(1200f, 170f), "");
        // Left column: Soru / Doğru / Süre stacked top-left so the player reads them in
        // one glance (the lens lives on the right). The timer is the biggest of the three.
        Text progress = MakeText(canvasGO.transform, "Progress", 52, TextAnchor.UpperLeft,
            new Vector2(0f, 1f), new Vector2(0f, 1f), new Vector2(28f, -24f), new Vector2(520f, 74f), "Soru 1/5");
        Text correct = MakeText(canvasGO.transform, "Correct", 44, TextAnchor.UpperLeft,
            new Vector2(0f, 1f), new Vector2(0f, 1f), new Vector2(28f, -98f), new Vector2(520f, 64f), "Doğru: 0");
        Text timer = MakeText(canvasGO.transform, "Timer", 88, TextAnchor.UpperLeft,
            new Vector2(0f, 1f), new Vector2(0f, 1f), new Vector2(28f, -176f), new Vector2(520f, 130f), "2:00");
        Text result = MakeText(canvasGO.transform, "Result", 110, TextAnchor.MiddleCenter,
            new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0f, 0f), new Vector2(1500f, 420f), "");
        result.gameObject.SetActive(false);

        if (Object.FindAnyObjectByType<UnityEngine.EventSystems.EventSystem>() == null)
        {
            var es = new GameObject("EventSystem");
            es.AddComponent<UnityEngine.EventSystems.EventSystem>();
            es.AddComponent<UnityEngine.EventSystems.StandaloneInputModule>();
        }

        // ---- Game systems (logic holders).
        var sysGO = new GameObject("GameSystems");
        sysGO.AddComponent<HandReceiver>();          // port defaults to 9000
        var lens  = sysGO.AddComponent<LensHunt>();
        var field = sysGO.AddComponent<MathField>();
        var round = sysGO.AddComponent<RoundManager>();

        // ---- Wire serialized (private) fields via SerializedObject.
        var soSpot = new SerializedObject(spotCtrl);
        soSpot.FindProperty("targetCamera").objectReferenceValue = cam;
        soSpot.FindProperty("flipY").boolValue = true;
        soSpot.FindProperty("followSpeed").floatValue = 25f;
        soSpot.FindProperty("predictionSeconds").floatValue = 0.015f;
        soSpot.FindProperty("edgeMarginX").floatValue = 0.10f;   // map the comfy centre of the frame to the full screen
        soSpot.FindProperty("edgeMarginY").floatValue = 0.10f;   // so edges/corners are reachable without losing the hand
        soSpot.FindProperty("visualRoot").objectReferenceValue = visuals;
        soSpot.ApplyModifiedPropertiesWithoutUndo();

        var soLens = new SerializedObject(lens);
        soLens.FindProperty("spotlight").objectReferenceValue = spotCtrl;
        soLens.FindProperty("round").objectReferenceValue = round;
        soLens.ApplyModifiedPropertiesWithoutUndo();

        var soField = new SerializedObject(field);
        soField.FindProperty("tokenParent").objectReferenceValue = tokensGO.transform;
        soField.FindProperty("exclusionCenter").vector2Value = new Vector2(7.5f, 4.2f);
        soField.FindProperty("exclusionRadius").floatValue = 2.4f;  // >= RESET radius(1.3) + arm radius(1.05): no token arms in the reset zone
        soField.ApplyModifiedPropertiesWithoutUndo();

        var soRound = new SerializedObject(round);
        soRound.FindProperty("lens").objectReferenceValue = lens;
        soRound.FindProperty("field").objectReferenceValue = field;
        soRound.FindProperty("promptText").objectReferenceValue = prompt;
        soRound.FindProperty("timerText").objectReferenceValue = timer;
        soRound.FindProperty("progressText").objectReferenceValue = progress;
        soRound.FindProperty("correctText").objectReferenceValue = correct;
        soRound.FindProperty("resultText").objectReferenceValue = result;
        soRound.FindProperty("startScreen").objectReferenceValue = startScreen;
        soRound.FindProperty("easyButton").objectReferenceValue = easyBtn;
        soRound.FindProperty("mediumButton").objectReferenceValue = medBtn;
        soRound.FindProperty("hardButton").objectReferenceValue = hardBtn;
        soRound.FindProperty("resetButton").objectReferenceValue = resetBtn;
        soRound.ApplyModifiedPropertiesWithoutUndo();

        // ---- Save the scene and register it as the build/startup scene.
        System.IO.Directory.CreateDirectory(Application.dataPath + "/Scenes");
        EditorSceneManager.MarkSceneDirty(scene);
        bool saved = EditorSceneManager.SaveScene(scene, ScenePath);
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();

        Debug.Log($"[MathLensBuilder] Done. Scene saved={saved} at {ScenePath}");
    }

    static Text MakeText(Transform parent, string name, int size, TextAnchor anchor,
                         Vector2 anchorMin, Vector2 anchorMax, Vector2 pos, Vector2 sizeDelta, string content)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        var t = go.AddComponent<Text>();
        t.font = GameFont.Get();
        t.fontSize = size;
        t.alignment = anchor;
        t.color = Color.white;
        t.text = content;
        t.horizontalOverflow = HorizontalWrapMode.Overflow;
        t.verticalOverflow = VerticalWrapMode.Overflow;
        var rt = t.rectTransform;
        rt.anchorMin = anchorMin;
        rt.anchorMax = anchorMax;
        rt.pivot = anchorMax;        // pivot on the anchored corner so the offset reads naturally
        rt.anchoredPosition = pos;
        rt.sizeDelta = sizeDelta;
        return t;
    }

    static GestureButton MakeButton(Transform parent, Vector3 localPos, string label, string subLabel,
                                    Color color, float radius, float bodyScale, float bodyAspect,
                                    float labelSize, SpotlightController spot)
    {
        var go = new GameObject(label + "Button");
        if (parent != null) go.transform.SetParent(parent, false);
        go.transform.localPosition = localPos;
        var gb = go.AddComponent<GestureButton>();
        var so = new SerializedObject(gb);
        so.FindProperty("labelText").stringValue = label;
        so.FindProperty("subLabel").stringValue = subLabel;
        so.FindProperty("color").colorValue = color;
        so.FindProperty("radius").floatValue = radius;
        so.FindProperty("bodyScale").floatValue = bodyScale;
        so.FindProperty("bodyAspect").floatValue = bodyAspect;
        so.FindProperty("labelSize").floatValue = labelSize;
        so.FindProperty("spot").objectReferenceValue = spot;
        so.ApplyModifiedPropertiesWithoutUndo();
        return gb;
    }

    static void ImportSprite(string path)
    {
        var ti = AssetImporter.GetAtPath(path) as TextureImporter;
        if (ti == null)
        {
            Debug.LogError($"[MathLensBuilder] No importer for {path} (missing file?)");
            return;
        }
        ti.textureType = TextureImporterType.Sprite;
        ti.spriteImportMode = SpriteImportMode.Single;
        ti.alphaIsTransparency = true;
        ti.mipmapEnabled = false;
        ti.filterMode = FilterMode.Bilinear;
        ti.textureCompression = TextureImporterCompression.Uncompressed;
        ti.maxTextureSize = 2048;
        ti.spritePixelsPerUnit = 200;
        ti.SaveAndReimport();
    }

    static Sprite Load(string path)
    {
        var s = AssetDatabase.LoadAssetAtPath<Sprite>(path);
        if (s == null) Debug.LogError($"[MathLensBuilder] Could not load sprite at {path}");
        return s;
    }
}
