// Check saved actual-HTTP bodies with C5-B's unmodified client validators.
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import {
  validateLiveHealth,
  validateLiveQueryResponse,
} from '../../../app/src/live-client.ts';

const read = (name) => readFileSync(new URL(name, import.meta.url), 'utf8');
const hash = (value) => createHash('sha256').update(value, 'utf8').digest('hex');
const health = await validateLiveHealth(JSON.parse(read('health-example.json')));
const cases = [];
for (const name of ['known-plot', 'temporary-tiny', 'outside']) {
  const body = read(`${name}-request.json`);
  const response = JSON.parse(read(`${name}-response.json`));
  await validateLiveQueryResponse(response, JSON.parse(body), hash(body), health);
  cases.push({ name, verified: true, selected: response.source_result.selected_cell_count });
}
const result = {
  method: 'Unmodified C5-B validators consumed saved actual-loopback HTTP responses; no added fields or serializer substitution.',
  snapshot_id: health.snapshot_id,
  cases,
};
writeFileSync(new URL('cross-language-verification.json', import.meta.url), JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify(result, null, 2));
