import { test, expect } from '@playwright/test';
import * as net from 'net';


function smtpSend(options: {host?: string, port: number, from: string, to: string, subject: string, body?: string, helo?: string}): Promise<{accepted: boolean, rcptRejected: boolean, transcript: string}> {
  const host = options.host || '127.0.0.1';
  const helo = options.helo || 'localhost';
  const body = options.body || 'Hello';
  const port = options.port;
  const from = options.from;
  const to = options.to;

  return new Promise((resolve) => {
    const sock = net.createConnection({ host, port });
    let buf = '';
    let transcript = '';

    function write(line: string) {
      transcript += `C: ${line}` + '\n';
      sock.write(line + '\r\n');
    }

    function takeLines() {
      const lines = buf.split(/\r?\n/);
      buf = lines.pop() || '';
      return lines.filter(l => l.length);
    }

    function lastCode(lines: string[]): number | null {
      for (let i = lines.length - 1; i >= 0; i--) {
        const m = /^(\d{3})[ -]/.exec(lines[i]);
        if (m) return parseInt(m[1], 10);
      }
      return null;
    }

    let stage: 'greet'|'ehlo'|'mail'|'rcpt'|'data'|'body'|'quit'|'done' = 'greet';
    let rcptRejected = false;

    sock.on('data', (d) => {
      buf += d.toString('utf-8');
      const lines = takeLines();
      for (const ln of lines) transcript += `S: ${ln}\n`;

      const code = lastCode(lines);
      if (code === null) return;

      if (stage === 'greet' && code === 220) {
        write(`EHLO ${helo}`);
        stage = 'ehlo';
        return;
      }
      if (stage === 'ehlo' && code === 250) {
        write(`MAIL FROM:<${from}>`);
        stage = 'mail';
        return;
      }
      if (stage === 'mail' && code === 250) {
        write(`RCPT TO:<${to}>`);
        stage = 'rcpt';
        return;
      }
      if (stage === 'rcpt') {
        if (code >= 500 && code < 600) {
          rcptRejected = true;
          write('QUIT');
          stage = 'quit';
          return;
        }
        if (code === 250) {
          write('DATA');
          stage = 'data';
          return;
        }
      }
      if (stage === 'data' && code === 354) {
        const content = [
          `From: ${from}`,
          `To: ${to}`,
          `Subject: ${options.subject}`,
          '',
          body,
          '.',
        ].join('\r\n');
        // Write raw without trailing CRLF added by write()
        transcript += `C: ${content}\n`;
        sock.write(content + '\r\n');
        stage = 'body';
        return;
      }
      if (stage === 'body' && code === 250) {
        write('QUIT');
        stage = 'quit';
        return;
      }
      if (stage === 'quit' && code === 221) {
        stage = 'done';
        sock.end();
        resolve({ accepted: !rcptRejected, rcptRejected, transcript });
        return;
      }
    });

    sock.on('error', (err) => {
      transcript += `ERR: ${String(err)}\n`;
      try { sock.destroy(); } catch {}
      resolve({ accepted: false, rcptRejected: true, transcript });
    });

    sock.setTimeout(20000, () => {
      transcript += 'ERR: timeout\n';
      try { sock.destroy(); } catch {}
      resolve({ accepted: false, rcptRejected: true, transcript });
    });
  });
}

async function mailhogHasSubject(request: any, subject: string, timeoutMs = 30_000): Promise<boolean> {
  const start = Date.now();
  for (;;) {
    const r = await request.get('http://127.0.0.1:8025/api/v2/messages?limit=50');
    if (r.ok()) {
      const j = await r.json();
      const items = (j && j.items) || j || [];
      for (const it of items) {
        const subj = it?.Content?.Headers?.Subject?.[0] || '';
        if (String(subj).includes(subject)) return true;
      }
    }
    if (Date.now() - start > timeoutMs) return false;
    await new Promise(r => setTimeout(r, 1000));
  }
}

async function mailhogMissingSubject(request: any, subject: string, waitMs = 10_000): Promise<boolean> {
  const start = Date.now();
  for (;;) {
    const r = await request.get('http://127.0.0.1:8025/api/v2/messages?limit=100');
    if (r.ok()) {
      const j = await r.json();
      const items = (j && j.items) || j || [];
      let found = false;
      for (const it of items) {
        const subj = it?.Content?.Headers?.Subject?.[0] || '';
        if (String(subj).includes(subject)) { found = true; break; }
      }
      if (!found) return true;
    }
    if (Date.now() - start > waitMs) return false;
    await new Promise(r => setTimeout(r, 500));
  }
}

async function clearSelections(page: any) {
  // Ensure no previous selections interfere; click outside table if needed
  await page.click('body');
}

async function ensureEntryVisible(page: any, email: string) {
  const body = page.getByRole('rowgroup').nth(1);
  await expect(body.getByRole('row', { name: new RegExp(email.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) })).toBeVisible({ timeout: 60000 });
}

async function getModeButtonInRow(page: any, email: string) {
  const body = page.getByRole('rowgroup').nth(1);
  const row = body.getByRole('row', { name: new RegExp(email.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) });
  return row.getByRole('button', { name: /Test|Enforce/ });
}


