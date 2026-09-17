"""Automatic, professional local Word report for each organization session."""
from datetime import datetime
import getpass
from pathlib import Path
import platform
import uuid
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


def human_size(size):
    for unit in ['B','KB','MB','GB','TB']:
        if size<1024 or unit=='TB':return f'{size:.1f} {unit}'
        size/=1024


def table(document, headers, rows, widths):
    grid=document.add_table(rows=1,cols=len(headers))
    grid.autofit=False
    for cell,width in zip(grid.columns,widths):cell.width=Inches(width)
    borders=OxmlElement('w:tblBorders')
    for edge in ['top','left','bottom','right','insideH','insideV']:
        element=OxmlElement('w:'+edge);element.set(qn('w:val'),'single');element.set(qn('w:sz'),'4');element.set(qn('w:color'),'D9D9D9');borders.append(element)
    grid._tbl.tblPr.append(borders)
    repeat=OxmlElement('w:tblHeader');grid.rows[0]._tr.get_or_add_trPr().append(repeat)
    values=[headers]+list(rows)
    for i,row_values in enumerate(values):
        row=grid.rows[0] if i==0 else grid.add_row()
        for cell,width,value in zip(row.cells,widths,row_values):
            cell.width=Inches(width);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            properties=cell._tc.get_or_add_tcPr()
            shading=OxmlElement('w:shd');shading.set(qn('w:fill'),'E7EDF3' if i==0 else 'F7F9FA' if i%2==0 else 'FFFFFF');properties.append(shading)
            margins=OxmlElement('w:tcMar')
            for edge in ['top','left','bottom','right']:
                margin=OxmlElement('w:'+edge);margin.set(qn('w:w'),'100');margin.set(qn('w:type'),'dxa');margins.append(margin)
            properties.append(margins)
            p=cell.paragraphs[0];p.paragraph_format.space_after=Pt(3);p.paragraph_format.space_before=Pt(3)
            p.paragraph_format.line_spacing=1.1
            p.add_run(str(value)).font.size=Pt(9)
            if i==0:p.runs[0].bold=True
    document.add_paragraph().paragraph_format.space_after=Pt(2)
    return grid


def generate(session, output_dir):
    document=Document()
    section=document.sections[0];section.orientation=WD_ORIENT.LANDSCAPE
    section.page_width=Inches(11.7);section.page_height=Inches(8.3)
    section.top_margin=section.bottom_margin=Inches(.6)
    section.left_margin=section.right_margin=Inches(.65)
    for name in ['Normal','Title','Subtitle','Heading 1','Heading 2']:
        style=document.styles[name];style.font.name='Calibri';style.font.color.rgb=RGBColor(0,0,0)
    for border in document.styles.element.xpath('.//w:pBdr'):
        border.getparent().remove(border)
    document.styles['Normal'].font.size=Pt(10)
    document.styles['Normal'].paragraph_format.space_after=Pt(7)
    document.styles['Title'].font.size=Pt(27)
    document.styles['Heading 1'].font.size=Pt(17)
    document.core_properties.title='Smart File Organizer Organization Report'
    document.core_properties.author='Smart File Organizer'
    document.add_paragraph('SMART FILE ORGANIZER',style='Title')
    document.add_paragraph('Organization Report',style='Subtitle')
    date=datetime.fromisoformat(session['created']).astimezone().strftime('%d %B %Y at %H:%M')
    document.add_paragraph(f'Date: {date}    Computer: {platform.node()}    User: {getpass.getuser()}')
    document.add_paragraph(f"This session organized {session['organized']} files and renamed {session['renamed']} files through safe organization actions. No files were permanently deleted. Cleanup candidates are suggested for review; their usefulness has not been determined.")
    document.add_heading('Session summary',level=1)
    summary=[('Files scanned',session['scanned']),('Files organized',session['organized']),('Files renamed',session['renamed']),('Folders created',session['folders_created']),('Files unchanged',session['unchanged']),('Files requiring review',session['needs_review']),('Cleanup candidates',len(session['cleanup'])),('Potential cleanup size',human_size(session['cleanup_size']))]
    if session.get('v2'):
        summary += [('Eligible personal files',session.get('eligible',0)),('Protected files found',session.get('protected',0)),('Projects protected',session.get('projects',0)),('Errors',len(session['failures']))]
    half=len(summary)//2
    summary_rows=[(*summary[i],*summary[i+half]) for i in range(half)]
    table(document,['Measure','Result','Measure','Result'],summary_rows,[3.1,2.1,3.1,2.1])
    document.add_heading('Folders scanned',level=1)
    for folder in session['folders'][:8]:document.add_paragraph(folder)
    if len(session['folders'])>8:document.add_paragraph(f"Additional scan roots: {len(session['folders'])-8}. Complete roots appear in the detailed local appendix.")
    document.add_page_break()
    document.add_heading('Organized files detailed appendix' if session.get('v2') else 'Organized files',level=1)
    if session['files']:
        rows=[(f['original'],f['name'],str(Path(f['source']).parent),str(Path(f['destination']).parent),f['category'].strip('/'),f.get('action','MOVE'),f['reason']) for f in session['files'][:1000]]
        table(document,['Original File','New Name','Original Location','New Location','Classification','Action','Reason'],rows,[1.2,1.2,1.6,1.7,1.1,1.1,2.5])
    else:document.add_paragraph('No files were moved in this session. Review the operation results below before retrying.')
    if session['cleanup']:
        document.add_page_break()
    document.add_heading('Cleanup suggestions',level=1)
    document.add_paragraph('Suggested for review only. No candidate is declared safe to delete. Potential cleanup size describes candidate bytes, not space already recovered.')
    if session['cleanup']:
        rows=[(c['file'],str(Path(c['source']).parent),c.get('review_location','Not moved'),c['reason'],human_size(c['size']),c['risk']) for c in session['cleanup'][:1000]]
        table(document,['File','Original Location','Review Location','Reason','Size','Evidence'],rows,[1.2,1.8,1.8,2.7,.7,2.2])
    else:document.add_paragraph('No cleanup candidates were identified in this scan.')
    if session['failures']:
        document.add_heading('Changes requiring review',level=1)
        for failure in session['failures']:document.add_paragraph(failure['file']+': '+failure['error'])
    if session.get('v2'):
        document.add_heading('Safety and exclusions',level=1)
        document.add_paragraph(f"No personal files were permanently deleted. {session.get('projects',0)} projects were protected. {session.get('needs_review',0)} files were left unchanged due to uncertainty or retained organization. Protected directory counts are subtree counts, not a claim to have counted files inside skipped trees.")
        for item in session.get('protected_directories',[])[:20]:document.add_paragraph(item['path']+'  -  '+item['kind'])
        document.add_paragraph('The complete session appendix is saved beside this report as a JSON file, including every change, cleanup destination, excluded directory, scan root and error. The Word tables show up to 1000 records per section to keep the report manageable.')
    document.add_paragraph('Undo is available in History when organized bytes remain unchanged and original locations are free. This report records the organization session; later restorations are tracked in application history.')
    footer=section.footer.paragraphs[0];footer.add_run('Smart File Organizer  |  Local organization report  |  ')
    field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)
    output=Path(output_dir);output.mkdir(parents=True,exist_ok=True)
    name='Smart_File_Organizer_Report_'+datetime.now().strftime('%Y-%m-%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]+'.docx'
    path=output/name
    with path.open('xb') as file:document.save(file)
    if session.get('v2'):
        import json
        with path.with_suffix('.json').open('x',encoding='utf-8') as appendix:json.dump(session,appendix,ensure_ascii=False,indent=2)
    return path
