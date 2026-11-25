#!/usr/bin/env python3
"""Build the A0 portrait hybrid poster from the repository's saved CSV reports.

Run: python poster/generate_poster.py
Requires reportlab. Writes poster/output/pdf/poster_hybrid.pdf.
The original editable LaTeX poster is preserved alongside this new version.
"""
import csv
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'poster/output/pdf/poster_hybrid.pdf'
REPO = 'https://github.com/dloweieu2025-create/amazon-locker-capacity-optimization'
W, H = 841*mm, 1189*mm
NAVY, BLUE = '#071F45', '#2446A6'
PALE, GRAY, INK, MUTED = '#EAF0FA', '#F4F6F9', '#202C40', '#59677D'
ORANGE, RED, GREEN = '#FF9900', '#CC6259', '#E9F3F1'


def read(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def fonts():
    candidates = [
        (Path('C:/Windows/Fonts/arial.ttf'), Path('C:/Windows/Fonts/arialbd.ttf')),
        (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
         Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')),
    ]
    for normal, bold in candidates:
        if normal.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont('Body', str(normal)))
            pdfmetrics.registerFont(TTFont('Body-Bold', str(bold)))
            pdfmetrics.registerFontFamily('Body', normal='Body', bold='Body-Bold',
                                          italic='Body', boldItalic='Body-Bold')
            return
    raise RuntimeError('Install Arial or DejaVu Sans to build the poster.')


fonts()
OUT.parent.mkdir(parents=True, exist_ok=True)
c = canvas.Canvas(str(OUT), pagesize=(W,H), pageCompression=1)
c.setTitle('Optimizing Amazon Locker Capacity')
c.setAuthor('Optimization I | IE University')
c.setSubject('Demand forecasts, dwell probabilities, and integer capacity reservation')


def rect(x,y,w,h,fill,stroke=None,r=0):
    c.setFillColor(colors.HexColor(fill))
    c.setStrokeColor(colors.HexColor(stroke or fill))
    if r:
        c.roundRect(x*mm,H-(y+h)*mm,w*mm,h*mm,r*mm,fill=1,stroke=int(stroke is not None))
    else:
        c.rect(x*mm,H-(y+h)*mm,w*mm,h*mm,fill=1,stroke=int(stroke is not None))


def line(x1,y1,x2,y2,color=MUTED,width=1):
    c.setStrokeColor(colors.HexColor(color)); c.setLineWidth(width)
    c.line(x1*mm,H-y1*mm,x2*mm,H-y2*mm)


def txt(x,y,value,size=26,color=INK,bold=False):
    c.setFillColor(colors.HexColor(color)); c.setFont('Body-Bold' if bold else 'Body',size)
    c.drawString(x*mm,H-y*mm,value)


def para(x,y,w,value,size=26,color=INK,bold=False,leading=None,maxh=None):
    style=ParagraphStyle('p',fontName='Body-Bold' if bold else 'Body',fontSize=size,
                         leading=leading or size*1.22,textColor=colors.HexColor(color))
    p=Paragraph(value,style); _,height=p.wrap(w*mm,H)
    if maxh is not None and height>maxh*mm:
        raise ValueError(f'Text exceeds allocated height: {value[:70]} ({height/mm:.1f} > {maxh}mm)')
    p.drawOn(c,x*mm,H-y*mm-height)
    return height/mm


def section(x,y,n,title,w=389):
    rect(x,y,w,16,BLUE)
    txt(x+6,y+11.4,f'{n}.  {title}',34,'#FFFFFF',True)


def arrow(x,y,w=10):
    line(x,y,x+w,y,BLUE,2)
    line(x+w-3,y-2,x+w,y,BLUE,2); line(x+w-3,y+2,x+w,y,BLUE,2)


def qrcode(x,y,size):
    widget=qr.QrCodeWidget(REPO,barLevel='M')
    a,b,d,e=widget.getBounds(); scale=size*mm/(d-a)
    drawing=Drawing(size*mm,size*mm,transform=[scale,0,0,scale,0,0]); drawing.add(widget)
    renderPDF.draw(drawing,c,x*mm,H-(y+size)*mm)
    c.linkURL(REPO,(x*mm,H-(y+size)*mm,(x+size)*mm,H-y*mm),relative=0)


# Header: same navy, blue, white and orange visual identity as the LaTeX project.
rect(0,0,841,175,NAVY)
txt(24,27,'IE UNIVERSITY',31,'#FFFFFF',True)
txt(24,43,'OPTIMIZATION I  /  SHIP-OPTION CAPACITY RESERVATION',23,'#DCE8F8')
txt(24,82,'Optimizing Amazon',94,'#FFFFFF',True)
txt(24,119,'Locker Capacity',94,'#FFFFFF',True)
para(24,135,680,'An integer programming approach using demand forecasts<br/>and package dwell-time probabilities',31,'#FFFFFF',maxh=31)
rect(735,17,82,82,'#FFFFFF'); qrcode(738,20,76)
txt(739,110,'CODE + DATA',23,'#FFFFFF',True)
rect(0,175,841,2,ORANGE)

# Overview and four large KPI cards.
txt(24,198,'THE DECISION',28,BLUE,True)
para(24,207,790,'Requests arrive today, but packages occupy slots for several days. The optimizer chooses what to accept across the week, maximizing throughput while keeping expected occupancy within capacity.',29,maxh=42)
summary=read(ROOT/'reports/base/locker_summary.csv')
demand=sum(float(r['demand']) for r in summary)
accepted=sum(int(r['accepted']) for r in summary)
assert demand==909 and accepted==803
for x,value,label,detail in [(24,'4','LOCKERS','46 slots each in the base case'),
                            (226,'7 days','HORIZON','A single synthetic planning week'),
                            (428,'909','REQUESTS','Two-Day + Standard demand'),
                            (630,'88.3%','BASE ACCEPTANCE','803 accepted / 106 rejected')]:
    rect(x,261,187,54,PALE)
    txt(x+7,275,label,22,BLUE,True)
    txt(x+7,295,value,49,NAVY,True)
    txt(x+7,308,detail,21,MUTED)

# Left column 1: a visual statement of the capacity problem.
x=24
section(x,330,'1','The capacity problem')
for bx,title,body in [(x,'Demand arrives','Two-Day + Standard'),(x+134,'Packages remain','Occupancy carries over'),(x+268,'Slots fill up','Future arrivals compete')]:
    rect(bx,357,121,49,PALE)
    para(bx+5,363,112,title,28,NAVY,True,maxh=23)
    para(bx+5,389,112,body,22,MUTED,maxh=13)
arrow(x+122,381,10); arrow(x+256,381,10)
txt(x+2,425,'FIRST-COME-FIRST-SERVED',23,BLUE,True)
txt(x+203,425,'OPTIMIZED RESERVATION',23,BLUE,True)
para(x+2,432,181,'Long stays can block later requests.',26,maxh=32)
para(x+203,432,184,'Use demand and dwell time to protect future capacity.',26,maxh=35)

# Left column 2: compact input cards, exact dwell probabilities, line chart.
section(x,483,'2','Model inputs')
for bx,title,body in [(x,'locker.csv','Capacity C: 46 slots per locker'),(x+199,'demand.csv','Demand d: locker, day, option')]:
    rect(bx,509,190,45,PALE)
    txt(bx+6,524,title,28,BLUE,True)
    txt(bx+6,543,body,24)
txt(x+2,575,'occupancy.csv',28,BLUE,True)
txt(x+2,589,'q: probability a package still occupies a slot',23,MUTED)
rows=read(ROOT/'data/occupancy.csv')
for xx,label in [(x+3,'Age'),(x+44,'Two-Day'),(x+113,'Standard')]: txt(xx,610,label,23,NAVY,True)
for i,row in enumerate(rows):
    yy=625+i*16
    for xx,val in [(x+6,row['days_since_arrival']),(x+52,f"{100*float(row['two_day']):g}%"),(x+124,f"{100*float(row['standard']):g}%")]: txt(xx,yy,val,25)
    line(x,yy+5,x+177,yy+5,'#D8DEE8',.7)
# Small dwell line chart with directly labeled series.
cx,cy,cw,ch=x+214,618,164,61
for v in [0,50,100]:
    yy=cy+ch-v/100*ch; line(cx,yy,cx+cw,yy,'#D8DEE8',.7); txt(cx-18,yy+2,str(v),19,MUTED)
for field,color in [('standard',ORANGE),('two_day',BLUE)]:
    points=[(cx+int(r['days_since_arrival'])/3*cw,cy+ch-float(r[field])*ch) for r in rows]
    for p1,p2 in zip(points,points[1:]): line(*p1,*p2,color,3)
    for px,py in points:
        c.setFillColor(colors.HexColor(color)); c.circle(px*mm,H-py*mm,1.6*mm,fill=1,stroke=0)
for i in range(4): txt(cx+i/3*cw-2,691,str(i),20,MUTED)
txt(cx,604,'Two-Day',22,BLUE,True); txt(cx+81,604,'Standard',22,'#A75A00',True)
txt(cx+28,704,'Days since arrival',21,MUTED)

# Left column 3: compact mathematics, with explicit meaning and carryover timeline.
section(x,732,'3','Optimization model')
para(x+2,757,385,'<b>y<sub>lst</sub></b> = nonnegative integer packages accepted<br/>at locker <b>l</b>, for option <b>s</b>, on day <b>t</b>.',27,maxh=30)
para(x+2,792,385,'<b>Maximize  ∑<sub>l,s,t</sub> y<sub>lst</sub></b>',34,NAVY,maxh=19)
txt(x+2,819,'Accept as many packages as possible.',24,MUTED)
para(x+2,830,385,'<b>0 ≤ y<sub>lst</sub> ≤ d<sub>lst</sub></b>  for every locker, option and day.',28,maxh=16)
txt(x+2,854,'Acceptance cannot exceed forecast demand.',24,MUTED)
para(x+2,866,385,'<b>∑<sub>s</sub> ∑<sub>v≤t</sub> q<sub>s,t−v</sub> y<sub>lsv</sub> ≤ C<sub>l</sub></b>  for every locker and day.',29,maxh=20)
txt(x+2,891,'Earlier arrivals also consume today’s capacity.',24,MUTED)
rect(x,902,389,35,PALE)
txt(x+6,916,'Standard arrival cohort',22,BLUE,True)
txt(x+6,930,'Day v: 100%    →    Day v+1: 70%    →    Day v+2: 25%',24,NAVY)

# Left assumptions: concise, visibly separate.
rect(x,961,389,142,GRAY)
txt(x+6,978,'ASSUMPTIONS',29,BLUE,True)
para(x+7,990,185,'• Lockers start empty.<br/>• One package, one slot.<br/>• No compartment sizes.<br/>• Deliveries before pickups.',25,leading=34,maxh=91)
para(x+204,990,177,'• Same dwell probabilities at all lockers.<br/>• Capacity in expectation.<br/>• No penalty for occupancy after day 7.',25,leading=34,maxh=106)

# Right column 4: data flow diagram and validation.
x=428
section(x,330,'4','How the program works')
for bx,label in [(x,'locker.csv'),(x+132,'demand.csv'),(x+264,'occupancy.csv')]:
    rect(bx,357,125,26,PALE); txt(bx+5,374,label,25,BLUE,True)
line(x+194,386,x+194,396,BLUE,2)
rect(x+49,399,291,31,ORANGE)
txt(x+65,419,'Validate  →  Pyomo ILP  →  HiGHS',28,NAVY,True)
para(x+2,440,385,'<b>Outputs:</b> acceptance decisions, expected capacity reservations and scenario reports.',25,maxh=29)
para(x+2,469,385,'<b>Checks:</b> complete locker/day pairs; positive capacity; matching options; valid, nonincreasing probabilities; 100% on arrival.',22,MUTED,maxh=24)

# Right column 5: dominant scenario comparison and representative occupancy.
section(x,503,'5','Results: capacity + pickup speed')
txt(x+1,533,'Same 909 requests in every scenario',25,MUTED)
rect(x+1,541,6,5,BLUE); txt(x+11,546,'Accepted',22)
rect(x+78,541,6,5,RED); txt(x+88,546,'Rejected',22)
cases=[('23 slots','capacity_23'),('46 slots · base','base'),('69 slots','capacity_69'),('Pickup +1 day','slower_pickups')]
for i,(label,folder) in enumerate(cases):
    data=read(ROOT/f'reports/{folder}/locker_summary.csv')
    a=sum(int(r['accepted']) for r in data); rej=round(sum(float(r['rejected']) for r in data))
    assert a+rej==909
    yy=563+i*35
    txt(x+1,yy+14,label,24,NAVY,folder=='base')
    bx,bw=x+112,238
    rect(bx,yy,bw*a/909,21,BLUE)
    if rej: rect(bx+bw*a/909,yy,bw*rej/909,21,RED)
    txt(bx+4,yy+14,str(a),26,'#FFFFFF',True)
    if rej: txt(bx+bw*a/909+4,yy+14,str(rej),25,'#FFFFFF',True)
    txt(x+354,yy+14,f'{a/909:.1%}',22,NAVY,True)
rect(x,710,389,34,PALE)
para(x+6,716,376,'<b>106 rejected</b> at 46 slots. A one-day pickup delay cuts acceptance from <b>88.3% to 61.3%</b> (−246 packages).',26,NAVY,maxh=26)
txt(x+2,760,'Hopkins · baseline expected occupancy',25,NAVY,True)
ox,oy,ow,oh=x+28,778,347,43
for level in [0,23,46]:
    yy=oy+oh-level/46*oh
    line(ox,yy,ox+ow,yy,'#D8DEE8',.6); txt(x+2,yy+2,str(level),19,MUTED)
line(ox,oy,ox+ow,oy,RED,1.5)
occ=sorted((int(r['day']),float(r['expected_occupancy'])) for r in read(ROOT/'reports/base/daily_occupancy.csv') if r['locker_id']=='hopkins')
points=[(ox+(day-1)/6*ow,oy+oh-value/46*oh) for day,value in occ]
for p1,p2 in zip(points,points[1:]): line(*p1,*p2,BLUE,2.5)
for day,(px,py) in enumerate(points,1):
    c.setFillColor(colors.HexColor(BLUE)); c.circle(px*mm,H-py*mm,1.3*mm,fill=1,stroke=0)
    txt(px-2,833,str(day),19,MUTED)
txt(x+231,772,'46-slot capacity',20,RED)
txt(x+122,845,'Planning day (1–7)',20,MUTED)

# The repository has no dashboard: label the intended explorer honestly.
section(x,861,'6','Interactive explorer: next step')
para(x+2,885,385,'<b>Proposed controls:</b> locker, day, capacity (23–69), pickup delay and ship option.',25,maxh=28)
para(x+2,915,385,'<b>Live outputs:</b> accepted / rejected, occupancy and unused slots. Scan the header QR for the current code and reproducible scenario runs.',24,maxh=34)

# Three conclusions, with large numbered blue markers.
section(x,963,'7','Conclusions')
for yy,num,title,body in [(989,'1','Capacity matters.','69 slots accept all 909 requests in this scenario.'),
                          (1026,'2','Pickup behavior matters.','One extra day of dwell costs 246 accepted packages.'),
                          (1063,'3','Optimize both together.','Demand and dwell probabilities shape the best plan.')]:
    txt(x+2,yy+13,num,38,BLUE,True)
    para(x+25,yy,360,f'<b>{title}</b> {body}',26,maxh=33)

# Restrained footer: real attribution and a prominent synthetic-data caveat.
rect(0,1121,841,68,GRAY)
para(24,1130,793,'<b>Synthetic scenario:</b> these results describe an assumed seven-day demand instance, not measured Amazon performance.',24,NAVY,maxh=14)
para(24,1149,793,'<b>Model context:</b> Sethuraman et al. (2024), “Amazon Locker Capacity Management,” <i>Manufacturing &amp; Service Operations Management</i>. doi:10.1287/msom.2021.0544.',20,MUTED,maxh=21)
txt(24,1177,'github.com/dloweieu2025-create/amazon-locker-capacity-optimization',20,BLUE)
txt(571,1177,'Visual structure: ICFO / baposter',19,MUTED)
c.linkURL(REPO,(24*mm,7*mm,555*mm,19*mm),relative=0)
c.showPage(); c.save()
print(OUT)

