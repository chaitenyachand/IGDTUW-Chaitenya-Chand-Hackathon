from lib import *
import random
H=250
# ---------- P1 NLP pipeline ----------
s=Svg(660,H)
w,h=180,76
pos={1:(10,40),2:(240,40),3:(470,40),4:(470,160),5:(240,160),6:(10,160)}
tone={1:"gray",2:"crim",3:"crim",4:"crim",5:"crim"}
ti={1:"Headline in",2:"Relevance gate",3:"Event classifier",4:"FinBERT sentiment",5:"Integrity score"}
ln={1:["GDELT · RSS · SEC 8-K","social, public only"],2:["MiniLM + LR + rules","AUC 0.78 (rules 0.56)"],3:["8 classes","rules override ML"],4:["zero-shot FinBERT","score −1 … +1"],5:["corroboration","source trust, flags"]}
for k,(x,y) in pos.items():
    if k==6:
        s.rect(x,y,w,h,fill=INK,stroke="none",rx=10,extra='filter="url(#sh)"')
        s.text(x+16,y+30,"Signal 0–10",16,"#fff",700); s.text(x+16,y+50,"impact + provenance",13,"#C9CEDA"); s.text(x+16,y+68,"persisted · streamed",13,"#C9CEDA")
    else: s.box(x,y,w,h,ti[k],ln[k],tone[k],tsize=16,lsize=13)
    s.badge(x+w-6,y,k,r=11)
cy1=40+38; cy2=160+38
s.arrow(f"M{10+w},{cy1} H240"); s.arrow(f"M{240+w},{cy1} H470"); s.arrow(f"M{470+w/2},{40+h} V160"); s.arrow(f"M470,{cy2} H{240+w}"); s.arrow(f"M240,{cy2} H{10+w}")
s.arrow(f"M{240+w/2},40 V26",AMBER,2,dash="5 4")
s.rect(240+10,0,160,26,fill=TINT["amber"],stroke="none",rx=13); s.text(240+w/2,18,"✕ noise dropped",13,AMBER,700,"middle")
s.save("p1.svg")
# ---------- P2 PRECEDENT ----------
s=Svg(660,H)
for i,(t,l,tn) in enumerate([("New signal",["embedding + event type","timestamp t₀"],"crim"),("Analog search",["cosine similarity","only events before t₀"],"teal"),("Forward paths",["SPY + sector returns","day 0 … +20"],"teal")]):
    x=10+i*225; s.box(x,0,190,66,t,l,tn,tsize=15.5,lsize=12.5)
    if i<2: s.arrow(f"M{x+190},33 H{x+225}")
cx,cy,cw_,ch=10,82,400,168
s.rect(cx,cy,cw_,ch,fill="#fff",stroke=LINE,rx=10,extra='filter="url(#sh)"')
ox,oy=cx+40,cy+ch-28; pw,ph=cw_-76,ch-64
s.add(f'<line x1="{ox}" y1="{oy-ph/2}" x2="{ox+pw}" y2="{oy-ph/2}" stroke="{LINE}" stroke-dasharray="4 4"/>')
rnd=random.Random(5)
def path(drift,vol):
    v=0; pts=[]
    for d in range(21): v+=drift+rnd.gauss(0,vol); pts.append(v)
    return pts
paths=[path(-0.12,0.4) for _ in range(14)]
med=[sorted(p[d] for p in paths)[7] for d in range(21)]
lo=[sorted(p[d] for p in paths)[2] for d in range(21)]; hi=[sorted(p[d] for p in paths)[11] for d in range(21)]
sx=lambda d:ox+pw*d/20; sy=lambda v:oy-ph/2-v*ph/7
band=" ".join(f"{sx(d)},{sy(hi[d])}" for d in range(21))+" "+" ".join(f"{sx(d)},{sy(lo[d])}" for d in range(20,-1,-1))
s.add(f'<polygon points="{band}" fill="{CRIM}" opacity="0.13"/>')
for p in paths: s.add(f'<polyline points="{" ".join(f"{sx(d)},{sy(p[d])}" for d in range(21))}" fill="none" stroke="#9AA1B2" stroke-width="1" opacity="0.7"/>')
s.add(f'<polyline points="{" ".join(f"{sx(d)},{sy(med[d])}" for d in range(21))}" fill="none" stroke="{CRIM}" stroke-width="3"/>')
s.add(f'<line x1="{ox}" y1="{oy-ph}" x2="{ox}" y2="{oy}" stroke="{INK}" stroke-width="1.5"/>')
for d in (0,5,10,15,20): s.text(sx(d),oy+18,f"+{d}d" if d else "t₀",12.5,MUTE,500,"middle")
s.text(cx+14,cy+22,"Analog fan chart (schematic)",13.5,INK,700)
s.text(cx+cw_-14,cy+22,"— median   ▬ P10–P90",12.5,CRIM,700,"end")
for i,(t,l,tn) in enumerate([("Low-n shrinkage",["w = n/(n+5), flagged"],"amber"),("Percentile → 1–10",["rank vs all events"],"crim"),("Shock vector",["→ Stress Lab"],"ink")]):
    y=82+i*60; s.box(430,y,220,48,t,l,tn,lsize=12.5,tsize=15)
    if i<2: s.arrow(f"M540,{y+48} V{y+60}")
