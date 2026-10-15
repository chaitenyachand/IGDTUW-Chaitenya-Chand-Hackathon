INK="#0B1020"; CRIM="#C8102E"; MUTE="#5B6475"; LINE="#D9DCE3"; PAPER="#FAF9F6"
TEAL="#0F7B6C"; AMBER="#B7791F"; BLUE="#2B4C8C"
TINT={"crim":"#FCEBEE","teal":"#E6F4F1","blue":"#E9EEF8","amber":"#FBF1DE","gray":"#F1F2F5","ink":"#E7E9EF"}
ACC={"crim":CRIM,"teal":TEAL,"blue":BLUE,"amber":AMBER,"gray":MUTE,"ink":INK}
def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
class Svg:
    def __init__(s,w,h,bg=PAPER):
        s.w,s.h=w,h; s.p=[]; s.bg=bg
    def add(s,x): s.p.append(x)
    def rect(s,x,y,w,h,fill="#fff",stroke=LINE,sw=1.5,rx=10,extra=""):
        s.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>')
    def text(s,x,y,t,size=15,fill=INK,weight=400,anchor="start",ls=0,family="Inter"):
        s.add(f'<text x="{x}" y="{y}" font-family="{family}, sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" letter-spacing="{ls}">{esc(t)}</text>')
    def box(s,x,y,w,h,title,lines=(),tone="gray",tsize=16,lsize=14,bar=True,fill="#fff",center=False):
        a=ACC[tone]
        s.rect(x,y,w,h,fill=fill,stroke=LINE,sw=1.4,rx=10,extra='filter="url(#sh)"')
        if bar: s.add(f'<path d="M{x+10},{y} h-0 a10,10 0 0 0 -10,10 v{h-20} a10,10 0 0 0 10,10" fill="none"/>'); s.rect(x,y+10,4,h-20,fill=a,stroke="none",rx=2)
        n=len(lines); th=tsize+ (n*(lsize+5) if n else 0)
        y0=y+(h-th)/2+tsize-2
        tx=x+w/2 if center else x+16
        an="middle" if center else "start"
        s.text(tx,y0,title,tsize,INK,700,an)
        for i,l in enumerate(lines): s.text(tx,y0+(lsize+5)*(i+1)+1,l,lsize,MUTE,400,an)
    def badge(s,cx,cy,n,r=13,fill=CRIM):
        s.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"/>'); s.text(cx,cy+5,str(n),14,"#fff",700,"middle")
    def arrow(s,d,color=INK,sw=2,dash=None,both=False):
        da=f'stroke-dasharray="{dash}"' if dash else ""
        ms='marker-start="url(#ar_s)"' if both else ""
        s.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" {da} marker-end="url(#ar)" {ms} stroke-linejoin="round"/>')
    def pill(s,x,y,w,h,label,tone="crim",size=13):
        s.rect(x,y,w,h,fill=ACC[tone],stroke="none",rx=h/2); s.text(x+w/2,y+h/2+size*0.35,label,size,"#fff",700,"middle",ls=1.2)
    def save(s,path):
        defs=f'''<defs><filter id="sh" x="-5%" y="-5%" width="110%" height="115%"><feDropShadow dx="0" dy="2" stdDeviation="2.5" flood-color="#0B1020" flood-opacity="0.08"/></filter>
<marker id="ar" markerUnits="userSpaceOnUse" markerWidth="11" markerHeight="11" refX="9" refY="5.5" orient="auto"><path d="M0,0 L11,5.5 L0,11 z" fill="{INK}"/></marker>
<marker id="ar_s" markerUnits="userSpaceOnUse" markerWidth="11" markerHeight="11" refX="9" refY="5.5" orient="auto-start-reverse"><path d="M0,0 L11,5.5 L0,11 z" fill="{INK}"/></marker></defs>'''
        open(path,"w").write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-8 -4 {s.w+16} {s.h+12}" width="{s.w+16}" height="{s.h+12}"><rect x="-8" y="-4" width="{s.w+16}" height="{s.h+12}" fill="{s.bg}"/>{defs}{"".join(s.p)}</svg>')
