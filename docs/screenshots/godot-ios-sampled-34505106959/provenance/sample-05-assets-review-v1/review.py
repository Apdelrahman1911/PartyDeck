"""Bounded, read-only analysis of the sole identity-verified sample-05 report."""

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import stat

ROOT = Path('/root/projects/PartyDeck')
OUT = Path(__file__).resolve().parent
RUN = ROOT / 'artifacts/evidence-storage/34505106959'
SAMPLES = RUN / 'godot-ios-retained-stack-samples-attempt-1'
MATERIAL = ROOT / 'artifacts/evidence-storage/34488350932-3d-material-source-review'
ITERATION = ROOT / 'artifacts/evidence-storage/34488350932-iteration-source-review'
SOURCE = ROOT / 'artifacts/evidence-storage/source-16d828e'
HEAD = '16d828e10212dbe7e930421c2fbe7d040f835c19'
PACK = 'd6adbba1b5cbd6a1ac3a5754e4294363eae70ae9540af4ba12040cd4cfff44e0'
RAW_SHA = 'ac389adbdd7745e5b3d66518362ab07e6eefc8dfde28acdb346e5a32c716ce5f'


def info(path):
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def load(path):
    return json.loads(path.read_bytes())


def save(name, value):
    with (OUT / name).open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


assert not (OUT / 'collection-frozen.json').exists()
expected = [
    (SAMPLES / 'sample-05.txt', RAW_SHA),
    (SAMPLES / 'sample-05.json', '40635a14a034ae531b7e427d2789da5c3f6ceb07a9cef9b0bba10d20b5576f0d'),
    (SAMPLES / 'context.json', '73414cd6e6e39aa0edc67daf0847db6e92dafd7a556d2442687b379a36a5c329'),
    (SAMPLES / 'summary.json', '386e72d712e2bbbafb4badc1c4da52c7e89a2b90e6114a1c4c0144a16317fd8a'),
    (MATERIAL / 'RESULT.md', 'a08448f869d96bd6a2d174009ee6a1ff310add33cb3f96c9f7047a9cd274a6af'),
    (ITERATION / 'RESULT.md', '530d908841a4b247ee214b89163dfb9f12f5577f2661b9cffddf5f263fe6fa5c'),
    (SOURCE / 'source-delta.json', 'd2d78a8989e85a355830a72b2d7407c614aa24c4d4720e428a6ce778e5ee4190'),
    (SOURCE / 'collection-frozen.json', 'f352377d994f595b96c07922965598563bc1cc0ca1731c72573ea8c26bd38193'),
    (RUN / 'causal-scope-v1.md', '572f61e086bbaab2709f631aa01a2d9fcf593be738f372ed9502334ff876403f'),
    (RUN / 'xcresult-decoded/app-stdout-stderr-001.log', '2bd4da73dcf05dc4c24131b64e3bc1ba44e289a1c9109effc0f297a23d8c93d2'),
    (ROOT / 'artifacts/evidence-storage/34505106959-msaa-experiment-v1/proposal-frozen.json',
     '616f3844d53c80f50d155d4f561ccf0acf610c49ebf3e274db61836e539cf4c0'),
]
inputs = []
for path, digest in expected:
    actual = info(path)
    assert actual['sha256'] == digest, str(path)
    inputs.append(actual)
for path in (SAMPLES / 'events.jsonl', SAMPLES / 'installed-sample.1', MATERIAL / 'source-inputs.json',
             RUN / 'godot-ios-host-engine/evidence/engine-artifact.json',
             RUN / 'godot-ios-host-engine/evidence/upstream-reference-audit.json', RUN / 'producer-observation-v1.json'):
    inputs.append(info(path))

receipt, context, summary = (load(SAMPLES / name) for name in ('sample-05.json', 'context.json', 'summary.json'))
assert context['sourceHead'] == HEAD and context['runId'] == '34505106959'
assert receipt['target']['identity']['pid'] == 29236 and receipt['target']['identity']['uid'] == 501
assert receipt['report']['sha256'] == RAW_SHA and receipt['reportHeaderPidMatches'] is True
assert receipt['sameProcessLifetimeBeforeAndAfter'] is True and receipt['executableIdentityStable'] is True
assert receipt['identityMonitorChecks'] == 93 and receipt['returnCode'] == 0
assert summary['sampleInvocations'] == 6

engine = load(RUN / 'godot-ios-host-engine/evidence/engine-artifact.json')
producer = load(RUN / 'producer-observation-v1.json')
assert engine['engine_commit'] == 'ed1daf0bf001b61586d9930840f2f1394092c079'
assert producer['pack']['sha256'] == PACK
assert engine['native_module_sources']['partydeck_ios_probe/PDGodotRuntime.mm'] == '042ad5a42ae33a7696c38c448a0e5eef120d1c75a19ad3c29e5c516899913fc8'
material_inputs = load(MATERIAL / 'source-inputs.json')
table = SOURCE / 'source-16d828e/godot/renderer/presentations/three_d/table.gd'
table_pin = next(row for row in material_inputs['product_sources'] if row['path'].endswith('three_d/table.gd'))
assert info(table)['sha256'] == table_pin['sha256']
assert table.read_text().splitlines()[155].strip() == '_viewport.msaa_3d = Viewport.MSAA_2X'
inputs.append(info(table))
for record in material_inputs['selected_engine_sources']:
    if record['path'] in ('scene/resources/material.cpp', 'drivers/gles3/shader_gles3.cpp', 'drivers/gles3/shader_gles3.h'):
        actual = info(Path(record['canonical_source']))
        assert actual['sha256'] == record['sha256']
        inputs.append(actual)

