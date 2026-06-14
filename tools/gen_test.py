"""Validate local SDXL image generation on this machine's GPU.
Generates ONE 'hero' mouse frame so we can check quality before building the
full pipeline. First run downloads the SDXL base model (~6.5 GB) from Hugging
Face (no token needed). Uses model-CPU-offload so it fits in 8 GB VRAM.
"""
import time
import torch
from diffusers import StableDiffusionXLPipeline

OUT = r"C:\Users\Sergi-Teknik\GestureExhibit\art_in\_test_hero.png"

print("torch", torch.__version__, "| CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))

pipe = StableDiffusionXLPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    torch_dtype=torch.float16,
    variant="fp16",
    use_safetensors=True,
)
pipe.enable_model_cpu_offload()   # fits 8 GB VRAM, offloads to the 32 GB RAM
pipe.enable_vae_tiling()

prompt = (
    "3D Pixar style render of a cute chubby grey cartoon mouse nibbling a wedge "
    "of yellow swiss cheese held in tiny paws, big glossy shiny eyes, soft "
    "rounded shapes, pink ears and nose, friendly happy expression, soft studio "
    "lighting, full body, side view, centered, isolated on plain solid white "
    "background, video game character, high quality, clean"
)
negative = (
    "blurry, low quality, deformed, extra limbs, extra tails, text, watermark, "
    "signature, multiple mice, cluttered background, realistic photo, scary, ugly"
)

t0 = time.time()
img = pipe(
    prompt=prompt,
    negative_prompt=negative,
    num_inference_steps=30,
    guidance_scale=6.5,
    width=1024,
    height=1024,
    generator=torch.Generator(device="cpu").manual_seed(4242),
).images[0]
img.save(OUT)
print(f"saved {OUT} in {time.time() - t0:.1f}s")
