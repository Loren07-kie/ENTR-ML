"""Render the academic report to PDF using reportlab (bundled runtime)."""
from pathlib import Path
import re
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Image,Table,TableStyle,KeepTogether
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
ROOT=Path(__file__).resolve().parents[1]
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='BodyTF',fontName='Helvetica',fontSize=9.4,leading=14,spaceAfter=9,textColor=colors.HexColor('#302d40')))
styles.add(ParagraphStyle(name='TitleTF',fontName='Helvetica-Bold',fontSize=25,leading=29,spaceAfter=22,textColor=colors.HexColor('#4c2e87')))
styles.add(ParagraphStyle(name='SectionTF',fontName='Helvetica-Bold',fontSize=14,leading=19,spaceBefore=15,spaceAfter=9,textColor=colors.HexColor('#623fa0'),keepWithNext=True))
def inline(t):
 t=escape(t);t=re.sub(r'\*\*(.*?)\*\*',r'<b>\1</b>',t);t=re.sub(r'`(.*?)`',r'<font name="Courier">\1</font>',t)
 return t
story=[];lines=(ROOT/'docs/Informe_TecnoForms.md').read_text(encoding='utf-8').splitlines();i=0
while i<len(lines):
 line=lines[i].strip();i+=1
 if not line:continue
 if line.startswith('# '):story.append(Paragraph(inline(line[2:]),styles['TitleTF']));continue
 if line.startswith('## '):story.append(Paragraph(inline(line[3:]),styles['SectionTF']));continue
 if line.startswith('!['):
  path=ROOT/'docs'/re.search(r'\((.*?)\)',line).group(1)
  from PIL import Image as PILImage
  w,h=PILImage.open(path).size;ww=475;hh=ww*h/w
  story.append(Image(str(path),width=ww,height=hh));story.append(Spacer(1,12));continue
 if line.startswith('|'):
  rows=[line]
  while i<len(lines) and lines[i].startswith('|'):rows.append(lines[i]);i+=1
  data=[[Paragraph(inline(c.strip()),styles['BodyTF']) for c in r.strip('|').split('|')] for r in rows if not re.fullmatch(r'[| :\-]+',r)]
  widths=[160,315] if len(data[0])==2 else [475/len(data[0])]*len(data[0])
  t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8dff8')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f7f5fa'),colors.white]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),4),('LINEBELOW',(0,0),(-1,0),1,colors.HexColor('#b49ad8'))]));story.append(t);story.append(Spacer(1,12));continue
 paragraph=line
 while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','![')):
  paragraph+=' '+lines[i].strip();i+=1
 story.append(Paragraph(inline(paragraph),styles['BodyTF']))
def footer(canvas,doc):
 canvas.saveState();canvas.setStrokeColor(colors.HexColor('#b49ad8'));canvas.line(60,45,535,45);canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#66606e'));canvas.drawString(60,31,'TECNOFORMS  /  Proyecto académico  /  Noviembre 2026');canvas.drawRightString(535,31,str(doc.page));canvas.restoreState()
doc=SimpleDocTemplate(str(ROOT/'docs/Informe_TecnoForms.pdf'),pagesize=A4,rightMargin=60,leftMargin=60,topMargin=55,bottomMargin=62,title='TecnoForms - Proyecto final',author='TecnoForms')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(doc.filename)
