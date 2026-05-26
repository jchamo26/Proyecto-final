import inspect
import ragas.metrics._faithfulness as faith
import ragas.metrics._answer_relevance as ar
import ragas.metrics._context_precision as cp_mod
import ragas.metrics._context_recall as cr_mod

print('FAITHFULNESS TYPE:', type(faith))
print('FAITHFULNESS DIR:', [d for d in dir(faith) if not d.startswith('_')])
for attr in ['output_schema', 'output_type', 'name', 'description', 'prompt']:
    if hasattr(faith, attr):
        print(f"faith.{attr}:", getattr(faith, attr))
if hasattr(faith, 'nli_statements_prompt'):
    print('\nfaith.nli_statements_prompt:\n', faith.nli_statements_prompt)
if hasattr(faith, 'statement_generator_prompt'):
    print('\nfaith.statement_generator_prompt:\n', faith.statement_generator_prompt)

print('\nANSWER_RELEVANCY TYPE:', type(ar))
print('ANSWER_RELEVANCY DIR:', [d for d in dir(ar) if not d.startswith('_')])
if hasattr(ar, 'answer_relevancy'):
    ar_obj = ar.answer_relevancy
    print('answer_relevancy type:', type(ar_obj))
    print('answer_relevancy dir:', [d for d in dir(ar_obj) if not d.startswith('_')])
    for attr in ['output_schema', 'output_type', 'name', 'description', 'prompt']:
        if hasattr(ar_obj, attr):
            print(f"answer_relevancy.{attr}:", getattr(ar_obj, attr))
    if hasattr(ar_obj, 'question_generation'):
        print('\nanswer_relevancy.question_generation:\n', ar_obj.question_generation)

print('\nCONTEXT_PRECISION TYPE:', type(cp_mod))
print('CONTEXT_PRECISION DIR:', [d for d in dir(cp_mod) if not d.startswith('_')])
if hasattr(cp_mod, 'context_precision'):
    cp = cp_mod.context_precision
    print('context_precision type:', type(cp))
    print('context_precision dir:', [d for d in dir(cp) if not d.startswith('_')])
    for attr in ['output_schema', 'output_type', 'name', 'prompt', 'statement_generator_prompt', 'nli_statements_prompt', 'question_generation']:
        if hasattr(cp, attr):
            print(f"context_precision.{attr}:", getattr(cp, attr))
    if hasattr(cp, 'context_precision_prompt'):
        print('\ncontext_precision.context_precision_prompt:\n', cp.context_precision_prompt)
if hasattr(cp_mod, 'context_precision_prompt'):
    print('\ncp_mod.context_precision_prompt:\n', cp_mod.context_precision_prompt)

print('\nCONTEXT_RECALL TYPE:', type(cr_mod))
print('CONTEXT_RECALL DIR:', [d for d in dir(cr_mod) if not d.startswith('_')])
if hasattr(cr_mod, 'context_recall'):
    cr = cr_mod.context_recall
    print('context_recall type:', type(cr))
    print('context_recall dir:', [d for d in dir(cr) if not d.startswith('_')])
    for attr in ['output_schema', 'output_type', 'name', 'prompt', 'statement_generator_prompt', 'nli_statements_prompt', 'question_generation']:
        if hasattr(cr, attr):
            print(f"context_recall.{attr}:", getattr(cr, attr))
    if hasattr(cr, 'context_recall_prompt'):
        print('\ncontext_recall.context_recall_prompt:\n', cr.context_recall_prompt)
if hasattr(cr_mod, 'context_recall_prompt'):
    print('\ncr_mod.context_recall_prompt:\n', cr_mod.context_recall_prompt)