test.describe('UI Mode toggle affects delivery (MailHog)', () => {
  // One-time suite reset happens in global-setup.ts. Avoid per-test resets.

  test('Address in Test mode delivers to MailHog; Enforce mode is rejected', async ({ page, request }) => {
    const smtpPort = 1026;

    await page.goto('/');

    // Add a unique address
    const nonce = Date.now();
    const email = `blocked-ui-${nonce}@example.com`;

    await page.getByPlaceholder('paste emails or regex (one per line)').fill(email);
    await page.getByRole('button', { name: 'Add', exact: true }).click();

    await ensureEntryVisible(page, email);

    // Verify default mode is Test
    const modeBtn = await getModeButtonInRow(page, email);
    await expect(modeBtn).toHaveText(/Test|Enforce/, { timeout: 30000 });
    const initialLabel = await modeBtn.textContent();
    // If it somehow starts as Enforce, click once to set to Test
    if ((initialLabel || '').includes('Enforce')) {
      await modeBtn.click();
      await expect(modeBtn).toHaveText('Test', { timeout: 30000 });
    }

    // Send an email and expect delivery to MailHog
    const subjTest = `UI-E2E Test ${nonce}-test`;
    const res1 = await smtpSend({ port: smtpPort, from: 'sender@example.com', to: email, subject: subjTest, body: 'hello test' });
    expect(res1.rcptRejected, `RCPT was rejected unexpectedly. Transcript:\n${res1.transcript}`).toBeFalsy();
    const seen1 = await mailhogHasSubject(request, subjTest, 60_000);
    expect(seen1).toBeTruthy();

    // Capture a marker (last line) before toggling to detect new activity
    const baseTail = await (async () => {
      const tr = await request.get('/logs/tail?name=blocker&lines=500');
      if (!tr.ok()) return '';
      const j = await tr.json();
      const content = String(j.content || '');
      const lines = content.split(/\r?\n/).filter((l: string) => l.length);
      return lines.length ? lines[lines.length - 1] : '';
    })();

    // Toggle to Enforce mode in the UI to apply enforced maps
    await modeBtn.click();
    await expect(modeBtn).toHaveText('Enforce', { timeout: 30000 });

    const sawBlockerApply = await (async (marker: string) => {
      const startTs = Date.now();
      let linesToFetch = 500;
      while (Date.now() - startTs < 90_000) {
        const tr = await request.get(`/logs/tail?name=blocker&lines=${linesToFetch}`);
        if (tr.ok()) {
          const j = await tr.json();
          const content = String(j.content || '');
          const lines = content.split(/\r?\n/).filter((l: string) => l.length);
          let idx = -1;
          if (marker) {
            for (let i = lines.length - 1; i >= 0; i--) { if (lines[i] === marker) { idx = i; break; } }
          }
          const delta = idx >= 0 ? lines.slice(idx + 1) : lines;
          const deltaText = delta.join('\n').toLowerCase();
          // Prefer a deterministic single-line marker emitted by the blocker service
          if (deltaText.includes('blocker_apply')) {
            return true;
          }
          // Backward compatible: infer from existing log phrases
          if (deltaText.includes('wrote maps:') && (deltaText.includes('reloading postfix') || deltaText.includes('running postmap'))) {
            return true;
          }
          // Fallback: if marker couldn't be found reliably, scan entire tail
          const allText = content.toLowerCase();
          if (allText.includes('blocker_apply')) {
            return true;
          }
          if (allText.includes('wrote maps:') && (allText.includes('reloading postfix') || allText.includes('running postmap'))) {
            return true;
          }
        }
        linesToFetch = Math.min(8000, linesToFetch + 1000);
        await new Promise(r => setTimeout(r, 1000));
      }
      return false;
    })(baseTail);
    if (!sawBlockerApply) {
      // Logging can lag; rely on actual delivery check to validate enforcement.
      // To see this note in CI, set PW_E2E_VERBOSE=1
      if (process.env.PW_E2E_VERBOSE === '1') {
        console.log('[info] No explicit blocker-apply marker observed; continuing with delivery check');
      }
      await new Promise(r => setTimeout(r, 2000));
    }

    // Now attempt send and expect RCPT 5xx; retry briefly in case of log-delay
    const subjEnf = `UI-E2E Test ${nonce}-enforce`;
    let rcptRejected = false;
    let lastTranscript = '';
    const start = Date.now();
    while (Date.now() - start < 45_000) {
      const res = await smtpSend({ port: smtpPort, from: 'sender@example.com', to: email, subject: subjEnf, body: 'hello enforce' });
      lastTranscript = res.transcript;
      if (res.rcptRejected) { rcptRejected = true; break; }
      await new Promise(r => setTimeout(r, 1500));
    }
    expect(rcptRejected, `Expected RCPT rejection in Enforce mode. Last transcript:\n${lastTranscript}`).toBeTruthy();

    // Confirm the enforce-subject does NOT arrive in MailHog
    const missing = await mailhogMissingSubject(request, subjEnf, 15_000);
    expect(missing).toBeTruthy();

    // Toggle back to Test to ensure UI remains responsive
    await modeBtn.click();
    await expect(modeBtn).toHaveText('Test', { timeout: 30000 });

    // Cleanup: delete the created entry to leave DB in a clean baseline
    const body = page.getByRole('rowgroup').nth(1);
    const row = body.getByRole('row', { name: new RegExp(email.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) });
    await row.click();
    await page.getByRole('button', { name: 'Delete Selected' }).click();
  });
});
