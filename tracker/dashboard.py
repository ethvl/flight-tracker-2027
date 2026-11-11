"""Static, mobile-responsive HTML dashboard (host anywhere; `serve` runs it live).

Layout: quiet header -> three spotlight insights -> one card per destination that
expands in place to show airlines, times and booking links -> value ranking.
"""
from __future__ import annotations

from datetime import datetime
from html import escape as e

from .aggregate import coverage
from .analysis import DailyReport, DestReport
from .config import Config
from .links import build_links
from .logos import avatar

FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800'
         '&display=swap">')

# restrained palette: monochrome surfaces, one green reserved for savings
DARK = ("--bg:#0a0a0c;--glow1:rgba(120,140,255,.10);--glow2:rgba(255,255,255,.05);--card:rgba(255,255,255,.045);"
        "--card-hi:rgba(255,255,255,.075);--inset:rgba(255,255,255,.04);--line:rgba(255,255,255,.08);"
        "--line-hi:rgba(255,255,255,.2);--ink:#f5f5f7;--ink2:#a1a1a6;--muted:#6e6e73;--green:#30d158;"
        "--green-bg:rgba(48,209,88,.14);--red:#ff6961;--red-bg:rgba(255,105,97,.13);--btn:#f5f5f7;--btn-ink:#000;--ambient:0 30px 80px -40px rgba(120,140,255,.25)")
LIGHT = ("--bg:#f5f5f7;--glow1:rgba(255,255,255,.9);--glow2:rgba(255,255,255,0);--card:#fff;--card-hi:#fff;"
         "--inset:#f5f5f7;--line:rgba(0,0,0,.08);--line-hi:rgba(0,0,0,.2);--ink:#1d1d1f;--ink2:#6e6e73;--muted:#86868b;"
         "--green:#1a7f37;--green-bg:rgba(26,127,55,.1);--red:#c9342c;--red-bg:rgba(201,52,44,.09);--btn:#1d1d1f;--btn-ink:#fff;"
         "--ambient:0 30px 60px -40px rgba(0,0,0,.25)")

