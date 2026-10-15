from lib import *
W,H=1400,640
s=Svg(W,H)
cw,gap=200,40
X=[i*(cw+gap) for i in range(6)]
heads=[("SOURCES","public data only","gray"),("INGEST & NLP","Python workers","crim"),("PLATFORM","state & audit","blue"),("INTELLIGENCE","analytics engines","teal"),("API","FastAPI","amber"),("TERMINAL","React / TanStack","ink")]
for i,(h1,h2,t) in enumerate(heads):
    s.rect(X[i],0,cw,H-90,fill=TINT[t],stroke="none",rx=14)
    s.text(X[i]+16,28,h1,15,ACC[t],800,ls=1.8); s.text(X[i]+16,47,h2,13,MUTE,500)
bx=lambda i:X[i]+10; bw=cw-20
# col0 sources
src=[("News & GDELT GKG",["headlines, themes"]),("SEC EDGAR",["8-K filings"]),("Social feeds",["Reddit · Bluesky"]),("Yahoo Finance",["prices, ETFs, FX"]),("FRED",["rates, VIX, spreads"])]
sy=[]; y=62
for t,l in src: s.box(bx(0),y,bw,80,t,l,"gray"); sy.append(y+40); y+=92
# col1 NLP
nlp=[("Ingest + dedupe",["point-in-time stamps"]),("Relevance gate",["MiniLM + LR + rules"]),("Event classifier",["8 types, rules override"]),("FinBERT sentiment",["−1 … +1, zero-shot"]),("Integrity score",["corroboration, trust"])]
ny=[]; y=62
for t,l in nlp: s.box(bx(1),y,bw,80,t,l,"crim"); ny.append(y); y+=92
for i in range(4): s.arrow(f"M{X[1]+cw/2},{ny[i]+80} V{ny[i+1]}",CRIM,2)
# col2 platform
s.box(bx(2),62,bw,112,"Redis Streams",["stream:signals","signal · risk · alert"],"blue")
s.box(bx(2),188,bw,112,"Audit ledger",["SHA-256 hash chain","append-only trigger"],"blue")
s.box(bx(2),314,bw,196,"PostgreSQL 16",["documents · signals","prices · portfolio","runs · rebalances","risk index history"],"blue")
# col3 engines
eng=[("PRECEDENT",["analog events + paths"]),("Impact model",["GBM on 8-K CARs"]),("Global Risk Index",["0–100, 3 regimes"]),("Stress Lab",["VaR/ES · Shapley"]),("Adaptive Index",["tilt · caps · turnover"])]
ey=[]; y=62
for t,l in eng: s.box(bx(3),y,bw,80,t,l,"teal"); ey.append(y+40); y+=92
# col4 API
s.box(bx(4),62,bw,236,"REST  /api/*",["envelope {data, meta}","ETag / 304 caching","rate limiting","bearer auth on writes","OpenAPI at /docs"],"amber")
s.box(bx(4),312,bw,148,"WebSocket",["/ws/signals","live push from","the Redis stream"],"amber")
# col5 terminal
pages=["Overview","Signals","PRECEDENT","Stress Lab","Adaptive Index","Exposure","Portfolio","Model","Audit"]
y=62
for p in pages:
    s.rect(bx(5),y,bw,42,fill="#fff",stroke=LINE,sw=1.4,rx=9,extra='filter="url(#sh)"'); s.rect(bx(5),y+9,4,24,fill=INK,stroke="none",rx=2)
    s.text(bx(5)+16,y+27,p,15.5,INK,600); y+=49
# arrows
g=lambda i:(X[i]+cw, X[i+1])
# 1 sources->ingest (first three) converge
x0,x1=g(0)
for k in range(3):
    s.arrow(f"M{x0-10},{sy[k]} C{x0+22},{sy[k]} {x1-14},{ny[0]+40} {x1+10},{ny[0]+40}",MUTE,2)
s.badge((x0+x1)/2,ny[0]+40-26,1)
# market data lane: yahoo, fred -> postgres via bottom lane
lane=H-90-26
for k in (3,4):
    s.arrow(f"M{x0-10},{sy[k]} H{x0+14+(k-3)*10} V{lane}",MUTE,2,dash="5 4") if False else None
s.add(f'<path d="M{x0-10},{sy[3]} H{x0+10} V{lane} H{X[2]+cw/2-30} V{314+196+2}" fill="none" stroke="{MUTE}" stroke-width="2" stroke-dasharray="6 4" marker-end="url(#ar)"/>')
s.add(f'<path d="M{x0-10},{sy[4]} H{x0+10}" fill="none" stroke="{MUTE}" stroke-width="2" stroke-dasharray="6 4"/>')
s.badge(X[1]+cw/2,lane,"1b",r=15,fill=MUTE)
# 2 inside nlp
s.badge(X[1]+cw-14,ny[2]-6,2)
# 3 nlp -> platform
x0,x1=g(1)
s.arrow(f"M{x0-10},{ny[4]+30} C{x0+20},{ny[4]+30} {x1-16},{314+120} {x1+10},{314+120}",CRIM,2.4)
s.arrow(f"M{x0-10},{ny[4]+30} C{x0+30},{ny[4]+30} {x1-30},{62+56} {x1+10},{62+56}",CRIM,2.4)
s.badge((x0+x1)/2,ny[4]+30-24,3)
# 4 platform <-> engines via bus
x0,x1=g(2)
bus=(x0+x1)/2
pm=[62+56,188+56,314+98]
s.add(f'<path d="M{bus},{min(pm+ey)} V{max(pm+ey)}" stroke="{BLUE}" stroke-width="3" stroke-linecap="round"/>')
for y in pm: s.arrow(f"M{x0-10},{y} H{bus}",BLUE,2.2,both=True)
for y in ey: s.arrow(f"M{x1+10},{y} H{bus}",TEAL,2.2,both=True)
s.badge(bus,min(pm+ey)-22,4)
# 5 engines -> API via bus
x0,x1=g(3)
bus=(x0+x1)/2
s.add(f'<path d="M{bus},{ey[0]} V{ey[4]}" stroke="{TEAL}" stroke-width="3" stroke-linecap="round"/>')
for y in ey: s.add(f'<path d="M{x0-10},{y} H{bus}" stroke="{TEAL}" stroke-width="2.2"/>')
s.arrow(f"M{bus},{180} H{x1+10}",TEAL,2.6)
s.arrow(f"M{bus},{386} H{x1+10}",TEAL,2.6,dash="6 4")
s.badge(bus,ey[0]-22,5)
# 6 API -> terminal
x0,x1=g(4)
s.arrow(f"M{x0-10},180 H{x1-2}",AMBER,2.6)
s.arrow(f"M{x0-10},386 H{x1-2}",AMBER,2.6)
s.badge((x0+x1)/2,180-22,6)
# bottom band
s.rect(0,H-72,W,72,fill=INK,stroke="none",rx=14)
s.text(24,H-44,"CROSS-CUTTING",13,"#FF8DA1",800,ls=2)
items=["Provenance tag on every row: live · replay · backfill · synthetic","Point-in-time analogs, no look-ahead","APScheduler jobs","Docker Compose","139 automated tests"]
s.text(24,H-20,"   ·   ".join(items),15.5,"#fff",500)
s.save("architecture.svg")
