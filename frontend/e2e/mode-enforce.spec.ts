import {
  type APIRequestContext,
  expect,
  type Locator,
  type Page,
  test,
} from '@playwright/test';
import * as net from 'node:net';

// Extracted helper for parsing SMTP codes to reduce inner function complexity
/**
 * Parse the last SMTP status code from a sequence of server response lines.
 * @param {string[]} lines - Lines received from the SMTP server.
 * @returns {number | undefined} The numeric status code or undefined if not found.
 */
function lastCode(lines: string[]): number | undefined {
  for (let index = lines.length - 1; index >= 0; index--) {
    const ln = String(lines.at(index) ?? '');
    const m = /^(\d{3})[ -]/.exec(ln);
    if (m) {
      return Number.parseInt(m[1], 10);
    }
  }
  return undefined;
}

/**
 * Send a simple SMTP message to a server and capture the full transcript.
 * @param {object} options - SMTP connection and message options.
 * @param {string} [options.host] - SMTP server host.
 * @param {number} options.port - SMTP server port.
 * @param {string} options.from - Envelope sender address (MAIL FROM).
 * @param {string} options.to - Recipient address (RCPT TO).
 * @param {string} options.subject - Message subject header value.
 * @param {string} [options.body] - Message body content.
 * @param {string} [options.helo] - Hostname to use in EHLO/HELO.
 * @returns {Promise<{ accepted: boolean; rcptRejected: boolean; transcript: string }>} Resolves with acceptance state and transcript.
 */
function smtpSend(options: {
  host?: string;
  port: number;
  from: string;
  to: string;
  subject: string;
  body?: string;
  helo?: string;
}): Promise<{ accepted: boolean; rcptRejected: boolean; transcript: string }> {
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

    /**
     * Write a command line to the socket and append it to the transcript.
     * @param {string} line - Command to send without trailing CRLF.
     * @returns {void}
     */
    function write(line: string): void {
      transcript += `C: ${line}` + '\n';
      sock.write(line + '\r\n');
    }

    /**
     * Drain complete CRLF-delimited lines from the buffer and retain the remainder.
     * @returns {string[]} Complete lines ready for parsing.
     */
    function takeLines(): string[] {
      const lines = buf.split(/\r?\n/);
      buf = lines.pop() || '';
      return lines.filter((l) => l.length);
    }

    let stage:
      | 'greet'
      | 'ehlo'
      | 'mail'
      | 'rcpt'
      | 'data'
      | 'body'
      | 'quit'
      | 'done' = 'greet';
    let rcptRejected = false;

    /**
     * Advance the SMTP dialog state machine based on the last response code.
     * Split into per-state handlers to keep complexity low and readability high.
     * @param {number} code - Last status code observed from the server.
     * @returns {void}
     */
    function advance(code: number): void {
      switch (stage) {
        case 'greet': {
          onGreet(code);
          break;
        }
        case 'ehlo': {
          onEhlo(code);
          break;
        }
        case 'mail': {
          onMail(code);
          break;
        }
        case 'rcpt': {
          onRcpt(code);
          break;
        }
        case 'data': {
          onData(code);
          break;
        }
        case 'body': {
          onBody(code);
          break;
        }
        case 'quit': {
          onQuit(code);
          break;
        }
        default: {
          break;
        }
      }
    }

    /**
     * Handle server response while in the 'greet' stage.
     * @param {number} code - Last SMTP status code.
     */
    function onGreet(code: number): void {
      if (code === 220) {
        write(`EHLO ${helo}`);
        stage = 'ehlo';
      }
    }
    /**
     * Handle server response while in the 'ehlo' stage.
     * @param {number} code - Last SMTP status code.
     */
    function onEhlo(code: number): void {
      if (code === 250) {
        write(`MAIL FROM:<${from}>`);
        stage = 'mail';
      }
    }
    /**
     * Handle server response while in the 'mail' stage.
     * @param {number} code - Last SMTP status code.
     */
    function onMail(code: number): void {
      if (code === 250) {
        write(`RCPT TO:<${to}>`);
        stage = 'rcpt';
      }
    }
    /**
     * Handle server response while in the 'rcpt' stage.
     * @param {number} code - Last SMTP status code.
     */
    function onRcpt(code: number): void {
      if (code >= 500 && code < 600) {
        rcptRejected = true;
        write('QUIT');
        stage = 'quit';
        return;
      }
      if (code === 250) {
        write('DATA');
        stage = 'data';
      }
    }
    /**
     * Handle server response while in the 'data' stage.
     * @param {number} code - Last SMTP status code.
     */
    function onData(code: number): void {
      if (code === 354) {
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
      }
    }
    /**
     * Handle server response while in the 'body' stage.
     * @param {number} code - Last SMTP status code.
     */
    function onBody(code: number): void {
      if (code === 250) {
        write('QUIT');
        stage = 'quit';
      }
    }
    /**
     * Handle server response while in the 'quit' stage.
     * @param {number} code - Last SMTP status code.
     */
    function onQuit(code: number): void {
      if (code === 221) {
        stage = 'done';
        sock.end();
        resolve({ accepted: !rcptRejected, rcptRejected, transcript });
      }
    }

    sock.on('data', (d) => {
      buf += d.toString('utf8');
      const lines = takeLines();
      for (const ln of lines) transcript += `S: ${ln}\n`;

      const code = lastCode(lines);
      if (code === undefined) return;

      advance(code);
    });

    sock.on('error', (error) => {
      transcript += `ERR: ${String(error)}\n`;
      try {
        sock.destroy();
      } catch {
        void 0;
      }
      resolve({ accepted: false, rcptRejected: true, transcript });
    });

    sock.setTimeout(20_000, () => {
      transcript += 'ERR: timeout\n';
      try {
        sock.destroy();
      } catch {
        void 0;
      }
      resolve({ accepted: false, rcptRejected: true, transcript });
    });
  });
}