CSS = (":root{" + LIGHT + ";color-scheme:light;"
       "--sans:-apple-system,BlinkMacSystemFont,'SF Pro Display','SF Pro Text','Inter',system-ui,sans-serif;"
       "--ease:cubic-bezier(.32,.72,0,1)}"
       # light is the default on every device; dark applies only when chosen with the toggle
       ":root[data-theme='dark']{" + DARK + ";color-scheme:dark}" + """
*{box-sizing:border-box}
body{margin:0;transition:background-color .35s ease,color .35s ease;color:var(--ink);font:400 15px/1.5 var(--sans);-webkit-font-smoothing:antialiased;background-color:var(--bg);
background-image:radial-gradient(1000px 500px at 50% -180px,var(--glow1),transparent 70%),radial-gradient(600px 300px at 85% 0,var(--glow2),transparent 70%);background-repeat:no-repeat}
.wrap{max-width:1160px;margin:0 auto;padding-block:28px 80px;padding-left:max(20px,env(safe-area-inset-left,0px));
padding-right:max(20px,env(safe-area-inset-right,0px));display:flex;flex-direction:column;gap:48px}
.num{font-variant-numeric:tabular-nums;font-feature-settings:"tnum" 1}
/* header */
.bar{display:flex;align-items:center;gap:12px 16px;flex-wrap:wrap}
.bar h1{font-size:1.05rem;font-weight:600;letter-spacing:-.01em;margin:0}
.tools{margin-left:auto;display:flex;align-items:center;gap:10px}
.rbtn{all:unset;box-sizing:border-box;display:inline-flex;align-items:center;gap:8px;cursor:pointer;font-size:.9rem;font-weight:600;border-radius:999px;
padding:10px 18px;background:var(--btn);color:var(--btn-ink);transition:transform .2s var(--ease),opacity .2s}
.rbtn svg{width:16px;height:16px}
.rbtn:active{transform:scale(.96)}.rbtn[disabled]{opacity:.6;cursor:default}
.rbtn.spin svg{animation:spin .9s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.tbtn{all:unset;box-sizing:border-box;cursor:pointer;width:40px;height:40px;border-radius:50%;display:grid;place-items:center;border:1px solid var(--line);
background:var(--card);color:var(--ink);transition:transform .2s var(--ease),background-color .2s}
.tbtn:active{transform:scale(.92)}
.tbtn svg{width:18px;height:18px;grid-area:1/1;transition:opacity .3s,transform .5s var(--ease)}
.tbtn .moon{opacity:0;transform:rotate(-60deg) scale(.6)}
:root[data-theme='dark'] .tbtn .moon{opacity:1;transform:none}
:root[data-theme='dark'] .tbtn .sun{opacity:0;transform:rotate(60deg) scale(.6)}
.rbtn:focus-visible,.tbtn:focus-visible{outline:2px solid var(--ink);outline-offset:3px}
.ov{padding:28px 32px;display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:24px 40px;align-items:center}
.ovr{display:grid;grid-template-columns:auto minmax(40px,1fr) auto;align-items:center;gap:18px}
.ovc{font-size:clamp(1.5rem,3vw,2.1rem);font-weight:700;letter-spacing:-.03em;line-height:1.1}
.ov .city{font-size:.85rem;color:var(--ink2)}
.ov .path{padding-top:0}
.ov .chips{justify-content:flex-end}
/* loading skeleton */
@keyframes shim{to{background-position:-200% 0}}
.loading .tot,.loading .per,.loading .big,.loading .cap,.loading .trend,.loading .via{color:transparent!important;border-radius:8px;
background:linear-gradient(90deg,var(--inset) 25%,var(--line) 50%,var(--inset) 75%);background-size:200% 100%;animation:shim 1.1s linear infinite;border-color:transparent}
.loading .tot,.loading .per,.loading .big{display:inline-block;min-width:4ch}
.loading .unit,.loading .trend>*,.loading .via>*,.loading .big *{visibility:hidden}
.status{display:inline-flex;align-items:center;gap:8px;font-size:.8rem;color:var(--ink2)}
.dot{width:7px;height:7px;border-radius:50%;background:var(--green);animation:pulse 2.6s infinite}
.dot.idle{background:var(--muted);animation:none}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(48,209,88,.5)}70%{box-shadow:0 0 0 9px rgba(48,209,88,0)}100%{box-shadow:0 0 0 0 rgba(48,209,88,0)}}
h1{font-size:clamp(2.2rem,5.2vw,3.5rem);font-weight:700;letter-spacing:-.035em;line-height:1.05;margin:0;text-wrap:balance}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{display:inline-flex;align-items:center;gap:7px;font-size:.82rem;font-weight:500;color:var(--ink2);border:1px solid var(--line);border-radius:999px;padding:6px 13px;background:var(--card);white-space:nowrap}
.chip svg{width:14px;height:14px;flex:none}
.chip.off{color:var(--muted);border-style:dashed;background:transparent}
.chip.on{color:var(--ink);border-color:var(--line-hi)}
.sellers{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:8px 14px;align-items:center;font-size:.88rem}
.sellers .sp{font-weight:600}
.empty{padding:48px 32px;text-align:center}
.empty h2{margin-bottom:8px}
.empty p{margin:0 auto;color:var(--ink2);max-width:46ch}
.legname{font-size:.72rem;font-weight:600;color:var(--muted);letter-spacing:.04em;text-transform:uppercase;display:flex;justify-content:space-between;gap:8px}
.route{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:start;gap:14px;padding:14px 16px;background:var(--inset);border-radius:14px}
.pt .code{font-size:1.3rem;font-weight:700;letter-spacing:-.01em;line-height:1.1}
.pt .city{font-size:.72rem;color:var(--muted)}
.pt .time{font-size:.95rem;font-weight:600;margin-top:6px}
.pt .chk{font-size:.7rem;color:var(--green);font-weight:600;white-space:nowrap}
.pt.r{text-align:right}
.path{display:flex;flex-direction:column;align-items:center;gap:5px;min-width:0;padding-top:8px}
.ln{display:flex;align-items:center;gap:8px;width:100%;color:var(--ink2)}
.ln::before,.ln::after{content:"";flex:1;height:1px;background:var(--line-hi)}
.ln svg{width:16px;height:16px;flex:none}
.dur{font-size:.72rem;color:var(--muted);white-space:nowrap}
.legsw{display:flex;flex-direction:column;gap:8px}
.fl{font-size:.78rem;color:var(--muted);font-weight:400}
.lede{font-size:clamp(1rem,1.6vw,1.2rem);color:var(--ink2);margin:0;max-width:60ch;font-weight:400}
h2{font-size:1.5rem;font-weight:600;letter-spacing:-.02em;margin:0}
.sech{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
.sech span{color:var(--muted);font-size:.85rem}
section{display:flex;flex-direction:column;gap:24px;min-width:0}
/* surfaces */
.glass{transition:background-color .35s ease,border-color .35s ease;border:1px solid var(--line);border-radius:24px;background:var(--card);backdrop-filter:blur(24px) saturate(140%);
-webkit-backdrop-filter:blur(24px) saturate(140%);box-shadow:var(--ambient)}
/* spotlight */
.spot{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}
.s{position:relative;overflow:hidden;padding:32px;display:flex;flex-direction:column;gap:6px;min-width:0}
.s::before{content:"";position:absolute;left:50%;top:-90px;width:260px;height:180px;transform:translateX(-50%);border-radius:50%;
background:var(--tint,var(--glow1));filter:blur(50px);pointer-events:none}
.s.save{--tint:var(--green-bg)}
.eyebrow{font-size:.8rem;font-weight:600;color:var(--ink2);position:relative}
.s .city{font-size:1.5rem;font-weight:600;letter-spacing:-.02em;position:relative}
.s .big{font-size:clamp(2.6rem,4.6vw,3.4rem);font-weight:700;letter-spacing:-.045em;line-height:1.05;margin-top:14px;position:relative}
.s.save .big{color:var(--green)}
.unit{white-space:nowrap;font-size:.85rem;font-weight:400;letter-spacing:0;color:var(--muted);margin-left:6px}
.s .cap{color:var(--ink2);font-size:.9rem;position:relative}
/* destination cards */
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;align-items:start}
.d{min-width:0;transition:transform .3s ease-out,border-color .3s ease-out,background-color .3s ease-out}
.d:hover{transform:scale(1.01);border-color:var(--line-hi);background:var(--card-hi)}
.d.open{transform:none;border-color:var(--line-hi);background:var(--card-hi)}
.d.na{box-shadow:none}
.d.na .name,.d.na .tot{color:var(--muted)}
.head{all:unset;box-sizing:border-box;display:flex;flex-direction:column;gap:18px;width:100%;padding:24px;cursor:pointer;border-radius:24px}
.head:focus-visible{outline:2px solid var(--ink);outline-offset:-4px}
.id{display:flex;align-items:center;gap:14px}
.ico{width:44px;height:44px;flex:none;border-radius:13px;display:grid;place-items:center;background:var(--inset);border:1px solid var(--line);color:var(--ink2)}
.ico svg{width:22px;height:22px}
.name{font-size:1.3rem;font-weight:600;letter-spacing:-.02em;line-height:1.2}
.where{font-size:.82rem;color:var(--muted);font-weight:400}
.plus{margin-left:auto;width:30px;height:30px;flex:none;border-radius:50%;display:grid;place-items:center;background:var(--inset);color:var(--ink2);
transition:transform .45s var(--ease),background-color .2s}
.plus svg{width:14px;height:14px}
.open .plus{transform:rotate(45deg);background:var(--line)}
.price{display:flex;justify-content:space-between;align-items:flex-end;gap:12px}
.tot{font-size:2.6rem;font-weight:700;letter-spacing:-.04em;line-height:1}
.per{font-size:.9rem;color:var(--ink2);margin-top:8px;font-weight:400}
.per{white-space:nowrap}
.trend{display:flex;align-items:center;gap:12px}
.trend svg{flex:1;min-width:0;height:40px}
.trend .lab{font-size:.72rem;color:var(--muted);white-space:nowrap}
.via{display:flex;align-items:center;gap:10px;padding-top:16px;border-top:1px solid var(--line);font-size:.9rem;min-width:0}
.via b{font-weight:600}.via .t{color:var(--muted);font-size:.8rem;margin-left:auto;text-align:right}
.av{width:28px;height:28px;flex:none;border-radius:8px;display:inline-grid;place-items:center;font-size:.62rem;font-weight:700;letter-spacing:.02em;overflow:hidden}
.av.logo{background:#fff;padding:3px;box-shadow:0 0 0 1px var(--line)}
.av img{width:100%;height:100%;object-fit:contain;display:block}
.av.lg{width:36px;height:36px;border-radius:10px;font-size:.75rem}
.legs .ok{color:var(--green);font-weight:500;white-space:nowrap}
.pills{display:flex;flex-wrap:wrap;gap:6px}
.pill{font-size:.75rem;font-weight:500;border-radius:999px;padding:4px 11px;color:var(--ink2);background:var(--inset);border:1px solid var(--line);white-space:nowrap}
.pill.solid{color:var(--ink);border-color:var(--line-hi)}
.pill.up{color:var(--red);background:var(--red-bg);border-color:transparent}
.pill.save{color:var(--green);background:var(--green-bg);border-color:transparent}
.pill.unmet{font-style:italic;color:var(--muted);border-style:dashed;background:transparent;white-space:normal;cursor:help}
/* expanding sheet */
.reveal{display:grid;grid-template-rows:0fr;transition:grid-template-rows .5s var(--ease)}
.open .reveal{grid-template-rows:1fr}
.reveal>div{overflow:hidden;min-height:0}
.sheet{padding:0 24px 24px;display:flex;flex-direction:column;gap:20px;opacity:0;transform:translateY(-6px);transition:opacity .35s ease-out,transform .5s var(--ease)}
.open .sheet{opacity:1;transform:none}
.sheet hr{border:0;border-top:1px solid var(--line);margin:0;width:100%}
.facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px 16px}
.facts div{font-size:.78rem;color:var(--muted)}
.facts b{display:block;font-size:1rem;font-weight:600;color:var(--ink);letter-spacing:-.01em}
.viaNote{font-size:.85rem;color:var(--ink2)}
.opt{display:flex;flex-direction:column;gap:12px}
.opt .hd{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.opt .hd .who{display:flex;align-items:center;gap:10px}
.opt .hd b{font-size:1.05rem;font-weight:600;letter-spacing:-.01em}
.opt .hd span{font-weight:600}
.opt .hd span small{font-weight:400;color:var(--muted);font-size:.8rem}
.legs{background:var(--inset);border-radius:14px;padding:12px 14px;display:grid;grid-template-columns:auto 1fr auto;gap:6px 12px;font-size:.85rem}
.legs i{font-style:normal;color:var(--muted)}
.legs span{color:var(--ink);overflow-wrap:anywhere}
.small{font-size:.78rem;color:var(--muted)}
.acts{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center}
.book{display:inline-flex;align-items:center;gap:8px;text-decoration:none;font-size:.9rem;font-weight:600;border-radius:999px;padding:10px 18px;
background:var(--btn);color:var(--btn-ink);transition:transform .2s var(--ease),opacity .2s}
.book .arr{display:inline-block;transition:transform .3s var(--ease)}
.book:hover .arr{transform:translateX(4px)}
.book:active{transform:scale(.96);opacity:.85}
.book:focus-visible,.alt:focus-visible{outline:2px solid var(--ink);outline-offset:3px}
.alt{color:var(--ink2);font-size:.85rem;text-decoration:none;border-bottom:1px solid var(--line-hi);padding-bottom:1px;transition:color .2s}
.alt:hover{color:var(--ink)}
.opts{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:24px 32px}
.opts .opt{padding-top:20px;border-top:1px solid var(--line)}
/* open card takes the full row: summary left, sheet right */
@media (min-width:641px){.d.open{grid-column:1/-1;display:grid;grid-template-columns:minmax(0,340px) minmax(0,1fr)}
.d.open .sheet{padding:24px 24px 24px 8px}.d.open .sheet>hr:first-child{display:none}.d.open .facts{grid-template-columns:repeat(4,minmax(0,1fr))}}
::view-transition-group(*){animation-duration:.5s;animation-timing-function:cubic-bezier(.32,.72,0,1)}
.vt .reveal,.vt .sheet{transition:none}
/* ranking */
.rank{padding:32px}
.rank p{margin:0;color:var(--ink2);max-width:68ch;font-size:1rem}
.bars{display:grid;grid-template-columns:auto minmax(0,1fr) auto auto;gap:14px 18px;align-items:center}
.bars .n{font-weight:500}.bars .v{color:var(--muted);font-size:.85rem;text-align:right}
.track{height:4px;border-radius:2px;background:var(--line)}
.track i{display:block;height:100%;border-radius:2px;background:var(--ink)}
footer{color:var(--muted);font-size:.78rem;max-width:80ch;line-height:1.6}
@media (max-width:1000px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.spot{grid-template-columns:1fr}.s{padding:28px}}
@media (max-width:640px){.wrap{gap:48px;padding-block:36px 64px}.grid{grid-template-columns:1fr;gap:14px}.spot{gap:14px}
.ov{grid-template-columns:1fr;padding:22px}.ov .chips{justify-content:flex-start}.ovr{gap:10px}.rbtn{padding:9px 14px}.head{padding:22px}.sheet{padding:0 22px 22px}.rank{padding:24px}.bars{grid-template-columns:auto minmax(0,1fr) auto}.bars .v{display:none}.d:hover{transform:none}}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
""")

