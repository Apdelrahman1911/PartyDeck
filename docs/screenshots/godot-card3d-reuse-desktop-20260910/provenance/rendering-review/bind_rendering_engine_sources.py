#!/usr/bin/env python3
"""Retain pinned engine implementation without executing Git or the engine."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parent
DECODER = Path('/tmp/partydeck-ios-retained-phase-review-game-34515678208-v1/bind_engine_sources.py')
UPSTREAM = Path('/root/projects/PartyDeck/godot/ios-host/build/upstream')
COMMIT = 'ed1daf0bf001b61586d9930840f2f1394092c079'
PATHS = ['scene/3d/mesh_instance_3d.cpp', 'scene/3d/mesh_instance_3d.h',
         'scene/3d/visual_instance_3d.cpp', 'scene/3d/visual_instance_3d.h',
         'scene/resources/3d/primitive_meshes.cpp', 'scene/resources/3d/primitive_meshes.h',
         'scene/resources/material.cpp', 'scene/main/node.cpp',
         'core/object/ref_counted.cpp', 'core/object/ref_counted.h']


def main():
    decoder_bytes = DECODER.read_bytes()
    assert hashlib.sha256(decoder_bytes).hexdigest() == 'c589c0f6e83154c2e7d9ba6423549c6de6d941249877920576499bee998264c5'
    helper = runpy.run_path(str(DECODER))
    objects = helper['PackedObjects']()
    kind, commit = objects.read(COMMIT)
    assert kind == 'commit'
    tree = commit.splitlines()[0].decode().removeprefix('tree ')
    (ROOT/'engine-commit.txt').write_bytes(commit)
    records = []
    for path in PATHS:
        oid, ancestry = tree, [tree]
        for part in Path(path).parts:
            kind, raw = objects.read(oid)
            assert kind == 'tree'
            _, oid = helper['tree_entries'](raw)[part]
            ancestry.append(oid)
        kind, raw = objects.read(oid)
        assert kind == 'blob' and raw == (UPSTREAM/path).read_bytes(), path
        target = ROOT/'engine-sources'/path
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(raw)
        records.append(dict(path=path,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                            gitBlobSHA1=oid,commitTreeAncestry=ancestry,matchesLocalCheckout=True,
                            url='https://github.com/godotengine/godot/blob/'+COMMIT+'/'+path))
    result = dict(verifiedUtc=datetime.now(timezone.utc).isoformat(),engineCommit=COMMIT,engineTree=tree,
                  decoder=dict(path=str(DECODER),sha256=hashlib.sha256(decoder_bytes).hexdigest()),
                  files=records,scope='Exact local source object decode with SHA-1 validation and checkout equality, using the previously reviewed read-only decoder class. Its main function was not called; its frozen root was not changed. No Git command, engine execution, archive/media extraction, or network request.')
    target = ROOT/'engine-source-binding.json'
    target.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(files=len(records),sha256=hashlib.sha256(target.read_bytes()).hexdigest())))


if __name__ == '__main__':
    main()
