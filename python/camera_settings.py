"""camera_settings.py — Matematik Avı kamera ayar penceresi (küçük tkinter GUI).

Oyuna bağlı kamerayı buradan seç: mevcut kameraları tarar, CANLI ÖNİZLEME gösterir,
seçimi config.json'a (camera.device_index + camera.flip_horizontal) yazar.

Çalıştır:
    cd python
    python camera_settings.py
(veya kökteki Kamera-Ayarlari.bat'a çift tıkla)

Not: Detektör (main.py) açıkken kamerayı tutar -> önce onu kapat, sonra burada seç.
Bağımlılık: opencv-python, Pillow (ikisi de requirements.txt'te), tkinter (stdlib).
"""

from __future__ import annotations

import json
import os
import sys

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCHER = os.path.join(PROJECT_ROOT, "Matematik-Avi-Baslat.bat")

try:
    import cv2
except ImportError:
    cv2 = None
try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None


# ---------------- config I/O (GUI'siz, test edilebilir) ----------------
def load_config_dict() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_camera(device_index: int, flip_horizontal: bool) -> None:
    """config.json'daki camera bölümünü güncelle, geri kalanı KORU."""
    data = load_config_dict()
    cam = data.setdefault("camera", {})
    cam["device_index"] = int(device_index)
    cam["flip_horizontal"] = bool(flip_horizontal)
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


# ---------------- kamera tarama ----------------
def list_cameras(max_idx: int = 6):
    """Açılabilen kameraların [(index, width, height)] listesi (DSHOW; webcam.py ile aynı)."""
    found = []
    if cv2 is None:
        return found
    for idx in range(max_idx):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        try:
            if cap.isOpened():
                ok, fr = cap.read()
                if ok and fr is not None:
                    found.append((idx, int(fr.shape[1]), int(fr.shape[0])))
        finally:
            cap.release()
    return found