raw = (SAMPLES / 'sample-05.txt').read_bytes()
raw_lines = raw.splitlines(keepends=True)
lines = raw.decode().splitlines()
assert len(raw) == 1858083 and len(lines) == 8486
assert 'RetainedHost [29236]' in lines[1]
call_start = lines.index('Call graph:') + 1
call_end = next(i for i, line in enumerate(lines) if line.startswith('Total number in stack'))
nodes, stack = [], []
for offset in range(call_start, call_end):
    match = re.match(r'^([ +!|:]*)(\d+) (.*)$', lines[offset])
    if not match:
        continue
    depth = len(match[1])
    while stack and nodes[stack[-1]]['depth'] >= depth:
        stack.pop()
    node = dict(line=offset + 1, depth=depth, count=int(match[2]), symbol=match[3],
                parent=stack[-1] if stack else None)
    nodes.append(node)
    stack.append(len(nodes) - 1)


def ancestry(index):
    result = []
    while index is not None:
        result.append(nodes[index])
        index = nodes[index]['parent']
    return list(reversed(result))


main_nodes = [(i, node) for i, node in enumerate(nodes) if any('Thread_84368' in ancestor['symbol'] for ancestor in ancestry(i))]
iteration_nodes = [(i, node) for i, node in main_nodes if 'Main::iteration()' in node['symbol']]
runtime_nodes = [(i, node) for i, node in main_nodes if '-[PDGodotRuntime iterate]' in node['symbol']]
draw_nodes = [(i, node) for i, node in main_nodes if 'RenderingServerDefault::_draw(' in node['symbol'] and
              any('Main::iteration()' in ancestor['symbol'] for ancestor in ancestry(i))]
assert [node['count'] for _, node in iteration_nodes] == [510, 10, 2, 14]
assert [node['count'] for _, node in draw_nodes] == [510, 2, 14]
assert len(runtime_nodes) == 3
runtime_indexes = {index for index, _ in runtime_nodes}
descendants = [(i, node) for i, node in main_nodes if any(ancestor['line'] == nodes[index]['line']
               for ancestor in ancestry(i)[:-1] for index in runtime_indexes)]
wait_pattern = re.compile(r'mach_msg|semaphore.*wait|__ulock_wait|__psynch.*wait|pthread.*wait|dispatch.*wait|cvm.*wait|glFinish', re.I)
iterate_waits = [dict(line=node['line'], count=node['count'], symbol=node['symbol']) for _, node in descendants if wait_pattern.search(node['symbol'])]
assert iterate_waits == []

specializations = []
for index, node in main_nodes:
    if 'ShaderGLES3::_compile_specialization(' in node['symbol']:
        branch = ancestry(index)
        phase = 'iteration' if any('Main::iteration()' in ancestor['symbol'] for ancestor in branch) else 'setup2'
        specializations.append(dict(line=node['line'], count=node['count'], phase=phase))
assert len(specializations) == 7

evidence_ranges = [(1, 24), (37, 41), (188, 211), (519, 537), (551, 555), (750, 754),
                   (1064, 1076), (1175, 1179), (1188, 1195), (1204, 1207), (1276, 1277),
                   (1763, 1768), (2073, 2091), (2121, 2127), (4091, 4102), (4995, 5023), (8423, 8438)]
excerpts = []
for first, last in evidence_ranges:
    selected = b''.join(raw_lines[first - 1:last])
    excerpts.append(dict(first_line=first, last_line=last, bytes=len(selected),
                         sha256=hashlib.sha256(selected).hexdigest(), text=selected.decode()))
save('selected-stack-excerpts.json', dict(source=str(SAMPLES / 'sample-05.txt'), source_sha256=RAW_SHA,
     scope='Verbatim bounded text excerpts; line endings retained in text values. No raw report is rewritten.', excerpts=excerpts))

events = [json.loads(line) for line in (SAMPLES / 'events.jsonl').read_text().splitlines()]
stale_markers = [event for event in events if event.get('kind') == 'original_test_log_marker' and
                event.get('marker', {}).get('case') == 'testStaleFirstReadyAndCloseCompletionReentry']