JS = """
(function(){
  var cards=[].slice.call(document.querySelectorAll('.d'));
  var vt=typeof document.startViewTransition==='function'&&!matchMedia('(prefers-reduced-motion: reduce)').matches;
  if(vt)document.documentElement.classList.add('vt');
  function set(card,open){card.classList.toggle('open',open);card.querySelector('.head').setAttribute('aria-expanded',open)}
  cards.forEach(function(card){
    card.querySelector('.head').addEventListener('click',function(){
      var open=!card.classList.contains('open');
      function apply(){cards.forEach(function(c){set(c,c===card&&open)})}
      if(vt)document.startViewTransition(apply);else apply();
    });
  });

  /* theme: light unless the viewer switched to dark */
  var root=document.documentElement,tb=document.getElementById('theme');
  function setTheme(t){root.setAttribute('data-theme',t);tb.setAttribute('aria-pressed',t==='dark');
    tb.setAttribute('aria-label',t==='dark'?'Switch to light mode':'Switch to dark mode');}
  var saved=null;try{saved=localStorage.getItem('ft-theme')}catch(e){}
  setTheme(saved==='dark'?'dark':'light');
  tb.addEventListener('click',function(){var t=root.getAttribute('data-theme')==='dark'?'light':'dark';setTheme(t);
    try{localStorage.setItem('ft-theme',t)}catch(e){}});

  /* refresh: ask the server for a new fetch if there is one, otherwise check for a newer published snapshot */
  var rb=document.getElementById('refresh'),stamp=document.getElementById('stamp'),wrap=document.querySelector('.wrap');
  function hhmm(){return new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}
  rb.addEventListener('click',function(){
    if(rb.disabled)return;
    rb.disabled=true;rb.classList.add('spin');wrap.classList.add('loading');
    var t0=Date.now(),gen=wrap.getAttribute('data-generated');
    function done(msg,reload){setTimeout(function(){
      if(reload){location.reload();return}
      wrap.classList.remove('loading');rb.classList.remove('spin');rb.disabled=false;stamp.textContent=msg;
    },Math.max(0,900-(Date.now()-t0)))}
    function snapshot(){return fetch('latest.json',{cache:'no-store'}).then(function(r){if(!r.ok)throw 0;return r.json()})
      .then(function(j){if(j.generated&&j.generated>gen)done('',true);else done('Up to date · checked '+hhmm())})}
    fetch('api/refresh',{method:'POST'}).then(function(r){if(!r.ok)throw 0;return r.json()})
      .then(function(){done('',true)},function(){return snapshot()})
      .catch(function(){done('Could not check · '+hhmm())});
  });
})();
"""

