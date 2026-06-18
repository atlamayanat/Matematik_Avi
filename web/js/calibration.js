/* calibration.js — biyometrik kalibrasyon giriş ekranı (ilk karşılama).
   Görsel/animasyon kaynağı: kalibrasyon-giris.html (DEĞİŞMEDEN taşındı).
   Tek fark: "FARE İLE TEST" bloğu kaldırıldı; yerine MA.input seam'inden
   el takibi sürücüsü bağlandı. window.MatematikKalibrasyon API'si korunur. */
(function () {
  const MA = (window.MA = window.MA || {});

  const stage  = document.getElementById('mk-stage');
  if (!stage) return;                      // markup yoksa sessizce çık
  const target = document.getElementById('mk-target');
  const halo   = document.getElementById('mk-halo');
  const ring   = document.getElementById('mk-ring');
  const fp     = document.getElementById('mk-fp');
  const pct    = document.getElementById('mk-pct');
  const fx     = document.getElementById('mk-fx');
  const status = document.getElementById('mk-status');
  const lock   = document.getElementById('mk-lock');

  let pointer = {x:0, y:0, present:false};
  let armed = false;
  let scanning = false;
  let calRaf = null, calPart = null, calDone = null;
  let onComplete = null;

  // ---- arka plan rakamları ----
  (function buildFloaters(){
    const host = document.getElementById('mk-floaters');
    const glyphs = ['7','3','½','π','%','9','4','=','∞','8','¾','+','×','2','√'];
    const cols = ['rgba(125,243,255,0.5)','rgba(159,95,255,0.5)','rgba(255,143,228,0.45)'];
    let html = '';
    for(let i=0;i<26;i++){
      const g = glyphs[Math.floor(Math.random()*glyphs.length)];
      html += '<span style="left:'+(Math.random()*96)+'%;top:'+(Math.random()*92)+'%;'
        + 'font-size:'+(2.2+Math.random()*4)+'cqmin;color:'+cols[Math.floor(Math.random()*cols.length)]+';'
        + 'opacity:'+(0.18+Math.random()*0.32)+';'
        + 'animation:mk-drift '+(5+Math.random()*5)+'s ease-in-out '+(Math.random()*3)+'s infinite alternate, '
        + 'mk-twinkle '+(2.5+Math.random()*3)+'s ease-in-out infinite;">'+g+'</span>';
    }
    host.innerHTML = html;
  })();

  // ---- merceği hedefe yaklaştırınca "armed" ----
  function updateArm(){
    if(scanning) return;
    const r = stage.getBoundingClientRect();
    const cx = r.width*0.5, cy = r.height*0.5;
    const d = Math.hypot(pointer.x-cx, pointer.y-cy);
    armed = pointer.present && d < r.width*0.13;
    target.style.transform = armed ? 'scale(1.07)' : 'scale(1)';
    halo.style.opacity     = armed ? '1' : '0.6';
    if(armed){ status.textContent='ŞİMDİ ELİNİZİ KAPATIN'; status.style.color='#7df3ff'; }
    else     { status.textContent='ELİNİZİ ORTAYA GETİRİN'; status.style.color='#eaf6ff'; }
  }

  // ---- tarama ----
  function startScan(){
    if(scanning || !armed) return;
    scanning = true; armed = false;

    target.style.transform = 'scale(1.05)';
    halo.style.opacity = '1';
    halo.style.background = 'radial-gradient(circle,rgba(0,235,255,0.42),rgba(125,243,255,0.12) 40%,transparent 66%)';
    ring.style.opacity = '1';
    pct.style.opacity = '1';
    lock.innerHTML = '<span style="width:1.2cqmin;height:1.2cqmin;border-radius:50%;background:#FFC83D;box-shadow:0 0 12px #FFC83D;"></span>TARANIYOR · <span id="mk-locknum">0</span>%';
    lock.style.color = '#FFC83D';
    status.textContent = 'TARAMA YAPILIYOR';
    status.style.color = '#FFC83D';
    status.style.textShadow = '0 0 22px rgba(255,200,61,0.65),0 0 40px rgba(255,200,61,0.3)';

    fp.style.filter = 'drop-shadow(0 0 8px rgba(125,243,255,1)) drop-shadow(0 0 18px rgba(0,235,255,0.85))';
    const circ = fp.querySelectorAll('circle'); const fast = ['1.4s','1s','0.6s'];
    circ.forEach((c,i)=>{ c.style.animationDuration = fast[i] || '1s'; });

    startParticles();

    const dur = 2500, t0 = performance.now();
    const step = (now)=>{
      const p = Math.min(1, (now-t0)/dur);
      const e = p<0.5 ? 2*p*p : 1-Math.pow(-2*p+2,2)/2;
      ring.style.setProperty('--p', (e*360).toFixed(1)+'deg');
      const pv = Math.round(e*100);
      pct.textContent = pv+'%';
      const ln = document.getElementById('mk-locknum'); if(ln) ln.textContent = pv;
      if(p<1){ calRaf = requestAnimationFrame(step); }
      else { finishScan(); }
    };
    calRaf = requestAnimationFrame(step);
  }

  function startParticles(){
    const cols = ['#7df3ff','#9be9ff','#ff8fe4','#ffffff'];
    const spawn = ()=>{
      const n = 1 + Math.floor(Math.random()*2);
      for(let i=0;i<n;i++){
        const s = document.createElement('span');
        const sz = (1.4+Math.random()*2.2).toFixed(1);
        const col = cols[Math.floor(Math.random()*cols.length)];
        s.style.cssText = 'position:absolute;left:50%;top:50%;width:'+sz+'px;height:'+sz+'px;border-radius:50%;background:'+col+';box-shadow:0 0 6px '+col+',0 0 12px '+col+';pointer-events:none;';
        fx.appendChild(s);
        const ang = Math.random()*Math.PI*2;
        const dist = fx.clientWidth*(0.22+Math.random()*0.26);
        const a = s.animate([
          {transform:'translate(-50%,-50%) translate(0,0) scale(0.4)',opacity:0},
          {opacity:1,offset:0.18},
          {transform:'translate(-50%,-50%) translate('+Math.cos(ang)*dist+'px,'+Math.sin(ang)*dist+'px) scale(1)',opacity:0}
        ],{duration:900+Math.random()*700, easing:'cubic-bezier(.2,.7,.3,1)'});
        a.onfinish = ()=>s.remove();
      }
    };
    spawn();
    calPart = setInterval(spawn, 150);
  }

  function stopParticles(){
    clearInterval(calPart);
    fx.innerHTML = '';
  }

  function finishScan(){
    stopParticles();
    halo.style.background = 'radial-gradient(circle,rgba(52,245,166,0.34),transparent 62%)';

    // tatmin edici bitiş
    target.animate([
      {transform:'scale(1.05)'},{transform:'scale(1.14)',offset:0.35},{transform:'scale(1)'}
    ],{duration:520, easing:'cubic-bezier(.25,1.3,.4,1)'});
    halo.animate([
      {opacity:1,filter:'brightness(1)'},{opacity:1,filter:'brightness(2.2)',offset:0.25},{opacity:1,filter:'brightness(1)'}
    ],{duration:520, easing:'ease-out'});
    for(let i=0;i<2;i++){
      const w = document.createElement('span');
      const col = i===0 ? '#34F5A6' : '#7df3ff';
      w.style.cssText = 'position:absolute;left:50%;top:50%;width:30%;height:30%;border-radius:50%;border:2px solid '+col+';box-shadow:0 0 18px '+col+';pointer-events:none;';
      fx.appendChild(w);
      const a = w.animate([
        {transform:'translate(-50%,-50%) scale(0.5)',opacity:0.95},
        {transform:'translate(-50%,-50%) scale(2.3)',opacity:0}
      ],{duration:620, delay:i*120, easing:'cubic-bezier(.2,.7,.3,1)'});
      a.onfinish = ()=>w.remove();
    }
    for(let i=0;i<14;i++){
      const s = document.createElement('span');
      s.style.cssText = 'position:absolute;left:50%;top:50%;width:3px;height:3px;border-radius:50%;background:#aef9d8;box-shadow:0 0 8px #34F5A6;pointer-events:none;';
      fx.appendChild(s);
      const ang = (i/14)*Math.PI*2, dist = fx.clientWidth*(0.28+Math.random()*0.12);
      const a = s.animate([
        {transform:'translate(-50%,-50%) translate(0,0) scale(1)',opacity:1},
        {transform:'translate(-50%,-50%) translate('+Math.cos(ang)*dist+'px,'+Math.sin(ang)*dist+'px) scale(0.3)',opacity:0}
      ],{duration:560, easing:'cubic-bezier(.15,.8,.3,1)'});
      a.onfinish = ()=>s.remove();
    }

    fp.style.filter = 'drop-shadow(0 0 6px rgba(52,245,166,1)) drop-shadow(0 0 14px rgba(52,245,166,0.7))';
    const circ = fp.querySelectorAll('circle'); const base = ['9s','6.5s','4s'];
    circ.forEach((c,i)=>{ c.style.animationDuration = base[i] || '6s'; });

    pct.textContent = '100%';
    status.textContent = 'TARAMA TAMAMLANDI';
    status.style.color = '#34F5A6';
    status.style.textShadow = '0 0 24px rgba(52,245,166,0.7),0 0 44px rgba(52,245,166,0.35)';
    lock.innerHTML = '<span style="width:1.2cqmin;height:1.2cqmin;border-radius:50%;background:#34F5A6;box-shadow:0 0 12px #34F5A6;"></span>ERİŞİM SAĞLANDI';
    lock.style.color = '#34F5A6';

    clearTimeout(calDone);
    calDone = setTimeout(()=>{
      scanning = false;
      stage.dispatchEvent(new CustomEvent('kalibrasyon-tamam', {bubbles:true}));
      if(typeof onComplete === 'function') onComplete();
    }, 1050);
  }

  function reset(){
    clearTimeout(calDone); clearInterval(calPart); cancelAnimationFrame(calRaf);
    scanning = false; armed = false; fx.innerHTML = '';
    ring.style.opacity = '0'; pct.style.opacity = '0'; pct.textContent = '0%';
    ring.style.setProperty('--p','0deg');
    halo.style.opacity = '0.6';
    halo.style.background = 'radial-gradient(circle,rgba(0,235,255,0.26),transparent 62%)';
    fp.style.filter = 'drop-shadow(0 0 3px rgba(125,243,255,0.55))';
    fp.querySelectorAll('circle').forEach((c,i)=>{ c.style.animationDuration = ['9s','6.5s','4s'][i]; });
    target.style.transform = 'scale(1)';
    status.textContent = 'ELİNİZİ ORTAYA GETİRİN'; status.style.color = '#eaf6ff';
    status.style.textShadow = '0 0 22px rgba(0,235,255,0.65),0 0 40px rgba(0,235,255,0.35)';
    lock.innerHTML = '<span style="width:1.2cqmin;height:1.2cqmin;border-radius:50%;background:#00EBFF;box-shadow:0 0 12px #00EBFF;animation:mk-pulse-dot 1.6s ease-in-out infinite;"></span>TARAMA BEKLENİYOR';
    lock.style.color = '#7aa9ff';
  }

  // ===== GENEL API (kalibrasyon-giris.html ile aynı sözleşme) =====
  window.MatematikKalibrasyon = {
    // El takibinden mercek konumunu besle (.mk-stage içi piksel)
    setPointer(x, y){ pointer.x = x; pointer.y = y; pointer.present = true; updateArm(); },
    clearPointer(){ pointer.present = false; updateArm(); },
    // El kapandığında çağır → mercek hedefteyse tarama başlar
    fist(){ startScan(); },
    // Tarama tamamlanınca tetiklenecek callback
    onComplete(cb){ onComplete = cb; },
    reset
  };

  // ===== EL TAKİBİ SÜRÜCÜSÜ (MA.input seam'i → setPointer/clearPointer/fist) =====
  // FARE TESTİNİN yerine: her karede MA.input.hand'i .mk-stage pikseline çevirip besler.
  let driverRaf = null, active = false, prevFist = false;
  function driverFrame(){
    if(!active) return;
    const hand = (window.MA && window.MA.input && window.MA.input.hand) || null;
    if(hand){
      if(hand.present){
        const r = stage.getBoundingClientRect();
        // hand.x/y 0..1 (#stage'e göre); .mk-stage #stage'i kapladığından doğrudan ölçekle
        window.MatematikKalibrasyon.setPointer(hand.x * r.width, hand.y * r.height);
      } else {
        window.MatematikKalibrasyon.clearPointer();
      }
      // Yumruk yükselen kenarı: jest sürerken tekrar tetikleme
      const isFist = hand.present && hand.gesture === 'fist';
      if(isFist && !prevFist) window.MatematikKalibrasyon.fist();
      prevFist = isFist;
    }
    driverRaf = requestAnimationFrame(driverFrame);
  }

  function show(){
    stage.classList.remove('mk-off');
    active = true; prevFist = false;
    if(!driverRaf) driverRaf = requestAnimationFrame(driverFrame);
  }
  function hide(){
    active = false;
    if(driverRaf){ cancelAnimationFrame(driverRaf); driverRaf = null; }
    stage.classList.add('mk-off');
  }
  // Ekranı baştan kur, tamamlanınca onDone çağır + overlay'i gizle.
  function boot(onDone){
    reset();
    onComplete = function(){
      hide();
      if(typeof onDone === 'function') onDone();
    };
    show();
  }

  MA.calib = { boot, show, hide, reset, get active(){ return active; } };
})();
