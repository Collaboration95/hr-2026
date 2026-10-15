// Focused independent controls created during the validator fix pass.
import {readFileSync,writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {validateDemo} from '../app/src/data.ts';
import {canopyLabel,lossLabel,maskLabel} from '../app/src/cell-values.ts';
const root=fileURLToPath(new URL('../',import.meta.url));
const read=p=>JSON.parse(readFileSync(root+p,'utf8'));
const checks=[];
for(const [file,accept] of [
 ['artifacts/demo-v1.json',true],
 ['validation/fix-verification/ui-unknown-valid.json',true],
 ['validation/fix-verification/ui-false-equality.json',false],
]) {
 let accepted=false,error=null;
 try{validateDemo(read(file));accepted=true;}catch(e){error=e.message;}
 checks.push({file,expectedAccepted:accept,accepted,error,pass:accepted===accept});
}
const cell=read('validation/fix-verification/ui-unknown-valid.json').plots.find(p=>p.plot_id==='P-0003').evidence.features[0];
const labels=[canopyLabel(cell),lossLabel(cell),maskLabel(cell)];
checks.push({kind:'actual nullable rendering helpers',labels,pass:labels.every(x=>x==='Unavailable')});
const report={checks,pass:checks.every(c=>c.pass),scope:'paired fresh and consistent-unknown positives versus original V7 negative; browser evidence recorded separately'};
writeFileSync(root+'docs/lab/validator-fix-loader.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
process.exitCode=report.pass?0:1;