backend = (RUN / 'xcresult-decoded/app-stdout-stderr-001.log').read_text().splitlines()[111766]
assert 'RetainedHost[29236:84368]' in backend and 'Apple Software Renderer' in backend
save('analysis.json', dict(schema_version=1, run_id='34505106959', source_head=HEAD,
    original_report=inputs[0], pid=29236, uid=501, executable_sha256=receipt['target']['installedExecutable']['sha256'],
    test_case=receipt['request']['case'], nominal_sampling_seconds=30, nominal_interval_milliseconds=10,
    tool_launched_at=receipt['toolLaunchedAt'], tool_finished_at=receipt['toolFinishedAt'],
    report_date_time_line=lines[11], report_launch_time_line=lines[12],
    counts_scope='Inclusive call-tree observations; not call counts, exclusive CPU time, exact elapsed duration or chronological samples. Only disjoint node totals below are summed.',
    main_thread_roots=[dict(line=node['line'], count=node['count']) for node in nodes if node['parent'] is None and 'Thread_84368' in node['symbol']],
    iteration_nodes=[dict(line=node['line'], count=node['count']) for _, node in iteration_nodes],
    disjoint_iteration_observations=536, draw_nodes=[dict(line=node['line'], count=node['count']) for _, node in draw_nodes],
    disjoint_draw_observations=526, examined_runtime_descendant_frame_records=len(descendants),
    explicit_wait_family_matches_under_sampled_iterate=iterate_waits,
    shader_specialization_nodes=specializations,
    deferred_compiler_queue=dict(line=4995, count=469, name='com.apple.opengl.cvmDoWork',
                                main_thread_dependency_demonstrated=False, simultaneous_sample_timestamps_available=False),
    concrete_observed_wait_paths=[
        dict(report_lines=[37, 41], count=72, path='dyld synchronous debugger/image notification → mach_msg2_trap', attributable_to_failed_iteration=False),
        dict(report_lines=[1068, 1076], count=16, path='AudioDriverCoreAudio::init → AudioUnitInitialize/AURemoteIO::Initialize → mach_msg2_trap', attributable_to_failed_iteration=False),
        dict(report_lines=[1178, 1195], count=3, path='startup ShaderGLES3 compile → glpGetBIArchiveData → dyld loaders lock → __ulock_wait2', attributable_to_failed_iteration=False),
        dict(report_lines=[4091, 4102], count=66, path='framework load → dyld synchronous debugger/image notification → mach_msg2_trap', attributable_to_failed_iteration=False)],
    original_app_backend=dict(path=str(RUN / 'xcresult-decoded/app-stdout-stderr-001.log'), line=111767, text=backend,
                              sha256='2bd4da73dcf05dc4c24131b64e3bc1ba44e289a1c9109effc0f297a23d8c93d2'),
    sampler_observed_case_markers=stale_markers,
    per_observation_timestamps_retained=False, exact_failed_iteration_stack_binding=False,
    first_frame_ordinal_identified=False, observer_and_foundation_clock_origins_equated=False,
    first_failed_repeated_case_has_usable_raw_sample=False, sampling_overhead_measured=False,
    material_shader_or_variant_identified=False, failed_deadline_blocked_call_identified=False,
    source_map_relation='The same renderer PCK and exact three_d/table.gd bytes retain the prior material-key/source map. Actual Godot specialization and Apple pipeline/CVM build work appear, but do not establish a Reveal/selection shader-key toggle or material-cache cause.',
    proposed_experiment=dict(status='Recommendation only; no product edit or export by this reviewer', source=str(table),
        line=156, before='_viewport.msaa_3d = Viewport.MSAA_2X', after='_viewport.msaa_3d = Viewport.MSAA_DISABLED',
        baseline_pack_sha256=PACK, owner='engine_ci',
        owner_proposal=str(ROOT / 'artifacts/evidence-storage/34505106959-msaa-experiment-v1/PROPOSAL.md'),
        aim='Test contribution from the 3D multisample render path while preserving geometry, materials, layouts, controls and gates.',
        cause_claim=False, actual_effective_sample_count_known=False, merge_or_acceptance_claim=False),
    native_qualification_added=False, product_edits=False, new_sample_runs=0, new_exports=0, full_collection_reaudits=0))
save('source-inputs.json', dict(schema_version=1, source_head=HEAD, engine_commit=engine['engine_commit'],
    renderer_pack_sha256=PACK, source_receipts=inputs, source_archives_copied_or_reaudited=False,
    scope='Only the named original report/receipts, prior maps and selected pinned source identities were consumed.'))
assert info(SAMPLES / 'sample-05.txt')['sha256'] == RAW_SHA
rows = [dict(file=path.name, bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(OUT.iterdir()) if path.is_file()]
save('collection-frozen.json', dict(schema_version=1, frozen_at_utc=datetime.now(timezone.utc).isoformat(),
    run_id='34505106959', source_head=HEAD, original_report_sha256=RAW_SHA,
    files=rows, file_count=len(rows), total_bytes=sum(row['bytes'] for row in rows),
    original_report_unchanged=True, product_edits=False, new_native_or_sample_execution=False,
    canonical_exports=False, native_qualification_added=False))
for path in OUT.iterdir():
    if path.is_file():
        path.chmod(stat.S_IMODE(path.stat().st_mode) & ~0o222)
print(json.dumps(dict(output=str(OUT), freeze=info(OUT / 'collection-frozen.json'),
    analysis=info(OUT / 'analysis.json'), result=info(OUT / 'RESULT.md'),
    examined_iterate_frame_records=len(descendants), bytes=sum(row['bytes'] for row in rows))))
