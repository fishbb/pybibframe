'''
marc2bfrdf -v -o /tmp/ph1.ttl -s /tmp/ph1.stats.js -b http://example.org test/resource/princeton-holdings1.xml 2> /tmp/ph1.log

'''

import re
import os
import json
import functools
import logging
import itertools
import asyncio
from collections import defaultdict, OrderedDict

from bibframe.contrib.datachefids import idgen#, FROM_EMPTY_64BIT_HASH

from amara3 import iri

from versa import I, VERSA_BASEIRI, ORIGIN, RELATIONSHIP, TARGET, ATTRIBUTES
from versa.util import duplicate_statements, OrderedJsonEncoder
from versa.driver import memory
#from versa.pipeline import context as versacontext

from bibframe import MARC, POSTPROCESS_AS_INSTANCE
from bibframe.reader.util import WORKID, IID
from bibframe import BF_INIT_TASK, BF_INPUT_TASK, BF_INPUT_XREF_TASK, BF_MARCREC_TASK, BF_MATRES_TASK, BF_FINAL_TASK
from bibframe.isbnplus import isbn_list, compute_ean13_check
from bibframe.reader.marcpatterns import TRANSFORMS, bfcontext
from bibframe.reader.marcworkidpatterns import WORK_HASH_TRANSFORMS, WORK_HASH_INPUT
from bibframe.reader.marcextra import transforms as default_extra_transforms


MARCXML_NS = "http://www.loc.gov/MARC21/slim"

NON_ISBN_CHARS = re.compile('\D')

NEW_RECORD = 'http://bibfra.me/purl/versa/' + 'newrecord'

# Namespaces

BL = 'http://bibfra.me/vocab/lite/'
ISBNNS = MARC

TYPE_REL = I(iri.absolutize('type', VERSA_BASEIRI))

def invert_dict(d):
    #http://code.activestate.com/recipes/252143-invert-a-dictionary-one-liner/#c3
    #See also: http://pypi.python.org/pypi/bidict
        #Though note: http://code.activestate.com/recipes/576968/#c2
    inv = {}
    for k, v in d.items():
        keys = inv.setdefault(v, [])
        keys.append(k)
    return inv


def marc_lookup(model, codes):
    #Note: should preserve code order in order to maintain integrity when used for hash input
    if isinstance(codes, str):
        codes = [codes]
    for code in codes:
        tag, sf = code.split('$') if '$' in code else (code, None)
        #Check for data field
        links = model.match(None, MARCXML_NS + '/data/' + tag)
        for link in links:
            for result in link[ATTRIBUTES].get(sf, []):
                yield (code, result)

        #Check for control field
        links = model.match(None, MARCXML_NS + '/control/' + tag)
        for link in links:
            yield code, link[TARGET]


ISBN_REL = I(iri.absolutize('isbn', ISBNNS))
ISBN_TYPE_REL = I(iri.absolutize('isbnType', ISBNNS))

