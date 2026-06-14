using UnityEngine;

/// <summary>
/// Single source of truth for the game's typeface. Loads "FredokaGame" (a patched
/// Fredoka that adds the Turkish letters İ ğ Ğ Ş ş — composed from Fredoka's own
/// shapes — plus the math glyphs √ π ∞, so every glyph the game shows renders).
/// Lives in Assets/Resources so it is loadable at runtime and bundled into builds.
/// Falls back to the built-in font if the asset is ever missing.
/// </summary>
public static class GameFont
{
    static Font _font;

    public static Font Get()
    {
        if (_font == null)
        {
            _font = Resources.Load<Font>("FredokaGame");
            if (_font == null)
            {
                Debug.LogWarning("[GameFont] FredokaGame not found in Resources; using built-in font.");
                _font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            }
        }
        return _font;
    }
}
