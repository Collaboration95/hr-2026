"""Copy canonical engine output or build a declaration-only fallback. Never mutate inputs."""
import csv, hashlib, json, pathlib, shutil
root = pathlib.Path(__file__).resolve().parents[2]
out = root / 'app/public/data'
out.mkdir(parents=True, exist_ok=True)
canonical = root / 'artifacts/demo-v1.json'
if canonical.exists():
    data = json.loads(canonical.read_text())
    assert data['schema_version'] == 'plotline.demo.v1', 'Unsupported artifact schema'
    assert len(data['plots']) == 17, 'Expected 17 real sample plots'
    shutil.copyfile(canonical, out / 'demo-v1.json')
    print('Copied canonical engine artifact (17 plots).')
else:
    source = root / 'data/company-sample/2026-10-12'
    csvpath = next(source.glob('*.csv'))
    geopath = next(source.glob('*.geojson'))
    rows = list(csv.DictReader(csvpath.open(encoding='utf-8-sig')))
    geometries = {f['properties']['ProductionPlace']: f['geometry'] for f in json.loads(geopath.read_text())['features']}
    assert len(rows) == len(geometries) == 17
    data = {'schema_version':'plotline.demo.v1','query_version':'hansen-centers.v1','dataset':{'status':'declarations_only','sources':[{'path':str(p.relative_to(root)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (csvpath,geopath)]},'periods':['2021-2023','2024-2025'],'plots':[{'plot_id':r['a3_plot_id'],'geometry':geometries[r['a3_plot_id']],'supplier':r,'source_result':None,'compact_result':None,'comparison':None,'receipt':None,'evidence':None} for r in rows],'summary':None,'benchmark':None,'limitations':['Mapped observations and encoding proof have not yet been computed. Supplier declarations are not independent findings.']}
    (out / 'demo-v1.json').write_text(json.dumps(data,ensure_ascii=False))
    print('Built 17-plot declaration fallback; computed fields are null.')

synthetic = root / 'artifacts/synthetic-v1.json'
if synthetic.exists():
    fixture = json.loads(synthetic.read_text())
    assert fixture.get('schema_version') == 'plotline.synthetic.v1' and fixture.get('synthetic') is True
    shutil.copyfile(synthetic, out / 'synthetic-v1.json')
    print('Copied separate synthetic query-support lab.')

# Explicit engine source-view acceptance, recorded in engine-jrc-interface.md.
# A changed experiment must be reviewed before this optional asset is shipped.
jrc = root / 'artifacts/jrc-baseline-v1.json'
jrc_output = out / 'jrc-baseline-v1.json'
accepted_jrc_file_sha256 = '933b3d302b8ec961444a7f252f74deb87f3f186f1b7f8d5bcb5012cb55658f71'
if jrc.exists() and hashlib.sha256(jrc.read_bytes()).hexdigest() == accepted_jrc_file_sha256:
    shutil.copyfile(jrc, jrc_output)
    print('Copied accepted separate JRC 2020 v4 companion.')
else:
    jrc_output.unlink(missing_ok=True)
    print('JRC companion unavailable: canonical file absent or changed from reviewed acceptance. Hansen remains usable.')