def isbn_instancegen(params, loop, model):
    '''
    Default handling of the idea of splitting a MARC record with FRBR Work info as well as instances signalled by ISBNs

    According to Vicki Instances can be signalled by 007, 020 or 3XX, but we stick to 020 for now
    '''
    #Handle ISBNs re: https://foundry.zepheira.com/issues/1976
    entbase = params['entbase']
    output_model = params['output_model']
    input_model = params['input_model']
    vocabbase = params['vocabbase']
    logger = params['logger']
    materialize_entity = params['materialize_entity']
    existing_ids = params['existing_ids']
    workid = params['workid']
    ids = params['ids']
    plugins = params['plugins']

    INSTANTIATES_REL = I(iri.absolutize('instantiates', vocabbase))

    isbns = list(( val for code, val in marc_lookup(input_model, '020$a')))
    logger.debug('Raw ISBNS:\t{0}'.format(isbns))

    # sorted to remove non-determinism which interferes with canonicalization
    normalized_isbns = sorted(list(isbn_list(isbns, logger=logger)))

    subscript = ord('a')
    instance_ids = []
    logger.debug('Normalized ISBN:\t{0}'.format(normalized_isbns))
    if normalized_isbns:
        for inum, itype in normalized_isbns:
            data = [['instantiates', workid], ['isbn', inum]]
            instanceid = materialize_entity('Instance', ctx_params=params, loop=loop, model_to_update=params['output_model'], data=data)
            if entbase: instanceid = I(iri.absolutize(instanceid, entbase))

            output_model.add(I(instanceid), ISBN_REL, compute_ean13_check(inum))
            output_model.add(I(instanceid), INSTANTIATES_REL, I(workid))
            if itype: output_model.add(I(instanceid), ISBN_TYPE_REL, itype)
            existing_ids.add(instanceid)
            instance_ids.append(instanceid)
    else:
        #If there are no ISBNs, we'll generate a default Instance
        data = [['instantiates', workid]]
        instanceid = materialize_entity('Instance', ctx_params=params, loop=loop, model_to_update=params['output_model'], data=data)
        if entbase: instanceid = I(iri.absolutize(instanceid, entbase))
        output_model.add(I(instanceid), INSTANTIATES_REL, I(workid))
        existing_ids.add(instanceid)
        instance_ids.append(instanceid)

    #output_model.add(instance_ids[0], I(iri.absolutize('instantiates', vocabbase)), I(workid))
    #output_model.add(I(instance_ids[0]), TYPE_REL, I(iri.absolutize('Instance', vocabbase)))

    return instance_ids


def instance_postprocess(params):
    instanceids = params['instanceids']
    model = params['output_model']
    vocabbase = params['vocabbase']
    def dupe_filter(o, r, t, a):
        #Filter out ISBN relationships
        return (r, t) != (TYPE_REL, I(iri.absolutize('Instance', vocabbase))) \
            and r not in (ISBN_REL, ISBN_TYPE_REL, I(iri.absolutize('instantiates', vocabbase)))
    if len(instanceids) > 1:
        base_instance_id = instanceids[0]
        for instanceid in instanceids[1:]:
            duplicate_statements(model, base_instance_id, instanceid, rfilter=dupe_filter)
    return


def gather_workid_data(model, origin):
    '''
    Called after a first pass has been made to derive a BIBFRAME model sufficient to
    Compute a hash for the work, a task undertaken by this function
    '''
    data = []
    for rel in WORK_HASH_INPUT:
        for link in model.match(origin, rel):
            data.append([link[RELATIONSHIP], link[TARGET]])
    return data

#WORK_HASH_TRANSFORMS, WORK_HASH_INPUT

def materialize_entity(etype, ctx_params=None, loop=None, model_to_update=None, data=None, addtype=True):
    '''
    Routine for creating a BIBFRAME resource. Takes the entity (resource) type and a data mapping
    according to the resource type. Implements the Libhub Resource Hash Convention
    As a convenience, if a vocabulary base is provided, concatenate it to etype and the data keys
    '''
    ctx_params = ctx_params or {}
    vocabbase = ctx_params.get('vocabbase', BL)
    existing_ids = ctx_params.get('existing_ids')
    plugins = ctx_params.get('plugins')
    logger = ctx_params.get('logger', logging)
    output_model = ctx_params.get('output_model')
    ids = ctx_params.get('ids')
    if vocabbase and not iri.is_absolute(etype):
        etype = vocabbase + etype
    params = {'logger': logger}

    data = data or []
    if addtype: data.insert(0, [TYPE_REL, etype])
    data_full =  [ ((vocabbase + k if not iri.is_absolute(k) else k), v) for (k, v) in data ]
    plaintext = json.dumps(data_full, separators=(',', ':'), cls=OrderedJsonEncoder)

    eid = ids.send(plaintext)

    if model_to_update:
        model_to_update.add(I(eid), TYPE_REL, I(etype))

    params['materialized_id'] = eid
    params['first_seen'] = eid in existing_ids
    params['plaintext'] = plaintext
    for plugin in plugins or ():
        #Not using yield from
        if BF_MATRES_TASK in plugin:
            for p in plugin[BF_MATRES_TASK](loop, output_model, params): pass
        #logger.debug("Pending tasks: %s" % asyncio.Task.all_tasks(loop))
    return eid


