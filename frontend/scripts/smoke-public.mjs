import { chromium } from 'playwright';

const baseUrl = process.env.PUBLIC_BASE_URL || 'https://agriai-demo.pages.dev';
const routes = ['/', '/features', '/login', '/register'];
const viewports = [
  { name: 'mobile', width: 390, height: 844 },
  { name: 'desktop', width: 1440, height: 900 },
];

const browser = await chromium.launch({ headless: true });
const failures = [];

for (const viewport of viewports) {
  const page = await browser.newPage({ viewport });
  const errors = [];
  const failedResponses = [];
  const remoteFonts = [];

  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('response', (response) => {
    if (response.status() >= 500) failedResponses.push(`${response.status()} ${response.url()}`);
  });
  page.on('request', (request) => {
    if (/fonts\.(googleapis|gstatic)\.com/.test(request.url())) remoteFonts.push(request.url());
  });

  for (const route of routes) {
    const response = await page.goto(`${baseUrl}${route}`, {
      waitUntil: 'networkidle',
      timeout: 30_000,
    });
    const overflows = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    );
    const heading = await page.locator('h1').first().textContent().catch(() => '');

    console.log(
      `${viewport.name} ${response?.status()} overflow=${overflows} ${route} ${heading?.trim() || '(no h1)'}`,
    );
    if (!response || response.status() !== 200 || overflows) {
      failures.push(`${viewport.name} ${route}`);
    }
  }

  if (errors.length || failedResponses.length || remoteFonts.length) {
    failures.push(
      `${viewport.name} browser errors=${JSON.stringify(errors)} `
      + `responses=${JSON.stringify(failedResponses)} fonts=${JSON.stringify(remoteFonts)}`,
    );
  }
  await page.close();
}

await browser.close();

if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}
