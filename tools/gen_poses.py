"""Generate the animation poses (eat-chew / panic / caught) keeping the SAME
character as hero_2, using IP-Adapter for character consistency.
Several variants per pose so we can pick the best. First run downloads the
IP-Adapter image encoder (~2.5 GB, cached afterwards).
"""
import time
import torch
from diffusers import StableDiffusionXLPipeline
from diffusers.utils import load_image

OUTDIR = r"C:\Users\Sergi-Teknik\GestureExhibit\art_in"
REF = OUTDIR + r"\hero_2.png"

STYLE = ("3D Pixar style render, cute chubby grey cartoon mouse, big glossy "
         "eyes, soft rounded shapes, pink ears and nose, soft studio lighting, "
         "isolated on plain solid white background, centered, full body, "
         "high quality, clean")
NEG = ("blurry, low quality, deformed, extra limbs, extra tails, text, "
       "watermark, signature, multiple mice, cluttered background, "
       "realistic photo, ugly, dark")

POSES = [
    ("eat", f"{STYLE}, the same grey mouse taking a big bite of a yellow swiss "
            f"cheese wedge, eyes closed happily, cheeks puffed, three-quarter "
            f"standing view", [11, 12]),
    ("panic", f"{STYLE}, the same grey mouse looking up in fear, eyes wide open, "
              f"mouth gasping in shock, ears pulled back, body recoiling "
              f"backward startled, sweat drop, no cheese, three-quarter "
              f"standing view", [21, 22]),
    ("caught", f"{STYLE}, the same grey mouse panicking with arms and legs "
               f"flailing in the air, scared wide eyes, mouth open screaming, "
               f"mid-air struggling pose, no cheese, three-quarter view", [31, 32]),
]

print("loading SDXL...")
pipe = StableDiffusionXLPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    torch_dtype=torch.float16, variant="fp16", use_safetensors=True)
print("loading IP-Adapter (downloads image encoder on first run)...")
pipe.load_ip_adapter("h94/IP-Adapter", subfolder="sdxl_models",
                     weight_name="ip-adapter_sdxl_vit-h.safetensors")
pipe.set_ip_adapter_scale(0.6)
pipe.enable_model_cpu_offload()
pipe.vae.enable_tiling()

ref = load_image(REF)

for name, prompt, seeds in POSES:
    for s in seeds:
        t0 = time.time()
        img = pipe(prompt=prompt, negative_prompt=NEG, ip_adapter_image=ref,
                   num_inference_steps=30, guidance_scale=6.5,
                   width=1024, height=1024,
                   generator=torch.Generator(device="cpu").manual_seed(s)).images[0]
        out = f"{OUTDIR}\\pose_{name}_{s}.png"
        img.save(out)
        print(f"saved {out} in {time.time()-t0:.1f}s")
print("done.")
