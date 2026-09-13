import assert from 'node:assert/strict'
import { parseRocDate } from '../src/rocDate.ts'

assert.equal(parseRocDate(''), '')
assert.equal(parseRocDate('  '), '')
assert.equal(parseRocDate('113/01/31'), '2024-01-31')
assert.equal(parseRocDate(' 113-2-29 '), '2024-02-29')
assert.equal(parseRocDate('1/1/1'), '1912-01-01')
for (const invalid of ['112/2/29', '113/4/31', '113/13/1', '113/0/1', '113/1/0', '0/1/1', '2024/1/1', '113/1', 'abc']) {
  assert.equal(parseRocDate(invalid), null, invalid)
}
console.log('ROC date conversion checks passed')
