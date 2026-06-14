using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

// Tek tikla oynanabilir "Mouse Trap" sahnesi olusturur ve acar.
// Menu: Tools > Mouse Trap > Build & Open Scene
//
// MouseTrapScene her seyi (kamera, fare, kapan, HandReceiver) Play'de kod ile
// kurar; bu yuzden sahnede sadece tek bir bos GameObject + script yeterli.
// Edit modunda sahne bos gorunur, bu NORMAL - her sey Play'e basinca olusur.
public static class MouseTrapBuilder
{
    const string ScenePath = "Assets/Scenes/MouseTrap.unity";

    [MenuItem("Tools/Mouse Trap/Build & Open Scene")]
    public static void Build()
    {
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        var go = new GameObject("MouseTrap");
        go.AddComponent<MouseTrapScene>();

        System.IO.Directory.CreateDirectory(Application.dataPath + "/Scenes");
        EditorSceneManager.MarkSceneDirty(scene);
        bool saved = EditorSceneManager.SaveScene(scene, ScenePath);

        Debug.Log("[MouseTrapBuilder] MouseTrap sahnesi hazir (saved=" + saved + "). Simdi Play'e bas.");
    }
}