s.arrow(f"M410,{cy+ch/2} H430")
s.save("p2.svg")
# ---------- P3 Stress Lab ----------
s=Svg(660,H)
s.box(10,16,160,76,"Scenario library",["8 historical events","PRECEDENT-based"],"teal",lsize=13,tsize=15.5)
s.box(10,150,160,76,"Manual sliders",["6 market factors","you set the shock"],"gray",lsize=13,tsize=15.5)
s.rect(215,0,200,250,fill=TINT["crim"],stroke="none",rx=14)
s.text(231,24,"FULL REVALUATION",12.5,CRIM,800,ls=1.4)
for i,(t,l) in enumerate([("Equity","beta · sector, ΔP/P"),("Bonds & loans","duration · spread"),("Derivatives","delta-style repricing"),("Aggregate","before · after · Δ")]):
    y=38+i*52; s.box(227,y,176,44,t,[l],"crim",tsize=14,lsize=12.5,bar=False)
s.arrow("M170,54 C192,54 195,100 213,110"); s.arrow("M170,188 C192,188 195,150 213,140")
for i,(t,l,tn) in enumerate([("VaR / ES","historical · before vs after","blue"),("Shapley attribution","factor · sector · country","blue"),("Reverse stress","worst-shock solver","amber"),("Trigger rules → alerts","cooldown · watchlist","teal")]):
    y=i*66; s.box(470,y,180,52,t,[l],tn,tsize=14,lsize=12.5)
    s.arrow(f"M415,125 C440,125 445,{y+26} 468,{y+26}")
s.save("p3.svg")
# ---------- P4 Adaptive index + audit ----------
s=Svg(660,H)
for i,(t,l,tn) in enumerate([("Issuer signal",["decayed z-score"],"teal"),("Tilt",["w = bench·e^(κz)"],"teal"),("Constraints",["cap 15% · floor 2%"],"teal"),("Turnover",["deadband · ≤ 5%"],"teal")]):
    x=10+i*168; s.box(x,0,136,52,t,l,tn,tsize=14.5,lsize=12.5)
    if i<3: s.arrow(f"M{x+136},26 H{x+168}")
s.arrow("M578,52 V82 H410")
s.rect(150,66,260,32,fill=TINT["amber"],stroke="none",rx=16); s.text(280,87,"Rebalance mode",14,AMBER,800,"middle")
s.arrow("M150,82 H100 V108"); s.arrow("M410,82 H480 V108") if False else s.add("")
s.arrow("M410,82 H500 V108") if False else None
s.arrow("M150,82 H100 V108")
s.add(f'<path d="M578,82" />')
s.box(10,108,180,42,"Auto-apply",["within limits"],"teal",tsize=14,lsize=12,bar=False) if False else s.box(10,108,180,42,"Auto-apply · in limits",[],"teal",tsize=14,bar=False)
s.box(390,108,260,42,"PM approval · approve / reject",[],"amber",tsize=14,bar=False)
s.arrow("M410,82 H520 V108")
s.arrow("M100,150 V172"); s.arrow("M520,150 V172")
for i,lab in enumerate(["entry n−2","entry n−1","entry n"]):
    x=10+i*225
    s.rect(x,172,185,78,fill="#fff",stroke=INK,sw=1.6,rx=10,extra='filter="url(#sh)"')
    s.text(x+14,196,lab,14,INK,800); s.text(x+14,215,"action · actor · timestamp",12,MUTE)
    s.text(x+14,238,["hash 2c8127c…","hash 5bed687…","SHA256(entry‖prev)"][i],12,CRIM if i==2 else MUTE,600,family="DejaVu Sans Mono")
    if i<2: s.arrow(f"M{x+225},212 H{x+185}",CRIM,2.2); s.text(x+205,203,"prev",11.5,CRIM,700,"middle")
s.save("p4.svg")