ICONS = {
    "hub": "M3 20h18M5 20V9l5-3v14M10 20V4l6 3v13M16 20v-8l4 2v6",
    "cultural": "M3 6c3 1.2 15 1.2 18 0M5 10h14M7.5 6.5V20M16.5 6.5V20M12 6.8V10",
    "island": "M3 19c2-1.8 4-1.8 6 0s4 1.8 6 0 4-1.8 6 0M12 16V8M12 8C10.5 5.5 7.5 5 6 6.5M12 8c1.5-2.5 4.5-3 6-1.5M12 8c0-2 1-3.5 2.5-4.5",
    "coastal": "M3 8c2-1.8 4-1.8 6 0s4 1.8 6 0 4-1.8 6 0M3 13c2-1.8 4-1.8 6 0s4 1.8 6 0 4-1.8 6 0M3 18c2-1.8 4-1.8 6 0s4 1.8 6 0 4-1.8 6 0",
    "": "M3 13l18-7-7 18-2.5-8z",
}
PLUS = ('<span class="plus" aria-hidden="true"><svg viewBox="0 0 14 14"><path d="M7 1v12M1 7h12" fill="none" '
        'stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></span>')


def _icon(tag: str) -> str:
    d = ICONS.get(tag.lower(), ICONS[""])
    return (f'<span class="ico" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="{d}" fill="none" stroke="currentColor" '
            'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg></span>')


