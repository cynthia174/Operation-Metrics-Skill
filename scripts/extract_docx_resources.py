"""Extract OLE preview images from the reference Feishu DOCX in object order."""
import argparse, json, re, zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image
from io import BytesIO

ROOT = Path(__file__).resolve().parents[1]
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--input-docx',required=True); ap.add_argument('--output-dir',required=True); args=ap.parse_args()
    reference=Path(args.input_docx); assets=Path(args.output_dir); assets.mkdir(parents=True,exist_ok=True); entries=[]
    with zipfile.ZipFile(reference) as z:
        rels=ET.fromstring(z.read('word/_rels/document.xml.rels'))
        relmap={x.attrib['Id']:x.attrib['Target'] for x in rels}
        doc=z.read('word/document.xml').decode('utf-8')
        objects=re.findall(r'<w:object>(.*?)</w:object>', doc, re.S)
        for i, frag in enumerate(objects, 1):
            ids=re.findall(r'(?:r:id|r:embed)="([^"]+)"', frag)
            media=next((relmap[x] for x in ids if relmap.get(x,'').startswith('media/')), None)
            emb=next((relmap[x] for x in ids if relmap.get(x,'').startswith('embeddings/')), None)
            dims=re.search(r'width:([^;]+);height:([^;]+)', frag)
            if not media:
                raise RuntimeError(f'MISSING_IMAGE_RESOURCE embedded_excel_{i:02d}: no preview relationship')
            src='word/'+media
            if src not in z.namelist():
                raise RuntimeError(f'MISSING_IMAGE_RESOURCE embedded_excel_{i:02d}: {src}')
            name=f'embedded_excel_{i:02d}.png'; Image.open(BytesIO(z.read(src))).convert('RGB').save(assets/name, 'PNG')
            xlsx_path = None
            if emb and ('word/'+emb) in z.namelist():
                xlsx_name = f'embedded_excel_{i:02d}.xlsx'
                (assets/xlsx_name).write_bytes(z.read('word/'+emb))
                xlsx_path = str(Path(args.output_dir)/xlsx_name)
            entries.append({'source':f'embedded_excel_{i:02d}', 'path':str(assets/name), 'xlsx_path':xlsx_path, 'reference_media':src, 'embedded_object':('word/'+emb if emb else None), 'width_pt':float(dims.group(1).replace('pt','')) if dims else None, 'height_pt':float(dims.group(2).replace('pt','')) if dims else None})
    out=assets/'resource_map.json'; out.write_text(json.dumps({'resources':entries},ensure_ascii=False,indent=2),encoding='utf-8'); print(out)

if __name__=='__main__': main()
