"""Contract/scorer checks on synthetic development fixtures; NOT model accuracy."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from assessment import (catalogue,fingerprint,input_errors,jsonl,output_errors,
                        referenced_text,score,text_hash,utf16_length)

BASE=Path(__file__).resolve().parent


def covering(case,span):
    choices=[r for r in case['evidence_catalogue'] if r['source_id']==span['source_id']
             and r['start_utf16']<=span['start_utf16'] and r['end_utf16']>=span['end_utf16']]
    return min(choices,key=lambda r:r['end_utf16']-r['start_utf16'])['evidence_id']


def fixture_prediction(case,ref):
    """Uses disclosed labels to test software only. This is NOT a classifier."""
    if ref['expected_status']=='INPUT_INVALID':
        return dict(case_id=case['case_id'],status='INPUT_INVALID',error_codes=input_errors(case),explanation='Synthetic invalid-input control.')
    evidence={covering(case,s) for s in ref['required_support']}
    buys=[]
    for asset,spans in ref['buy_support'].items():
        ids=sorted({covering(case,s)for s in spans});evidence.update(ids)
        buys.append(dict(asset_mention=asset,evidence_ids=ids))
    return dict(case_id=case['case_id'],status='OK',label=ref['label'],confidence=.9,current_buys=buys,
                evidence_ids=sorted(evidence),explanation=ref['reference_reason'],
                limitations=['Synthetic contract fixture; missing interpretation details are in the reference reason.'] if ref['label']=='UNCLEAR' else [],
                execution_verified=False)


class AssessmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs=jsonl(BASE/'development.inputs.jsonl');cls.refs=jsonl(BASE/'development.references.jsonl')
        cls.rm={r['case_id']:r for r in cls.refs}
        cls.pred=[fixture_prediction(c,cls.rm[c['case_id']])for c in cls.inputs]
        cls.positive=next(c for c in cls.inputs if cls.rm[c['case_id']]['label']=='BUY')

    def test_fixture_population(self):
        self.assertEqual(len(self.inputs),24)
        self.assertEqual(sum(bool(input_errors(c))for c in self.inputs),3)
        self.assertEqual(sum(r['label']=='BUY'for r in self.refs),8)

    def test_fixture_roundtrip_contract(self):
        self.assertTrue(all(not output_errors(c,p)for c,p in zip(self.inputs,self.pred)))
        r=score(self.inputs,self.refs,self.pred)
        self.assertEqual(r['accepted_at_075']['label_correct'],21)
        self.assertEqual(r['technical']['correct_integrity_rejections'],3)
        self.assertEqual(r['support_span_coverage_cases'],21)

    def test_source_tamper_rejected(self):
        c=copy.deepcopy(self.positive);c['primary']['text']+=' changed'
        self.assertIn('TEXT_HASH_MISMATCH',input_errors(c))

    def test_missing_author_is_technical(self):
        c=copy.deepcopy(self.positive);c['primary']['author_id']=None
        self.assertIn('MISSING_AUTHOR_ID',input_errors(c))
        self.assertIn('INPUT_INVALID_MUST_NOT_CLASSIFY',output_errors(c,fixture_prediction(self.positive,self.rm[c['case_id']])))

    def test_unknown_and_cross_case_evidence(self):
        c=self.positive;p=fixture_prediction(c,self.rm[c['case_id']]);p['evidence_ids']=['ev_unknown']
        self.assertIn('UNKNOWN_EVIDENCE_ID',output_errors(c,p))

    def test_catalogue_tamper(self):
        c=copy.deepcopy(self.positive);c['evidence_catalogue'][0]['end_utf16']-=1
        self.assertIn('EVIDENCE_CATALOGUE_MISMATCH',input_errors(c))

    def test_exact_unicode_newline_reconstruction(self):
        c=copy.deepcopy(self.positive);t='🧭 A\r\n e\u0301\n\nAn allocation to $VEKRA today.'
        c['primary']['text']=t;c['primary']['text_sha256']=text_hash(t);c['context']=[];c['evidence_catalogue']=catalogue(c)
        self.assertFalse(input_errors(c))
        full=next(r for r in c['evidence_catalogue']if r['start_utf16']==0 and r['end_utf16']==utf16_length(t))
        self.assertEqual(referenced_text(c,full),t)
        self.assertNotEqual(len(t),utf16_length(t))

    def test_future_context_rejected(self):
        c=copy.deepcopy(next(c for c in self.inputs if c['context'] and not input_errors(c)))
        c['context'][0]['published_at_utc']='2035-01-01T00:00:00Z'
        self.assertIn('FUTURE_CONTEXT',input_errors(c))

    def test_context_cannot_supply_own_intent(self):
        c=next(c for c in self.inputs if c['context'] and self.rm[c['case_id']]['label']=='BUY')
        p=fixture_prediction(c,self.rm[c['case_id']])
        context_ids=[r['evidence_id']for r in c['evidence_catalogue']if r['source_id']!=c['primary']['source_id']]
        p['evidence_ids']=context_ids
        for a in p['current_buys']:a['evidence_ids']=context_ids
        self.assertIn('PRIMARY_EVIDENCE_REQUIRED',output_errors(c,p))

    def test_empty_buy_array_is_not_repaired(self):
        c=self.positive;p=fixture_prediction(c,self.rm[c['case_id']]);p['current_buys']=[]
        self.assertIn('LABEL_ASSET_CONTRADICTION',output_errors(c,p))
        self.assertEqual(p['label'],'BUY')

    def test_multi_asset_full_post_not_reused(self):
        c=next(c for c in self.inputs if len(self.rm[c['case_id']]['buy_assets'])>1)
        p=fixture_prediction(c,self.rm[c['case_id']])
        full=next(r['evidence_id']for r in c['evidence_catalogue']if r['source_id']==c['primary']['source_id'] and r['start_utf16']==0 and r['end_utf16']==utf16_length(c['primary']['text']))
        p['evidence_ids']=[full]
        for a in p['current_buys']:a['evidence_ids']=[full]
        self.assertIn('MULTI_ASSET_SHARED_PRIMARY_SPAN',output_errors(c,p))

    def test_literal_asset_and_execution_limits(self):
        c=self.positive;p=fixture_prediction(c,self.rm[c['case_id']]);p['current_buys'][0]['asset_mention']='$NOTHERE'
        self.assertIn('ASSET_NOT_IN_CITED_SOURCE',output_errors(c,p))
        p=fixture_prediction(c,self.rm[c['case_id']]);p['execution_verified']=True
        self.assertIn('EXECUTION_NOT_VERIFIED',output_errors(c,p))

    def test_invalid_binding_keeps_raw_label_separate(self):
        predictions=copy.deepcopy(self.pred);idx=next(i for i,c in enumerate(self.inputs)if c['case_id']==self.positive['case_id'])
        predictions[idx]['evidence_ids']=['ev_fake']
        r=score(self.inputs,self.refs,predictions)
        self.assertEqual(r['raw_proposals_UNACCEPTED_DIAGNOSTIC']['label_correct'],21)
        self.assertEqual(r['accepted_at_075']['label_correct'],20)
        self.assertEqual(r['technical']['invalid_outputs'],1)

    def test_low_confidence_is_unaccepted_not_unclear(self):
        predictions=copy.deepcopy(self.pred);idx=next(i for i,c in enumerate(self.inputs)if c['case_id']==self.positive['case_id'])
        predictions[idx]['confidence']=.749
        r=score(self.inputs,self.refs,predictions)
        row=next(r for r in r['rows']if r['case_id']==self.positive['case_id'])
        self.assertEqual(row['outcome'],'LOW_CONFIDENCE_ABSTAIN');self.assertIsNone(row['accepted_label'])
        predictions[idx]['confidence']=.75
        self.assertEqual(score(self.inputs,self.refs,predictions)['accepted_at_075']['label_correct'],21)

    def test_capacity_abstentions_do_not_inflate_recall(self):
        p=[dict(case_id=c['case_id'],status='CAPACITY_LIMIT',error_codes=['LOCAL_INPUT_CAPACITY'],explanation='No complete processing available.')for c in self.inputs]
        r=score(self.inputs,self.refs,p)
        self.assertEqual(r['accepted_at_075']['recall_all_reference_BUY'],0)
        self.assertEqual(r['accepted_at_075']['missed_reference_BUY_including_abstentions'],8)
        self.assertEqual(r['technical']['correct_integrity_rejections'],0)

    def test_nonok_cannot_contain_label(self):
        p=dict(case_id=self.positive['case_id'],status='CAPACITY_LIMIT',error_codes=['LOCAL_INPUT_CAPACITY'],explanation='Too long',label='NO_NEW_BUY')
        self.assertIn('NON_OK_FIELDS',output_errors(self.positive,p))

    def test_reference_input_hash_locked(self):
        refs=copy.deepcopy(self.refs);refs[0]['input_sha256']='0'*64
        with self.assertRaises(ValueError):score(self.inputs,refs,self.pred)

    def test_duplicate_rows_keys_and_nonfinite_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'input.jsonl'
            for text in ['{"case_id":"x"}\n{"case_id":"x"}\n','{"case_id":"x","case_id":"y"}\n','{"case_id":"x","confidence":NaN}\n']:
                p.write_text(text)
                with self.assertRaises(ValueError):jsonl(p)

    def test_missing_prediction_remains_visible(self):
        r=score(self.inputs,self.refs,self.pred[1:])
        self.assertEqual(r['technical']['missing'],1)
        self.assertEqual(len(r['rows']),24)

    def test_missing_media_is_not_a_class_label(self):
        labels={self.rm[c['case_id']]['label']for c in self.inputs if any(m['kind']=='IMAGE'for m in c['unavailable_context'])}
        self.assertEqual(labels,{'BUY','NO_NEW_BUY','UNCLEAR'})

    def test_long_inputs_include_opposite_labels(self):
        labels={self.rm[c['case_id']]['label']for c in self.inputs if len(c['primary']['text'])>4000}
        self.assertEqual(labels,{'BUY','NO_NEW_BUY'})

    def test_unknown_submission_id_rejected(self):
        p=copy.deepcopy(self.pred);p[0]['case_id']='dev-fffffffffe'
        with self.assertRaises(ValueError):score(self.inputs,self.refs,p)


if __name__=='__main__':unittest.main()