def _m(cfg, v):
    return f"{cfg.trip.symbol}{v:,.0f}"


def _cut(cfg) -> str:
    t = cfg.trip.outbound_arrive_by
    return t.strftime("%-I %p") if t.minute == 0 else f"{t:%H:%M}"


def _delta(cfg, r: DestReport, mult: int = 1) -> str:
    """Colour-coded day-over-day badge."""
    if r.delta is None:
        return '<span class="pill">New</span>'
    if abs(r.delta) < 0.5:
        return '<span class="pill">No change</span>'
    amt = _m(cfg, abs(r.delta) * mult)
    tip = f"vs {r.prev_date:%d %b}, total for {mult}" if mult > 1 else f"vs {r.prev_date:%d %b}"
    if r.delta < 0:
        return f'<span class="pill save num" title="{tip}">−{amt} today</span>'
    return f'<span class="pill up num" title="{tip}">+{amt} today</span>'


def sparkline(history, days=14, w=240, h=40, pad=4) -> str:
    """Area sparkline of the last `days` snapshots; green when lower than at the start, red when higher."""
    vals = [p for _, p in history][-days:]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    pts = [(pad + i * (w - 2 * pad) / (len(vals) - 1), h - pad - (v - lo) / span * (h - 2 * pad))
           for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    diff = vals[-1] - vals[0]
    col = "var(--ink2)" if abs(diff) < 0.5 else ("var(--green)" if diff < 0 else "var(--red)")
    ex, ey = pts[-1]
    label = f"{len(vals)}-day price trend: {vals[0]:.0f} to {vals[-1]:.0f}, low {lo:.0f}, high {hi:.0f}"
    return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" role="img" aria-label="{label}"><title>{label}</title>'
            f'<polygon points="{pad},{h} {line} {w - pad},{h}" fill="{col}" fill-opacity=".1"/>'
            f'<polyline points="{line}" fill="none" stroke="{col}" stroke-width="1.6" stroke-linecap="round" '
            f'stroke-linejoin="round" vector-effect="non-scaling-stroke"/></svg>'), len(vals)


CITY = {"SIN": "Singapore", "NRT": "Tokyo Narita", "HND": "Tokyo Haneda", "KIX": "Osaka Kansai", "OKA": "Okinawa",
        "ICN": "Seoul Incheon", "GMP": "Seoul Gimpo", "CJU": "Jeju", "PUS": "Busan"}
PLANE = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M21.5 12c0 .8-.7 1.5-1.5 1.5h-5.2l-4.3 '
         '6.5H8.4l2.1-6.5H6.2l-1.7 2H3l1-3.5L3 8.5h1.5l1.7 2h4.3L8.4 4h2.1l4.3 6.5H20c.8 0 1.5.7 1.5 1.5z"/></svg>')
CHIP_ICONS = {
    "cal": "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4",
    "moon": "M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z",
    "plane": "M3 13l18-7-7 18-2.5-8z",
    "bag": "M6 8h12v12H6zM9 8V5h6v3M10 12v4M14 12v4",
    "clock": "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7v5l3 2",
}


