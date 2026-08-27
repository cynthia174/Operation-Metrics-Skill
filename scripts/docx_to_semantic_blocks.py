"""Extract content from a target DOCX without reading any reference report."""
import argparse, json, re
from pathlib import Path
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

STYLE_ROLE_MAP = {
    'feishu document title':'document_title', 'feishu section heading':'section_heading',
    'feishu module heading':'module_heading', 'feishu finding heading':'finding_heading',
    'feishu body':'body', 'feishu list':'list_item', 'feishu image caption':'image_caption',
    'title':'document_title', 'heading 1':'section_heading', 'heading 2':'module_heading',
    'heading 3':'finding_heading', 'normal':'body',
}

def role_for(p, index, title_seen):
    if index == 0 and p.text.strip() and not title_seen: return 'document_title'
    style = (p.style.name if p.style is not None else '').strip().lower()
    if style in STYLE_ROLE_MAP: return STYLE_ROLE_MAP[style]
    if p._p.pPr is not None and p._p.pPr.numPr is not None: return 'list_item'
    return 'body'

def runs_for(p):
    out=[]
    for r in p.runs:
        item={'text':r.text}
        if r.font.name == 'Consolas' or re.search(r'[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9*]+)+', r.text): item['type']='inline_code'
        out.append(item)
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--input-docx',required=True); ap.add_argument('--output',required=True); args=ap.parse_args()
    doc=Document(args.input_docx); blocks=[]; title_seen=False
    title_seen=False
    body = doc.element.body
    ordered = (Paragraph(child, doc) if child.tag.endswith('}p') else Table(child, doc) for child in body.iterchildren() if child.tag.endswith('}p') or child.tag.endswith('}tbl'))
    for i,item in enumerate(ordered):
        if isinstance(item, Table):
            blocks.append({'type':'table','rows':[[cell.text for cell in row.cells] for row in item.rows]})
            continue
        p=item
        text=p.text.strip()
        if not text and not p._p.xpath('.//w:drawing'): continue
        role=role_for(p,i,title_seen)
        if role=='document_title': title_seen=True
        blocks.append({'type':role,'runs':runs_for(p)} if len(p.runs)>1 else {'type':role,'text':p.text})
    Path(args.output).parent.mkdir(parents=True,exist_ok=True); Path(args.output).write_text(json.dumps({'blocks':blocks},ensure_ascii=False,indent=2),encoding='utf-8')
    print(args.output)
if __name__=='__main__': main()
