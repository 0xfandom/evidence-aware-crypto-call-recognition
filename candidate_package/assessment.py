"""Standalone synthetic assessment contract and scorer. Python standard library only.

Never imports candidate code, calls a provider, loads a model or repairs a result.
Valid references establish source location, not semantic correctness.
"""
import argparse
from collections import Counter,defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys

VERSION='synthetic-buy-assessment-v1'
LABELS=('BUY','NO_NEW_BUY','UNCLEAR')
THRESHOLD=.75


def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def fingerprint(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def text_hash(text):return hashlib.sha256(text.encode()).hexdigest()
def utf16_length(text):return len(text.encode('utf-16-le'))//2


def source_spans(source,case_id,role):
    text=source['text'];bounds={(0,len(text))};cursor=0
    for line in text.splitlines(keepends=True):
        if line.strip():bounds.add((cursor,cursor+len(line)))
        cursor+=len(line)
    return [dict(evidence_id='ev_'+fingerprint([VERSION,case_id,role,source['source_id'],source['author_id'],source['published_at_utc'],source['capture_scope'],text_hash(text),utf16_length(text[:a]),utf16_length(text[:b])])[:24],
                 source_id=source['source_id'],start_utf16=utf16_length(text[:a]),end_utf16=utf16_length(text[:b]))
            for a,b in sorted(bounds) if b>a]


def catalogue(case):
    return [span for i,s in enumerate([case['primary'],*case['context']])
            for span in source_spans(s,case['case_id'],'PRIMARY' if i==0 else 'RETAINED_CONTEXT')]


def timestamp(value):
    if not isinstance(value,str) or not value.endswith('Z'):raise ValueError('UTC timestamp required')
    return datetime.fromisoformat(value[:-1]+'+00:00')


def input_errors(case):
    errors=[]
    try:
        if set(case)!={'case_id','synthetic','available_at_utc','primary','context','unavailable_context','asset_identity_evidence','evidence_catalogue'}:
            errors.append('INPUT_FIELDS')
        if case.get('synthetic') is not True:errors.append('NOT_SYNTHETIC')
        if not re.fullmatch(r'(dev|eval)-[0-9a-f]{10}',case['case_id']):errors.append('CASE_ID')
        cutoff=timestamp(case['available_at_utc'])
        sources=[case['primary'],*case['context']]
        ids=[s['source_id'] for s in sources]
        if len(ids)!=len(set(ids)):errors.append('DUPLICATE_SOURCE_ID')
        primary_time=None
        for i,s in enumerate(sources):
            if set(s)!={'source_id','author_id','published_at_utc','text','text_sha256','capture_scope'}:errors.append('SOURCE_FIELDS')
            if not isinstance(s['source_id'],str) or not s['source_id'].startswith('sim_post_'):errors.append('SOURCE_ID')
            if not isinstance(s['author_id'],str) or not re.fullmatch(r'sim_author_[0-9a-f]{12}',s['author_id']):errors.append('MISSING_AUTHOR_ID')
            if not isinstance(s['text'],str) or not s['text']:errors.append('EMPTY_SOURCE_TEXT')
            if s['text_sha256']!=text_hash(s['text']):errors.append('TEXT_HASH_MISMATCH')
            if s['capture_scope'] not in ('FULL_TEXT','FRAGMENT'):errors.append('CAPTURE_SCOPE')
            try:
                t=timestamp(s['published_at_utc'])
                if i==0:primary_time=t
                elif primary_time and t>primary_time:errors.append('FUTURE_CONTEXT')
                if t>cutoff:errors.append('AFTER_INPUT_CUTOFF')
            except (ValueError,TypeError):errors.append('MISSING_OR_INVALID_TIMESTAMP')
        if not isinstance(case['asset_identity_evidence'],list) or case['asset_identity_evidence']:
            errors.append('UNEXPECTED_EXTERNAL_ASSET_EVIDENCE')
        if any(set(m)!={'kind','reference'} or m['kind'] not in ('IMAGE','VIDEO','REPLY_PARENT','LINKED_PAGE','MISSING_PREFIX')
               or not isinstance(m['reference'],str) for m in case['unavailable_context']):errors.append('UNAVAILABLE_CONTEXT_FIELDS')
        if case['evidence_catalogue']!=catalogue(case):errors.append('EVIDENCE_CATALOGUE_MISMATCH')
    except (KeyError,TypeError,ValueError,AttributeError,UnicodeError):
        errors.append('MALFORMED_INPUT')
    return sorted(set(errors))


def referenced_text(case,ref):
    source=next(s for s in [case['primary'],*case['context']] if s['source_id']==ref['source_id'])
    return source['text'].encode('utf-16-le')[2*ref['start_utf16']:2*ref['end_utf16']].decode('utf-16-le')


def output_errors(case,prediction):
    errors=[]
    if not isinstance(prediction,dict):return ['OUTPUT_OBJECT_REQUIRED']
    if prediction.get('case_id')!=case['case_id']:errors.append('CASE_BINDING')
    status=prediction.get('status')
    if status in ('INPUT_INVALID','CAPACITY_LIMIT'):
        if set(prediction)!={'case_id','status','error_codes','explanation'}:errors.append('NON_OK_FIELDS')
        if not isinstance(prediction.get('error_codes'),list) or not prediction['error_codes'] or any(not isinstance(x,str) or not x for x in prediction['error_codes']):errors.append('ERROR_CODES')
        if not isinstance(prediction.get('explanation'),str) or not prediction['explanation'].strip():errors.append('EXPLANATION')
        return sorted(set(errors))
    if status!='OK':return ['OUTPUT_STATUS']
    if input_errors(case):return sorted(set(errors+['INPUT_INVALID_MUST_NOT_CLASSIFY']))
    expected={'case_id','status','label','confidence','current_buys','evidence_ids','explanation','limitations','execution_verified'}
    if set(prediction)!=expected:errors.append('OK_FIELDS')
    if prediction.get('label') not in LABELS:errors.append('LABEL')
    confidence=prediction.get('confidence')
    if type(confidence) not in (float,int) or not 0<=confidence<=1:errors.append('CONFIDENCE')
    if prediction.get('execution_verified') is not False:errors.append('EXECUTION_NOT_VERIFIED')
    if not isinstance(prediction.get('explanation'),str) or not prediction['explanation'].strip() or len(prediction['explanation'])>3000:errors.append('EXPLANATION')
    limits=prediction.get('limitations')
    if not isinstance(limits,list) or len(limits)>12 or any(not isinstance(x,str) or not x.strip() for x in limits):errors.append('LIMITATIONS')
    elif prediction.get('label')=='UNCLEAR' and not limits:errors.append('UNCLEAR_REQUIRES_LIMITATION')
    refs={r['evidence_id']:r for r in case.get('evidence_catalogue',[])}
    evidence=prediction.get('evidence_ids')
    if not isinstance(evidence,list) or not evidence or len(evidence)>32 or any(not isinstance(x,str) for x in evidence):
        errors.append('EVIDENCE_IDS');evidence=[]
    if len(evidence)!=len(set(evidence)):errors.append('DUPLICATE_EVIDENCE')
    if set(evidence)-refs.keys():errors.append('UNKNOWN_EVIDENCE_ID')
    primary_id=case['primary']['source_id']
    if not any(refs[x]['source_id']==primary_id for x in evidence if x in refs):errors.append('PRIMARY_EVIDENCE_REQUIRED')
    buys=prediction.get('current_buys')
    if not isinstance(buys,list) or len(buys)>16:errors.append('CURRENT_BUYS');buys=[]
    if (prediction.get('label')=='BUY')!=bool(buys):errors.append('LABEL_ASSET_CONTRADICTION')
    seen=set();asset_spans=[]
    for buy in buys:
        if not isinstance(buy,dict) or set(buy)!={'asset_mention','evidence_ids'}:
            errors.append('BUY_FIELDS');continue
        asset=buy['asset_mention'];ids=buy['evidence_ids']
        if not isinstance(asset,str) or not re.fullmatch(r'\$[A-Z][A-Z0-9]{2,11}',asset) or asset in seen:errors.append('DUPLICATE_OR_INVALID_ASSET')
        if not isinstance(asset,str):continue
        seen.add(asset)
        if not isinstance(ids,list) or not ids or any(not isinstance(x,str) for x in ids):errors.append('BUY_EVIDENCE');continue
        if len(ids)!=len(set(ids)):errors.append('DUPLICATE_BUY_EVIDENCE')
        if set(ids)-set(evidence):errors.append('BUY_EVIDENCE_NOT_DECLARED')
        selected=[refs[x] for x in ids if x in refs]
        spans=[r for r in selected if r['source_id']==primary_id]
        if not spans:errors.append('BUY_PRIMARY_INTENT_REQUIRED')
        try:
            if not any(asset in referenced_text(case,r) for r in selected):errors.append('ASSET_NOT_IN_CITED_SOURCE')
        except (UnicodeError,KeyError):errors.append('EVIDENCE_BOUNDARY')
        asset_spans.append(spans)
    if len(buys)>1:
        for i,left in enumerate(asset_spans):
            for right in asset_spans[i+1:]:
                if any(max(a['start_utf16'],b['start_utf16'])<min(a['end_utf16'],b['end_utf16']) for a in left for b in right):
                    errors.append('MULTI_ASSET_SHARED_PRIMARY_SPAN')
    return sorted(set(errors))


def jsonl(path):
    result=[]
    for n,line in enumerate(Path(path).read_text().splitlines(),1):
        if not line.strip():continue
        def unique_fields(pairs):
            result={}
            for k,v in pairs:
                if k in result:raise ValueError('Duplicate JSON field')
                result[k]=v
            return result
        try:
            value=json.loads(line,object_pairs_hook=unique_fields,parse_constant=lambda s:(_ for _ in ()).throw(ValueError(s)))
            if not isinstance(value,dict):raise ValueError('JSON object required')
            result.append(value)
        except (ValueError,json.JSONDecodeError) as e:raise ValueError(f'{path}: invalid JSON on line {n}') from e
    ids=[r.get('case_id') for r in result]
    if None in ids or len(ids)!=len(set(ids)):raise ValueError('Missing or duplicate case IDs')
    return result


def covered(required,selected):
    return any(r['source_id']==required['source_id'] and r['start_utf16']<=required['start_utf16'] and r['end_utf16']>=required['end_utf16'] for r in selected)


def score(inputs,references,predictions):
    im={r['case_id']:r for r in inputs};rm={r['case_id']:r for r in references};pm={r['case_id']:r for r in predictions}
    if len(im)!=len(inputs) or len(rm)!=len(references) or len(pm)!=len(predictions):raise ValueError('Duplicate case IDs')
    if set(im)!=set(rm):raise ValueError('Reference/input membership differs')
    if set(pm)-set(im):raise ValueError('Unexpected prediction case IDs')
    matrix_raw=defaultdict(Counter);matrix_gated=defaultdict(Counter);rows=[]
    for cid,case in im.items():
        ref=rm[cid]
        if ref['input_sha256']!=fingerprint(case):raise ValueError('Reference bound to different input')
        observed_errors=input_errors(case)
        if ref['expected_status']=='INPUT_INVALID':
            if not observed_errors or not set(ref['expected_errors'])<=set(observed_errors):raise ValueError('Broken negative-integrity fixture')
        elif observed_errors:raise ValueError('Invalid reference input')
        p=pm.get(cid);errors=output_errors(case,p) if p is not None else ['MISSING_PREDICTION']
        raw=(p.get('label') if isinstance(p,dict) and p.get('status')=='OK' and p.get('label') in LABELS else None)
        gated=raw if p and not errors and p['status']=='OK' and p['confidence']>=THRESHOLD else None
        reason=('MISSING' if p is None else 'INVALID_OUTPUT' if errors else p['status'] if p['status']!='OK' else 'LOW_CONFIDENCE_ABSTAIN' if gated is None else gated)
        raw_buys=p.get('current_buys') if isinstance(p,dict) else None
        row=dict(case_id=cid,expected_status=ref['expected_status'],reference_label=ref.get('label'),raw_proposed_label=raw,
                 accepted_label=gated,output_errors=errors,outcome=reason,technical_output_valid=not errors,
                 reference_assets=ref.get('buy_assets',[]),predicted_assets=[a.get('asset_mention') for a in raw_buys if isinstance(a,dict) and isinstance(a.get('asset_mention'),str)] if isinstance(raw_buys,list) else [],
                 support_span_coverage=False,explanation_review='MANUAL_REVIEW_REQUIRED_NOT_AUTOMATICALLY_GRADED',
                 reference_reason=ref.get('reference_reason'),boundary_tags=ref.get('boundary_tags',[]),
                 submitted_explanation=p.get('explanation') if isinstance(p,dict) else None)
        if ref['expected_status']=='OK':
            matrix_raw[ref['label']][raw or reason]+=1
            matrix_gated[ref['label']][gated or reason]+=1
            if p and not errors and p['status']=='OK':
                cat={e['evidence_id']:e for e in case['evidence_catalogue']}
                row['support_span_coverage']=all(covered(r,[cat[x] for x in p['evidence_ids']]) for r in ref['required_support'])
                for asset,requirements in ref.get('buy_support',{}).items():
                    entry=next((a for a in p['current_buys'] if a['asset_mention']==asset),None)
                    if not entry or not all(covered(r,[cat[x] for x in entry['evidence_ids']]) for r in requirements):row['support_span_coverage']=False
        else:
            row['input_guard_correct']=bool(p and not errors and p['status']=='INPUT_INVALID' and set(ref['expected_errors'])&set(p['error_codes']))
        rows.append(row)
    semantic=[r for r in rows if r['expected_status']=='OK'];positive=[r for r in semantic if r['reference_label']=='BUY']
    def metrics(key):
        tp=sum(r[key]=='BUY' for r in positive)
        fp=sum(r[key]=='BUY' for r in semantic if r['reference_label']!='BUY')
        return dict(TP=tp,FP=fp,missed_reference_BUY_including_abstentions=len(positive)-tp,
                    decided_false_negative=sum(r[key]=='NO_NEW_BUY' for r in positive),
                    unclear_on_reference_BUY=sum(r[key]=='UNCLEAR' for r in positive),
                    false_BUY_on_NO_NEW_BUY=sum(r[key]=='BUY' for r in semantic if r['reference_label']=='NO_NEW_BUY'),
                    false_BUY_on_UNCLEAR=sum(r[key]=='BUY' for r in semantic if r['reference_label']=='UNCLEAR'),
                    precision=tp/(tp+fp) if tp+fp else None,recall_all_reference_BUY=tp/len(positive) if positive else None,
                    label_correct=sum(r[key]==r['reference_label'] for r in semantic),semantic_reference_count=len(semantic),
                    label_accuracy_all_reference_cases=sum(r[key]==r['reference_label'] for r in semantic)/len(semantic) if semantic else None)
    return dict(version=VERSION,threshold=THRESHOLD,inputs=len(inputs),predictions=len(predictions),
                raw_proposals_UNACCEPTED_DIAGNOSTIC=metrics('raw_proposed_label'),accepted_at_075=metrics('accepted_label'),
                raw_confusion={k:dict(v) for k,v in matrix_raw.items()},accepted_confusion={k:dict(v) for k,v in matrix_gated.items()},
                technical=dict(invalid_outputs=sum(bool(r['output_errors']) for r in rows if r['outcome']!='MISSING'),
                               missing=sum(r['outcome']=='MISSING' for r in rows),capacity_limits=sum(r['outcome']=='CAPACITY_LIMIT' for r in rows),
                               integrity_controls=sum(r['expected_status']=='INPUT_INVALID' for r in rows),
                               correct_integrity_rejections=sum(r.get('input_guard_correct',False) for r in rows),
                               incorrect_input_rejections_on_valid_sources=sum(r['outcome']=='INPUT_INVALID' for r in semantic)),
                asset_attribution=dict(reference_BUY_cases=len(positive),
                    exact_sets_on_reference_BUY=sum(r['technical_output_valid'] and r['outcome'] in LABELS and set(r['reference_assets'])==set(r['predicted_assets']) for r in positive),
                    extra_buy_assets=sum(len(set(r['predicted_assets'])-set(r['reference_assets'])) for r in semantic),
                    missed_buy_assets=sum(len(set(r['reference_assets'])-set(r['predicted_assets'])) for r in positive)),
                support_span_coverage_cases=sum(r['support_span_coverage'] for r in semantic),
                limitations=['Synthetic policy-authored references; no independently human-adjudicated gold labels.',
                             'Raw label proposals with invalid evidence never count as accepted classifications.',
                             'Span coverage and valid references do not establish truthful explanations or semantic completeness.',
                             'No general accuracy, ranking, hiring PASS, model evaluation or production readiness follows from harness self-tests.'],rows=rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['validate-inputs','validate-outputs','score'])
    parser.add_argument('--inputs',required=True);parser.add_argument('--predictions');parser.add_argument('--references');parser.add_argument('--report')
    args=parser.parse_args();inputs=jsonl(args.inputs)
    if args.command=='validate-inputs':
        result=[dict(case_id=c['case_id'],errors=input_errors(c)) for c in inputs]
        print(json.dumps(result,indent=2));return 2 if any(r['errors'] for r in result) else 0
    if not args.predictions:parser.error('--predictions required')
    predictions=jsonl(args.predictions)
    if args.command=='score':
        if not args.references:parser.error('--references required')
        result=score(inputs,jsonl(args.references),predictions)
    else:
        pm={p['case_id']:p for p in predictions};im={i['case_id']:i for i in inputs}
        if set(pm)-im.keys():raise ValueError('Unexpected prediction IDs')
        result=[dict(case_id=c['case_id'],errors=output_errors(c,pm[c['case_id']]) if c['case_id'] in pm else ['MISSING_PREDICTION']) for c in inputs]
    data=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.report:Path(args.report).write_text(data)
    else:print(data)
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,OSError,KeyError,TypeError) as e:
        print('Assessment error: '+str(e),file=sys.stderr);sys.exit(2)