def _chip(icon, text, cls=""):
    return (f'<span class="chip {cls}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="{CHIP_ICONS[icon]}" fill="none" '
            f'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>{e(text)}</span>')


def _unmet(r: DestReport, cfg) -> tuple[str, str]:
    """(badge, one-line reason) for a destination with no qualifying itinerary."""
    msg = (r.message or "").lower()
    if r.status == "error":
        return "Price check failed", "Today's lookup failed. Try again tomorrow."
    if "landing" in msg or "cut-off" in msg or "lands by" in msg:
        return f"Constraint unmet: arrives > {_cut(cfg)}", f"No direct flight lands by {_cut(cfg)} both ways."
    return "Constraint unmet: no direct flight", "No direct flight on these dates."


def _actions(links: dict) -> str:
    agg = ("Google Flights", "Skyscanner", "Kayak")
    own = [(k, v) for k, v in links.items() if not k.startswith(agg)]
    rest = [(k, v) for k, v in links.items() if k.startswith(agg)]
    if own:
        label, (_, url) = "Book direct", own[0]
        title = f"Opens {own[0][0]}"
    else:
        (name, url), rest = rest[0], rest[1:]
        label, title = "Find flight", f"Opens {name}"
    out = [f'<a class="book" href="{e(url, quote=True)}" target="_blank" rel="noopener" title="{e(title, quote=True)}">'
           f'{label} <span class="arr" aria-hidden="true">→</span></a>']
    for k, v in rest:
        out.append(f'<a class="alt" href="{e(v, quote=True)}" target="_blank" rel="noopener">{e(k.split(" (")[0])}</a>')
    return f'<div class="acts">{"".join(out)}</div>'


def _same(seller: str, airline: str) -> bool:
    a, b = seller.lower().strip(), airline.lower().strip()
    return bool(a) and (a in b or b in a)


def _dur(mins: int) -> str:
    return f"{mins // 60}h {mins % 60:02d}m" if mins else ""


def _route(label: str, leg, cfg) -> str:
    """Airline-style leg: origin ---- plane ---- destination, times underneath."""
    plus = " +1" if leg.arrive_time.date() > leg.depart_time.date() else ""
    dur = " · ".join(x for x in ("Non-stop", _dur(leg.duration_min)) if x)

    def pt(code, time, right=False, chk=""):
        return (f'<div class="pt{" r" if right else ""}"><div class="code">{e(code)}</div>'
                f'<div class="city">{e(CITY.get(code, code))}</div><div class="time num">{time}</div>{chk}</div>')

    chk = f'<div class="chk">✓ &lt; {_cut(cfg)}</div>'
    return (f'<div class="legsw"><div class="legname"><span>{label} · {leg.depart_time:%a %d %b}</span>'
            f'<span>{e(leg.flight_number)}</span></div><div class="route">'
            f'{pt(leg.depart_airport, f"{leg.depart_time:%H:%M}")}'
            f'<div class="path"><div class="ln">{PLANE}</div><div class="dur num">{dur}</div></div>'
            f'{pt(leg.arrive_airport, f"{leg.arrive_time:%H:%M}{plus}", True, chk)}</div></div>')


def _sheet(r: DestReport, cfg) -> str:
    n = max(cfg.trip.pax)
    if not r.best:
        _, why = _unmet(r, cfg)
        return (f'<div class="sheet"><hr><div class="viaNote">{e(why)}</div>'
                f'{_actions(build_links(cfg.trip, r.dest, []))}</div>')
    facts = []
    if r.hist_median is not None:
        facts += [("Typical", _m(cfg, r.hist_median)), ("Lowest", _m(cfg, min(r.hist_min, r.price)))]
    facts += [("All-in / pax", _m(cfg, r.trip_cost)), ("Value", f"{r.value_score:.1f}")]
    fh = "".join(f'<div><b class="num">{e(v)}</b>{e(k)}</div>' for k, v in facts)
    groups: dict[tuple, list] = {}
    for q in r.options:                                   # one block per itinerary, its sellers listed inside
        groups.setdefault((q.outbound.flight_number, q.inbound.flight_number), []).append(q)
    opts = []
    for qs in groups.values():
        q = qs[0]                                         # cheapest seller for this itinerary
        bag = "Bag included" if q.bag_included else f"Incl. {_m(cfg, q.bag_fee_per_pax)} bag (est.)"
        named = [x for x in qs if x.seller and x.seller != "Google Flights"]
        direct = next((x for x in named if _same(x.seller, x.airline) and x.booking_url), None)
        links = dict(q.links)
        if direct:                                        # the airline's own deep link beats its home page
            links = {q.outbound.airline: direct.booking_url,
                     **{k: v for k, v in links.items() if k.startswith(("Google Flights", "Skyscanner", "Kayak"))}}
        sellers = ""
        if named:
            rows = "".join(
                f'<span>{e(x.seller)}</span><span class="sp num">{_m(cfg, x.total_per_pax)}</span>'
                + (f'<a class="alt" href="{e(x.booking_url, quote=True)}" target="_blank" rel="noopener">Book</a>'
                   if x.booking_url else "<span></span>") for x in named)
            sellers = f'<div class="legname"><span>Sellers · per pax</span></div><div class="sellers">{rows}</div>'
        opts.append(
            f'<div class="opt"><div class="hd"><span class="who">{avatar(q.outbound.airline, q.outbound.flight_number, "lg")}'
            f'<span><b>{e(q.airline)}</b><br><span class="fl">{e(bag)}</span></span></span>'
            f'<span class="num">{_m(cfg, q.total_per_pax)} <small>/ pax</small><br>'
            f'<small>{_m(cfg, q.total_per_pax * n)} for {n}</small></span></div>'
            f'{_route("Outbound", q.outbound, cfg)}{_route("Return", q.inbound, cfg)}{sellers}{_actions(links)}</div>')
    return f'<div class="sheet"><hr><div class="facts">{fh}</div><div class="opts">{"".join(opts)}</div></div>'


