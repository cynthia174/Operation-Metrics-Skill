import hashlib, json, zipfile
from pathlib import Path
import shutil

def fact_qa(stage, root):
    src=root/'outputs/runtime/rule_results.json'; out=root/'outputs/runtime/fact_qa.json'
    data=json.loads(src.read_text(encoding='utf-8'))
    ok=isinstance(data.get('results'),list) and all('evidence' in x and 'hit' in x for x in data['results'])
    out.write_text(json.dumps({'all_pass':ok,'result':'PASS' if ok else 'FAIL'},indent=2),encoding='utf-8'); return ok

def semantic(stage, root):
    raise RuntimeError('semantic adapter is retired; AssembleReport owns semantic_blocks.json')

def ooxml(stage, root):
    docx=root/'outputs/runtime/report.docx'; out=root/'outputs/runtime/ooxml_qa.json'
    with zipfile.ZipFile(docx) as z: ok=all(x in z.namelist() for x in ('word/document.xml','word/styles.xml','word/numbering.xml'))
    out.write_text(json.dumps({'all_pass':ok,'result':'PASS' if ok else 'FAIL'},indent=2),encoding='utf-8'); return ok

def artifact_lineage_qa(stage, root):
    runtime = root/'outputs/runtime'; manifest_path = runtime/'run_manifest.json'; manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    expected = [runtime/'preflight.json', runtime/'channel_metrics.csv', runtime/'category_metrics.csv', runtime/'rule_results.csv', runtime/'rule_results.json', runtime/'fact_qa.json', runtime/'semantic_blocks.json', runtime/'report.docx', runtime/'ooxml_qa.json']
    checks = {p.name: p.is_file() for p in expected}; rules = json.loads((runtime/'rule_results.json').read_text(encoding='utf-8')); blocks = json.loads((runtime/'semantic_blocks.json').read_text(encoding='utf-8'))
    report = '\n'.join(p.text for p in __import__('docx').Document(runtime/'report.docx').paragraphs)
    checks['report_matches_current_rules'] = '2025-08' not in report and '2025-10' not in report and 'R9 已命中' not in report and (not rules.get('results') or all(r.get('rule_id') in report for r in rules['results'] if r.get('hit') is True))
    checks['semantic_blocks_current_run'] = blocks.get('run_id') == manifest.get('run_id') and blocks.get('source_rule_results') == str(runtime/'rule_results.json')
    manifest['outputs'] = {p.name: {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in expected}; manifest['lineage_checks'] = checks; manifest['status'] = 'PASS' if all(checks.values()) else 'FAIL'; manifest['all_pass'] = all(checks.values())
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (runtime/'artifact_lineage_qa.json').write_text(json.dumps({'all_pass': all(checks.values()), 'checks': checks}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return all(checks.values())
