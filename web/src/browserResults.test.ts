import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { expect, test } from 'vitest';

test('separate Playwright invocations do not reuse or clear the project results directory', () => {
  const env = { ...process.env };
  delete env.PDTL_BROWSER_RESULTS;
  delete env.PDTL_BROWSER_INPUTS;
  const cli = resolve('node_modules/@playwright/test/cli.js');
  const outputs = Array.from({length: 2}, () => {
    const result = execFileSync(process.execPath, [cli, 'test', '--list', '--reporter=json'], {
      cwd: process.cwd(), env, encoding: 'utf8', timeout: 30_000,
    });
    return JSON.parse(result).config.projects[0].outputDir as string;
  });
  expect(outputs[0]).not.toBe(outputs[1]);
  expect(outputs).not.toContain(resolve('test-results'));
}, 75_000);