#XXX Generalize by using URIs for phase IDs
def process_marcpatterns(params, transforms, input_model, main_phase=False):
    if main_phase:
        # Need to sort our way through the input model so that the materializations occur
        # at the same place each time, otherwise canonicalization fails due to the
        # addition of the subfield context (at the end of materialize())

        # XXX Is the int() cast necessary? If not we could do key=operator.itemgetter(0)
        input_model_iter= sorted(list(params['input_model']), key=lambda x: int(x[0]))
    else:
        input_model_iter= params['input_model']
    params['to_postprocess'] = []
    for lid, marc_link in input_model_iter:
        origin, taglink, val, attribs = marc_link
        if taglink == MARCXML_NS + '/leader':
            params['leader'] = leader = val
            continue
        #Sort out attributes
        params['indicators'] = indicators = { k: v for k, v in attribs.items() if k.startswith('ind') }
        params['subfields'] = subfields = attribs.copy() # preserve class
        #for k in list(subfields.keys()):
        #    if k[:3] in ('tag', 'ind'):
        #        del subfields[k]
        subfields = { k: v for (k, v) in subfields.items() if k[:3] not in ('tag', 'ind') }
        params['code'] = tag = attribs['tag']
        if taglink.startswith(MARCXML_NS + '/control'):
            #No indicators on control fields. Turn them off, in effect
            indicator_list = ('#', '#')
            key = 'tag-' + tag
            if tag == '006':
                params['fields006'].append(val)
            if tag == '007':
                params['fields007'].append(val)
            if tag == '008':
                params['field008'] = val
            if main_phase:
                params['transform_log'].append((tag, key))
                params['fields_used'].append((tag,))
        elif taglink.startswith(MARCXML_NS + '/data'):
            indicator_list = ((attribs.get('ind1') or ' ')[0].replace(' ', '#'), (attribs.get('ind2') or ' ')[0].replace(' ', '#'))
            key = 'tag-' + tag
            #logger.debug('indicators: ', repr(indicators))
            #indicator_list = (indicators['ind1'], indicators['ind2'])
            if main_phase: params['fields_used'].append(tuple([tag] + list(subfields.keys())))

        #This is where we check each incoming MARC link to see if it matches a transform into an output link (e.g. renaming 001 to 'controlCode')
        to_process = []
        #Start with most specific matches, then to most general

        # "?" syntax in lookups is a single char wildcard
        #First with subfields, with & without indicators:
        for k, v in subfields.items():
            #if indicator_list == ('#', '#'):
            lookups = [
                '{0}-{1}{2}${3}'.format(tag, indicator_list[0], indicator_list[1], k),
                '{0}-?{2}${3}'.format(tag, indicator_list[0], indicator_list[1], k),
                '{0}-{1}?${3}'.format(tag, indicator_list[0], indicator_list[1], k),
                '{0}${1}'.format(tag, k),
            ]
            for valitems in v:
                for lookup in lookups:
                    if lookup in transforms:
                        to_process.append((transforms[lookup], valitems))
                    else:
                        # don't report on subfields for which a code-transform exists,
                        # disregard wildcards
                        if main_phase and not tag in transforms and '?' not in lookup:

                            params['dropped_codes'].setdefault(lookup,0)
                            params['dropped_codes'][lookup] += 1

        #Now just the tag, with & without indicators
        lookups = [
            '{0}-{1}{2}'.format(tag, indicator_list[0], indicator_list[1]),
            '{0}-?{2}'.format(tag, indicator_list[0], indicator_list[1]),
            '{0}-{1}?'.format(tag, indicator_list[0], indicator_list[1]),
            tag,
        ]

        #Remember how many lookups were successful based on subfields
        subfields_results_len = len(to_process)
        for lookup in lookups:
            if lookup in transforms:
                to_process.append((transforms[lookup], val))

        if main_phase and subfields_results_len == len(to_process) and not subfields:
            # Count as dropped if subfields were not processed and theer were no matches on non-subfield lookups
            params['dropped_codes'].setdefault(tag,0)
            params['dropped_codes'][tag] += 1

        mat_ent = functools.partial(materialize_entity, ctx_params=params, loop=params['loop'])

        #Apply all the handlers that were found
        for funcinfo, val in to_process:
            #Support multiple actions per lookup
            funcs = funcinfo if isinstance(funcinfo, tuple) else (funcinfo,)

            for func in funcs:
                extras = {
                    WORKID: params['workid'],
                    IID: params['instanceids'][0],
                    'logger': params['logger'],
                    'postprocessing': []
                }
                #Build Versa processing context
                #Should we include indicators?
                #Should we be passing in taglik rather than tag?
                ctx = bfcontext((origin, tag, val, subfields), input_model,
                                    params['output_model'], extras=extras,
                                    base=params['vocabbase'], idgen=mat_ent,
                                    existing_ids=params['existing_ids'])
                func(ctx)
                params['to_postprocess'].extend(ctx.extras['postprocessing'])

        if main_phase and not to_process:
            #Nothing else has handled this data field; go to the fallback
            fallback_rel_base = '../marcext/tag-' + tag
            if not subfields:
                #Fallback for control field: Captures MARC tag & value
                params['output_model'].add(I(params['workid']), I(iri.absolutize(fallback_rel_base, params['vocabbase'])), val)
            for k, v in subfields.items():
                #Fallback for data field: Captures MARC tag, indicators, subfields & value
                fallback_rel = '../marcext/{0}-{1}{2}-{3}'.format(
                    fallback_rel_base, indicator_list[0].replace('#', 'X'),
                    indicator_list[1].replace('#', 'X'), k)
                #params['transform_log'].append((code, fallback_rel))
                for valitem in v:
                    try:
                        params['output_model'].add(I(params['workid']), I(iri.absolutize(fallback_rel, params['vocabbase'])), valitem)
                    except ValueError as e:
                        logger.warning('{}\nSkipping statement for {}: "{}"'.format(e, control_code[0], dumb_title[0]))

    extra_stmts = set() # prevent duplicate statements
    extra_transforms = params['extra_transforms']
    for origin, k, v in itertools.chain(
                extra_transforms.process_leader(params),
                extra_transforms.process_006(params['fields006'], params),
                extra_transforms.process_007(params['fields007'], params),
                extra_transforms.process_008(params['field008'], params)):
        v = v if isinstance(v, tuple) else (v,)
        for item in v:
            o = origin or I(params['workid'])
            if o and (o, k, item) not in extra_stmts:
                params['output_model'].add(o, k, item)
                extra_stmts.add((o, k, item))
    return