def _card(r: DestReport, cfg, i: int) -> str:
    n = max(cfg.trip.pax)
    sub = r.dest.airport_label + (" · via Osaka" if r.dest.code == "KIX" else "")
    ident = (f'<span class="id">{_icon(r.dest.tag)}<span><span class="name">{e(r.dest.name)}</span><br>'
             f'<span class="where">{e(sub)}</span></span>{PLUS}</span>')
    badges = [f'<span class="pill">{e(" · ".join(x for x in (r.dest.country, r.dest.tag) if x))}</span>']
    if r.best:
        if r.is_cheapest:
            badges.append('<span class="pill solid">Cheapest</span>')
        if r.value_rank == 1:
            badges.append('<span class="pill solid">Best value</span>')
        if r.dest.primary:
            badges.append('<span class="pill solid">Primary pick</span>')
        if r.deal:
            badges.append(f'<span class="pill save" title="{e(r.deal_reason, quote=True)}">'
                          f'{"Great price" if r.deal == "great" else "Good deal"}</span>')
        q = r.best
        spark = sparkline(r.history)
        trend = (f'<span class="trend">{spark[0]}<span class="lab">{spark[1]}d</span>{_delta(cfg, r)}</span>'
                 if spark else f'<span class="trend">{_delta(cfg, r)}</span>')
        more = len({(x.outbound.flight_number, x.inbound.flight_number) for x in r.options}) - 1
        body = (f'<span class="pills">{"".join(badges)}</span>'
                f'<span><span class="tot num">{_m(cfg, r.price)}</span><span class="unit">/ pax</span><br>'
                f'<span class="per num">Total: {_m(cfg, r.price * n)} for {n}</span></span>{trend}'
                f'<span class="via">{avatar(q.outbound.airline, q.outbound.flight_number)}<span><b>{e(q.airline)}</b></span>'
                f'<span class="t num">{e(q.outbound.flight_number)}' + (f" · +{more} more" if more else "") + '</span></span>')
    else:
        label, why = _unmet(r, cfg)
        if r.dest.primary:
            badges.append('<span class="pill solid">Primary pick</span>')
        badges.append(f'<span class="pill unmet" title="{e(why, quote=True)}">{e(label)}</span>')
        body = (f'<span class="pills">{"".join(badges)}</span><span><span class="tot">No fare</span></span>')
    cls = "d glass" + ("" if r.best else " na")
    return (f'<article class="{cls}" style="view-transition-name:card{i}"><button class="head" type="button" '
            f'aria-expanded="false" aria-controls="s{i}">{ident}{body}</button>'
            f'<div class="reveal" id="s{i}"><div>{_sheet(r, cfg)}</div></div></article>')


def _spot(label, city, big, cap, save=False) -> str:
    return (f'<div class="s glass{" save" if save else ""}"><div class="eyebrow">{e(label)}</div>'
            f'<div class="city">{e(city)}</div><div class="big num">{big}</div><div class="cap num">{cap}</div></div>')


