"""Generate a few 'hero' mouse candidates (same style, different poses/seeds) so
the user can pick the final character. SDXL stays loaded -> fast iteration.
Saves hero_1..hero_4.png into art_in/.
"""
import time
import torch
from diffusers import StableDiffusionXLPipeline

OUTDIR = r"C:\Users\Sergi-Teknik\GestureExhibit\art_in"

STYLE = ("3D Pixar style render, cute chubby grey cartoon mouse, big glossy "
         "shiny eyes, soft rounded shapes, pink ears and nose, friendly happy, "
         "soft studio lighting, isolated on plain solid white background, "
         "centered, full body, video game character, high quality, clean")
NEG = ("blurry, low quality, deformed, extra limbs, extra tails, text, "
       "watermark, signature, multiple mice, cluttered background, "
       "realistic photo, scary, ugly, dark")

VARIANTS = [
    ("hero_1", f"{STYLE}, nibbling a wedge of yellow swiss cheese held in tiny paws, front view", 4242),
    ("hero_2", f"{STYLE}, holding and nibbling a wedge of yellow swiss cheese, three-quarter side view", 101),
    ("hero_3", f"{STYLE}, sitting and eating a wedge of yellow swiss cheese, side profile view", 202),
    ("hero_4", f"{STYLE}, happily nibbling yellow swiss cheese, front three-quarter view, cheerful", 777),
]

print("loading SDXL...")
pipe = StableDiffusionXLPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    torch_dtype=torch.float16, variant="fp16", use_safetensors=True)
pipe.enable_model_cpu_offload()
pipe.vae.enable_tiling()

for name, prompt, seed in VARIANTS:
    t0 = time.time()
    img = pipe(prompt=prompt, negative_prompt=NEG, num_inference_steps=30,
               guidance_scale=6.5, width=1024, height=1024,
               generator=torch.Generator(device="cpu").manual_seed(seed)).images[0]
    out = f"{OUTDIR}\\{name}.png"
    img.save(out)
    print(f"saved {out} in {time.time()-t0:.1f}s")
print("done.")