@asyncio.coroutine
def record_handler( loop, model, entbase=None, vocabbase=BL, limiting=None,
                    plugins=None, ids=None, postprocess=None, out=None,
                    logger=logging, transforms=TRANSFORMS,
                    extra_transforms=default_extra_transforms(),
                    canonical=False, **kwargs):
    '''
    loop - asyncio event loop
    model - the Versa model for the record
    entbase - base IRI used for IDs of generated entity resources
    limiting - mutable pair of [count, limit] used to control the number of records processed
    '''
    model_factory = kwargs.get('model_factory', memory.connection)
    main_transforms = transforms

    _final_tasks = set() #Tasks for the event loop contributing to the MARC processing

    plugins = plugins or []
    if ids is None: ids = idgen(entbase)

    #FIXME: For now always generate instances from ISBNs, but consider working this through the plugins system
    instancegen = isbn_instancegen

    existing_ids = set()
    #Start the process of writing out the JSON representation of the resulting Versa
    if out and not canonical: out.write('[')
    first_record = True

    try:
        while True:
            input_model = yield
            leader = None
            #Add work item record, with actual hash resource IDs based on default or plugged-in algo
            #FIXME: No plug-in support yet
            params = {
                'input_model': input_model, 'output_model': model, 'logger': logger,
                'entbase': entbase, 'vocabbase': vocabbase, 'ids': ids,
                'existing_ids': existing_ids, 'plugins': plugins,
                'materialize_entity': materialize_entity, 'leader': leader,
                'loop': loop, 'extra_transforms': extra_transforms
            }

            # Earliest plugin stage, with an unadulterated input model
            for plugin in plugins:
                if BF_INPUT_TASK in plugin:
                    yield from plugin[BF_INPUT_TASK](loop, input_model, params)

            #Prepare cross-references (i.e. 880s)
            #XXX: Figure out a way to declare in TRANSFORMS? We might have to deal with non-standard relationship designators: https://github.com/lcnetdev/marc2bibframe/issues/83
            xrefs = {}
            remove_links = set()
            add_links = []

            for lid, marc_link in input_model:
                origin, taglink, val, attribs = marc_link
                if taglink == MARCXML_NS + '/leader' or taglink.startswith(MARCXML_NS + '/data/9'):
                    #900 fields are local and might not follow the general xref rules
                    params['leader'] = leader = val
                    continue
                tag = attribs['tag']
                for xref in attribs.get('6', []):
                    xref_parts = xref.split('-')
                    if len(xref_parts) != 2:
                        logger.warning('Skipping invalid $6: "{}" for {}: "{}"'.format(xref, control_code[0], dumb_title[0]))
                        continue

                    xreftag, xrefid = xref_parts
                    #Locate the matching taglink
                    if tag == '880' and xrefid.startswith('00'):
                        #Special case, no actual xref, just the non-roman text
                        #Rule for 880s: merge in & add language indicator
                        langinfo = xrefid.split('/')[-1]
                        #Not using langinfo, really, at present because it seems near useless. Eventually we can handle by embedding a lang indicator token into attr values for later postprocessing
                        attribs['tag'] = xreftag
                        add_links.append((origin, MARCXML_NS + '/data/' + xreftag, val, attribs))

                    links = input_model.match(None, MARCXML_NS + '/data/' + xreftag)
                    for link in links:
                        #6 is the cross-reference subfield
                        for dest in link[ATTRIBUTES].get('6', []):
                            if [tag, xrefid] == dest.split('/')[0].split('-'):
                                if tag == '880':
                                    #880s will be handled by merger via xref, so take out for main loop
                                    #XXX: This does, however, make input_model no longer a true representation of the input XML. Problem?
                                    remove_links.add(lid)

                                if xreftag == '880':
                                    #Rule for 880s: merge in & add language indicator
                                    langinfo = dest.split('/')[-1]
                                    #Not using langinfo, really, at present because it seems near useless. Eventually we can handle by embedding a lang indicator token into attr values for later postprocessing
                                    remove_links.add(lid)
                                    copied_attribs = attribs.copy()
                                    for k, v in link[ATTRIBUTES].items():
                                        if k[:3] not in ('tag', 'ind'):
                                            copied_attribs.setdefault(k, []).extend(v)
                                    add_links.append((origin, taglink, val, copied_attribs))

            input_model.remove(remove_links)
            input_model.add_many(add_links)

            # hook for plugins interested in the xref-resolved input model
            for plugin in plugins:
                if BF_INPUT_XREF_TASK in plugin:
                    yield from plugin[BF_INPUT_XREF_TASK](loop, input_model, params)

            #Do one pass to establish work hash
            #XXX Should crossrefs precede this?
            temp_workhash = next(params['input_model'].match())[ORIGIN]
            logger.debug('Temp work hash: {0}'.format(temp_workhash))

            params['workid'] = temp_workhash
            params['instanceids'] = [temp_workhash + '-instance']
            params['output_model'] = model_factory()

            params['field008'] = leader = None
            params['fields006'] = fields006 = []
            params['fields007'] = fields007 = []
            params['to_postprocess'] = []

            process_marcpatterns(params, WORK_HASH_TRANSFORMS, input_model, main_phase=False)

            workid_data = gather_workid_data(params['output_model'], temp_workhash)
            workid = materialize_entity('Work', ctx_params=params, loop=loop, data=workid_data)

            is_folded = workid in existing_ids
            existing_ids.add(workid)

            control_code = list(marc_lookup(input_model, '001')) or ['NO 001 CONTROL CODE']
            dumb_title = list(marc_lookup(input_model, '245$a')) or ['NO 245$a TITLE']
            logger.debug('Work hash data: {0}'.format(repr(workid_data)))
            logger.debug('Control code: {0}'.format(control_code[0]))
            logger.debug('Uniform title: {0}'.format(dumb_title[0]))
            logger.debug('Work ID: {0}'.format(workid))

            workid = I(iri.absolutize(workid, entbase)) if entbase else I(workid)
            folded = [workid] if is_folded else []

            model.add(workid, TYPE_REL, I(iri.absolutize('Work', vocabbase)))

            params['workid'] = workid
            params['folded'] = folded

            #Switch to the main output model for processing
            params['output_model'] = model

            #Figure out instances
            instanceids = instancegen(params, loop, model)

            params['instanceids'] = instanceids or [None]
            params['transform_log'] = [] # set()
            params['fields_used'] = []
            params['dropped_codes'] = {}
            #Defensive coding against missing leader or 008
            params['field008'] = leader = None
            params['fields006'] = fields006 = []
            params['fields007'] = fields007 = []
            params['to_postprocess'] = []

            process_marcpatterns(params, main_transforms, input_model, main_phase=True)

            for op, rid in params['to_postprocess']:
                if op == POSTPROCESS_AS_INSTANCE:
                    if params['instanceids'] == [None]:
                        params['instanceids'] = [rid]
                    else:
                        params['instanceids'].append(rid)
            instance_postprocess(params)

            logger.debug('+')

            for plugin in plugins:
                #Each plug-in is a task
                #task = asyncio.Task(plugin[BF_MARCREC_TASK](loop, relsink, params), loop=loop)
                if BF_MARCREC_TASK in plugin:
                    yield from plugin[BF_MARCREC_TASK](loop, model, params)
                logger.debug("Pending tasks: %s" % asyncio.Task.all_tasks(loop))
                #FIXME: This blocks and thus serializes the plugin operation, rather than the desired coop scheduling approach
                #For some reason seting to async task then immediately deferring to next task via yield from sleep leads to the "yield from wasn't used with future" error (Not much clue at: https://codereview.appspot.com/7396044/)
                #yield from asyncio.Task(asyncio.sleep(0.01), loop=loop)
                #yield from asyncio.async(asyncio.sleep(0.01))
                #yield from asyncio.sleep(0.01) #Basically yield to next task

            #Can we somehow move this to passed-in postprocessing?
            if out and not canonical and not first_record: out.write(',\n')
            if out:
                if not canonical:
                    first_record = False
                    last_chunk = None
                    #Using iterencode avoids building a big JSON string in memory, or having to resort to file pointer seeking
                    #Then again builds a big list in memory, so still working on opt here
                    for chunk in json.JSONEncoder().iterencode([ link for link in model ]):
                        if last_chunk is None:
                            last_chunk = chunk[1:]
                        else:
                            out.write(last_chunk)
                            last_chunk = chunk
                    if last_chunk: out.write(last_chunk[:-1])
            #FIXME: Postprocessing should probably be a task too
            if postprocess: postprocess()
            #limiting--running count of records processed versus the max number, if any
            limiting[0] += 1
            if limiting[1] is not None and limiting[0] >= limiting[1]:
                break
    except GeneratorExit:
        logger.debug('Completed processing {0} record{1}.'.format(limiting[0], '' if limiting[0] == 1 else 's'))
        if out and not canonical: out.write(']')

        #if not plugins: loop.stop()
        for plugin in plugins:
            #Each plug-in is a task
            func = plugin.get(BF_FINAL_TASK)
            if not func: continue
            task = asyncio.Task(func(loop), loop=loop)
            _final_tasks.add(task)
            def task_done(task):
                #print('Task done: ', task)
                _final_tasks.remove(task)
                #logger.debug((plugins))
                #if plugins and len(_final_tasks) == 0:
                    #print("_final_tasks is empty, stopping loop.")
                    #loop = asyncio.get_event_loop()
                #    loop.stop()
            #Once all the plug-in tasks are done, all the work is done
            task.add_done_callback(task_done)
        #print('DONE')
        #raise

    return