def _content(rep: DailyReport | None, cfg: Config) -> str:
    t, n = cfg.trip, max(cfg.trip.pax)
    live = rep is not None
    now = datetime.fromisoformat(rep.fetched_at) if live and rep.fetched_at else None
    chips = [_chip("cal", f"{t.depart_date:%d}–{t.return_date:%d %b %Y}"), _chip("moon", f"{t.nights} Nights"),
             _chip("plane", "Direct Only"), _chip("bag", "Checked Bag Included"), _chip("clock", f"Lands < {_cut(cfg)}")]
    countries = list(dict.fromkeys(d.country for d in cfg.destinations))
    where = " & ".join([", ".join(countries[:-1]), countries[-1]]) if len(countries) > 1 else countries[0]
    icon = lambda d: (f'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="{d}" fill="none" stroke="currentColor" '
                      'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    P = [f'<header class="bar"><h1>Flight Tracker</h1>'
         f'<span class="status"><span class="dot{"" if live else " idle"}"></span><span id="stamp">'
         + (f"Live · Updated {now:%d %b, %H:%M}" if now else "No live fares yet") + '</span></span>'
         f'<span class="tools"><button class="rbtn" id="refresh" type="button">'
         f'{icon("M20 12a8 8 0 1 1-2.6-5.9M20 4v5h-5")}Refresh Fares</button>'
         f'<button class="tbtn" id="theme" type="button" aria-pressed="false" aria-label="Switch to dark mode">'
         f'<span style="display:contents">{icon("M12 4V2M12 22v-2M4 12H2M22 12h-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M5.6 18.4l-1.4 1.4M19.8 4.2l-1.4 1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z").replace("<svg", "<svg class=\"sun\"")}</span>'
         f'<span style="display:contents">{icon("M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z").replace("<svg", "<svg class=\"moon\"")}</span>'
         f'</button></span></header>',
         f'<div class="ov glass"><div class="ovr"><div class="pt"><div class="ovc">{t.origin}</div>'
         f'<div class="city">{e(CITY.get(t.origin, t.origin))}</div></div>'
         f'<div class="path"><div class="ln">{PLANE}</div></div>'
         f'<div class="pt r"><div class="ovc">{len(cfg.destinations)} Destinations</div>'
         f'<div class="city">{e(where)}</div></div></div>'
         f'<div class="chips">{"".join(chips)}</div></div>']
    if not live:
        P.append('<div class="empty glass"><h2>No live fares yet</h2><p>Connect a fare source, then run the tracker. '
                 'Prices appear here after the first fetch.</p></div>')
        return f'<div class="wrap" data-generated="">{"".join(P)}</div><script>{JS}</script>'

    if rep.priced:
        S = []
        v, c = rep.by_value[0], rep.cheapest
        unit = '<span class="unit">/ pax</span>'
        S.append(_spot("Best value", v.dest.name, f"{_m(cfg, v.price)}{unit}", f"{_m(cfg, v.price * n)} for {n}"))
        S.append(_spot("Lowest price", c.dest.name, f"{_m(cfg, c.price)}{unit}",
                       f"{_m(cfg, c.price * n)} for {n} · {e(c.best.airline)}"))
        drops = [r for r in rep.priced if r.delta is not None and r.delta < -0.5]
        if drops:
            m = min(drops, key=lambda r: r.delta)
            S.append(_spot("Biggest drop", m.dest.name, f"−{_m(cfg, -m.delta)}{unit}",
                           f"−{_m(cfg, -m.delta * n)} for {n} · vs. yesterday", save=True))
        else:
            S.append(_spot("Biggest drop", "None today", "—", "No fare fell"))
        P.append(f'<div class="spot">{"".join(S)}</div>')

    cards = "".join(_card(r, cfg, i) for i, r in enumerate(rep.rows))
    P.append('<section><div class="sech"><h2>Destinations</h2><span>Tap a card for flights</span></div>'
             f'<div class="grid">{cards}</div></section>')

    if rep.priced:
        top = max(r.value_score for r in rep.priced)
        bars = "".join(
            f'<span class="n">{e(r.dest.name)}</span><span class="track"><i style="width:{r.value_score / top * 100:.0f}%">'
            f'</i></span><span class="num">{r.value_score:.1f}</span>'
            f'<span class="v num">{_m(cfg, r.trip_cost)} all-in</span>' for r in rep.by_value)
        P.append('<section><div class="sech"><h2>Value ranking</h2><span>Experience ÷ all-in cost per pax</span></div>'
                 f'<div class="rank glass"><div class="bars">{bars}</div></div></section>')

    cov = coverage([q for r in rep.rows for q in r.options])
    chips = "".join(f'<span class="chip {"on" if ok else "off"}">{"✓ " if ok else ""}{e(name)}</span>'
                    for name, ok in cov.items())
    P.append('<section><div class="sech"><h2>Sources</h2><span>✓ priced or operating in today\'s fares</span></div>'
             f'<div class="chips">{chips}</div></section>')

    P.append("<footer>Per adult, round trip, one checked bag. Budget-airline bag fees are estimates. "
             "Confirm the price when booking.</footer>")
    return (f'<div class="wrap" data-generated="{rep.fetched_at}">{"".join(P)}</div>'
            f'<script>{JS}</script>')


def render_fragment(rep: DailyReport | None, cfg: Config) -> str:
    """Page without the document skeleton (for hosts that wrap it themselves)."""
    return (f"<title>{cfg.trip.origin} Flight Tracker</title>\n"
            '<meta name="claude:viewport-fit-sides" content="cover">\n'
            f"{FONTS}\n<style>{CSS}</style>\n{_content(rep, cfg)}")


def render_dashboard(rep: DailyReport | None, cfg: Config) -> str:
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'>"
            f"<title>{cfg.trip.origin} Flight Tracker</title>{FONTS}<style>{CSS}</style></head>"
            f"<body>{_content(rep, cfg)}</body></html>")