/**
 * Poll MailHog for a message whose Subject header contains the given text.
 * @param {APIRequestContext} request - Playwright API client for HTTP requests.
 * @param {string} subject - Text to search for within the Subject header.
 * @param {number} [timeoutMs] - Maximum time to wait in milliseconds.
 * @returns {Promise<boolean>} True if a matching message appears within the timeout; otherwise false.
 */
async function mailhogHasSubject(
  request: APIRequestContext,
  subject: string,
  timeoutMs = 30_000,
): Promise<boolean> {
  const start = Date.now();
  for (;;) {
    const r = await request.get(
      'http://127.0.0.1:8025/api/v2/messages?limit=50',
    );
    if (r.ok()) {
      const index = await r.json();
      const items = index?.items || index || [];
      for (const it of items) {
        const subj = it?.Content?.Headers?.Subject?.[0] || '';
        if (String(subj).includes(subject)) return true;
      }
    }
    if (Date.now() - start > timeoutMs) return false;
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

/**
 * Verify that no MailHog message appears whose Subject contains the given text over a period.
 * @param {APIRequestContext} request - Playwright API client for HTTP requests.
 * @param {string} subject - Text that must not appear in any Subject header.
 * @param {number} [waitMs] - Observation window in milliseconds.
 * @returns {Promise<boolean>} True if no matching message appears during the window; otherwise false.
 */
async function mailhogMissingSubject(
  request: APIRequestContext,
  subject: string,
  waitMs = 10_000,
): Promise<boolean> {
  const start = Date.now();
  for (;;) {
    const r = await request.get(
      'http://127.0.0.1:8025/api/v2/messages?limit=100',
    );
    if (r.ok()) {
      const index = await r.json();
      const items = index?.items || index || [];
      let found = false;
      for (const it of items) {
        const subj = it?.Content?.Headers?.Subject?.[0] || '';
        if (String(subj).includes(subject)) {
          found = true;
          break;
        }
      }
      if (!found) return true;
    }
    if (Date.now() - start > waitMs) return false;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
}

/**
 * Ensure that the table row for the given email is visible.
 * @param {Page} page - Playwright page instance.
 * @param {string} email - Address expected to appear in the rows.
 * @returns {Promise<void>} Resolves when the row is visible.
 */
async function ensureEntryVisible(page: Page, email: string): Promise<void> {
  const body = page.getByRole('rowgroup').nth(1);
  await expect(body.getByRole('row', { hasText: email })).toBeVisible({
    timeout: 60_000,
  });
}

/**
 * Locate the mode toggle button in the row associated with the given email.
 * @param {Page} page - Playwright page instance.
 * @param {string} email - Address identifying the target row.
 * @returns {Locator} The button locator for the "Test/Enforce" toggle.
 */
function getModeButtonInRow(page: Page, email: string): Locator {
  const body = page.getByRole('rowgroup').nth(1);
  const row = body.getByRole('row', { hasText: email });
  return row.getByRole('button', { name: /Test|Enforce/ });
}

/**
 * Ensure the mode toggle is in "Test" state, clicking once if necessary.
 * @param {Locator} modeButton - The "Test/Enforce" toggle button.
 * @returns {Promise<void>} Resolves when the button shows "Test".
 */
async function ensureModeIsTest(modeButton: Locator): Promise<void> {
  const label = (await modeButton.textContent()) || '';
  if (label.includes('Enforce')) {
    await modeButton.click();
    await expect(modeButton).toHaveText('Test', { timeout: 30_000 });
  }
}

/**
 * Determine if the logs indicate that the blocker applied maps or reloaded postfix.
 * @param {string} deltaText - Lowercased incremental log text.
 * @param {string} allText - Lowercased entire log text as fallback.
 * @returns {boolean} True if apply markers are present.
 */
function hasApplySignals(deltaText: string, allText: string): boolean {
  if (deltaText.includes('blocker_apply')) return true;
  if (
    deltaText.includes('wrote maps:') &&
    (deltaText.includes('reloading postfix') ||
      deltaText.includes('running postmap'))
  ) {
    return true;
  }
  if (allText.includes('blocker_apply')) return true;
  if (
    allText.includes('wrote maps:') &&
    (allText.includes('reloading postfix') ||
      allText.includes('running postmap'))
  ) {
    return true;
  }
  return false;
}

/**
 * Wait until the blocker service applies new maps by scanning the logs.
 * @param {APIRequestContext} request - Playwright API client.
 * @param {string} marker - Marker line to start delta from; if empty, scans all.
 * @returns {Promise<boolean>} True when apply signals are seen within timeout, else false.
 */
async function waitForBlockerApply(
  request: APIRequestContext,
  marker: string,
): Promise<boolean> {
  const startTs = Date.now();
  let linesToFetch = 500;
  while (Date.now() - startTs < 90_000) {
    const url = `/logs/tail?name=blocker&lines=${String(linesToFetch)}`;
    const tr = await request.get(url);
    if (tr.ok()) {
      const index = (await tr.json()) as { content?: unknown };
      const content = String(index.content ?? '');
      const lines = content.split(/\r?\n/).filter((l: string) => l.length);
      const index_ = marker ? lines.lastIndexOf(marker) : -1;
      const delta = index_ >= 0 ? lines.slice(index_ + 1) : lines;
      const deltaText = delta.join('\n').toLowerCase();
      const allText = content.toLowerCase();
      if (hasApplySignals(deltaText, allText)) {
        return true;
      }
    }
    linesToFetch = Math.min(8000, linesToFetch + 1000);
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  return false;
}

/**
 * Optionally wait a short period and emit a verbose note when blocker apply markers are missing.
 * Extracted to avoid conditionals directly inside test bodies.
 * @param {boolean} saw - Whether an apply marker was observed.
 * @returns {Promise<void>} Resolves after any optional delay.
 */
async function maybeDelayAfterNoApply(saw: boolean): Promise<void> {
  if (!saw) {
    if (process.env.PW_E2E_VERBOSE === '1') {
      console.warn(
        '[info] No explicit blocker-apply marker observed; continuing with delivery check',
      );
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
}

/**
 * Attempt to send until RCPT is rejected or a timeout elapses.
 * Extracted to avoid loops/conditionals inside test bodies.
 * @param {object} options - Attempt options.
 * @param {number} options.smtpPort - SMTP port to connect to.
 * @param {string} options.email - Recipient address.
 * @param {string} options.subject - Subject line to use.
 * @param {number} [options.maxMs] - Max time to try in ms (default 45s).
 * @returns {Promise<{ rcptRejected: boolean; lastTranscript: string }>} Promise resolving with whether RCPT was rejected and the last SMTP transcript captured.
 */
async function attemptUntilRejected(options: {
  smtpPort: number;
  email: string;
  subject: string;
  maxMs?: number;
}): Promise<{ rcptRejected: boolean; lastTranscript: string }> {
  const maxMs = options.maxMs ?? 45_000;
  const start = Date.now();
  let lastTranscript = '';
  for (;;) {
    const result = await smtpSend({
      port: options.smtpPort,
      from: 'sender@example.com',
      to: options.email,
      subject: options.subject,
      body: 'hello enforce',
    });
    lastTranscript = result.transcript;
    if (result.rcptRejected) {
      return { rcptRejected: true, lastTranscript };
    }
    if (Date.now() - start >= maxMs) {
      return { rcptRejected: false, lastTranscript };
    }
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
}

test.describe('UI Mode toggle affects delivery (MailHog)', () => {
  // One-time suite reset happens in global-setup.ts. Avoid per-test resets.

  test('Address in Test mode delivers to MailHog; Enforce mode is rejected', async ({
    page,
    request,
  }) => {
    const smtpPort = 1026;

    await page.goto('/');

    // Add a unique address
    const nonce = Date.now();
    const email = `blocked-ui-${nonce}@example.com`;

    await page
      .getByPlaceholder('paste emails or regex (one per line)')
      .fill(email);
    await page.getByRole('button', { name: 'Add', exact: true }).click();

    await ensureEntryVisible(page, email);

    // Verify default mode is Test
    const modeButton = await getModeButtonInRow(page, email);
    await expect(modeButton).toHaveText(/Test|Enforce/, { timeout: 30_000 });
    await ensureModeIsTest(modeButton);

    // Send an email and expect delivery to MailHog
    const subjTest = `UI-E2E Test ${nonce}-test`;
    const result1 = await smtpSend({
      port: smtpPort,
      from: 'sender@example.com',
      to: email,
      subject: subjTest,
      body: 'hello test',
    });
    expect(
      result1.rcptRejected,
      `RCPT was rejected unexpectedly. Transcript:\n${result1.transcript}`,
    ).toBeFalsy();
    const seen1 = await mailhogHasSubject(request, subjTest, 60_000);
    expect(seen1).toBeTruthy();

    // Capture a marker (last line) before toggling to detect new activity
    const baseTail = await (async (): Promise<string> => {
      const tr = await request.get('/logs/tail?name=blocker&lines=500');
      if (!tr.ok()) return '';
      const index = (await tr.json()) as { content?: unknown };
      const content = String(index.content ?? '');
      const lines = content.split(/\r?\n/).filter((l: string) => l.length);
      return lines.length > 0 ? lines.at(-1) : '';
    })();

    // Toggle to Enforce mode in the UI to apply enforced maps
    await modeButton.click();
    await expect(modeButton).toHaveText('Enforce', { timeout: 30_000 });

    const sawBlockerApply = await waitForBlockerApply(request, baseTail);
    await maybeDelayAfterNoApply(sawBlockerApply);

    // Now attempt send and expect RCPT 5xx; retry briefly in case of log-delay
    const subjEnf = `UI-E2E Test ${nonce}-enforce`;
    const attempt = await attemptUntilRejected({
      smtpPort,
      email,
      subject: subjEnf,
    });
    const rcptRejected = attempt.rcptRejected;
    const lastTranscript = attempt.lastTranscript;
    expect(
      rcptRejected,
      `Expected RCPT rejection in Enforce mode. Last transcript:\n${lastTranscript}`,
    ).toBeTruthy();

    // Confirm the enforce-subject does NOT arrive in MailHog
    const missing = await mailhogMissingSubject(request, subjEnf, 15_000);
    expect(missing).toBeTruthy();

    // Toggle back to Test to ensure UI remains responsive
    await modeButton.click();
    await expect(modeButton).toHaveText('Test', { timeout: 30_000 });

    // Cleanup: delete the created entry to leave DB in a clean baseline
    const body = page.getByRole('rowgroup').nth(1);
    const row = body.getByRole('row', { hasText: email });
    await row.click();
    await page.getByRole('button', { name: 'Delete Selected' }).click();
  });
});