# ---------------- GUI ----------------
def run_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox

    if cv2 is None or Image is None:
        # tkinter'siz erken uyarı zor; basit print + return
        print("HATA: opencv-python ve Pillow gerekli:  pip install opencv-python pillow")
        return

    cfg = load_config_dict()
    cur_idx = int(cfg.get("camera", {}).get("device_index", 0))
    cur_flip = bool(cfg.get("camera", {}).get("flip_horizontal", True))

    root = tk.Tk()
    root.title("Matematik Avı — Kamera Ayarları")
    root.configure(bg="#0b0a1a")
    root.geometry("600x560")

    state = {"cap": None, "cams": [], "after": None}

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    tk.Label(root, text="KAMERA AYARLARI", fg="#7df3ff", bg="#0b0a1a",
             font=("Segoe UI", 14, "bold")).pack(pady=(12, 2))
    tk.Label(root, text="Oyuna bağlanacak kamerayı seç, önizle, kaydet.",
             fg="#a9a4d6", bg="#0b0a1a", font=("Segoe UI", 9)).pack()

    top = tk.Frame(root, bg="#0b0a1a"); top.pack(pady=8, fill="x", padx=16)
    tk.Label(top, text="Kamera:", fg="#eef1ff", bg="#0b0a1a",
             font=("Segoe UI", 10)).pack(side="left")
    combo = ttk.Combobox(top, state="readonly", width=34); combo.pack(side="left", padx=8)
    rescan_btn = tk.Button(top, text="Yeniden Tara"); rescan_btn.pack(side="left")

    flip_var = tk.BooleanVar(value=cur_flip)
    tk.Checkbutton(root, text="Aynalama (flip_horizontal) — ayna gibi göster",
                   variable=flip_var, fg="#eef1ff", bg="#0b0a1a", selectcolor="#1a1830",
                   activebackground="#0b0a1a", activeforeground="#eef1ff").pack()

    # Sabit piksel önizleme alanı (Frame width/height piksel; pack_propagate(False) korur).
    pv_frame = tk.Frame(root, bg="#04030d", width=512, height=288)
    pv_frame.pack(pady=10)
    pv_frame.pack_propagate(False)
    preview = tk.Label(pv_frame, bg="#04030d")
    preview.pack(expand=True)

    status = tk.Label(root, text="", fg="#34F5A6", bg="#0b0a1a", font=("Segoe UI", 9))
    status.pack()

    btns = tk.Frame(root, bg="#0b0a1a"); btns.pack(pady=10)
    save_btn = tk.Button(btns, text="Kaydet", width=14, bg="#1a1830", fg="#eef1ff")
    save_btn.pack(side="left", padx=6)
    save_launch_btn = tk.Button(btns, text="Kaydet ve Oyunu Başlat", width=22,
                                bg="#143", fg="#7DFFC4")
    save_launch_btn.pack(side="left", padx=6)

    tk.Label(root, text="Not: Detektör/oyun açıksa kamerayı bırakması için önce kapat. "
                        "Kaydettikten sonra oyunu yeniden başlat.",
             fg="#8f8ac0", bg="#0b0a1a", font=("Segoe UI", 8), wraplength=560).pack(pady=(4, 0))

    # ---- kamera açma/önizleme ----
    def open_cam(idx):
        close_cam()
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        state["cap"] = cap if cap.isOpened() else None
        if state["cap"] is None:
            cap.release()
            status.config(text=f"İndeks {idx} açılamadı (meşgul olabilir).", fg="#FF5470")

    def close_cam():
        if state["cap"] is not None:
            try: state["cap"].release()
            except Exception: pass
            state["cap"] = None

    def selected_index():
        sel = combo.current()
        if sel < 0 or sel >= len(state["cams"]):
            return None
        return state["cams"][sel][0]

    def on_select(_evt=None):
        idx = selected_index()
        if idx is not None:
            open_cam(idx)

    def tick():
        cap = state["cap"]
        if cap is not None:
            ok, fr = cap.read()
            if ok and fr is not None:
                if flip_var.get():
                    fr = cv2.flip(fr, 1)
                rgb = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[:2]
                scale = min(512 / w, 288 / h)
                img = Image.fromarray(rgb).resize((max(1, int(w * scale)), max(1, int(h * scale))))
                photo = ImageTk.PhotoImage(img)
                preview.configure(image=photo)
                preview.image = photo  # GC koruması
        state["after"] = root.after(50, tick)

    def scan():
        status.config(text="Kameralar taranıyor…", fg="#FFC83D")
        root.update_idletasks()
        cams = list_cameras()
        state["cams"] = cams
        if not cams:
            combo["values"] = []
            status.config(text="Kamera bulunamadı. Bağlı mı? Başka uygulama tutuyor olabilir.",
                          fg="#FF5470")
            close_cam()
            return
        labels = [f"İndeks {i} — {w}x{h}" for (i, w, h) in cams]
        combo["values"] = labels
        # mevcut config kamerasını seç, yoksa ilkini
        pick = next((k for k, (i, _, _) in enumerate(cams) if i == cur_idx), 0)
        combo.current(pick)
        status.config(text=f"{len(cams)} kamera bulundu.", fg="#34F5A6")
        on_select()

    def do_save():
        idx = selected_index()
        if idx is None:
            status.config(text="Önce bir kamera seç.", fg="#FF5470"); return False
        try:
            save_camera(idx, flip_var.get())
            status.config(text=f"Kaydedildi: kamera indeksi {idx}, aynalama {flip_var.get()}. "
                               f"Oyunu yeniden başlat.", fg="#34F5A6")
            return True
        except Exception as e:
            messagebox.showerror("Hata", f"config.json yazılamadı:\n{e}")
            return False

    def do_save_launch():
        if not do_save():
            return
        close_cam()  # önizleme kamerayı bıraksın ki oyun açabilsin
        if os.path.isfile(LAUNCHER):
            try:
                os.startfile(LAUNCHER)  # type: ignore[attr-defined]
                on_close()
            except Exception as e:
                messagebox.showwarning("Uyarı", f"Başlatıcı çalıştırılamadı:\n{e}")
        else:
            messagebox.showinfo("Bilgi", "Kaydedildi. Başlatıcı bulunamadı; oyunu elle başlat.")

    def on_close():
        if state["after"] is not None:
            try: root.after_cancel(state["after"])
            except Exception: pass
        close_cam()
        root.destroy()

    combo.bind("<<ComboboxSelected>>", on_select)
    rescan_btn.config(command=scan)
    save_btn.config(command=do_save)
    save_launch_btn.config(command=do_save_launch)
    root.protocol("WM_DELETE_WINDOW", on_close)

    root.after(100, scan)
    root.after(120, tick)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
