"""Compose report model from capabilities/facts/rules; no Word concerns."""
import argparse, json
from pathlib import Path

def compose(preflight, capabilities, facts, rules):
    available = {c["capability_id"] for c in capabilities if c["status"] == "AVAILABLE"}
    blocks = [{"type":"document_title","text":"经营分析报告"}, {"type":"section_heading","text":"数据覆盖与分析能力"}]
    blocks.append({"type":"body","text":f"观察期：{preflight.get('discoveries',[{}])[0].get('date_range',{})}. 当前可用事实 {len(facts)} 条；趋势/环比能力按完整周期条件启用。"})
    for dimension, title in (("channel","渠道当前周期事实"),("category","品类当前周期事实")):
        if not any(c in available for c in (f"{dimension}_revenue_summary", f"{dimension}_cost_summary")):
            continue
        blocks.append({"type":"section_heading","text":title})
        rows = [f for f in facts if f["dimension"] == dimension and f["capability_id"].endswith(("summary","rank","share"))]
        for f in rows[:20]: blocks.append({"type":"body","text":f"{f['entity']}：{f['metric']}={f['value']:.2f}（{f['period']}）"})
    if rules.get("results"):
        blocks.append({"type":"section_heading","text":"规则与跨周期判断"})
        for r in rules["results"]:
            if r.get("hit") is True: blocks.append({"type":"finding_heading","text":f"{r.get('rule_id')}｜{r.get('rule_name')}"})
    else:
        blocks.append({"type":"section_heading","text":"跨周期分析边界"})
        blocks.append({"type":"body","text":"当前没有可用的规则结果；本报告保留当前周期描述性事实，不生成无数据支持的环比或连续趋势结论。"})
    return {"schema_version":"1.0","blocks":blocks,"facts_count":len(facts)}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--preflight',type=Path,required=True); ap.add_argument('--capabilities',type=Path,required=True); ap.add_argument('--facts',type=Path,required=True); ap.add_argument('--rules',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args()
    model=compose(json.loads(a.preflight.read_text(encoding='utf-8')), json.loads(a.capabilities.read_text(encoding='utf-8'))['capabilities'], json.loads(a.facts.read_text(encoding='utf-8'))['facts'], json.loads(a.rules.read_text(encoding='utf-8')))
    a.output.write_text(json.dumps(model,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__': main()
